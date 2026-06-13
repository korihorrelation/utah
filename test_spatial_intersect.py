import pandas as pd
import geopandas as gpd
from shapely.ops import unary_union
from pipeline.utils import safe_value
from pipeline.config import SINGLE_PROMOTED_PLAT_BASE

def _is_parcel_unassigned(p_row, plat_sub_lookup):
    plat_oid = p_row.get("_plat_oid")
    if pd.isna(plat_oid):
        return True
    return int(plat_oid) not in plat_sub_lookup

def match_unassigned_by_intersection(parcels, plats, subdivisions):
    print("\nAssigning unassigned parcels by spatial intersection...")
    parcels_proj = parcels.to_crs(epsg=3566)
    subdivs_proj = subdivisions.to_crs(epsg=3566)
    
    plat_sub_lookup = plats.set_index("OBJECTID")["_sub_id"].to_dict()
    unassigned_mask = parcels.apply(lambda row: _is_parcel_unassigned(row, plat_sub_lookup), axis=1)
    unassigned_parcels_proj = parcels_proj[unassigned_mask].copy()
    
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
                
        # If it's mostly inside a subdivision
        if pct_not_in < 0.98 and best_sub_id is not None:
            if best_sub_id not in orphans_by_sub:
                orphans_by_sub[best_sub_id] = []
            orphans_by_sub[best_sub_id].append(p_idx)
            
    # Create Misc plats for these spatially matched parcels
    sub_id_to_name = subdivisions.set_index("ID")["NAME"].to_dict()
    plat_counter = len(plats) # use length to avoid collisions if called multiple times, actually let's use a safe offset
    
    new_plat_rows = []
    assigned_count = 0
    
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
        assigned_count += len(p_indices)
        
    if len(new_plat_rows) > 0:
        new_plat_df = gpd.GeoDataFrame(new_plat_rows, crs=plats.crs)
        plats = pd.concat([plats, new_plat_df], ignore_index=True)
        print(f"  Spatially assigned {assigned_count} parcels into {len(new_plat_rows)} Misc plats.")
    else:
        print("  No unassigned parcels were spatially inside existing subdivisions.")
        
    return parcels, plats

# Test the refactored function
