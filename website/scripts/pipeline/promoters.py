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
                     CLUSTER_PROMOTED_PLAT_BASE,
                     ROADS_SUB_ID, ROADS_PLAT_BASE)


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


def _is_parcel_unassigned(p_row, plat_sub_lookup):
    """Check if a parcel is unassigned (no plat or plat has no subdivision)."""
    plat_oid = p_row.get("_plat_oid")
    if pd.isna(plat_oid):
        return True
    sub_id = plat_sub_lookup.get(int(plat_oid))
    return pd.isna(sub_id)


def _clean_sub_name(sub_name):
    """Clean a SUB_NAME value for fuzzy matching against subdivision names."""
    s = str(sub_name).strip().lower()
    s = re.sub(r'[\s,]+(plat|phase|ph|road church)[\s\w]*$', '', s)
    s = re.sub(r'[\s,]+plat[\s\w]*$', '', s)
    s = re.sub(r'[\s,]+phase[\s\w]*$', '', s)
    return s.strip()


def match_unassigned_by_name(parcels, plats, subdivisions):
    """Match unassigned parcels to existing subdivisions by SUB_NAME field.
    
    Returns:
        (parcels, plats) — both modified in place and returned.
    """
    plat_sub_lookup = plats.set_index("OBJECTID")["_sub_id"].to_dict()
    unassigned_mask = parcels.apply(
        lambda row: _is_parcel_unassigned(row, plat_sub_lookup), axis=1
    )

    print("Matching unassigned parcels to existing subdivisions by SUB_NAME...")
    sub_name_lookup = {
        str(row["NAME"]).strip().lower(): int(row["ID"])
        for _, row in subdivisions.iterrows()
    }

    name_matched_count = 0
    new_plat_rows = []

    for p_idx, p_row in parcels[unassigned_mask].iterrows():
        sub_name_val = p_row.get("SUB_NAME")
        if pd.isna(sub_name_val) or not str(sub_name_val).strip():
            continue

        clean_name = _clean_sub_name(sub_name_val)
        if clean_name in sub_name_lookup:
            matched_sub_id = sub_name_lookup[clean_name]

            sub_plats = plats[plats["_sub_id"] == matched_sub_id]
            best_plat_oid = None

            sub_name_val_lower = str(sub_name_val).lower()
            for _, plat_row in sub_plats.iterrows():
                plat_name = str(plat_row.get("Name") or "").lower()
                plat_label = str(plat_row.get("Plat") or "").lower()
                if (plat_name in sub_name_val_lower
                        or (plat_label and f"plat {plat_label}" in sub_name_val_lower)
                        or (plat_label and f"phase {plat_label}" in sub_name_val_lower)):
                    best_plat_oid = int(plat_row["OBJECTID"])
                    break

            if best_plat_oid is None:
                if len(sub_plats) > 0:
                    best_plat_oid = int(sub_plats.iloc[0]["OBJECTID"])
                else:
                    best_plat_oid = NAME_MATCHED_PLAT_BASE + p_idx
                    new_plat_rows.append({
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
            if best_plat_oid >= NAME_MATCHED_PLAT_BASE:
                plat_sub_lookup[best_plat_oid] = matched_sub_id
            name_matched_count += 1

    if len(new_plat_rows) > 0:
        new_plat_df = gpd.GeoDataFrame(new_plat_rows, crs=plats.crs)
        plats = pd.concat([plats, new_plat_df], ignore_index=True)
        print(f"  Created {len(new_plat_rows)} virtual plats for name-matched unassigned parcels.")

    # Re-evaluate unassigned count
    unassigned_mask = parcels.apply(
        lambda row: _is_parcel_unassigned(row, plat_sub_lookup), axis=1
    )
    remaining = unassigned_mask.sum()
    print(f"  Name-matched and assigned {name_matched_count} parcels to existing subdivisions. Remaining unassigned: {remaining}")

    return parcels, plats


def _infer_sub_type(land_use_val):
    """Infer subdivision TYPE from a land use description string."""
    land_use_lower = str(land_use_val or "").lower()
    if any(x in land_use_lower for x in ["res", "dwelling", "apartment", "condo", "townhouse", "housing"]):
        return "Subdivision"
    elif any(x in land_use_lower for x in ["comm", "retail", "office", "shop", "business", "industrial"]):
        return "Commercial"
    return "CommunityPlan"


def _get_parcel_display_name(orig_p_row):
    """Get a display name for a parcel from SUB_NAME, address, or parcel ID."""
    import pandas as _pd
    sub_name_val = orig_p_row.get("SUB_NAME")
    if _pd.notna(sub_name_val) and str(sub_name_val).strip():
        return str(sub_name_val).strip().title()
    site_addr = orig_p_row.get("SITE_FULL_")
    parcel_id = orig_p_row.get("PARCELID")
    return site_addr or f"Parcel {parcel_id}"


def promote_unassigned_parcels(parcels, subdivisions, plats, rules=None):
    """Promote unassigned parcels to subdivision status.
    
    Three strategies executed in priority order:
    1. Spatial Intersection: Unassigned parcels physically inside an existing
       subdivision are attached to it as a 'Misc' plat.
    2. Owner Clustering: Remaining unassigned parcels touching other parcels
       with the same owner are clustered into a new 'Owner Area' subdivision.
    3. Single Promotion: Any still unassigned, isolated parcels are promoted
       into their own single-parcel subdivisions.
    """
    import networkx as nx

    print("\nPromoting unassigned parcels...")
    parcels_proj = parcels.to_crs(epsg=3566)
    subdivs_proj = subdivisions.to_crs(epsg=3566)

    plat_sub_lookup = plats.set_index("OBJECTID")["_sub_id"].to_dict()
    
    def get_unassigned_mask():
        return parcels.apply(lambda row: _is_parcel_unassigned(row, plat_sub_lookup), axis=1)
        
    unassigned_mask = get_unassigned_mask()
    unassigned_parcels_proj = parcels_proj[unassigned_mask].copy()

    new_subdiv_rows = []
    new_plat_rows = []
    
    # ── Phase 1: Spatial Intersection ──
    subdiv_sindex = subdivs_proj.sindex
    orphans_by_sub = {}
    
    for p_idx, p_row in unassigned_parcels_proj.iterrows():
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

            intersect_geom = geom.intersection(unary_union(intersecting.geometry.tolist()))
            if geom.area > 0:
                pct_not_in = (geom.area - intersect_geom.area) / geom.area

        if pct_not_in < 0.98 and best_sub_id is not None:
            if best_sub_id not in orphans_by_sub:
                orphans_by_sub[best_sub_id] = []
            orphans_by_sub[best_sub_id].append(p_idx)

    # Attach spatially matched parcels
    sub_id_to_name = subdivisions.set_index("ID")["NAME"].to_dict()
    plat_counter = 0
    spatial_assigned_count = 0
    for sub_id, p_indices in orphans_by_sub.items():
        sub_name = sub_id_to_name.get(sub_id, f"Subdivision {sub_id}")
        plat_oid = int(SINGLE_PROMOTED_PLAT_BASE + 50000 + plat_counter)
        plat_counter += 1
        
        group_parcels = parcels.loc[p_indices]
        group_geom = unary_union(group_parcels.geometry.dropna().tolist())
        group_acres = sum(safe_value(p.get("ACREAGE") or 0.0) for _, p in group_parcels.iterrows())
        
        new_plat_rows.append({
            "OBJECTID": plat_oid, "Name": f"{sub_name} Parcels Misc", "label": "Misc",
            "Acres": round(group_acres, 2),
            "SubID": sub_id, "_sub_id": sub_id,
            "landUse": "Mixed", "geometry": group_geom
        })
        parcels.loc[p_indices, "_plat_oid"] = plat_oid
        plat_sub_lookup[plat_oid] = sub_id
        spatial_assigned_count += len(p_indices)

    # ── Refresh unassigned mask ──
    unassigned_mask = get_unassigned_mask()
    unassigned_parcels_proj = parcels_proj[unassigned_mask].copy()

    # ── Phase 2: Owner Clustering ──
    unassigned_parcels_proj["owner_clean"] = unassigned_parcels_proj["OWNER_NAME"].fillna("").str.strip().str.upper()
    valid_owner_mask = unassigned_parcels_proj["owner_clean"] != ""
    unassigned_with_owner = unassigned_parcels_proj[valid_owner_mask]

    clusters = []
    clustered_indices = set()

    for owner, group in unassigned_with_owner.groupby("owner_clean"):
        if len(group) < 2:
            continue

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
                if geom.intersects(other_geom.buffer(0.1)):
                    G.add_edge(idx, other_idx)

        for component in nx.connected_components(G):
            if len(component) >= 2:
                clusters.append((owner, list(component)))
                clustered_indices.update(component)

    cluster_promotions = 0
    for c_idx, (owner, comp_indices) in enumerate(clusters):
        owner_display = clean_owner_name(owner)
        sub_name = f"{owner_display} Area"
        sub_id = int(CLUSTER_PROMOTED_SUB_BASE + c_idx)

        first_row = parcels.loc[comp_indices[0]]
        sub_type = _infer_sub_type(first_row.get("landUse"))

        cluster_geoms = parcels.loc[comp_indices, "geometry"]
        subdiv_geom = unary_union(cluster_geoms.tolist())
        total_acres = sum(safe_value(parcels.loc[idx].get("ACREAGE") or 0.0) for idx in comp_indices)

        new_subdiv_rows.append({
            "ID": sub_id, "NAME": sub_name, "DENSITY": "N/A",
            "ACRE": round(total_acres, 2), "STATUS": "Active",
            "TYPE": sub_type, "geometry": subdiv_geom
        })

        for p_idx in comp_indices:
            orig_p_row = parcels.loc[p_idx]
            p_name = orig_p_row.get("SITE_FULL_") or f"Parcel {orig_p_row.get('PARCELID')}"
            plat_oid = int(CLUSTER_PROMOTED_PLAT_BASE + p_idx)

            new_plat_rows.append({
                "OBJECTID": plat_oid, "Name": f"Plat for {p_name}", "label": "A",
                "Acres": safe_value(orig_p_row.get("ACREAGE")),
                "SubID": sub_id, "_sub_id": sub_id,
                "landUse": orig_p_row.get("landUse"), "geometry": orig_p_row.geometry
            })
            parcels.at[p_idx, "_plat_oid"] = plat_oid
            plat_sub_lookup[plat_oid] = sub_id
            cluster_promotions += 1

    # ── Phase 3: Single Promotions ──
    misc_public_indices = []
    misc_other_indices = []
    
    public_owners = set()
    if rules:
        public_owners = rules.get("_public_owners_upper", set())

    for p_idx, p_row in unassigned_parcels_proj.iterrows():
        if p_idx in clustered_indices:
            continue
            
        owner = str(parcels.loc[p_idx].get("OWNER_NAME") or "").strip().upper()
        if owner in public_owners:
            misc_public_indices.append(p_idx)
        else:
            misc_other_indices.append(p_idx)

    single_promotions = 0
    
    def create_misc_group(indices, name, base_sub_id, base_plat_id):
        if not indices:
            return 0
            
        group_parcels = parcels.loc[indices]
        group_geom = unary_union(group_parcels.geometry.dropna().tolist())
        group_acres = sum(safe_value(p.get("ACREAGE") or 0.0) for _, p in group_parcels.iterrows())

        new_subdiv_rows.append({
            "ID": base_sub_id, "NAME": name, "DENSITY": "N/A",
            "ACRE": round(group_acres, 2),
            "STATUS": "Active", "TYPE": "Subdivision", "geometry": group_geom
        })
        new_plat_rows.append({
            "OBJECTID": base_plat_id, "Name": name, "label": "Misc",
            "Acres": round(group_acres, 2),
            "SubID": base_sub_id, "_sub_id": base_sub_id,
            "landUse": "Mixed", "geometry": group_geom
        })
        parcels.loc[indices, "_plat_oid"] = base_plat_id
        plat_sub_lookup[base_plat_id] = base_sub_id
        return len(indices)

    single_promotions += create_misc_group(misc_public_indices, "Misc Parcels", int(SINGLE_PROMOTED_SUB_BASE), int(SINGLE_PROMOTED_PLAT_BASE))
    single_promotions += create_misc_group(misc_other_indices, "Misc Parcels", int(SINGLE_PROMOTED_SUB_BASE) + 1, int(SINGLE_PROMOTED_PLAT_BASE) + 1)

    print(f"  Spatially assigned {spatial_assigned_count} parcels to existing subdivisions.")
    print(f"  Promoted {cluster_promotions} clustered parcels and {single_promotions} single parcels.")

    if len(new_subdiv_rows) > 0:
        new_subdiv_df = gpd.GeoDataFrame(new_subdiv_rows, crs=subdivisions.crs)
        subdivisions = pd.concat([subdivisions, new_subdiv_df], ignore_index=True)
        print(f"  Appended {len(new_subdiv_rows)} subdivisions.")

    if len(new_plat_rows) > 0:
        new_plat_df = gpd.GeoDataFrame(new_plat_rows, crs=plats.crs)
        plats = pd.concat([plats, new_plat_df], ignore_index=True)
        print(f"  Appended {len(new_plat_rows)} plats.")

    return parcels, subdivisions, plats


def breakout_ssd_subdivisions(subdivisions, plats):
    """Break out the Saratoga Springs Development mega-subdivision into constituent neighborhoods."""
    ssd_plats_mask = (plats["_sub_id"] == 910)
    ssd_plats = plats[ssd_plats_mask].copy()
    
    if len(ssd_plats) == 0:
        return subdivisions, plats
        
    def get_ssd_group(row):
        sub = str(row.get('Subdivision', ''))
        name = str(row.get('Name', ''))
        if 'Ironwood' in sub or 'Ironwood' in name: return 'Ironwood'
        if 'Wiltshire' in sub or 'Wiltshire' in name: return 'Wiltshire'
        if 'Lakeside' in name: return 'Lakeside'
        if 'Talons Cove' in name: return 'Talons Cove'
        if 'Eagle Park' in name: return 'Eagle Park'
        if 'Fairway' in name: return 'Fairway'
        return 'Saratoga Springs Development'
        
    groups = ssd_plats.apply(get_ssd_group, axis=1)
    
    new_subdiv_rows = []
    base_id = 91000
    
    for g_idx, (g_name, g_plats) in enumerate(ssd_plats.groupby(groups)):
        if g_name == 'Saratoga Springs Development':
            continue
            
        g_geom = unary_union(g_plats.geometry.dropna().tolist())
        g_acres = sum(safe_value(p.get("Acres") or p.get("ACRE") or 0.0) for _, p in g_plats.iterrows())
        g_id = base_id + g_idx + 1
        
        new_subdiv_rows.append({
            "ID": g_id,
            "NAME": g_name,
            "DENSITY": "N/A",
            "ACRE": round(g_acres, 2),
            "STATUS": "Active",
            "TYPE": "Subdivision",
            "CATEGORY": "Other", 
            "geometry": g_geom
        })
        
        plats.loc[g_plats.index, "_sub_id"] = g_id
        
    if new_subdiv_rows:
        new_subdiv_df = gpd.GeoDataFrame(new_subdiv_rows, crs=subdivisions.crs)
        subdivisions = pd.concat([subdivisions, new_subdiv_df], ignore_index=True)
        print(f"  Created {len(new_subdiv_rows)} new SSD neighborhoods.")
        
    generic_mask = (plats["_sub_id"] == 910)
    generic_plats = plats[generic_mask]
    if len(generic_plats) > 0:
        new_ssd_geom = unary_union(generic_plats.geometry.dropna().tolist())
        ssd_sub_mask = subdivisions["ID"] == 910
        if ssd_sub_mask.any():
            subdivisions.loc[ssd_sub_mask, "geometry"] = gpd.GeoSeries([new_ssd_geom], crs=subdivisions.crs).values
            
    return subdivisions, plats


def create_roads_subdivision(parcels, subdivisions, plats, rules):
    """Pull UDOT/State-owned road parcels into a dedicated 'Roads' subdivision.
    
    Parcels owned by transportation agencies are removed from their current
    plat assignments and grouped by owner into new plats under a single
    'Roads' subdivision with Public zoning. Any promoted subdivisions that
    become empty as a result are also cleaned up.
    
    Returns:
        (parcels, subdivisions, plats) — all modified.
    """
    print("\nCreating Roads subdivision for UDOT/State-owned parcels...")
    
    road_owners_upper = {o.upper() for o in rules.get("road_owners", [
        "UTAH DEPARTMENT OF TRANSPORTATION",
        "UDOT",
        "DEPARTMENT OF TRANSPORTATION",
        "STATE ROAD COMMISSION OF UTAH",
    ])}
    
    owner_col = parcels["OWNER_NAME"].fillna("").str.strip().str.upper()
    plat_sub_lookup = plats.set_index("OBJECTID")["_sub_id"].to_dict()
    
    def get_unassigned_mask():
        return parcels.apply(lambda row: _is_parcel_unassigned(row, plat_sub_lookup), axis=1)
        
    road_mask = owner_col.isin(road_owners_upper) & get_unassigned_mask()
    
    if not road_mask.any():
        print("  No road parcels found.")
        return parcels, subdivisions, plats
    
    road_parcels = parcels[road_mask]
    print(f"  Found {len(road_parcels)} unassigned UDOT/State road parcels.")
    
    # Create the Roads subdivision
    roads_geom = unary_union(road_parcels.geometry.dropna().tolist())
    total_acres = sum(safe_value(p.get("ACREAGE") or 0.0) for _, p in road_parcels.iterrows())
    
    roads_sub_df = gpd.GeoDataFrame([{
        "ID": ROADS_SUB_ID,
        "NAME": "Roads",
        "DENSITY": "N/A",
        "ACRE": round(total_acres, 2),
        "STATUS": "Active",
        "TYPE": "CommunityPlan",
        "CATEGORY": "Public",
        "geometry": roads_geom
    }], crs=subdivisions.crs)
    subdivisions = pd.concat([subdivisions, roads_sub_df], ignore_index=True)
    
    # Group parcels by cleaned owner name into plats
    owner_groups = road_parcels.groupby(owner_col[road_mask])
    new_plat_rows = []
    
    for p_idx, (owner_name, group) in enumerate(owner_groups):
        plat_oid = ROADS_PLAT_BASE + p_idx
        group_geom = unary_union(group.geometry.dropna().tolist())
        group_acres = sum(safe_value(p.get("ACREAGE") or 0.0) for _, p in group.iterrows())
        
        # Clean up the display name
        display_name = owner_name.title()
        
        new_plat_rows.append({
            "OBJECTID": plat_oid,
            "Name": display_name,
            "label": "",
            "Acres": round(group_acres, 2),
            "SubID": ROADS_SUB_ID,
            "_sub_id": ROADS_SUB_ID,
            "landUse": "Transportation",
            "geometry": group_geom
        })
        parcels.loc[group.index, "_plat_oid"] = plat_oid
    
    if new_plat_rows:
        new_plat_df = gpd.GeoDataFrame(new_plat_rows, crs=plats.crs)
        plats = pd.concat([plats, new_plat_df], ignore_index=True)
        print(f"  Created {len(new_plat_rows)} owner-grouped plats under Roads subdivision.")
    
    return parcels, subdivisions, plats

