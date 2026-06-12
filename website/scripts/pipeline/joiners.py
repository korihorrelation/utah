"""
Spatial and attribute joins that build the hierarchy relationships.
"""

import os
import numpy as np
import pandas as pd
import geopandas as gpd

from .config import BUILDING_CLASS_HEIGHTS, OUTPUT_DIR


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


def join_buildings_to_parcels(buildings, parcels):
    """Join buildings to parcels via spatial centroid-in-polygon.
    
    Also estimates building heights from BUILDINGCL and footprint area.
    
    Returns:
        buildings GeoDataFrame with _parcel_idx and _height columns.
    """
    print("\nJoining Building -> Parcel (spatial centroid-in-polygon)...")

    # Estimate heights from BUILDINGCL
    buildings["_height"] = buildings["BUILDINGCL"].map(BUILDING_CLASS_HEIGHTS).fillna(8.0)
    if "SHAPE_Area" in buildings.columns:
        areas = buildings["SHAPE_Area"].fillna(0)
        area_factor = 1.0 + 0.1 * np.clip((areas - areas.median()) / (areas.std() + 1), -1, 1)
        buildings["_height"] = buildings["_height"] * area_factor
        buildings["_height"] = buildings["_height"].round(1)

    buildings["_bldg_idx"] = buildings.index
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

    buildings["_parcel_idx"] = None
    for idx, row in spatial_b2p.iterrows():
        if pd.notna(row.get("index_right")):
            buildings.at[idx, "_parcel_idx"] = int(row["index_right"])

    bldg_matched = buildings["_parcel_idx"].notna().sum()
    print(f"  Matched: {bldg_matched}/{len(buildings)}")
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
