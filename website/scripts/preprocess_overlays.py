"""
Preprocess GIS overlays for the web app (Parks & POIs).

Output: website/public/data/
"""

import os
import json
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import mapping

# ─── Config ──────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WEBSITE_DIR = os.path.dirname(SCRIPT_DIR)
WORKSPACE_DIR = os.path.dirname(WEBSITE_DIR)
MAPS_DIR = os.path.join(WORKSPACE_DIR, "city_of_saratoga_springs_maps")
OUTPUT_DIR = os.path.join(WEBSITE_DIR, "public", "data")

SIMPLIFY_PARK = 0.00005     # ~5.5m — park boundaries
COORD_PRECISION = 6         # decimal places for coordinates

from pipeline.utils import load_layer, simplify_geometry, round_coords, safe_value, safe_int, write_json

# ─── POI Categorization ─────────────────────────────────────────────────────

def classify_open_source(row):
    cat = row.get("category")
    amenity = row.get("amenity")
    shop = row.get("shop")
    tourism = row.get("tourism")
    
    resolved_cat = "other"
    resolved_group = "other"
    
    # 1. Amenity check
    if pd.notna(amenity):
        if amenity in ["school", "college", "kindergarten", "university"]:
            resolved_cat = "school"
            resolved_group = "education"
        elif amenity in ["restaurant", "cafe", "fast_food", "food_court", "bar", "pub"]:
            resolved_cat = "food"
            resolved_group = "retail_food"
        elif amenity in ["place_of_worship"]:
            resolved_cat = "worship"
            resolved_group = "civic_community"
        elif amenity in ["bank", "atm"]:
            resolved_cat = "bank"
            resolved_group = "retail_food"
        elif amenity in ["dentist", "doctors", "pharmacy", "hospital", "clinic"]:
            resolved_cat = amenity
            resolved_group = "healthcare"
        elif amenity in ["fire_station", "police", "post_office", "library", "townhall", "community_centre"]:
            resolved_cat = amenity
            resolved_group = "civic_community"
        elif amenity in ["playground", "swimming_pool"]:
            resolved_cat = amenity
            resolved_group = "other"
            
    # 2. Shop check
    elif pd.notna(shop):
        resolved_cat = "shop"
        resolved_group = "retail_food"
        
    # 3. Tourism check
    elif pd.notna(tourism):
        resolved_cat = tourism
        resolved_group = "other"
        
    # 4. General category check
    elif pd.notna(cat):
        if cat in ["park", "playground", "picnic_site", "dog_park", "sports_centre", "golf_course"]:
            resolved_cat = cat
            resolved_group = "other"  # Parks are represented separately as polygons.
        elif cat in ["fast_food", "restaurant", "bank", "convenience", "pharmacy", "cafe", "beverages", "shop", "bakery", "hairdresser", "beauty_shop", "mobile_phone_shop", "car_wash", "laundry", "cinema"]:
            if cat in ["fast_food", "restaurant", "cafe", "beverages", "bakery", "convenience"]:
                resolved_cat = "food"
                resolved_group = "retail_food"
            elif cat in ["pharmacy"]:
                resolved_cat = "pharmacy"
                resolved_group = "healthcare"
            else:
                resolved_cat = "shop"
                resolved_group = "retail_food"
        elif cat in ["christian"]:
            resolved_cat = "worship"
            resolved_group = "civic_community"
        elif cat in ["school"]:
            resolved_cat = "school"
            resolved_group = "education"
        elif cat in ["hospital", "doctors", "veterinary"]:
            resolved_cat = "healthcare"
            resolved_group = "healthcare"
        elif cat in ["fire_station", "library", "community_centre", "post_office"]:
            resolved_cat = cat
            resolved_group = "civic_community"
            
    return resolved_cat, resolved_group

# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=== Preprocessing Overlays (Parks & POIs) ===\n")
    
    # 1. Process Parks
    parks_path = os.path.join(MAPS_DIR, "parks_and_recreation", "park_boundaries_maintained_by_city_only.geojson")
    if os.path.exists(parks_path):
        print("Processing Parks...")
        parks_gdf = load_layer(parks_path)
        parks_s = simplify_geometry(parks_gdf, SIMPLIFY_PARK)
        
        park_features = []
        for idx, row in parks_s.iterrows():
            # Standardize attributes
            props = {
                "id": safe_value(row.get("OBJECTID") or idx),
                "name": safe_value(row.get("COMMONNAME") or row.get("NAME") or "Unnamed Park"),
                "address": safe_value(row.get("ADDRESS")),
                "acres": safe_value(row.get("AREA_ACRES")),
                "status": safe_value(row.get("STATUS")),
                "amenities": {
                    "bathroom": True if str(row.get("BATHROOM")).lower() in ["yes", "y", "true", "1"] else False,
                    "playground": True if safe_int(row.get("PLAYGRNDTOT")) > 0 or str(row.get("PLAYGRNDSCHL")).lower() in ["yes", "y"] else False,
                    "pavilion": True if str(row.get("PAVILION")).lower() in ["yes", "y", "true", "1"] or str(row.get("HASPAVILION")).lower() in ["yes", "y"] else False,
                    "tables": True if str(row.get("HASTABLES")).lower() in ["yes", "y"] or safe_int(row.get("TABLES")) > 0 else False,
                    "bbq": True if str(row.get("HASBBQGRILLS")).lower() in ["yes", "y"] or str(row.get("BBQGRILLS")).lower() in ["yes", "y"] or str(row.get("HASBBQ")).lower() in ["yes", "y"] else False,
                    "basketball": True if safe_int(row.get("BBALLCOURT")) > 0 else False,
                    "tennis": True if safe_int(row.get("TENNISCOURT")) > 0 else False,
                    "vball": True if safe_int(row.get("VBALLCOURT")) > 0 else False,
                    "pickleball": True if str(row.get("HASPICKLE")).lower() in ["yes", "y", "true", "1"] else False,
                }
            }
            
            geom = mapping(row.geometry)
            geom = round_coords(geom)
            park_features.append({
                "type": "Feature",
                "properties": props,
                "geometry": geom
            })
            
        write_json({
            "type": "FeatureCollection",
            "features": park_features
        }, os.path.join(OUTPUT_DIR, "parks.json"))
        print(f"  Processed {len(park_features)} parks.")
    else:
        print(f"Parks file not found at {parks_path}")
        
    # 2. Process POIs (Unified Points of Interest)
    print("\nProcessing POIs...")
    poi_list = []
    
    # Track coordinates to deduplicate extremely close points of similar types
    existing_coords = [] # List of (lat, lon, group)
    
    def is_duplicate(lat, lon, group, thresh=0.0005):
        for ex_lat, ex_lon, ex_grp in existing_coords:
            if ex_grp == group and abs(ex_lat - lat) < thresh and abs(ex_lon - lon) < thresh:
                return True
        return False

    # A. Dedicated layers (High priority, detailed details)
    dedicated_configs = [
        {"file": os.path.join("facilities", "schools.zip"), "group": "education", "cat": "school", "name_col": "SchoolName", "addr_col": "Address"},
        {"file": os.path.join("facilities", "fire_stations.zip"), "group": "civic_community", "cat": "fire_station", "name_col": "NAME", "addr_col": "ADDRESS"},
        {"file": os.path.join("facilities", "public_libraries.zip"), "group": "civic_community", "cat": "library", "name_col": "LIBRARY", "addr_col": "ADDRESS"},
        {"file": os.path.join("facilities", "law_enforcement_locations.zip"), "group": "civic_community", "cat": "police", "name_col": "name", "addr_col": "address"}
    ]
    
    for conf in dedicated_configs:
        path = os.path.join(MAPS_DIR, conf["file"])
        if os.path.exists(path):
            try:
                gdf = load_layer(f"zip://{path}")
                added_count = 0
                for _, row in gdf.iterrows():
                    name = row.get(conf["name_col"])
                    addr = row.get(conf["addr_col"])
                    
                    if not name or pd.isna(name):
                        continue
                        
                    geom = row.geometry
                    lon, lat = geom.x, geom.y
                    
                    # Deduplicate
                    if is_duplicate(lat, lon, conf["group"]):
                        continue
                        
                    existing_coords.append((lat, lon, conf["group"]))
                    
                    props = {
                        "name": safe_value(name),
                        "category": conf["cat"],
                        "group": conf["group"],
                        "address": safe_value(addr) if addr else None
                    }
                    
                    # Extra metadata based on layer type
                    if conf["cat"] == "school":
                        props["details"] = f"Level: {safe_value(row.get('SchoolLeve'))}"
                    elif conf["cat"] == "library":
                        props["details"] = f"Hours: {safe_value(row.get('HOURS'))}"
                    elif conf["cat"] == "fire_station":
                        props["details"] = f"Tel: {safe_value(row.get('TELEPHONE'))}"
                    elif conf["cat"] == "police":
                        props["details"] = f"Tel: {safe_value(row.get('phone'))}"
                        
                    poi_list.append({
                        "type": "Feature",
                        "properties": props,
                        "geometry": {
                            "type": "Point",
                            "coordinates": [round(lon, COORD_PRECISION), round(lat, COORD_PRECISION)]
                        }
                    })
                    added_count += 1
                print(f"  Added {added_count} features from {conf['file']}.")
            except Exception as e:
                print(f"  Error reading {conf['file']}: {e}")
                
    # B. Open source places (Lower priority, fallback)
    osp_path = os.path.join(MAPS_DIR, "places_of_interest", "open_source_places.zip")
    if os.path.exists(osp_path):
        try:
            gdf = load_layer(f"zip://{osp_path}")
            added_count = 0
            for _, row in gdf.iterrows():
                name = row.get("name")
                if not name or pd.isna(name):
                    continue
                    
                resolved_cat, resolved_group = classify_open_source(row)
                if resolved_group == "other" and resolved_cat == "other":
                    # Skip boring places to keep payload lightweight
                    continue
                
                # We skip 'park' or 'playground' category since they are better represented as polygons or park markers
                if resolved_cat in ["park", "playground"]:
                    continue
                    
                geom = row.geometry
                lon, lat = geom.x, geom.y
                
                # Check duplication with higher priority dedicated layers or same-group spots
                if is_duplicate(lat, lon, resolved_group):
                    continue
                    
                existing_coords.append((lat, lon, resolved_group))
                
                addr_parts = []
                for field in ["ugrc_addr", "osm_addr"]:
                    val = row.get(field)
                    if pd.notna(val) and val:
                        addr_parts.append(str(val))
                        break
                addr = addr_parts[0] if addr_parts else None
                
                props = {
                    "name": safe_value(name),
                    "category": resolved_cat,
                    "group": resolved_group,
                    "address": safe_value(addr)
                }
                
                details_parts = []
                for d_field in ["phone", "website", "cuisine", "amenity"]:
                    val = row.get(d_field)
                    if pd.notna(val) and val:
                        details_parts.append(f"{d_field.capitalize()}: {val}")
                if details_parts:
                    props["details"] = " | ".join(details_parts)
                    
                poi_list.append({
                    "type": "Feature",
                    "properties": props,
                    "geometry": {
                        "type": "Point",
                        "coordinates": [round(lon, COORD_PRECISION), round(lat, COORD_PRECISION)]
                    }
                })
                added_count += 1
            print(f"  Added {added_count} features from open_source_places.zip.")
        except Exception as e:
            print(f"  Error reading open_source_places.zip: {e}")
            
    # Write POIs
    write_json({
        "type": "FeatureCollection",
        "features": poi_list
    }, os.path.join(OUTPUT_DIR, "pois.json"))
    print(f"  Total unified POI count: {len(poi_list)}")
    print("\nPreprocessing overlays complete!")

if __name__ == "__main__":
    main()
