"""
Subdivision classification logic: determines zoning categories.
"""

import pandas as pd

from .utils import safe_value


def check_is_public_subdivision(sub_id, plats, parcels, public_owners):
    """Check if all parcels in a subdivision are owned by public entities.
    
    Args:
        sub_id: Subdivision ID to check.
        plats: Plats GeoDataFrame (must have _sub_id column).
        parcels: Parcels GeoDataFrame (must have _plat_oid column).
        public_owners: Set of uppercase owner names considered public.
    """
    sub_plats = plats[plats["_sub_id"] == sub_id]
    if len(sub_plats) == 0:
        return False
    plat_ids = set(sub_plats["OBJECTID"].dropna().unique())
    sub_parcels = parcels[parcels["_plat_oid"].isin(plat_ids)]
    if len(sub_parcels) == 0:
        return False
    for _, p_row in sub_parcels.iterrows():
        owner = str(p_row.get("OWNER_NAME") or "").strip().upper()
        if not owner or owner not in public_owners:
            return False
    return True


def check_is_religious_subdivision(sub_name, sub_id, plats, parcels, rules):
    """Check if a subdivision is religious based on name and owner keywords.
    
    Args:
        sub_name: Subdivision name.
        sub_id: Subdivision ID.
        plats: Plats GeoDataFrame.
        parcels: Parcels GeoDataFrame.
        rules: Classification rules dict.
    """
    name_clean = str(sub_name).strip().lower()

    # Check subdivision name first
    religious_name_kw = rules.get("religious_name_keywords", [])
    if any(kw in name_clean for kw in religious_name_kw):
        return True

    # Check parcels owner
    sub_plats = plats[plats["_sub_id"] == sub_id]
    if len(sub_plats) == 0:
        return False
    plat_ids = set(sub_plats["OBJECTID"].dropna().unique())
    sub_parcels = parcels[parcels["_plat_oid"].isin(plat_ids)]
    if len(sub_parcels) == 0:
        return False

    religious_owners = [kw.upper() for kw in rules.get("religious_owner_keywords", [])]

    for _, p_row in sub_parcels.iterrows():
        owner = str(p_row.get("OWNER_NAME") or "").strip().upper()
        if not owner:
            return False
        if not any(kw in owner for kw in religious_owners):
            return False

    return True


def resolve_category(sub_name, sub_id, sub_type, plats, parcels, rules):
    """Determine the zoning category for a subdivision.
    
    Args:
        sub_name: Subdivision name.
        sub_id: Subdivision ID.
        sub_type: Subdivision TYPE field value.
        plats: Plats GeoDataFrame.
        parcels: Parcels GeoDataFrame.
        rules: Classification rules dict (must have precomputed _*_lower sets).
    
    Returns:
        Category string: "Religious", "Commercial", "Mixed Housing",
        "Residential Communities", "Public", or "Other".
    """
    name_clean = str(sub_name).strip().lower()

    # 00. Religious check
    if check_is_religious_subdivision(sub_name, sub_id, plats, parcels, rules):
        return "Religious"

    # 0. Commercial Subdivisions check
    if name_clean in rules["_commercial_sub_lower"]:
        return "Commercial"

    # 1. Mixed Housing list
    if name_clean in rules["_mixed_housing_lower"]:
        return "Mixed Housing"

    # 2. Residential Communities list
    if name_clean in rules["_residential_lower"]:
        return "Residential Communities"

    # 3. Public owner list
    if name_clean in rules.get("_public_sub_lower", set()) or sub_id == 4400000 or check_is_public_subdivision(sub_id, plats, parcels, rules["_public_owners_upper"]):
        return "Public"

    # 4. Commercial check
    type_str = str(sub_type).lower() if sub_type else ""
    if type_str == "commercial" or "commercial" in name_clean or "commerical" in name_clean:
        return "Commercial"

    commercial_kw = rules.get("commercial_keywords", [])
    if any(kw in name_clean for kw in commercial_kw):
        return "Commercial"

    return "Other"


def classify_all_subdivisions(subdivisions, plats, parcels, rules):
    """Compute and assign CATEGORY for all subdivisions.
    
    Modifies subdivisions in place — sets CATEGORY and TYPE columns.
    """
    print("\nComputing subdivision categories...")
    subdivisions["CATEGORY"] = "Other"
    for idx, row in subdivisions.iterrows():
        sub_id = int(row["ID"])
        sub_name = row["NAME"]
        sub_type = row["TYPE"]
        cat = resolve_category(sub_name, sub_id, sub_type, plats, parcels, rules)
        subdivisions.at[idx, "CATEGORY"] = cat
        if cat == "Religious":
            subdivisions.at[idx, "TYPE"] = "Religious"
