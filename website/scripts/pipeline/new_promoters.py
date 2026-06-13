def promote_unassigned_parcels(parcels, subdivisions, plats):
    """Promote unassigned parcels to subdivision status.
    
    Three strategies executed in priority order:
    1. Spatial Intersection: Unassigned parcels physically inside an existing
       subdivision are attached to it as a 'Misc' plat.
    2. Owner Clustering: Remaining unassigned parcels touching other parcels
       with the same owner are clustered into a new 'Owner Area' subdivision.
    3. Single Promotion: Any still unassigned, isolated parcels are promoted
       into their own single-parcel subdivisions.
    """
    import pandas as pd
    import geopandas as gpd
    import networkx as nx
    from shapely.ops import unary_union
    from pipeline.utils import safe_value
    from pipeline.config import (CLUSTER_PROMOTED_SUB_BASE, CLUSTER_PROMOTED_PLAT_BASE,
                                 SINGLE_PROMOTED_SUB_BASE, SINGLE_PROMOTED_PLAT_BASE)
    
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
    single_promotions = 0
    for p_idx, p_row in unassigned_parcels_proj.iterrows():
        if p_idx in clustered_indices:
            continue
            
        orig_p_row = parcels.loc[p_idx]
        p_name = _get_parcel_display_name(orig_p_row)
        sub_type = _infer_sub_type(orig_p_row.get("landUse"))
        sub_id = int(SINGLE_PROMOTED_SUB_BASE + p_idx)
        plat_oid = int(SINGLE_PROMOTED_PLAT_BASE + p_idx)

        new_subdiv_rows.append({
            "ID": sub_id, "NAME": p_name, "DENSITY": "N/A",
            "ACRE": safe_value(orig_p_row.get("ACREAGE")),
            "STATUS": "Active", "TYPE": sub_type, "geometry": orig_p_row.geometry
        })
        new_plat_rows.append({
            "OBJECTID": plat_oid, "Name": f"Plat for {p_name}", "label": "A",
            "Acres": safe_value(orig_p_row.get("ACREAGE")),
            "SubID": sub_id, "_sub_id": sub_id,
            "landUse": orig_p_row.get("landUse"), "geometry": orig_p_row.geometry
        })
        parcels.at[p_idx, "_plat_oid"] = plat_oid
        plat_sub_lookup[plat_oid] = sub_id
        single_promotions += 1

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
