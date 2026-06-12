"""
Spatial and attribute-based filtering for GIS layers.
"""

import numpy as np
import pandas as pd


def filter_out_of_bounds(gdf, city_geom, rules):
    """Filter features that are outside the city boundary or belong to excluded cities.
    
    Args:
        gdf: GeoDataFrame to filter.
        city_geom: Unary union of city boundary geometry.
        rules: Classification rules dict (needs out_of_bounds_cities,
               out_of_bounds_tax_cities, out_of_bounds_site_cities).
    """
    if gdf.empty:
        return gdf

    # 1. Spatial check: must intersect city boundary
    mask = gdf.geometry.intersects(city_geom)
    gdf = gdf[mask].copy()

    # 2. Attribute checks for excluded cities
    excluded_cities = rules.get("out_of_bounds_cities", [])
    city_mask = pd.Series(True, index=gdf.index)
    for col in gdf.select_dtypes(include=['object', 'string']).columns:
        col_lower = col.lower()
        is_city_col = any(x in col_lower for x in ["city", "dist", "address", "site_full"])
        if is_city_col:
            for city_name in excluded_cities:
                city_mask = city_mask & (~gdf[col].astype(str).str.contains(
                    city_name, case=False, na=False
                ))
    gdf = gdf[city_mask].copy()

    # 3. Specific check for parcels with TAX_CITY / SITE_CITY columns
    if "TAX_CITY" in gdf.columns:
        tax_cities = rules.get("out_of_bounds_tax_cities", [])
        site_cities = rules.get("out_of_bounds_site_cities", [])
        tax_city_mask = ~gdf["TAX_CITY"].isin(tax_cities)
        site_city_mask = ~gdf["SITE_CITY"].isin(site_cities)
        gdf = gdf[tax_city_mask & site_city_mask].copy()

    return gdf


def filter_small_geoms(gdf, min_area_sqm=5.0, min_pp=0.01):
    """Remove tiny or degenerate polygon geometries.
    
    Args:
        gdf: GeoDataFrame to filter.
        min_area_sqm: Minimum area in square meters.
        min_pp: Minimum Polsby-Popper compactness score.
    """
    if gdf.empty or not gdf.geometry.geom_type.isin(['Polygon', 'MultiPolygon']).any():
        return gdf
    
    is_poly = gdf.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])
    proj_geoms = gdf[is_poly].geometry.to_crs(epsg=3566)
    areas = proj_geoms.area
    perimeters = proj_geoms.length
    # Protect against div by zero
    perimeters = perimeters.replace(0, np.nan)
    pp_scores = (4 * np.pi * areas) / (perimeters ** 2)

    valid_poly_mask = (areas >= min_area_sqm) & (pp_scores >= min_pp)
    valid_mask = pd.Series(True, index=gdf.index)
    valid_mask.loc[is_poly] = valid_poly_mask

    return gdf[valid_mask].copy()


def apply_filters(layers, city_geom, rules):
    """Apply out-of-bounds and small geometry filters to all layers.
    
    Args:
        layers: dict of layer name -> GeoDataFrame.
        city_geom: Unary union of city boundary geometry.
        rules: Classification rules dict.
    
    Returns:
        Updated layers dict.
    """
    print("\nFiltering layers (out of bounds and tiny geometries)...")
    
    layers["subdivisions"] = filter_out_of_bounds(
        filter_small_geoms(layers["subdivisions"]), city_geom, rules
    )
    layers["plats"] = filter_out_of_bounds(
        filter_small_geoms(layers["plats"]), city_geom, rules
    )
    layers["parcels"] = filter_out_of_bounds(
        filter_small_geoms(layers["parcels"]), city_geom, rules
    )
    layers["buildings"] = filter_out_of_bounds(
        filter_small_geoms(layers["buildings"], min_area_sqm=1.0), city_geom, rules
    )
    layers["addresses"] = filter_out_of_bounds(layers["addresses"], city_geom, rules)
    layers["roads"] = filter_out_of_bounds(layers["roads"], city_geom, rules)
    layers["paths"] = filter_out_of_bounds(layers["paths"], city_geom, rules)

    for name in ["subdivisions", "plats", "parcels", "addresses", "buildings", "roads", "paths"]:
        print(f"  After filter {name.capitalize()}: {len(layers[name])}")
    
    return layers
