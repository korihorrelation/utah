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
from pipeline.promoters import (create_israel_canyon, match_unassigned_by_name,
                                 promote_unassigned_parcels, breakout_ssd_subdivisions,
                                 create_roads_subdivision)
from pipeline.exporters import export_overlay_layers, export_hierarchy

# ──────────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WEBSITE_DIR = os.path.dirname(SCRIPT_DIR)
WORKSPACE_DIR = os.path.dirname(WEBSITE_DIR)
MAPS_DIR = os.path.join(WORKSPACE_DIR, "city_of_saratoga_springs_maps")
OUTPUT_DIR = os.path.join(WEBSITE_DIR, "public", "data")
LAND_USE_PATH = os.path.join(MAPS_DIR, "boundaries", "land_use.geojson")

from pipeline.utils import load_layer

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
    
    # ── Breakout SSD Subdivisions ──
    subdivisions, plats = breakout_ssd_subdivisions(subdivisions, plats)
    
    parcels = join_parcels_to_plats(parcels, plats)
    addresses = join_addresses_to_parcels(addresses, parcels)

    # ── Create Israel Canyon custom subdivision ──
    parcels, subdivisions, plats = create_israel_canyon(parcels, subdivisions, plats)

    # ── Promote unassigned parcels ──
    parcels, plats = match_unassigned_by_name(parcels, plats, subdivisions)
    parcels, subdivisions, plats = promote_unassigned_parcels(parcels, subdivisions, plats)

    # ── Create Roads subdivision for UDOT/State-owned parcels ──
    parcels, subdivisions, plats = create_roads_subdivision(parcels, subdivisions, plats, rules)

    # ── Build hierarchy: Building → Parcel + POI matching ──
    buildings = join_buildings_to_parcels(buildings, parcels)
    buildings = join_pois_to_buildings(buildings)

    # ── Compute subdivision categories ──
    classify_all_subdivisions(subdivisions, plats, parcels, rules)

    # ── Export overlay layers ──
    export_overlay_layers(city_boundary, subdivisions, roads, paths, addresses)

    # ── Export hierarchy ──
    export_hierarchy(subdivisions, plats, parcels, buildings, addresses)


if __name__ == "__main__":
    main()


