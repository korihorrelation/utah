import os
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

WORK_DIR = os.path.abspath(os.path.dirname(__file__))
bf_zip = os.path.join(WORK_DIR, "city_of_saratoga_springs_maps", "buildings_and_parcels", "building_footprints.zip")
hu_zip = os.path.join(WORK_DIR, "city_of_saratoga_springs_maps", "buildings_and_parcels", "housing_unit_inventory.zip")

bf = gpd.read_file(f"zip://{bf_zip}!building_footprints.shp")
hu = gpd.read_file(f"zip://{hu_zip}!housing_unit_inventory.shp")

print(f"Loaded {len(bf)} building footprints and {len(hu)} housing unit polygons.")

# Compute overlapping geometry for display
ov = gpd.overlay(bf[['geometry']], hu[['geometry']], how='intersection')
print(f"Computed {len(ov)} overlap geometries.")

fig, ax = plt.subplots(figsize=(14, 12))
bf.plot(ax=ax, color='lightgray', edgecolor='none', alpha=0.45)
hu.plot(ax=ax, color='steelblue', edgecolor='none', alpha=0.3)
ov.plot(ax=ax, color='orangered', edgecolor='darkred', alpha=0.65)

patches = [
    mpatches.Patch(color='lightgray', alpha=0.45, label='Building footprints'),
    mpatches.Patch(color='steelblue', alpha=0.3, label='Housing inventory'),
    mpatches.Patch(color='orangered', alpha=0.65, label='Overlap')
]
ax.legend(handles=patches, loc='lower left', framealpha=0.9)
ax.set_title('Saratoga Springs: Building Footprints vs Housing Unit Inventory Overlap', fontsize=16)
ax.axis('off')
ax.set_aspect('equal')

out_path = os.path.join(WORK_DIR, 'city_of_saratoga_springs_maps', 'buildings_and_parcels', 'overlap_map.png')
fig.savefig(out_path, dpi=150, bbox_inches='tight')
print(f"Saved map to: {out_path}")
