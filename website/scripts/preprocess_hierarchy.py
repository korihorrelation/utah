"""
Preprocess GIS data into a spatial hierarchy for the web app.

Hierarchy: City â†’ Subdivisions â†’ Plats â†’ Parcels â†’ Address Points
Roads/Paths are exported as simple overlay layers.

Output: website/public/data/
"""

import os
import json
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import mapping

# â”€â”€â”€ Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WEBSITE_DIR = os.path.dirname(SCRIPT_DIR)
WORKSPACE_DIR = os.path.dirname(WEBSITE_DIR)
MAPS_DIR = os.path.join(WORKSPACE_DIR, "city_of_saratoga_springs_maps")
OUTPUT_DIR = os.path.join(WEBSITE_DIR, "public", "data")

# Geometry simplification tolerances (in degrees, ~1Â° â‰ˆ 111km)
SIMPLIFY_SUBDIV = 0.00008   # ~9m â€” subdivision outlines
SIMPLIFY_PLAT = 0.00005     # ~5.5m â€” plat boundaries
SIMPLIFY_PARCEL = 0.00003   # ~3.3m â€” parcel polygons
SIMPLIFY_ROAD = 0.00005     # ~5.5m â€” road lines
SIMPLIFY_PATH = 0.00008     # ~9m â€” trail lines
COORD_PRECISION = 6         # decimal places for coordinates


def load_layer(path):
    """Load a GIS layer and reproject to EPSG:4326."""
    gdf = gpd.read_file(path)
    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def simplify_geometry(gdf, tolerance):
    """Simplify geometries and drop empty/null results."""
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.simplify(tolerance, preserve_topology=True)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    return gdf


def round_coords(geojson_dict, precision=COORD_PRECISION):
    """Recursively round coordinates in a GeoJSON-like dict to save space."""
    if isinstance(geojson_dict, dict):
        return {k: round_coords(v, precision) for k, v in geojson_dict.items()}
    elif isinstance(geojson_dict, list):
        return [round_coords(item, precision) for item in geojson_dict]
    elif isinstance(geojson_dict, float):
        return round(geojson_dict, precision)
    return geojson_dict


def safe_value(val):
    """Convert numpy/pandas types to JSON-safe Python types."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return round(float(val), 4)
    if isinstance(val, (pd.Timestamp,)):
        return val.isoformat()
    return val


def gdf_to_features(gdf, properties_map, id_field=None):
    """
    Convert a GeoDataFrame to a list of GeoJSON features with selected properties.
    properties_map: dict of {output_key: source_column}
    """
    features = []
    for idx, row in gdf.iterrows():
        props = {}
        for out_key, src_col in properties_map.items():
            if src_col in row.index:
                props[out_key] = safe_value(row[src_col])
            else:
                props[out_key] = None
        if id_field and id_field in row.index:
            props["id"] = safe_value(row[id_field])

        geom = mapping(row.geometry)
        geom = round_coords(geom)
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": geom
        })
    return features


def write_json(data, path):
    """Write JSON to file, creating directories as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    size_kb = os.path.getsize(path) / 1024
    print(f"  Wrote {path} ({size_kb:.0f} KB)")


