"""
Preprocess GIS data into a spatial hierarchy for the web app.

Hierarchy: City -> Subdivisions -> Plats -> Parcels -> Buildings -> Address Points
Roads/Paths are exported as simple overlay layers.

Output: website/public/data/
"""

import os
import json
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import mapping

from pipeline.classifiers import classify_all_subdivisions
from pipeline.config import load_classification_rules
from pipeline.filters import apply_filters
from pipeline.joiners import (join_land_use, join_plats_to_subdivisions,
                               join_parcels_to_plats, join_addresses_to_parcels,
                               join_buildings_to_parcels, join_pois_to_buildings)

# ──────────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WEBSITE_DIR = os.path.dirname(SCRIPT_DIR)
WORKSPACE_DIR = os.path.dirname(WEBSITE_DIR)
MAPS_DIR = os.path.join(WORKSPACE_DIR, "city_of_saratoga_springs_maps")
OUTPUT_DIR = os.path.join(WEBSITE_DIR, "public", "data")
LAND_USE_PATH = os.path.join(MAPS_DIR, "boundaries", "land_use.geojson")

# Geometry simplification tolerances (in degrees, ~1° ≈ 111km)
SIMPLIFY_SUBDIV = 0.00008   # ~9m — subdivision outlines
SIMPLIFY_PLAT = 0.00005     # ~5.5m — plat boundaries
SIMPLIFY_PARCEL = 0.00003   # ~3.3m — parcel polygons
SIMPLIFY_BUILDING = 0.00002 # ~2.2m — building footprints
SIMPLIFY_ROAD = 0.00005     # ~5.5m — road lines
SIMPLIFY_PATH = 0.00008     # ~9m — trail lines
COORD_PRECISION = 6         # decimal places for coordinates

# Building class labels and estimated heights (meters)
BUILDING_CLASS_LABELS = {
    1: 'Residential', 2: 'Commercial', 3: 'Industrial', 4: 'Government',
    6: 'Agricultural', 7: 'Religious', 8: 'Education', 11: 'Utility', 12: 'Other',
}
BUILDING_CLASS_HEIGHTS = {
    1: 8.0, 2: 12.0, 3: 10.0, 4: 14.0,
    6: 6.0, 7: 12.0, 8: 12.0, 11: 8.0, 12: 6.0,
}


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



