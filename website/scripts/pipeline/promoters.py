"""
Parcel promotion logic: Israel Canyon, name-matching, and unassigned parcel promotion.
"""

import re
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.ops import unary_union

from .utils import safe_value, clean_owner_name
from .config import (ISRAEL_CANYON_SUB_ID, ISRAEL_CANYON_PLAT_BASE,
                     NAME_MATCHED_PLAT_BASE, SINGLE_PROMOTED_SUB_BASE,
                     SINGLE_PROMOTED_PLAT_BASE, CLUSTER_PROMOTED_SUB_BASE,
                     CLUSTER_PROMOTED_PLAT_BASE)


def create_israel_canyon(parcels, subdivisions, plats):
    """Create the Israel Canyon custom subdivision from specific parcels.
    
    Removes Teguayo, identifies Israel Canyon parcels by ID and owner name,
    groups them by owner into plats, and appends to subdivisions/plats.
    
    Returns:
        (parcels, subdivisions, plats) — all modified in place and returned.
    """
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
        ic_geom = unary_union(ic_parcels.geometry.dropna().tolist())
        total_ic_acres = sum(safe_value(p.get("ACREAGE") or 0.0) for _, p in ic_parcels.iterrows())

        ic_sub_df = gpd.GeoDataFrame([{
            "ID": ISRAEL_CANYON_SUB_ID,
            "NAME": "Israel Canyon",
            "DENSITY": "N/A",
            "ACRE": round(total_ic_acres, 2),
            "STATUS": "Active",
            "TYPE": "Subdivision",
            "geometry": ic_geom
        }], crs=subdivisions.crs)
        subdivisions = pd.concat([subdivisions, ic_sub_df], ignore_index=True)

        new_plat_rows_ic = []
        parcels.loc[ic_mask, "_plat_oid"] = None

        ic_owners = ic_parcels["OWNER_NAME"].apply(clean_owner_name)
        ic_parcels_grouped = ic_parcels.groupby(ic_owners)

        for p_idx, (owner_name, group) in enumerate(ic_parcels_grouped):
            plat_oid = ISRAEL_CANYON_PLAT_BASE + p_idx
            group_geom = unary_union(group.geometry.dropna().tolist())
            group_acres = sum(safe_value(p.get("ACREAGE") or 0.0) for _, p in group.iterrows())

            new_plat_rows_ic.append({
                "OBJECTID": plat_oid,
                "Name": f"Plat for {owner_name}",
                "label": "A",
                "Acres": round(group_acres, 2),
                "SubID": ISRAEL_CANYON_SUB_ID,
                "_sub_id": ISRAEL_CANYON_SUB_ID,
                "landUse": "Mixed",
                "geometry": group_geom
            })
            parcels.loc[group.index, "_plat_oid"] = plat_oid

        ic_plat_df = gpd.GeoDataFrame(new_plat_rows_ic, crs=plats.crs)
        plats = pd.concat([plats, ic_plat_df], ignore_index=True)

        print(f"  Assigned {ic_mask.sum()} parcels to Israel Canyon across {len(new_plat_rows_ic)} plats")

    return parcels, subdivisions, plats