# â”€â”€â”€ Main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main():
    print("=== Preprocessing GIS Hierarchy ===\n")

    # â”€â”€ Load layers â”€â”€
    print("Loading layers...")
    city_boundary = load_layer(os.path.join(MAPS_DIR, "boundaries", "city_boundary.geojson"))
    subdivisions = load_layer(os.path.join(MAPS_DIR, "boundaries", "subdivisions.geojson"))
    # Override Beacon Pointe to Subdivision (Residential) as requested by the user
    subdivisions.loc[subdivisions["NAME"] == "Beacon Pointe", "TYPE"] = "Subdivision"
    plats = load_layer(os.path.join(MAPS_DIR, "boundaries", "plat.geojson"))
    parcels = load_layer(os.path.join(MAPS_DIR, "buildings_and_parcels", "parcels.zip"))
    addresses = load_layer(os.path.join(MAPS_DIR, "buildings_and_parcels", "address_points.zip"))
    roads = load_layer(os.path.join(MAPS_DIR, "transportation", "roads.zip"))
    paths = load_layer(os.path.join(MAPS_DIR, "parks_and_recreation", "path.geojson"))

    print(f"  Subdivisions: {len(subdivisions)}")
    print(f"  Plats: {len(plats)}")
    print(f"  Parcels: {len(parcels)}")
    print(f"  Addresses: {len(addresses)}")
    print(f"  Roads: {len(roads)}")
    print(f"  Paths: {len(paths)}")

    # â”€â”€ Build hierarchy: Plat â†’ Subdivision â”€â”€
    print("\nJoining Plat â†’ Subdivision...")

    # Attribute join first (SubID â†’ ID)
    plats["_sub_id"] = None
    subdiv_id_set = set(subdivisions["ID"].dropna().unique())

    for idx, row in plats.iterrows():
        sub_id = row.get("SubID")
        if pd.notna(sub_id) and int(sub_id) in subdiv_id_set:
            plats.at[idx, "_sub_id"] = int(sub_id)

    matched = plats["_sub_id"].notna().sum()
    print(f"  Attribute-matched: {matched}/{len(plats)}")

    # Spatial fallback for unmatched
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

    total_matched = plats["_sub_id"].notna().sum()
    print(f"  Total matched: {total_matched}/{len(plats)}")

    # â”€â”€ Build hierarchy: Parcel â†’ Plat (spatial join) â”€â”€
    print("\nJoining Parcel â†’ Plat (spatial centroid-in-polygon)...")

    parcels["_parcel_idx"] = parcels.index
    parcel_centroids = parcels.copy()
    parcel_centroids["_centroid"] = parcel_centroids.geometry.centroid
    parcel_centroids = parcel_centroids.set_geometry("_centroid")

    # Use plat OBJECTID as join key
    plats["_plat_oid"] = plats["OBJECTID"]
    spatial_p2pl = gpd.sjoin(
        parcel_centroids[["_centroid", "_parcel_idx"]],
        plats[["_plat_oid", "geometry"]],
        how="left",
        predicate="within"
    )
    # Handle duplicates (parcel centroid in overlapping plats) â€” take first
    spatial_p2pl = spatial_p2pl[~spatial_p2pl.index.duplicated(keep="first")]

    parcels["_plat_oid"] = None
    for idx, row in spatial_p2pl.iterrows():
        if pd.notna(row.get("_plat_oid")):
            parcels.at[idx, "_plat_oid"] = int(row["_plat_oid"])

    parcel_matched = parcels["_plat_oid"].notna().sum()
    print(f"  Matched: {parcel_matched}/{len(parcels)}")

    # â”€â”€ Build hierarchy: Address â†’ Parcel (attribute join) â”€â”€
    print("\nJoining Address â†’ Parcel (ParcelID)...")

    # Create lookup: PARCELID â†’ parcel index
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

    # â”€â”€ Simplify geometries â”€â”€
    print("\nSimplifying geometries...")
    subdivisions_s = simplify_geometry(subdivisions, SIMPLIFY_SUBDIV)
    plats_s = simplify_geometry(plats, SIMPLIFY_PLAT)
    parcels_s = simplify_geometry(parcels, SIMPLIFY_PARCEL)
    roads_s = simplify_geometry(roads, SIMPLIFY_ROAD)
    paths_s = simplify_geometry(paths, SIMPLIFY_PATH)

    # â”€â”€ Export city boundary â”€â”€
    print("\nExporting layers...")
    city_features = gdf_to_features(city_boundary, {}, None)
    write_json({
        "type": "FeatureCollection",
        "features": city_features
    }, os.path.join(OUTPUT_DIR, "city_boundary.json"))

    # â”€â”€ Export subdivisions â”€â”€
    subdiv_features = gdf_to_features(subdivisions_s, {
        "id": "ID",
        "name": "NAME",
        "density": "DENSITY",
        "acres": "ACRE",
        "status": "STATUS",
        "type": "TYPE",
        "recordedUnits": "RECORDEDUNITS",
        "plannedUnits": "PLANNEDUNITS",
        "existingUnits": "EXISTINGUNITS",
    }, "ID")
    write_json({
        "type": "FeatureCollection",
        "features": subdiv_features
    }, os.path.join(OUTPUT_DIR, "subdivisions.json"))

    # â”€â”€ Export roads â”€â”€
    road_features = gdf_to_features(roads_s, {
        "name": "FULLNAME",
        "type": "POSTTYPE",
        "speedLimit": "SPEED_LMT",
    })
    write_json({
        "type": "FeatureCollection",
        "features": road_features
    }, os.path.join(OUTPUT_DIR, "roads.json"))

    # â”€â”€ Export paths â”€â”€
    path_features = gdf_to_features(paths_s, {
        "use": "PATHUSE",
        "type": "TYPE",
        "surface": "SURFACE",
        "name": "NAME",
    })
    write_json({
        "type": "FeatureCollection",
        "features": path_features
    }, os.path.join(OUTPUT_DIR, "paths.json"))

    # â”€â”€ Build per-subdivision tiles + hierarchy tree â”€â”€
    print("\nBuilding hierarchy tree and subdivision tiles...")
    hierarchy_tree = {
        "name": "Saratoga Springs",
        "type": "city",
        "children": []
    }

    subdiv_ids = sorted(subdivisions["ID"].dropna().unique())

    for sub_id in subdiv_ids:
        sub_id = int(sub_id)
        sub_row = subdivisions[subdivisions["ID"] == sub_id].iloc[0]
        sub_name = sub_row["NAME"] if pd.notna(sub_row["NAME"]) else f"Subdivision {sub_id}"

        # Get plats in this subdivision
        sub_plats = plats_s[plats_s["_sub_id"] == sub_id]

        sub_node = {
            "id": sub_id,
            "name": sub_name,
            "type": "subdivision",
            "subdivisionType": safe_value(sub_row.get("TYPE")),
            "platCount": len(sub_plats),
            "children": []
        }

        # Build tile data for this subdivision
        tile_plat_features = []
        tile_parcel_features = []
        tile_address_features = []

        for _, plat_row in sub_plats.iterrows():
            plat_oid = int(plat_row["OBJECTID"])
            plat_name = plat_row["Name"] if pd.notna(plat_row.get("Name")) else f"Plat {plat_oid}"
            plat_label = plat_row["Plat"] if pd.notna(plat_row.get("Plat")) else ""

            # Get parcels in this plat
            plat_parcels = parcels_s[parcels_s["_plat_oid"] == plat_oid]

            # Get addresses for these parcels
            plat_parcel_indices = set(plat_parcels.index)
            plat_addresses = addresses[addresses["_parcel_idx"].isin(plat_parcel_indices)]

            plat_node = {
                "id": plat_oid,
                "name": plat_name,
                "label": plat_label,
                "type": "plat",
                "parcelCount": len(plat_parcels),
                "addressCount": len(plat_addresses),
                "children": []
            }

            # Add parcel children to hierarchy
            for p_idx, p_row in plat_parcels.iterrows():
                parcel_id = safe_value(p_row.get("PARCELID"))
                parcel_addr = safe_value(p_row.get("SITE_FULL_"))
                p_addresses = addresses[addresses["_parcel_idx"] == p_idx]

                parcel_node = {
                    "id": parcel_id,
                    "name": parcel_addr or f"Parcel {parcel_id}",
                    "type": "parcel",
                    "addressCount": len(p_addresses),
                }

                if len(p_addresses) > 0:
                    parcel_node["children"] = []
                    for _, a_row in p_addresses.iterrows():
                        parcel_node["children"].append({
                            "id": safe_value(a_row.get("UTAddPtID")),
                            "name": safe_value(a_row.get("FullAdd")) or "Unknown Address",
                            "type": "address",
                        })

                plat_node["children"].append(parcel_node)

            sub_node["children"].append(plat_node)

            # Build tile features
            plat_geom = mapping(plat_row.geometry)
            plat_geom = round_coords(plat_geom)
            tile_plat_features.append({
                "type": "Feature",
                "properties": {
                    "id": plat_oid,
                    "name": plat_name,
                    "label": plat_label,
                    "acres": safe_value(plat_row.get("Acres")),
                    "subdivision": sub_name,
                },
                "geometry": plat_geom
            })

            for p_idx, p_row in plat_parcels.iterrows():
                p_geom = mapping(p_row.geometry)
                p_geom = round_coords(p_geom)
                tile_parcel_features.append({
                    "type": "Feature",
                    "properties": {
                        "id": safe_value(p_row.get("PARCELID")),
                        "address": safe_value(p_row.get("SITE_FULL_")),
                        "owner": safe_value(p_row.get("OWNER_NAME")),
                        "acreage": safe_value(p_row.get("ACREAGE")),
                        "marketValue": safe_value(p_row.get("MKT_CUR_VA")),
                        "platId": plat_oid,
                    },
                    "geometry": p_geom
                })

            for _, a_row in plat_addresses.iterrows():
                a_geom = mapping(a_row.geometry)
                a_geom = round_coords(a_geom)
                tile_address_features.append({
                    "type": "Feature",
                    "properties": {
                        "id": safe_value(a_row.get("UTAddPtID")),
                        "fullAddress": safe_value(a_row.get("FullAdd")),
                        "city": safe_value(a_row.get("City")),
                        "zipCode": safe_value(a_row.get("ZipCode")),
                        "parcelId": safe_value(a_row.get("ParcelID")),
                        "structureType": safe_value(a_row.get("Structure")),
                        "pointType": safe_value(a_row.get("PtType")),
                    },
                    "geometry": a_geom
                })

        # Update counts on subdivision node
        sub_node["parcelCount"] = len(tile_parcel_features)
        sub_node["addressCount"] = len(tile_address_features)

        # Write subdivision tile
        write_json({
            "plats": {"type": "FeatureCollection", "features": tile_plat_features},
            "parcels": {"type": "FeatureCollection", "features": tile_parcel_features},
            "addresses": {"type": "FeatureCollection", "features": tile_address_features},
        }, os.path.join(OUTPUT_DIR, "subdivisions", f"{sub_id}.json"))

        hierarchy_tree["children"].append(sub_node)

    # â”€â”€ Handle unassigned plats (no subdivision) â”€â”€
    unassigned_plats = plats_s[plats_s["_sub_id"].isna()]
    if len(unassigned_plats) > 0:
        print(f"\n  Unassigned plats: {len(unassigned_plats)}")
        unassigned_node = {
            "id": "unassigned",
            "name": "Unassigned Areas",
            "type": "subdivision",
            "subdivisionType": "Unassigned",
            "platCount": len(unassigned_plats),
            "children": []
        }

        tile_plat_features = []
        tile_parcel_features = []
        tile_address_features = []

        for _, plat_row in unassigned_plats.iterrows():
            plat_oid = int(plat_row["OBJECTID"])
            plat_name = plat_row["Name"] if pd.notna(plat_row.get("Name")) else f"Plat {plat_oid}"

            plat_parcels = parcels_s[parcels_s["_plat_oid"] == plat_oid]
            plat_parcel_indices = set(plat_parcels.index)
            plat_addresses = addresses[addresses["_parcel_idx"].isin(plat_parcel_indices)]

            plat_node = {
                "id": plat_oid,
                "name": plat_name,
                "type": "plat",
                "parcelCount": len(plat_parcels),
                "addressCount": len(plat_addresses),
                "children": []
            }

            for p_idx, p_row in plat_parcels.iterrows():
                parcel_id = safe_value(p_row.get("PARCELID"))
                parcel_addr = safe_value(p_row.get("SITE_FULL_"))
                p_addresses = addresses[addresses["_parcel_idx"] == p_idx]
                parcel_node = {
                    "id": parcel_id,
                    "name": parcel_addr or f"Parcel {parcel_id}",
                    "type": "parcel",
                    "addressCount": len(p_addresses),
                }
                if len(p_addresses) > 0:
                    parcel_node["children"] = []
                    for _, a_row in p_addresses.iterrows():
                        parcel_node["children"].append({
                            "id": safe_value(a_row.get("UTAddPtID")),
                            "name": safe_value(a_row.get("FullAdd")) or "Unknown Address",
                            "type": "address",
                        })
                plat_node["children"].append(parcel_node)

            unassigned_node["children"].append(plat_node)

            plat_geom = mapping(plat_row.geometry)
            plat_geom = round_coords(plat_geom)
            tile_plat_features.append({
                "type": "Feature",
                "properties": {"id": plat_oid, "name": plat_name},
                "geometry": plat_geom
            })

            for p_idx, p_row in plat_parcels.iterrows():
                p_geom = mapping(p_row.geometry)
                p_geom = round_coords(p_geom)
                tile_parcel_features.append({
                    "type": "Feature",
                    "properties": {
                        "id": safe_value(p_row.get("PARCELID")),
                        "address": safe_value(p_row.get("SITE_FULL_")),
                        "owner": safe_value(p_row.get("OWNER_NAME")),
                        "platId": plat_oid,
                    },
                    "geometry": p_geom
                })

            for _, a_row in plat_addresses.iterrows():
                a_geom = mapping(a_row.geometry)
                a_geom = round_coords(a_geom)
                tile_address_features.append({
                    "type": "Feature",
                    "properties": {
                        "id": safe_value(a_row.get("UTAddPtID")),
                        "fullAddress": safe_value(a_row.get("FullAdd")),
                        "parcelId": safe_value(a_row.get("ParcelID")),
                    },
                    "geometry": a_geom
                })

        unassigned_node["parcelCount"] = len(tile_parcel_features)
        unassigned_node["addressCount"] = len(tile_address_features)

        write_json({
            "plats": {"type": "FeatureCollection", "features": tile_plat_features},
            "parcels": {"type": "FeatureCollection", "features": tile_parcel_features},
            "addresses": {"type": "FeatureCollection", "features": tile_address_features},
        }, os.path.join(OUTPUT_DIR, "subdivisions", "unassigned.json"))

        hierarchy_tree["children"].append(unassigned_node)

    # â”€â”€ Handle unassigned parcels (not in any plat) â”€â”€
    all_assigned_parcel_indices = set(parcels_s[parcels_s["_plat_oid"].notna()].index)
    orphan_parcels = parcels_s[~parcels_s.index.isin(all_assigned_parcel_indices)]
    print(f"  Orphan parcels (no plat): {len(orphan_parcels)}")

    # â”€â”€ Write hierarchy.json â”€â”€
    # Add summary counts
    total_parcels = sum(
        child.get("parcelCount", 0)
        for child in hierarchy_tree["children"]
    )
    total_addresses = sum(
        child.get("addressCount", 0)
        for child in hierarchy_tree["children"]
    )
    hierarchy_tree["subdivisionCount"] = len(hierarchy_tree["children"])
    hierarchy_tree["totalParcels"] = total_parcels
    hierarchy_tree["totalAddresses"] = total_addresses

    write_json(hierarchy_tree, os.path.join(OUTPUT_DIR, "hierarchy.json"))

    print(f"\n=== Preprocessing complete! ===")
    print(f"  Subdivisions: {len(hierarchy_tree['children'])}")
    print(f"  Total parcels in hierarchy: {total_parcels}")
    print(f"  Total addresses in hierarchy: {total_addresses}")


if __name__ == "__main__":
    main()