def main():
    print("=== Preprocessing GIS Hierarchy ===\n")

    # ── Load classification rules ──
    rules = load_classification_rules()
    print("Loaded classification rules from YAML.")

    # ── Load layers ──
    print("Loading layers...")
    city_boundary = load_layer(os.path.join(MAPS_DIR, "boundaries", "city_boundary.geojson"))
    subdivisions = load_layer(os.path.join(MAPS_DIR, "boundaries", "subdivisions.geojson"))
    subdivisions.loc[subdivisions["NAME"] == "Beacon Pointe", "TYPE"] = "Subdivision"
    subdivisions.loc[subdivisions["NAME"] == "Saratoga Springs Development", "ID"] = 910

    plats = load_layer(os.path.join(MAPS_DIR, "boundaries", "plat.geojson"))
    parcels = load_layer(os.path.join(MAPS_DIR, "buildings_and_parcels", "parcels.zip"))
    addresses = load_layer(os.path.join(MAPS_DIR, "buildings_and_parcels", "address_points.zip"))
    buildings = load_layer(os.path.join(MAPS_DIR, "buildings_and_parcels", "building_footprints.zip"))
    roads = load_layer(os.path.join(MAPS_DIR, "transportation", "roads.zip"))
    paths = load_layer(os.path.join(MAPS_DIR, "parks_and_recreation", "path.geojson"))

    if not os.path.exists(LAND_USE_PATH):
        print("Downloading Land Use layer...")
        os.makedirs(os.path.dirname(LAND_USE_PATH), exist_ok=True)
        landuse_url = "https://utility.arcgis.com/usrsvcs/servers/68e4307530da49a7a70929e966c2f833/rest/services/Planning/LandUse/MapServer/2/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=geojson"
        import urllib.request
        req = urllib.request.Request(landuse_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as response:
            with open(LAND_USE_PATH, "wb") as f:
                f.write(response.read())
        print("  Land Use layer downloaded and cached.")

    landuse = load_layer(LAND_USE_PATH)

    print(f"  Subdivisions: {len(subdivisions)}")
    print(f"  Plats: {len(plats)}")
    print(f"  Parcels: {len(parcels)}")
    print(f"  Addresses: {len(addresses)}")
    print(f"  Buildings: {len(buildings)}")
    print(f"  Roads: {len(roads)}")
    print(f"  Paths: {len(paths)}")
    print(f"  Land Use: {len(landuse)}")

    city_geom = city_boundary.geometry.unary_union

    layers = {
        "subdivisions": subdivisions, "plats": plats, "parcels": parcels,
        "buildings": buildings, "addresses": addresses, "roads": roads, "paths": paths,
    }
    layers = apply_filters(layers, city_geom, rules)
    subdivisions = layers["subdivisions"]
    plats = layers["plats"]
    parcels = layers["parcels"]
    buildings = layers["buildings"]
    addresses = layers["addresses"]
    roads = layers["roads"]
    paths = layers["paths"]
    # ── Land use joins ──
    plats = join_land_use(plats, landuse, label="Plats")
    parcels = join_land_use(parcels, landuse, label="Parcels")

    # ── Build hierarchy joins ──
    plats = join_plats_to_subdivisions(plats, subdivisions)
    parcels = join_parcels_to_plats(parcels, plats)
    addresses = join_addresses_to_parcels(addresses, parcels)

    # ── Create Israel Canyon custom subdivision ──
    print("\nCreating Israel Canyon subdivision...")
    teguayo_mask = subdivisions["NAME"].astype(str).str.contains("Teguayo", case=False, na=False)
    teguayo_geom = None
    if teguayo_mask.any():
        teguayo_geom = subdivisions[teguayo_mask].geometry.iloc[0]
        subdivisions = subdivisions[~teguayo_mask].copy()

    israel_canyon_pids = [
        "590110005", "590110006", "590110010", "590110011", "590110012",
        "590110015", "590110016", "590110017", "590110018", "590110019",
        "590110021", "590110023", "590110024", "590110025", "590110026",
        "590110027", "590110028", "590110030", "590110032", "590110034",
        "590110036", "590110037", "590110038", "590110041", "590110042",
        "590110046", "590110048", "590110050", "590110053", "590110055",
        "590110058", "590110059", "590110060", "590110061", "590110070",
        "590110073", "590110075", "590110076", "590110079", "590110082",
        "590110086", "590110087", "590110088", "590230032", "590230036",
        "590230037", "590230038", "590230034",
        "590230027", "590230005", "590230030", "590130095"
    ]
    
    mask_pid = parcels["PARCELID"].astype(str).isin(israel_canyon_pids)
    mask_waldo = parcels["OWNER_NAME"].astype(str).str.contains("Waldo", case=False, na=False)
    mask_weakland = parcels["OWNER_NAME"].astype(str).str.contains("Weakland", case=False, na=False)
    mask_jeppesen = parcels["OWNER_NAME"].astype(str).str.contains("Jeppesen", case=False, na=False)
    mask_scp = parcels["OWNER_NAME"].astype(str).str.contains("Scp Fox Hollow", case=False, na=False)
    mask_johnson = parcels["OWNER_NAME"].astype(str).str.contains("Johnson, Kathy", case=False, na=False)
    
    mask_teguayo = pd.Series(False, index=parcels.index)
    if teguayo_geom is not None:
        centroids_4326 = parcels.to_crs(epsg=3566).geometry.centroid.to_crs(epsg=4326)
        mask_teguayo = centroids_4326.within(teguayo_geom)

    ic_mask = mask_pid | mask_waldo | mask_weakland | mask_jeppesen | mask_scp | mask_johnson | mask_teguayo

    if ic_mask.any():
        ic_parcels = parcels[ic_mask]
        ic_sub_id = 4500000
        
        from shapely.ops import unary_union
        ic_geom = unary_union(ic_parcels.geometry.dropna().tolist())
        total_ic_acres = sum(safe_value(p.get("ACREAGE") or 0.0) for _, p in ic_parcels.iterrows())
        
        ic_sub_df = gpd.GeoDataFrame([{
            "ID": ic_sub_id,
            "NAME": "Israel Canyon",
            "DENSITY": "N/A",
            "ACRE": round(total_ic_acres, 2),
            "STATUS": "Active",
            "TYPE": "Subdivision",
            "geometry": ic_geom
        }], crs=subdivisions.crs)
        subdivisions = pd.concat([subdivisions, ic_sub_df], ignore_index=True)
        
        new_plat_rows_ic = []
        base_plat_oid = 4600000
        
        parcels.loc[ic_mask, "_plat_oid"] = None

        def clean_owner(name):
            if pd.isna(name): return "Unknown Owner"
            s = str(name).strip().title()
            if not s: return "Unknown Owner"
            return s.replace("Lds", "LDS").replace("Udot", "UDOT").replace(" Us ", " US ")

        ic_owners = ic_parcels["OWNER_NAME"].apply(clean_owner)
        ic_parcels_grouped = ic_parcels.groupby(ic_owners)

        for p_idx, (owner_name, group) in enumerate(ic_parcels_grouped):
            plat_oid = base_plat_oid + p_idx
            group_geom = unary_union(group.geometry.dropna().tolist())
            group_acres = sum(safe_value(p.get("ACREAGE") or 0.0) for _, p in group.iterrows())
            
            new_plat_rows_ic.append({
                "OBJECTID": plat_oid,
                "Name": f"Plat for {owner_name}",
                "label": "A",
                "Acres": round(group_acres, 2),
                "SubID": ic_sub_id,
                "_sub_id": ic_sub_id,
                "landUse": "Mixed",
                "geometry": group_geom
            })
            parcels.loc[group.index, "_plat_oid"] = plat_oid

        ic_plat_df = gpd.GeoDataFrame(new_plat_rows_ic, crs=plats.crs)
        plats = pd.concat([plats, ic_plat_df], ignore_index=True)
        
        print(f"  Assigned {ic_mask.sum()} parcels to Israel Canyon across {len(new_plat_rows_ic)} plats")

    # ── Promote parcels 98% not in a subdivision to subdivision status ──
    print("\nPromoting unassigned parcels...")
    # Project to EPSG:3566 for accurate spatial calculations in meters
    parcels_proj = parcels.to_crs(epsg=3566)
    subdivs_proj = subdivisions.to_crs(epsg=3566)

    # 1. Identify unassigned parcels
    # Build a lookup mapping plat OBJECTID -> subdivision _sub_id
    plat_sub_lookup = plats.set_index("OBJECTID")["_sub_id"].to_dict()

    # A parcel is unassigned if it has no plat, or if its plat's subdivision is NaN/None
    def is_parcel_unassigned(p_row):
        plat_oid = p_row.get("_plat_oid")
        if pd.isna(plat_oid):
            return True
        sub_id = plat_sub_lookup.get(int(plat_oid))
        return pd.isna(sub_id)

    unassigned_mask = parcels.apply(is_parcel_unassigned, axis=1)

    # ── Match unassigned parcels to existing subdivisions by SUB_NAME ──
    print("Matching unassigned parcels to existing subdivisions by SUB_NAME...")
    sub_name_lookup = {str(row["NAME"]).strip().lower(): int(row["ID"]) for _, row in subdivisions.iterrows()}
    
    import re
    def clean_sub_name(sub_name):
        s = str(sub_name).strip().lower()
        s = re.sub(r'[\s,]+(plat|phase|ph|road church)[\s\w]*$', '', s)
        s = re.sub(r'[\s,]+plat[\s\w]*$', '', s)
        s = re.sub(r'[\s,]+phase[\s\w]*$', '', s)
        return s.strip()

    name_matched_count = 0
    new_plat_rows_from_unassigned = []
    base_virtual_plat_oid = 7000000
    
    for p_idx, p_row in parcels[unassigned_mask].iterrows():
        sub_name_val = p_row.get("SUB_NAME")
        if pd.isna(sub_name_val) or not str(sub_name_val).strip():
            continue
            
        clean_name = clean_sub_name(sub_name_val)
        if clean_name in sub_name_lookup:
            matched_sub_id = sub_name_lookup[clean_name]
            
            sub_plats = plats[plats["_sub_id"] == matched_sub_id]
            best_plat_oid = None
            
            sub_name_val_lower = str(sub_name_val).lower()
            for _, plat_row in sub_plats.iterrows():
                plat_name = str(plat_row.get("Name") or "").lower()
                plat_label = str(plat_row.get("Plat") or "").lower()
                if plat_name in sub_name_val_lower or (plat_label and f"plat {plat_label}" in sub_name_val_lower) or (plat_label and f"phase {plat_label}" in sub_name_val_lower):
                    best_plat_oid = int(plat_row["OBJECTID"])
                    break
            
            if best_plat_oid is None:
                if len(sub_plats) > 0:
                    best_plat_oid = int(sub_plats.iloc[0]["OBJECTID"])
                else:
                    best_plat_oid = base_virtual_plat_oid + p_idx
                    new_plat_rows_from_unassigned.append({
                        "OBJECTID": best_plat_oid,
                        "Name": f"Plat for {sub_name_val.strip().title()}",
                        "label": "A",
                        "Acres": safe_value(p_row.get("ACREAGE")),
                        "SubID": matched_sub_id,
                        "_sub_id": matched_sub_id,
                        "landUse": p_row.get("landUse"),
                        "geometry": p_row.geometry
                    })
            
            parcels.at[p_idx, "_plat_oid"] = best_plat_oid
            if best_plat_oid >= base_virtual_plat_oid:
                plat_sub_lookup[best_plat_oid] = matched_sub_id
            name_matched_count += 1

    if len(new_plat_rows_from_unassigned) > 0:
        new_plat_df = gpd.GeoDataFrame(new_plat_rows_from_unassigned, crs=plats.crs)
        plats = pd.concat([plats, new_plat_df], ignore_index=True)
        print(f"  Created {len(new_plat_rows_from_unassigned)} virtual plats for name-matched unassigned parcels.")

    # Re-evaluate unassigned_mask after matches have been assigned
    unassigned_mask = parcels.apply(is_parcel_unassigned, axis=1)
    unassigned_parcels_proj = parcels_proj[unassigned_mask].copy()
    print(f"  Name-matched and assigned {name_matched_count} parcels to existing subdivisions. Remaining unassigned: {len(unassigned_parcels_proj)}")

    # Group by cleaned owner name
    unassigned_parcels_proj["owner_clean"] = unassigned_parcels_proj["OWNER_NAME"].fillna("").str.strip().str.upper()
    valid_owner_mask = unassigned_parcels_proj["owner_clean"] != ""
    unassigned_with_owner = unassigned_parcels_proj[valid_owner_mask]

    import networkx as nx
    clusters = []
    clustered_indices = set()

    for owner, group in unassigned_with_owner.groupby("owner_clean"):
        if len(group) < 2:
            continue
        
        # Build graph of touching geometries
        G = nx.Graph()
        G.add_nodes_from(group.index)
        
        sindex = group.sindex
        for idx, row in group.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            possible = list(sindex.intersection(geom.bounds))
            for p_idx in possible:
                other_idx = group.index[p_idx]
                if other_idx == idx:
                    continue
                other_geom = group.loc[other_idx].geometry
                # Use tiny buffer to account for rounding/overlap/touch precision
                if geom.intersects(other_geom.buffer(0.1)):
                    G.add_edge(idx, other_idx)
                    
        for component in nx.connected_components(G):
            if len(component) >= 2:
                clusters.append((owner, list(component)))
                clustered_indices.update(component)

    print(f"  Found {len(clusters)} clusters of touching parcels with matching owner.")

    # We will track newly created virtual subdivisions and virtual plats
    new_subdiv_rows = []
    new_plat_rows = []
    
    # Track promoted counts
    cluster_promotions = 0
    single_promotions = 0

    # A. Process clusters (touching parcels of same owner)
    for c_idx, (owner, comp_indices) in enumerate(clusters):
        # Format owner name for display: Title Case (e.g. "Alpine School District")
        owner_display = owner.title()
        # Clean up acronyms
        owner_display = owner_display.replace("Lds", "LDS").replace("Udot", "UDOT").replace(" Us ", " US ")
        
        sub_name = f"{owner_display} Area"
        
        # Virtual subdivision ID (use a unique range for clusters: 5500000 + c_idx)
        sub_id = int(5500000 + c_idx)
        
        # Determine sub_type from the land use of the first parcel in cluster
        first_row = parcels.loc[comp_indices[0]]
        land_use_val = first_row.get("landUse") or ""
        land_use_lower = str(land_use_val).lower()
        if any(x in land_use_lower for x in ["res", "dwelling", "apartment", "condo", "townhouse", "housing"]):
            sub_type = "Subdivision"
        elif any(x in land_use_lower for x in ["comm", "retail", "office", "shop", "business", "industrial"]):
            sub_type = "Commercial"
        else:
            sub_type = "CommunityPlan"

        # Construct combined geometry for the subdivision outline
        cluster_geoms = parcels.loc[comp_indices, "geometry"]
        from shapely.ops import unary_union
        subdiv_geom = unary_union(cluster_geoms.tolist())

        # Total acreage
        total_acres = sum(safe_value(parcels.loc[idx].get("ACREAGE") or 0.0) for idx in comp_indices)

        new_subdiv_rows.append({
            "ID": sub_id,
            "NAME": sub_name,
            "DENSITY": "N/A",
            "ACRE": round(total_acres, 2),
            "STATUS": "Active",
            "TYPE": sub_type,
            "geometry": subdiv_geom
        })

        for p_idx in comp_indices:
            orig_p_row = parcels.loc[p_idx]
            parcel_id = orig_p_row.get("PARCELID")
            site_addr = orig_p_row.get("SITE_FULL_")
            p_name = site_addr or f"Parcel {parcel_id}"
            
            # Virtual plat ID
            plat_oid = int(6500000 + p_idx)
            
            new_plat_rows.append({
                "OBJECTID": plat_oid,
                "Name": f"Plat for {p_name}",
                "label": "A",
                "Acres": safe_value(orig_p_row.get("ACREAGE")),
                "SubID": sub_id,
                "_sub_id": sub_id,
                "landUse": orig_p_row.get("landUse"),
                "geometry": orig_p_row.geometry
            })
            
            # Reassign parcel parent plat
            parcels.at[p_idx, "_plat_oid"] = plat_oid
            cluster_promotions += 1

    # B. Process single unassigned parcels (same behavior as before)
    # They must not be part of any cluster, and must have no plat (orphan)
    subdiv_sindex = subdivs_proj.sindex
    
    for p_idx, p_row in unassigned_parcels_proj.iterrows():
        # Only check orphans (no plat) that are NOT in a cluster
        if p_idx in clustered_indices:
            continue
        if not pd.isna(parcels.loc[p_idx, "_plat_oid"]):
            continue
            
        geom = p_row.geometry
        if geom is None or geom.is_empty:
            continue

        possible = list(subdiv_sindex.intersection(geom.bounds))
        pct_not_in = 1.0
        best_sub_id = None
        if len(possible) > 0:
            intersecting = subdivs_proj.iloc[possible]
            max_area = 0
            for _, sub_row in intersecting.iterrows():
                if sub_row.geometry is None or sub_row.geometry.is_empty:
                    continue
                inter_area = geom.intersection(sub_row.geometry).area
                if inter_area > max_area:
                    max_area = inter_area
                    best_sub_id = sub_row["ID"]

            from shapely.ops import unary_union
            intersect_geom = geom.intersection(unary_union(intersecting.geometry.tolist()))
            if geom.area > 0:
                pct_not_in = (geom.area - intersect_geom.area) / geom.area

        if pct_not_in >= 0.98:
            orig_p_row = parcels.loc[p_idx]
            parcel_id = orig_p_row.get("PARCELID")
            site_addr = orig_p_row.get("SITE_FULL_")
            sub_name_val = orig_p_row.get("SUB_NAME")
            if pd.notna(sub_name_val) and str(sub_name_val).strip():
                p_name = str(sub_name_val).strip().title()
            else:
                p_name = site_addr or f"Parcel {parcel_id}"
            land_use_val = orig_p_row.get("landUse") or ""

            # Categorize TYPE
            land_use_lower = str(land_use_val).lower()
            if any(x in land_use_lower for x in ["res", "dwelling", "apartment", "condo", "townhouse", "housing"]):
                sub_type = "Subdivision"
            elif any(x in land_use_lower for x in ["comm", "retail", "office", "shop", "business", "industrial"]):
                sub_type = "Commercial"
            else:
                sub_type = "CommunityPlan"

            # Generate unique integer IDs (5000000 + p_idx)
            sub_id = int(5000000 + p_idx)
            plat_oid = int(6000000 + p_idx)

            # Virtual subdivision row
            new_subdiv_rows.append({
                "ID": sub_id,
                "NAME": p_name,
                "DENSITY": "N/A",
                "ACRE": safe_value(orig_p_row.get("ACREAGE")),
                "STATUS": "Active",
                "TYPE": sub_type,
                "geometry": orig_p_row.geometry
            })

            # Virtual plat row
            new_plat_rows.append({
                "OBJECTID": plat_oid,
                "Name": f"Plat for {p_name}",
                "label": "A",
                "Acres": safe_value(orig_p_row.get("ACREAGE")),
                "SubID": sub_id,
                "_sub_id": sub_id,
                "landUse": orig_p_row.get("landUse"),
                "geometry": orig_p_row.geometry
            })

            # Update parcel's parent plat link
            parcels.at[p_idx, "_plat_oid"] = plat_oid
            single_promotions += 1
            
        elif best_sub_id is not None:
            # Parcel falls inside a subdivision, so create a virtual plat for it inside that subdivision
            orig_p_row = parcels.loc[p_idx]
            parcel_id = orig_p_row.get("PARCELID")
            site_addr = orig_p_row.get("SITE_FULL_")
            sub_name_val = orig_p_row.get("SUB_NAME")
            if pd.notna(sub_name_val) and str(sub_name_val).strip():
                p_name = str(sub_name_val).strip().title()
            else:
                p_name = site_addr or f"Parcel {parcel_id}"
            plat_oid = int(6000000 + p_idx)
            
            new_plat_rows.append({
                "OBJECTID": plat_oid,
                "Name": f"Plat for {p_name}",
                "label": "A",
                "Acres": safe_value(orig_p_row.get("ACREAGE")),
                "SubID": best_sub_id,
                "_sub_id": best_sub_id,
                "landUse": orig_p_row.get("landUse"),
                "geometry": orig_p_row.geometry
            })
            parcels.at[p_idx, "_plat_oid"] = plat_oid

    print(f"  Promoted {cluster_promotions} clustered parcels and {single_promotions} single parcels to subdivision status.")

    if len(new_subdiv_rows) > 0:
        new_subdiv_df = gpd.GeoDataFrame(new_subdiv_rows, crs=subdivisions.crs)
        subdivisions = pd.concat([subdivisions, new_subdiv_df], ignore_index=True)
        print(f"  Appended {len(new_subdiv_rows)} subdivisions.")

    if len(new_plat_rows) > 0:
        new_plat_df = gpd.GeoDataFrame(new_plat_rows, crs=plats.crs)
        plats = pd.concat([plats, new_plat_df], ignore_index=True)
        print(f"  Appended {len(new_plat_rows)} plats.")


    # ── Build hierarchy: Building → Parcel + POI matching ──
    buildings = join_buildings_to_parcels(buildings, parcels)
    buildings = join_pois_to_buildings(buildings)

    # ── Compute subdivision categories ──
    classify_all_subdivisions(subdivisions, plats, parcels, rules)

    # ── Simplify geometries (Disabled) ──
    print("\nSimplifying geometries (disabled)...")
    subdivisions_s = subdivisions
    plats_s = plats
    parcels_s = parcels
    buildings_s = buildings
    roads_s = roads
    paths_s = paths

    # ── Export city boundary ──
    print("\nExporting layers...")
    city_features = gdf_to_features(city_boundary, {}, None)
    write_json({
        "type": "FeatureCollection",
        "features": city_features
    }, os.path.join(OUTPUT_DIR, "city_boundary.json"))

    # ── Export residential addresses for heatmap ──
    print("Exporting residential addresses for heatmap...")
    res_addresses = addresses[addresses["PtType"].astype(str).str.strip().str.lower().isin(["residential", "unknown"])]
    res_features = gdf_to_features(res_addresses, {}, None)
    write_json({
        "type": "FeatureCollection",
        "features": res_features
    }, os.path.join(OUTPUT_DIR, "residential_addresses.json"))

    # ── Export subdivisions ──
    subdiv_features = gdf_to_features(subdivisions_s, {
        "id": "ID",
        "name": "NAME",
        "density": "DENSITY",
        "acres": "ACRE",
        "status": "STATUS",
        "type": "TYPE",
        "category": "CATEGORY",
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
            "category": safe_value(sub_row.get("CATEGORY")),
            "platCount": len(sub_plats),
            "children": []
        }

        # Build tile data for this subdivision
        tile_plat_features = []
        tile_parcel_features = []
        tile_building_features = []
        tile_address_features = []

        for _, plat_row in sub_plats.iterrows():
            plat_oid = int(plat_row["OBJECTID"])
            plat_name = plat_row["Name"] if pd.notna(plat_row.get("Name")) else f"Plat {plat_oid}"
            plat_label = plat_row["Plat"] if pd.notna(plat_row.get("Plat")) else ""

            # Get parcels in this plat
            plat_parcels = parcels_s[parcels_s["_plat_oid"] == plat_oid]
            if len(plat_parcels) == 0:
                continue

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
                p_buildings = buildings_s[buildings_s["_parcel_idx"] == p_idx]

                parcel_node = {
                    "id": parcel_id,
                    "name": parcel_addr or f"Parcel {parcel_id}",
                    "type": "parcel",
                    "buildingCount": len(p_buildings),
                    "addressCount": len(p_addresses),
                    "children": [],
                }

                # Add buildings as children of parcel
                for b_idx, b_row in p_buildings.iterrows():
                    bldg_cls = safe_value(b_row.get("BUILDINGCL")) or 0
                    bldg_cls_int = int(bldg_cls) if bldg_cls else 0
                    bldg_label = BUILDING_CLASS_LABELS.get(bldg_cls_int, "Building")
                    bldg_addr = safe_value(b_row.get("FULLADDRES"))
                    bldg_name_raw = safe_value(b_row.get("NAME"))
                    bldg_name = bldg_name_raw or bldg_addr or bldg_label
                    bldg_id = safe_value(b_row.get("GLOBALID"))

                    building_node = {
                        "id": bldg_id,
                        "name": bldg_name,
                        "type": "building",
                        "buildingClass": bldg_cls_int,
                        "classLabel": bldg_label,
                    }

                    # Try to assign addresses to this building via point-in-polygon
                    if len(p_addresses) > 0 and b_row.geometry is not None:
                        bldg_addrs = p_addresses[p_addresses.geometry.within(b_row.geometry)]
                        if len(bldg_addrs) > 0:
                            building_node["addressCount"] = len(bldg_addrs)
                            building_node["children"] = []
                            for _, a_row in bldg_addrs.iterrows():
                                building_node["children"].append({
                                    "id": safe_value(a_row.get("UTAddPtID")),
                                    "name": safe_value(a_row.get("FullAdd")) or "Unknown Address",
                                    "type": "address",
                                })

                    parcel_node["children"].append(building_node)

                # Add remaining addresses directly under parcel (not inside any building)
                assigned_addr_ids = set()
                for b_idx, b_row in p_buildings.iterrows():
                    if b_row.geometry is not None and len(p_addresses) > 0:
                        bldg_addrs = p_addresses[p_addresses.geometry.within(b_row.geometry)]
                        for _, a_row in bldg_addrs.iterrows():
                            assigned_addr_ids.add(a_row.get("UTAddPtID"))

                unassigned_addrs = p_addresses[~p_addresses["UTAddPtID"].isin(assigned_addr_ids)]
                for _, a_row in unassigned_addrs.iterrows():
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
                    "landUse": safe_value(plat_row.get("landUse")),
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
                        "landUse": safe_value(p_row.get("landUse")),
                    },
                    "geometry": p_geom
                })

                # Add buildings for this parcel to tile
                p_buildings = buildings_s[buildings_s["_parcel_idx"] == p_idx]
                for _, b_row in p_buildings.iterrows():
                    b_geom = mapping(b_row.geometry)
                    b_geom = round_coords(b_geom)
                    bldg_cls = int(safe_value(b_row.get("BUILDINGCL")) or 0)
                    tile_building_features.append({
                        "type": "Feature",
                        "properties": {
                            "id": safe_value(b_row.get("GLOBALID")),
                            "name": safe_value(b_row.get("NAME")),
                            "address": safe_value(b_row.get("FULLADDRES")),
                            "class": bldg_cls,
                            "classLabel": BUILDING_CLASS_LABELS.get(bldg_cls, "Building"),
                            "height": safe_value(b_row.get("_height")),
                            "yearBuilt": safe_value(b_row.get("YEAR_BUILT")),
                            "stories": safe_value(b_row.get("NUMSTORIES")),
                            "parcelId": safe_value(p_row.get("PARCELID")),
                            "platId": plat_oid,
                        },
                        "geometry": b_geom
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
        sub_node["buildingCount"] = len(tile_building_features)
        sub_node["addressCount"] = len(tile_address_features)

        # Write subdivision tile
        write_json({
            "plats": {"type": "FeatureCollection", "features": tile_plat_features},
            "parcels": {"type": "FeatureCollection", "features": tile_parcel_features},
            "buildings": {"type": "FeatureCollection", "features": tile_building_features},
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
            "category": "Other",
            "platCount": len(unassigned_plats),
            "children": []
        }

        tile_plat_features = []
        tile_parcel_features = []
        tile_building_features = []
        tile_address_features = []

        for _, plat_row in unassigned_plats.iterrows():
            plat_oid = int(plat_row["OBJECTID"])
            plat_name = plat_row["Name"] if pd.notna(plat_row.get("Name")) else f"Plat {plat_oid}"

            plat_parcels = parcels_s[parcels_s["_plat_oid"] == plat_oid]
            if len(plat_parcels) == 0:
                continue
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
                p_buildings = buildings_s[buildings_s["_parcel_idx"] == p_idx]

                parcel_node = {
                    "id": parcel_id,
                    "name": parcel_addr or f"Parcel {parcel_id}",
                    "type": "parcel",
                    "buildingCount": len(p_buildings),
                    "addressCount": len(p_addresses),
                    "children": [],
                }

                # Add buildings
                for b_idx, b_row in p_buildings.iterrows():
                    bldg_cls = safe_value(b_row.get("BUILDINGCL")) or 0
                    bldg_cls_int = int(bldg_cls) if bldg_cls else 0
                    bldg_label = BUILDING_CLASS_LABELS.get(bldg_cls_int, "Building")
                    bldg_addr = safe_value(b_row.get("FULLADDRES"))
                    bldg_name_raw = safe_value(b_row.get("NAME"))
                    bldg_name = bldg_name_raw or bldg_addr or bldg_label
                    bldg_id = safe_value(b_row.get("GLOBALID"))
                    building_node = {
                        "id": bldg_id, "name": bldg_name, "type": "building",
                        "buildingClass": bldg_cls_int, "classLabel": bldg_label,
                    }
                    if len(p_addresses) > 0 and b_row.geometry is not None:
                        bldg_addrs = p_addresses[p_addresses.geometry.within(b_row.geometry)]
                        if len(bldg_addrs) > 0:
                            building_node["addressCount"] = len(bldg_addrs)
                            building_node["children"] = []
                            for _, a_row in bldg_addrs.iterrows():
                                building_node["children"].append({
                                    "id": safe_value(a_row.get("UTAddPtID")),
                                    "name": safe_value(a_row.get("FullAdd")) or "Unknown Address",
                                    "type": "address",
                                })
                    parcel_node["children"].append(building_node)

                # Add remaining addresses directly under parcel
                assigned_addr_ids = set()
                for b_idx, b_row in p_buildings.iterrows():
                    if b_row.geometry is not None and len(p_addresses) > 0:
                        bldg_addrs = p_addresses[p_addresses.geometry.within(b_row.geometry)]
                        for _, a_row in bldg_addrs.iterrows():
                            assigned_addr_ids.add(a_row.get("UTAddPtID"))
                unassigned_addrs = p_addresses[~p_addresses["UTAddPtID"].isin(assigned_addr_ids)]
                for _, a_row in unassigned_addrs.iterrows():
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
                "properties": {
                    "id": plat_oid,
                    "name": plat_name,
                    "landUse": safe_value(plat_row.get("landUse")),
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
                        "platId": plat_oid,
                        "landUse": safe_value(p_row.get("landUse")),
                    },
                    "geometry": p_geom
                })

                # Add buildings to tile
                p_buildings = buildings_s[buildings_s["_parcel_idx"] == p_idx]
                for _, b_row in p_buildings.iterrows():
                    b_geom = mapping(b_row.geometry)
                    b_geom = round_coords(b_geom)
                    bldg_cls = int(safe_value(b_row.get("BUILDINGCL")) or 0)
                    tile_building_features.append({
                        "type": "Feature",
                        "properties": {
                            "id": safe_value(b_row.get("GLOBALID")),
                            "name": safe_value(b_row.get("NAME")),
                            "address": safe_value(b_row.get("FULLADDRES")),
                            "class": bldg_cls,
                            "classLabel": BUILDING_CLASS_LABELS.get(bldg_cls, "Building"),
                            "height": safe_value(b_row.get("_height")),
                            "yearBuilt": safe_value(b_row.get("YEAR_BUILT")),
                            "parcelId": safe_value(p_row.get("PARCELID")),
                            "platId": plat_oid,
                        },
                        "geometry": b_geom
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
        unassigned_node["buildingCount"] = len(tile_building_features)
        unassigned_node["addressCount"] = len(tile_address_features)

        write_json({
            "plats": {"type": "FeatureCollection", "features": tile_plat_features},
            "parcels": {"type": "FeatureCollection", "features": tile_parcel_features},
            "buildings": {"type": "FeatureCollection", "features": tile_building_features},
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

    # ── Sort hierarchy tree ──
    print("\nSorting hierarchy tree...")
    sub_acres_lookup = {}
    for idx, row in subdivisions.iterrows():
        sid = row.get("ID")
        if pd.notna(sid):
            sub_acres_lookup[int(sid)] = float(row.get("ACRE") or 0.0)
            
    plat_acres_lookup = {}
    for idx, row in plats_s.iterrows():
        poid = row.get("OBJECTID")
        if pd.notna(poid):
            plat_acres_lookup[int(poid)] = float(row.get("Acres") or row.get("ACRE") or 0.0)
            
    parcel_acres_lookup = {}
    for idx, row in parcels_s.iterrows():
        pid = row.get("PARCELID")
        if pid:
            parcel_acres_lookup[str(pid)] = float(row.get("ACREAGE") or 0.0)

    def sort_hierarchy_node(node):
        children = node.get("children", [])
        if not children:
            return
            
        for child in children:
            sort_hierarchy_node(child)
            
        child_type = children[0].get("type")
        
        if child_type == "subdivision":
            # Sort subdivisions alphabetically, then by size (acres descending)
            children.sort(key=lambda x: (
                x.get("name", "").lower(), 
                -sub_acres_lookup.get(int(x.get("id")) if isinstance(x.get("id"), (int, float)) else 0, 0.0)
            ))
            
        elif child_type == "plat":
            # Sort plats alphabetically, then by size (acres descending)
            children.sort(key=lambda x: (
                x.get("name", "").lower(),
                -plat_acres_lookup.get(int(x.get("id")) if isinstance(x.get("id"), (int, float)) else 0, 0.0)
            ))
            
        elif child_type == "parcel":
            # Sort parcels alphabetically, then by size (acres descending)
            children.sort(key=lambda x: (
                x.get("name", "").lower(),
                -parcel_acres_lookup.get(str(x.get("id")), 0.0)
            ))

    sort_hierarchy_node(hierarchy_tree)

    write_json(hierarchy_tree, os.path.join(OUTPUT_DIR, "hierarchy.json"))


    print(f"\n=== Preprocessing complete! ===")
    print(f"  Subdivisions: {len(hierarchy_tree['children'])}")
    print(f"  Total parcels in hierarchy: {total_parcels}")
    print(f"  Total addresses in hierarchy: {total_addresses}")


if __name__ == "__main__":
    main()


