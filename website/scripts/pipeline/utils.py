"""
Shared GIS utility functions used by both preprocessing scripts.
"""

import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import mapping

from .config import COORD_PRECISION


def load_layer(path):
    """Load a GIS layer and reproject to EPSG:4326."""
    gdf = gpd.read_file(path)
    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def simplify_geometry(gdf, tolerance):
    """Simplify geometries and drop empty/null results."""
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.simplify(tolerance, preserve_topology=True)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    return gdf


def round_coords(geojson_dict, precision=COORD_PRECISION):
    """Recursively round coordinates in a GeoJSON-like dict to save space."""
    if isinstance(geojson_dict, dict):
        return {k: round_coords(v, precision) for k, v in geojson_dict.items()}
    elif isinstance(geojson_dict, list):
        return [round_coords(item, precision) for item in geojson_dict]
    elif isinstance(geojson_dict, float):
        return round(geojson_dict, precision)
    return geojson_dict


def safe_value(val):
    """Convert numpy/pandas types to JSON-safe Python types."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return round(float(val), 4)
    if isinstance(val, (pd.Timestamp,)):
        return val.isoformat()
    return val


def safe_int(val):
    """Safely convert a value to an integer."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def gdf_to_features(gdf, properties_map, id_field=None):
    """
    Convert a GeoDataFrame to a list of GeoJSON features with selected properties.
    properties_map: dict of {output_key: source_column}
    """
    features = []
    for idx, row in gdf.iterrows():
        props = {}
        for out_key, src_col in properties_map.items():
            if src_col in row.index:
                props[out_key] = safe_value(row[src_col])
            else:
                props[out_key] = None
        if id_field and id_field in row.index:
            props["id"] = safe_value(row[id_field])

        geom = mapping(row.geometry)
        geom = round_coords(geom)
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": geom
        })
    return features


def write_json(data, path):
    """Write JSON to file, creating directories as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    size_kb = os.path.getsize(path) / 1024
    print(f"  Wrote {path} ({size_kb:.0f} KB)")


def clean_owner_name(name):
    """Normalize an owner name to Title Case with common acronym fixes."""
    if pd.isna(name):
        return "Unknown Owner"
    s = str(name).strip().title()
    if not s:
        return "Unknown Owner"
    return s.replace("Lds", "LDS").replace("Udot", "UDOT").replace(" Us ", " US ")


def clean_address(addr):
    """Normalize an address to Title Case with common direction acronym fixes."""
    if pd.isna(addr) or addr is None:
        return None
    s = str(addr).strip()
    if not s:
        return None
    words = s.lower().split()
    capitalized = []
    for w in words:
        if w in ['ne', 'nw', 'se', 'sw']:
            capitalized.append(w.upper())
        else:
            capitalized.append(w.capitalize())
    return " ".join(capitalized)

