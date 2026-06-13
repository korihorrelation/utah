import json
import os

h = json.load(open('website/public/data/hierarchy.json'))
pub = [c for c in h['children'] if c['category'] == 'Public']
roads = [c for c in pub if 'road' in c['name'].lower()]

print(f"Total Public subdivisions: {len(pub)}")
print("Roads in Public:")
for c in roads:
    print(f"  {c['name']} (Plats: {c.get('platCount',0)}, Addresses: {c.get('addressCount',0)})")
