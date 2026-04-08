"""
Data Transformation Script for Explore Utah
============================================
This script documents and performs all transformations from raw source data
(in ../data/) to the optimized GeoJSON files served by the app (in public/data/).

Source data is NOT committed to the repo — only the filtered/optimized outputs are.
"""

import json
import os

RAW = r'c:\Users\ajave\OneDrive\Documents\GitHub\utah\data'
OUT = r'c:\Users\ajave\OneDrive\Documents\GitHub\utah\explore-utah\public\data'

def simplify_coords(coords, precision=5):
    """Round coordinate precision to reduce file size."""
    if isinstance(coords[0], (int, float)):
        return [round(c, precision) for c in coords]
    return [simplify_coords(c, precision) for c in coords]

def simplify_geojson(data, precision=5):
    """Reduce coordinate precision in all features."""
    for feat in data['features']:
        feat['geometry']['coordinates'] = simplify_coords(
            feat['geometry']['coordinates'], precision
        )
    return data

def transform_all():
    results = []

    # 1. Federal Lands -- filter to owner='Federal' only, simplify coords
    print("1. Federal Lands (Land_Ownership.geojson -> Federal only)")
    src = os.path.join(RAW, 'Parks and Monuments', 'Land_Ownership.geojson')
    dst = os.path.join(OUT, 'federal_lands.geojson')
    d = json.load(open(src, 'r', encoding='utf-8'))
    print(f"   Source: {len(d['features'])} features (all owners)")
    d['features'] = [f for f in d['features'] if f['properties'].get('owner') == 'Federal']
    print(f"   After filter: {len(d['features'])} federal features")
    d = simplify_geojson(d, precision=4)
    json.dump(d, open(dst, 'w'), separators=(',', ':'))
    sz = os.path.getsize(dst) / 1024 / 1024
    results.append(f"federal_lands.geojson: {sz:.1f} MB ({len(d['features'])} features, owner=Federal, precision=4)")
    print(f"   Output: {sz:.1f} MB")

    # 2. Population Density — strip geometry precision + compute density
    print("2. Population Density (CensusBlockGroups2020)")
    src = os.path.join(RAW, 'Demographic', 'CensusBlockGroups2020_-7810440248936075411.geojson')
    dst = os.path.join(OUT, 'population_density.geojson')
    d = json.load(open(src, 'r', encoding='utf-8'))
    simplified = []
    for feat in d['features']:
        p = feat['properties']
        pop = p.get('POP100', 0) or 0
        land = p.get('ALAND20', 0) or 0
        density = round(pop / (land / 1_000_000), 1) if land > 0 else 0
        simplified.append({
            'type': 'Feature',
            'geometry': feat['geometry'],
            'properties': {
                'POP100': pop,
                'DENSITY': density,
                'COUNTY': p.get('COUNTYFP20', ''),
                'GEOID': p.get('GEOID20', ''),
                'NAME': p.get('NAMELSAD20', ''),
            }
        })
    d['features'] = simplified
    d = simplify_geojson(d, precision=4)
    json.dump(d, open(dst, 'w'), separators=(',', ':'))
    sz = os.path.getsize(dst) / 1024 / 1024
    results.append(f"population_density.geojson: {sz:.1f} MB ({len(simplified)} features, density=pop/km², precision=4)")
    print(f"   Output: {sz:.1f} MB")

    # 3. Highways — filter roads to CARTOCODE 1-4, strip fields
    print("3. Highways (UtahRoads -> filtered)")
    src = os.path.join(RAW, 'Transportation', 'UtahRoads_3660517298827247026.geojson')
    dst = os.path.join(OUT, 'highways.geojson')
    print("   Loading 886MB roads file...")
    d = json.load(open(src, 'r', encoding='utf-8'))
    highways = []
    for feat in d['features']:
        cc = str(feat['properties'].get('CARTOCODE', ''))
        if cc in ('1', '2', '3', '4'):
            props = feat['properties']
            highways.append({
                'type': 'Feature',
                'geometry': feat['geometry'],
                'properties': {
                    'name': props.get('FULLNAME') or props.get('DOT_HWYNAM') or '',
                    'CARTOCODE': cc,
                    'DOT_HWYNAM': props.get('DOT_HWYNAM', ''),
                    'DOT_FCLASS': props.get('DOT_FCLASS', ''),
                }
            })
    out = {'type': 'FeatureCollection', 'features': highways}
    out = simplify_geojson(out, precision=5)
    json.dump(out, open(dst, 'w'), separators=(',', ':'))
    sz = os.path.getsize(dst) / 1024 / 1024
    results.append(f"highways.geojson: {sz:.1f} MB ({len(highways)} features from {len(d['features'])} roads, CARTOCODE 1-4 only)")
    print(f"   Output: {sz:.1f} MB ({len(highways)} highways from {len(d['features'])} total roads)")

    # 4. Bus Routes — filter non-TRAX/FrontRunner from UTA routes
    print("4. Bus Routes")
    src = os.path.join(RAW, 'Transportation', 'UTA_Routes_and_Most_Recent_Ridership.geojson')
    dst = os.path.join(OUT, 'bus_routes.geojson')
    d = json.load(open(src, 'r', encoding='utf-8'))
    bus = [f for f in d['features'] if f['properties'].get('routetype') not in ('TRAX', 'FrontRunner')]
    d['features'] = bus
    json.dump(d, open(dst, 'w'), separators=(',', ':'))
    sz = os.path.getsize(dst) / 1024 / 1024
    results.append(f"bus_routes.geojson: {sz:.1f} MB ({len(bus)} routes, excludes TRAX/FrontRunner)")
    print(f"   Output: {sz:.1f} MB")

    # 5. Bus Stops — filter by mode
    print("5. Bus Stops")
    src = os.path.join(RAW, 'Transportation', 'UTA_Stops_and_Most_Recent_Ridership.geojson')
    dst = os.path.join(OUT, 'bus_stops.geojson')
    d = json.load(open(src, 'r', encoding='utf-8'))
    bus = [f for f in d['features'] if f['properties'].get('mode', '').startswith(('Bus', 'Flex', 'BRT', 'Micro'))]
    d['features'] = bus
    json.dump(d, open(dst, 'w'), separators=(',', ':'))
    sz = os.path.getsize(dst) / 1024 / 1024
    results.append(f"bus_stops.geojson: {sz:.1f} MB ({len(bus)} stops, bus/flex/BRT modes only)")
    print(f"   Output: {sz:.1f} MB")

    # 6-11. Direct copies (already small enough)
    copies = [
        ('Transportation/UTA_TRAX_Light_Rail_Routes.geojson', 'trax_routes.geojson'),
        ('Transportation/UTA_TRAX_Light_Rail_Stations.geojson', 'trax_stations.geojson'),
        ('Transportation/UTA_FrontRunner_Commuter_Rail_Route_Centerline.geojson', 'frontrunner_routes.geojson'),
        ('Transportation/UTA_FrontRunner_Commuter_Rail_Stations.geojson', 'frontrunner_stations.geojson'),
        ('Transportation/UtahRailroads_2492796540508595677.geojson', 'railroads.geojson'),
        ('Transportation/Airports_2168169738332772848.geojson', 'airports.geojson'),
        ('Parks and Monuments/MonumentsAndMarkers_4002612531229348260.geojson', 'monuments_and_markers.geojson'),
        ('Parks and Monuments/UtahStateParks_-6677367889837449498.geojson', 'utah_state_parks.geojson'),
        ('Boundaries/UtahCountyBoundaries_5349923461392872237.geojson', 'county_boundaries.geojson'),
        ('Boundaries/UtahMunicipalBoundaries_3270165437107876927.geojson', 'municipal_boundaries.geojson'),
        ('Boundaries/UtahHouseDistricts2022to2032_8782807203839658187.geojson', 'house_districts.geojson'),
        ('Boundaries/political_us_congress_districts_2026_to_2032_-5887061284363321862.geojson', 'congress_districts.geojson'),
    ]
    for src_rel, dst_name in copies:
        src_path = os.path.join(RAW, src_rel)
        dst_path = os.path.join(OUT, dst_name)
        if os.path.exists(src_path):
            d = json.load(open(src_path, 'r', encoding='utf-8'))
            json.dump(d, open(dst_path, 'w'), separators=(',', ':'))
            sz = os.path.getsize(dst_path) / 1024 / 1024
            results.append(f"{dst_name}: {sz:.1f} MB (direct copy, minified)")

    print("\n" + "="*60)
    print("TRANSFORMATION SUMMARY")
    print("="*60)
    for r in results:
        print(f"  {r}")

    # Total
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT) if f.endswith('.geojson'))
    print(f"\n  TOTAL public/data: {total / 1024 / 1024:.1f} MB")

if __name__ == '__main__':
    transform_all()
