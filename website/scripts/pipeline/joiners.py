"""
Spatial and attribute joins that build the hierarchy relationships.
"""

import os
import numpy as np
import pandas as pd
import geopandas as gpd

from .config import BUILDING_CLASS_HEIGHTS, OUTPUT_DIR, MAPS_DIR


def join_land_use(target_gdf, landuse, label="layer"):
    """Join land use descriptions to a GeoDataFrame via centroid spatial join.
    
    Args:
        target_gdf: GeoDataFrame to enrich with land use.
        landuse: Land use GeoDataFrame with LANDUSEDESC column.
        label: Label for log messages.
    
    Returns:
        target_gdf with a new 'landUse' column.
    """
    print(f"Matching {label} to majority Land Use...")
    centroids = target_gdf.copy()
    centroids["geometry"] = centroids.geometry.centroid
    sj = gpd.sjoin(centroids, landuse[["LANDUSEDESC", "geometry"]], how="left", predicate="within")
    sj = sj[~sj.index.duplicated(keep="first")]
    target_gdf["landUse"] = sj["LANDUSEDESC"]
    return target_gdf


def join_plats_to_subdivisions(plats, subdivisions):
    """Join plats to subdivisions via SubID attribute + spatial centroid fallback.
    
    Returns:
        plats GeoDataFrame with _sub_id column populated.
    """
    print("\nJoining Plat -> Subdivision...")
    plats["_sub_id"] = None
    subdiv_id_set = set(subdivisions["ID"].dropna().unique())

    for idx, row in plats.iterrows():
        sub_id = row.get("SubID")
        if pd.notna(sub_id) and int(sub_id) in subdiv_id_set:
            plats.at[idx, "_sub_id"] = int(sub_id)

    matched = plats["_sub_id"].notna().sum()
    print(f"  Attribute-matched: {matched}/{len(plats)}")

    unmatched_mask = plats["_sub_id"].isna()
    if unmatched_mask.any():
        unmatched_plats = plats[unmatched_mask].copy()
        unmatched_plats["_centroid"] = unmatched_plats.geometry.centroid
        unmatched_points = unmatched_plats.set_geometry("_centroid")

        spatial_join = gpd.sjoin(
            unmatched_points[["_centroid", "geometry"]],
            subdivisions[["ID", "geometry"]],
            how="left",
            predicate="within"
        )
        for plat_idx, sj_row in spatial_join.iterrows():
            if pd.notna(sj_row.get("ID")):
                plats.at[plat_idx, "_sub_id"] = int(sj_row["ID"])

        newly_matched = plats["_sub_id"].notna().sum() - matched
        print(f"  Spatial-matched: {newly_matched} additional")

    return plats


def join_parcels_to_plats(parcels, plats):
    """Join parcels to plats via spatial centroid-in-polygon.
    
    Returns:
        parcels GeoDataFrame with _plat_oid column populated.
    """
    print("\nJoining Parcel -> Plat (spatial centroid-in-polygon)...")
    parcels["_parcel_idx"] = parcels.index
    parcel_centroids = parcels.copy()
    parcel_centroids["_centroid"] = parcel_centroids.geometry.centroid
    parcel_centroids = parcel_centroids.set_geometry("_centroid")

    plats["_plat_oid"] = plats["OBJECTID"]
    spatial_p2pl = gpd.sjoin(
        parcel_centroids[["_centroid", "_parcel_idx"]],
        plats[["_plat_oid", "geometry"]],
        how="left",
        predicate="within"
    )
    spatial_p2pl = spatial_p2pl[~spatial_p2pl.index.duplicated(keep="first")]

    parcels["_plat_oid"] = None
    for idx, row in spatial_p2pl.iterrows():
        if pd.notna(row.get("_plat_oid")):
            parcels.at[idx, "_plat_oid"] = int(row["_plat_oid"])

    return parcels


