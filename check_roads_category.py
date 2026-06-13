import json

h = json.load(open('website/public/data/hierarchy.json'))
for c in h['children']:
    if 'road' in c['name'].lower():
        print(f"{c['name']} -> {c['category']}")
