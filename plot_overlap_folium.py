import os
import geopandas as gpd
import folium
from shapely.geometry import mapping

WORK_DIR = os.path.abspath(os.path.dirname(__file__))
bf_zip = os.path.join(WORK_DIR, "city_of_saratoga_springs_maps", "buildings_and_parcels", "building_footprints.zip")
hu_zip = os.path.join(WORK_DIR, "city_of_saratoga_springs_maps", "buildings_and_parcels", "housing_unit_inventory.zip")

bf = gpd.read_file(f"zip://{bf_zip}!building_footprints.shp")
hu = gpd.read_file(f"zip://{hu_zip}!housing_unit_inventory.shp")

# Reproject to WGS84 for folium
bf = bf.to_crs(epsg=4326)
hu = hu.to_crs(epsg=4326)

# Base map centered on dataset bounds
bounds = bf.total_bounds if len(bf) else hu.total_bounds
if len(hu):
    bounds = [min(bounds[0], hu.total_bounds[0]), min(bounds[1], hu.total_bounds[1]), max(bounds[2], hu.total_bounds[2]), max(bounds[3], hu.total_bounds[3])]
center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

m = folium.Map(location=center, zoom_start=13, tiles='cartodbpositron')

# Simplify feature properties to avoid unsupported Timestamp serialization in GeoJSON
bf_simple = bf[['BLDG_ID', 'FULLADDRES', 'geometry']].copy()
bf_simple['BLDG_ID'] = bf_simple['BLDG_ID'].astype(str)
bf_simple['FULLADDRES'] = bf_simple['FULLADDRES'].astype(str)

hu_simple = hu[['UNIT_ID', 'TYPE', 'UNIT_COUNT', 'geometry']].copy()
hu_simple['UNIT_ID'] = hu_simple['UNIT_ID'].astype(str)
hu_simple['TYPE'] = hu_simple['TYPE'].astype(str)
hu_simple['UNIT_COUNT'] = hu_simple['UNIT_COUNT'].astype(str)

# Building footprints layer (gray fill, subtle)
folium.GeoJson(
    bf_simple.__geo_interface__,
    name='Building footprints',
    style_function=lambda feature: {
        'fillColor': '#999999',
        'color': '#666666',
        'weight': 0.5,
        'fillOpacity': 0.3,
    },
    tooltip=folium.GeoJsonTooltip(fields=['BLDG_ID', 'FULLADDRES'], aliases=['Building ID', 'Address'], localize=True)
).add_to(m)

# Housing inventory color mapping
type_colors = {
    'single_family': '#1f78b4',
    'multi_family': '#33a02c',
}

# Draw the housing inventory with type-based fill colors
folium.GeoJson(
    hu_simple.__geo_interface__,
    name='Housing unit inventory',
    style_function=lambda feature: {
        'fillColor': type_colors.get(feature['properties'].get('TYPE'), '#ff7f00'),
        'color': '#222222',
        'weight': 0.5,
        'fillOpacity': 0.45,
    },
    tooltip=folium.GeoJsonTooltip(fields=['UNIT_ID', 'TYPE', 'UNIT_COUNT'], aliases=['Unit ID', 'Type', 'Unit count'], localize=True)
).add_to(m)

# Add legend manually
legend_html = '''
<div style="position: fixed; bottom: 20px; left: 20px; width: 180px; height: 110px;
     background-color: white; border:2px solid grey; z-index:9999; font-size:14px; padding: 10px;">
     <b>Housing Unit Type</b><br>
     <i style="background:#1f78b4; width:12px; height:12px; display:inline-block;"></i> Single family<br>
     <i style="background:#33a02c; width:12px; height:12px; display:inline-block;"></i> Multi family<br>
     <i style="background:#999999; width:12px; height:12px; display:inline-block;"></i> Building footprints
</div>
'''

m.get_root().html.add_child(folium.Element(legend_html))

folium.LayerControl(collapsed=False).add_to(m)

out_path = os.path.join(WORK_DIR, 'city_of_saratoga_springs_maps', 'buildings_and_parcels', 'folium_overlap.html')
m.save(out_path)
print(f"Saved interactive map to: {out_path}")