def join_addresses_to_parcels(addresses, parcels):
    """Join addresses to parcels via ParcelID attribute match.
    
    Returns:
        addresses GeoDataFrame with _parcel_idx column populated.
    """
    print("\nJoining Address -> Parcel (ParcelID)...")
    parcel_lookup = {}
    for idx, row in parcels.iterrows():
        pid = row.get("PARCELID")
        if pid:
            parcel_lookup[str(pid)] = idx

    addresses["_parcel_idx"] = None
    for idx, row in addresses.iterrows():
        pid = row.get("ParcelID")
        if pid and str(pid) in parcel_lookup:
            addresses.at[idx, "_parcel_idx"] = parcel_lookup[str(pid)]

    addr_matched = addresses["_parcel_idx"].notna().sum()
    print(f"  Matched: {addr_matched}/{len(addresses)}")
    return addresses


def join_buildings_to_parcels(buildings, parcels, addresses=None):
    """Join buildings to parcels via address points and spatial centroid-in-polygon.
    
    If the building contains address points, it is joined to all parcels
    associated with those address points.
    If the building has no address points inside it, it falls back to centroid-in-polygon.
    
    Returns:
        buildings GeoDataFrame with _parcel_indices and _height columns.
    """
    print("\nJoining Building -> Parcel...")

    # Estimate heights from BUILDINGCL
    buildings["_height"] = buildings["BUILDINGCL"].map(BUILDING_CLASS_HEIGHTS).fillna(8.0)
    if "SHAPE_Area" in buildings.columns:
        areas = buildings["SHAPE_Area"].fillna(0)
        area_factor = 1.0 + 0.1 * np.clip((areas - areas.median()) / (areas.std() + 1), -1, 1)
        buildings["_height"] = buildings["_height"] * area_factor
        buildings["_height"] = buildings["_height"].round(1)

    buildings["_bldg_idx"] = buildings.index

    # Initialize empty lists for _parcel_indices
    buildings["_parcel_indices"] = [[] for _ in range(len(buildings))]

    # 1. Match via addresses
    address_matches = 0
    if addresses is not None and len(addresses) > 0:
        # Project to epsg=3566 for spatial query
        bldg_proj = buildings.to_crs(epsg=3566)
        addr_proj = addresses.to_crs(epsg=3566)
        
        # We want to match address points inside building footprints
        addr_points = addr_proj[["geometry", "_parcel_idx"]].copy()
        addr_points["_addr_idx"] = addr_points.index
        
        spatial_a2b = gpd.sjoin(
            addr_points,
            bldg_proj[["geometry", "_bldg_idx"]],
            how="inner",
            predicate="within"
        )
        
        # Group by building index to find all parcel indices
        for b_idx, group in spatial_a2b.groupby("index_right"):
            p_indices = group["_parcel_idx"].dropna().unique().astype(int).tolist()
            if p_indices:
                buildings.at[b_idx, "_parcel_indices"] = p_indices
                address_matches += 1

    # 2. Fallback to centroid-in-polygon for buildings with no address points
    bldg_centroids = buildings.copy()
    bldg_centroids["_centroid"] = bldg_centroids.geometry.centroid
    bldg_centroids = bldg_centroids.set_geometry("_centroid")

    spatial_b2p = gpd.sjoin(
        bldg_centroids[["_centroid", "_bldg_idx"]],
        parcels[["geometry"]],
        how="left",
        predicate="within"
    )
    spatial_b2p = spatial_b2p[~spatial_b2p.index.duplicated(keep="first")]

    centroid_matches = 0
    for idx, row in spatial_b2p.iterrows():
        existing_indices = buildings.at[idx, "_parcel_indices"]
        if existing_indices:
            continue
            
        if pd.notna(row.get("index_right")):
            p_idx = int(row["index_right"])
            buildings.at[idx, "_parcel_indices"] = [p_idx]
            centroid_matches += 1

    print(f"  Matched via addresses: {address_matches}")
    print(f"  Matched via centroid (fallback): {centroid_matches}")
    print(f"  Total matched: {address_matches + centroid_matches}/{len(buildings)}")

    # Propagate parcel address to building for tooltip display (use first parcel address as fallback)
    buildings["_parcel_address"] = None
    for idx, row in buildings.iterrows():
        p_indices = row.get("_parcel_indices")
        if p_indices:
            p_idx = p_indices[0]
            if p_idx in parcels.index:
                addr = parcels.at[p_idx, "SITE_FULL_"] if "SITE_FULL_" in parcels.columns else None
                if pd.notna(addr) and str(addr).strip():
                    buildings.at[idx, "_parcel_address"] = str(addr).strip()

    addr_count = buildings["_parcel_address"].notna().sum()
    print(f"  Buildings with parcel address: {addr_count}/{len(buildings)}")
    return buildings


