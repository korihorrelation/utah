import geopandas as gpd
import pandas as pd
import json

def run_eda():
    print("Loading data...")
    parcels = gpd.read_file('city_of_saratoga_springs_maps/buildings_and_parcels/parcels.zip')
    # we don't strictly need plats for this script, we just need parcels and hierarchy.json
    
    with open('website/public/data/hierarchy.json', 'r', encoding='utf-8') as f:
        hierarchy = json.load(f)
        
    # Build a lookup from parcel ID -> Subdivision Name
    parcel_to_sub_name = {}
    
    for sub in hierarchy.get('children', []):
        sub_name = sub.get('name', 'Unknown')
        for plat in sub.get('children', []):
            for p in plat.get('children', []):
                parcel_to_sub_name[p['id']] = sub_name
                
    # Now loop through the raw parcels and compare
    total_assigned = 0
    exact_match = 0
    contains_match = 0
    empty_sub_name = 0
    conflict = 0
    
    conflict_examples = []
    
    for idx, row in parcels.iterrows():
        pid = row.get('PARCELID')
        if not pid or pid not in parcel_to_sub_name:
            continue
            
        total_assigned += 1
        assigned_sub_name = parcel_to_sub_name[pid]
        
        raw_sub_name = row.get('SUB_NAME')
        
        if pd.isna(raw_sub_name) or not str(raw_sub_name).strip():
            empty_sub_name += 1
        else:
            raw_clean = str(raw_sub_name).strip().lower()
            assigned_clean = assigned_sub_name.strip().lower()
            
            if raw_clean == assigned_clean:
                exact_match += 1
            elif raw_clean in assigned_clean or assigned_clean in raw_clean:
                contains_match += 1
            else:
                conflict += 1
                if len(conflict_examples) < 10:
                    conflict_examples.append((pid, raw_sub_name, assigned_sub_name))
                    
    print("\n--- EDA: Parcel SUB_NAME vs Assigned Subdivision ---")
    print(f"Total Assigned Parcels Evaluated: {total_assigned}")
    print(f"  - No SUB_NAME in raw data: {empty_sub_name} ({(empty_sub_name/total_assigned)*100:.1f}%)")
    print(f"  - Exact Match: {exact_match} ({(exact_match/total_assigned)*100:.1f}%)")
    print(f"  - Partial/Contains Match: {contains_match} ({(contains_match/total_assigned)*100:.1f}%)")
    print(f"  - Conflict (Mismatched): {conflict} ({(conflict/total_assigned)*100:.1f}%)")
    
    print("\n--- Examples of Conflicts ---")
    for pid, raw, assigned in conflict_examples:
        print(f"Parcel {pid}: Raw SUB_NAME='{raw}'  ==>  Assigned to '{assigned}'")

if __name__ == "__main__":
    run_eda()
