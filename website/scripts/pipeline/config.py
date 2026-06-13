"""
Pipeline configuration: paths, constants, and classification rules loader.
"""

import os
import yaml


# ── Directory paths ──────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # scripts/
WEBSITE_DIR = os.path.dirname(SCRIPT_DIR)
WORKSPACE_DIR = os.path.dirname(WEBSITE_DIR)
MAPS_DIR = os.path.join(WORKSPACE_DIR, "city_of_saratoga_springs_maps")
OUTPUT_DIR = os.path.join(WEBSITE_DIR, "public", "data")
LAND_USE_PATH = os.path.join(MAPS_DIR, "boundaries", "land_use.geojson")
RULES_PATH = os.path.join(SCRIPT_DIR, "classification_rules.yaml")


# ── Geometry simplification tolerances (in degrees, ~1° ≈ 111km) ────────────

SIMPLIFY_SUBDIV = 0.00008   # ~9m — subdivision outlines
SIMPLIFY_PLAT = 0.00005     # ~5.5m — plat boundaries
SIMPLIFY_PARCEL = 0.00003   # ~3.3m — parcel polygons
SIMPLIFY_BUILDING = 0.00002 # ~2.2m — building footprints
SIMPLIFY_ROAD = 0.00005     # ~5.5m — road lines
SIMPLIFY_PATH = 0.00008     # ~9m — trail lines
COORD_PRECISION = 6         # decimal places for coordinates


# ── Building class labels and estimated heights (meters) ─────────────────────

BUILDING_CLASS_LABELS = {
    1: 'Residential', 2: 'Commercial', 3: 'Industrial', 4: 'Government',
    6: 'Agricultural', 7: 'Religious', 8: 'Education', 11: 'Utility', 12: 'Other',
}
BUILDING_CLASS_HEIGHTS = {
    1: 8.0, 2: 12.0, 3: 10.0, 4: 14.0,
    6: 6.0, 7: 12.0, 8: 12.0, 11: 8.0, 12: 6.0,
}


# ── Virtual ID ranges (documented to prevent collisions) ─────────────────────

ROADS_SUB_ID = 4400000
ROADS_PLAT_BASE = 4400100
ISRAEL_CANYON_SUB_ID = 4500000
ISRAEL_CANYON_PLAT_BASE = 4600000
SINGLE_PROMOTED_SUB_BASE = 5000000
CLUSTER_PROMOTED_SUB_BASE = 5500000
SINGLE_PROMOTED_PLAT_BASE = 6000000
CLUSTER_PROMOTED_PLAT_BASE = 6500000
NAME_MATCHED_PLAT_BASE = 7000000


# ── Classification rules loader ──────────────────────────────────────────────

def load_classification_rules(path=None):
    """Load classification rules from YAML file.
    
    Returns a dict with keys: residential_communities, mixed_housing,
    commercial_subdivisions, public_owners, religious_name_keywords,
    religious_owner_keywords, commercial_keywords, out_of_bounds_cities,
    out_of_bounds_tax_cities, out_of_bounds_site_cities.
    """
    path = path or RULES_PATH
    with open(path, "r", encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    
    # Convert lists to sets for O(1) lookup where appropriate
    rules["_residential_lower"] = {n.lower() for n in rules.get("residential_communities", [])}
    rules["_mixed_housing_lower"] = {n.lower() for n in rules.get("mixed_housing", [])}
    rules["_commercial_sub_lower"] = {n.lower() for n in rules.get("commercial_subdivisions", [])}
    rules["_public_sub_lower"] = {n.lower() for n in rules.get("public_subdivisions", [])}
    rules["_public_owners_upper"] = {n.upper() for n in rules.get("public_owners", [])}
    
    return rules