def join_pois_to_buildings(buildings):
    """Match close POIs to buildings (<12 meters) and assign names.
    
    Reads POIs from the output directory if available.
    """
    print("\nMatching POIs to buildings (<12 meters)...")
    pois_path = os.path.join(OUTPUT_DIR, "pois.json")
    if os.path.exists(pois_path):
        pois = gpd.read_file(pois_path)
        if len(pois) > 0:
            pois_proj = pois.to_crs(epsg=3566)
            buildings_proj = buildings.to_crs(epsg=3566)
            for idx, row in pois_proj.iterrows():
                poi_geom = row.geometry
                distances = buildings_proj.distance(poi_geom)
                min_dist = distances.min()
                if min_dist < 12.0:
                    nearest_idx = distances.idxmin()
                    poi_name = row.get("name")
                    print(f"  POI '{poi_name}' is {min_dist:.1f}m from building. Assigning name.")
                    buildings.at[nearest_idx, "NAME"] = poi_name
    return buildings


# ── Subtype display labels ───────────────────────────────────────────────

_SUBTYPE_LABELS = {
    'single_family': 'Single Family Home',
    'townhome': 'Townhome',
    'duplex': 'Duplex',
    'apartment': 'Apartment Complex',
    'condo': 'Condo',
    'mixed th/single_family': 'Multi-Family',
}


def _build_hui_label(group):
    """Build a human-readable label from a group of HUI records overlapping one building."""
    total_units = int(group['UNIT_COUNT'].sum())
    n_records = len(group)
    dominant_subtype = group['SUBTYPE'].mode().iloc[0] if len(group) > 0 else 'single_family'
    base_label = _SUBTYPE_LABELS.get(dominant_subtype, 'Residential')

    if n_records == 1 and total_units == 1:
        return base_label
    if n_records == 1 and total_units > 1:
        return f"{total_units}-unit {base_label}"
    # Multiple HUI records overlapping one building
    return f"{total_units}-unit {base_label}"


def join_housing_to_buildings(buildings):
    """Spatially join Housing Unit Inventory to buildings and generate labels.

    For each building footprint, finds overlapping HUI records (via centroid-in-polygon)
    and generates a human-readable housing description like '4-unit Townhome'.

    Writes result into buildings['_hui_label'].
    """
    hui_path = os.path.join(MAPS_DIR, 'buildings_and_parcels', 'housing_unit_inventory.zip')
    if not os.path.exists(hui_path):
        print("  Housing Unit Inventory not found, skipping.")
        buildings['_hui_label'] = None
        return buildings

    print("\nJoining Housing Unit Inventory -> Buildings (spatial centroid-in-polygon)...")
    hui = gpd.read_file(hui_path)
    print(f"  HUI records loaded: {len(hui)}")

    # Reproject to a common projected CRS for accurate spatial ops
    bldg_proj = buildings.to_crs(epsg=3566)
    hui_proj = hui.to_crs(epsg=3566)

    # Use HUI centroids for the join
    hui_proj['_centroid'] = hui_proj.geometry.centroid
    hui_points = hui_proj.set_geometry('_centroid')

    sj = gpd.sjoin(
        hui_points[['_centroid', 'TYPE', 'SUBTYPE', 'UNIT_COUNT']],
        bldg_proj[['geometry']],
        how='inner',
        predicate='within'
    )

    # Group by building index and build labels
    buildings['_hui_label'] = None
    grouped = sj.groupby('index_right')
    label_count = 0
    for bldg_idx, group in grouped:
        label = _build_hui_label(group)
        buildings.at[bldg_idx, '_hui_label'] = label
        label_count += 1

    print(f"  Buildings with HUI labels: {label_count}/{len(buildings)}")
    return buildings
