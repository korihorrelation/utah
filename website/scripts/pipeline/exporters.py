"""
Export pipeline results to JSON files for the web app.

Two main export phases:
1. export_overlay_layers — city boundary, roads, paths, subdivisions, addresses
2. export_hierarchy — subdivision tiles + hierarchy.json tree
"""

import os
import json
import pandas as pd
from shapely.geometry import mapping

from .utils import safe_value, round_coords, gdf_to_features, write_json, clean_address
from .config import OUTPUT_DIR, BUILDING_CLASS_LABELS, SIMPLIFY_BUILDING, COORD_PRECISION


def export_overlay_layers(city_boundary, subdivisions, roads, paths, addresses):
    """Export city boundary, subdivisions, roads, paths, and residential addresses."""
    print("\nExporting layers...")

    # City boundary
    city_features = gdf_to_features(city_boundary, {}, None)
    write_json({
        "type": "FeatureCollection",
        "features": city_features
    }, os.path.join(OUTPUT_DIR, "city_boundary.json"))

    # Residential addresses for heatmap
    print("Exporting residential addresses for heatmap...")
    res_addresses = addresses[addresses["PtType"].astype(str).str.strip().str.lower().isin(["residential", "unknown"])]
    res_features = gdf_to_features(res_addresses, {}, None)
    write_json({
        "type": "FeatureCollection",
        "features": res_features
    }, os.path.join(OUTPUT_DIR, "residential_addresses.json"))

    # Subdivisions
    subdiv_features = gdf_to_features(subdivisions, {
        "id": "ID",
        "name": "NAME",
        "density": "DENSITY",
        "acres": "ACRE",
        "status": "STATUS",
        "type": "TYPE",
        "category": "CATEGORY",
        "recordedUnits": "RECORDEDUNITS",
        "plannedUnits": "PLANNEDUNITS",
        "existingUnits": "EXISTINGUNITS",
    }, "ID")
    write_json({
        "type": "FeatureCollection",
        "features": subdiv_features
    }, os.path.join(OUTPUT_DIR, "subdivisions.json"))

    # Roads
    road_features = gdf_to_features(roads, {
        "name": "FULLNAME",
        "type": "POSTTYPE",
        "speedLimit": "SPEED_LMT",
    })
    write_json({
        "type": "FeatureCollection",
        "features": road_features
    }, os.path.join(OUTPUT_DIR, "roads.json"))

    # Paths
    path_features = gdf_to_features(paths, {
        "use": "PATHUSE",
        "type": "TYPE",
        "surface": "SURFACE",
        "name": "NAME",
    })
    write_json({
        "type": "FeatureCollection",
        "features": path_features
    }, os.path.join(OUTPUT_DIR, "paths.json"))


def _build_parcel_node(p_idx, p_row, addresses, buildings):
    """Build a hierarchy tree node for a single parcel, including buildings and addresses."""
    parcel_id = safe_value(p_row.get("PARCELID"))
    parcel_addr = clean_address(safe_value(p_row.get("SITE_FULL_")))
    p_addresses = addresses[addresses["_parcel_idx"] == p_idx]
    p_buildings = buildings[buildings["_parcel_indices"].apply(lambda lst: p_idx in lst if lst is not None else False)]

    parcel_node = {
        "id": parcel_id,
        "name": parcel_addr or f"Parcel {parcel_id}",
        "type": "parcel",
        "buildingCount": len(p_buildings),
        "addressCount": len(p_addresses),
        "children": [],
    }

    # Add buildings as children of parcel
    for b_idx, b_row in p_buildings.iterrows():
        bldg_cls = safe_value(b_row.get("BUILDINGCL")) or 0
        bldg_cls_int = int(bldg_cls) if bldg_cls else 0
        bldg_label = BUILDING_CLASS_LABELS.get(bldg_cls_int, "Building")
        bldg_addr = clean_address(safe_value(b_row.get("_parcel_address")) or safe_value(b_row.get("FULLADDRES")))
        bldg_name_raw = safe_value(b_row.get("NAME"))
        bldg_name = bldg_name_raw or bldg_addr or bldg_label
        bldg_id = safe_value(b_row.get("GLOBALID"))

        building_node = {
            "id": bldg_id, "name": bldg_name, "type": "building",
            "buildingClass": bldg_cls_int, "classLabel": bldg_label,
        }

        # Assign addresses inside building footprint
        if len(p_addresses) > 0 and b_row.geometry is not None:
            bldg_addrs = p_addresses[p_addresses.geometry.within(b_row.geometry)]
            if len(bldg_addrs) > 0:
                building_node["addressCount"] = len(bldg_addrs)
                building_node["children"] = []
                for _, a_row in bldg_addrs.iterrows():
                    building_node["children"].append({
                        "id": safe_value(a_row.get("UTAddPtID")),
                        "name": clean_address(safe_value(a_row.get("FullAdd"))) or "Unknown Address",
                        "type": "address",
                    })

        parcel_node["children"].append(building_node)

    # Add remaining addresses directly under parcel (not inside any building)
    assigned_addr_ids = set()
    for b_idx, b_row in p_buildings.iterrows():
        if b_row.geometry is not None and len(p_addresses) > 0:
            bldg_addrs = p_addresses[p_addresses.geometry.within(b_row.geometry)]
            for _, a_row in bldg_addrs.iterrows():
                assigned_addr_ids.add(a_row.get("UTAddPtID"))

    unassigned_addrs = p_addresses[~p_addresses["UTAddPtID"].isin(assigned_addr_ids)]
    for _, a_row in unassigned_addrs.iterrows():
        parcel_node["children"].append({
            "id": safe_value(a_row.get("UTAddPtID")),
            "name": clean_address(safe_value(a_row.get("FullAdd"))) or "Unknown Address",
            "type": "address",
        })

    return parcel_node


def _build_tile_features(plat_parcels, plat_addresses, plat_oid, plat_name,
                          plat_row, sub_name, buildings, is_assigned=True):
    """Build GeoJSON tile features for plats, parcels, buildings, addresses."""
    tile_plat_props = {"id": plat_oid, "name": plat_name}
    if is_assigned:
        plat_label = plat_row["Plat"] if pd.notna(plat_row.get("Plat")) else ""
        tile_plat_props["label"] = plat_label
        tile_plat_props["acres"] = safe_value(plat_row.get("Acres"))
        tile_plat_props["subdivision"] = sub_name
    tile_plat_props["landUse"] = safe_value(plat_row.get("landUse"))

    plat_geom = mapping(plat_row.geometry)
    plat_geom = round_coords(plat_geom)
    tile_plat_features = [{"type": "Feature", "properties": tile_plat_props, "geometry": plat_geom}]

    tile_parcel_features = []
    tile_building_features = []
    tile_address_features = []

    for p_idx, p_row in plat_parcels.iterrows():
        p_geom = mapping(p_row.geometry)
        p_geom = round_coords(p_geom)
        p_props = {
            "id": safe_value(p_row.get("PARCELID")),
            "address": clean_address(safe_value(p_row.get("SITE_FULL_"))),
            "owner": safe_value(p_row.get("OWNER_NAME")),
            "platId": plat_oid,
            "landUse": safe_value(p_row.get("landUse")),
        }
        if is_assigned:
            p_props["acreage"] = safe_value(p_row.get("ACREAGE"))
            p_props["marketValue"] = safe_value(p_row.get("MKT_CUR_VA"))
        tile_parcel_features.append({"type": "Feature", "properties": p_props, "geometry": p_geom})

        # Buildings for this parcel
        p_buildings = buildings[buildings["_parcel_indices"].apply(lambda lst: p_idx in lst if lst is not None else False)]
        for _, b_row in p_buildings.iterrows():
            b_geom = mapping(b_row.geometry)
            b_geom = round_coords(b_geom)
            bldg_cls = int(safe_value(b_row.get("BUILDINGCL")) or 0)
            b_props = {
                "id": safe_value(b_row.get("GLOBALID")),
                "name": safe_value(b_row.get("NAME")),
                "address": clean_address(safe_value(b_row.get("_parcel_address")) or safe_value(b_row.get("FULLADDRES"))),
                "class": bldg_cls,
                "classLabel": BUILDING_CLASS_LABELS.get(bldg_cls, "Building"),
                "height": safe_value(b_row.get("_height")),
                "housingLabel": safe_value(b_row.get("_hui_label")),
                "yearBuilt": safe_value(b_row.get("YEAR_BUILT")),
                "parcelId": safe_value(p_row.get("PARCELID")),
                "platId": plat_oid,
            }
            if is_assigned:
                b_props["stories"] = safe_value(b_row.get("NUMSTORIES"))
            tile_building_features.append({"type": "Feature", "properties": b_props, "geometry": b_geom})

    for _, a_row in plat_addresses.iterrows():
        a_geom = mapping(a_row.geometry)
        a_geom = round_coords(a_geom)
        a_props = {
            "id": safe_value(a_row.get("UTAddPtID")),
            "fullAddress": clean_address(safe_value(a_row.get("FullAdd"))),
            "parcelId": safe_value(a_row.get("ParcelID")),
        }
        if is_assigned:
            a_props["city"] = safe_value(a_row.get("City"))
            a_props["zipCode"] = safe_value(a_row.get("ZipCode"))
            a_props["structureType"] = safe_value(a_row.get("Structure"))
            a_props["pointType"] = safe_value(a_row.get("PtType"))
        tile_address_features.append({"type": "Feature", "properties": a_props, "geometry": a_geom})

    return tile_plat_features, tile_parcel_features, tile_building_features, tile_address_features


def export_hierarchy(subdivisions, plats, parcels, buildings, addresses):
    """Build and export hierarchy tree + per-subdivision tile JSON files."""
    print("\nBuilding hierarchy tree and subdivision tiles...")
    hierarchy_tree = {
        "name": "Saratoga Springs",
        "type": "city",
        "children": []
    }

    subdiv_ids = sorted(subdivisions["ID"].dropna().unique())

    for sub_id in subdiv_ids:
        sub_id = int(sub_id)
        sub_row = subdivisions[subdivisions["ID"] == sub_id].iloc[0]
        sub_name = sub_row["NAME"] if pd.notna(sub_row["NAME"]) else f"Subdivision {sub_id}"

        sub_plats = plats[plats["_sub_id"] == sub_id]

        sub_node = {
            "id": sub_id,
            "name": sub_name,
            "type": "subdivision",
            "subdivisionType": safe_value(sub_row.get("TYPE")),
            "category": safe_value(sub_row.get("CATEGORY")),
            "platCount": len(sub_plats),
            "children": []
        }

        all_tile_plat = []
        all_tile_parcel = []
        all_tile_building = []
        all_tile_address = []

        for _, plat_row in sub_plats.iterrows():
            plat_oid = int(plat_row["OBJECTID"])
            plat_name = plat_row["Name"] if pd.notna(plat_row.get("Name")) else f"Plat {plat_oid}"
            plat_label = plat_row["Plat"] if pd.notna(plat_row.get("Plat")) else ""

            plat_parcels = parcels[parcels["_plat_oid"] == plat_oid]
            if len(plat_parcels) == 0:
                continue

            plat_parcel_indices = set(plat_parcels.index)
            plat_addresses = addresses[addresses["_parcel_idx"].isin(plat_parcel_indices)]

            plat_node = {
                "id": plat_oid,
                "name": plat_name,
                "label": plat_label,
                "type": "plat",
                "parcelCount": len(plat_parcels),
                "addressCount": len(plat_addresses),
                "children": []
            }

            for p_idx, p_row in plat_parcels.iterrows():
                plat_node["children"].append(
                    _build_parcel_node(p_idx, p_row, addresses, buildings)
                )

            sub_node["children"].append(plat_node)

            # Build tile features
            tp, tpa, tb, ta = _build_tile_features(
                plat_parcels, plat_addresses, plat_oid, plat_name,
                plat_row, sub_name, buildings, is_assigned=True
            )
            all_tile_plat.extend(tp)
            all_tile_parcel.extend(tpa)
            all_tile_building.extend(tb)
            all_tile_address.extend(ta)

        sub_node["parcelCount"] = len(all_tile_parcel)
        sub_node["buildingCount"] = len(all_tile_building)
        sub_node["addressCount"] = len(all_tile_address)

        write_json({
            "plats": {"type": "FeatureCollection", "features": all_tile_plat},
            "parcels": {"type": "FeatureCollection", "features": all_tile_parcel},
            "buildings": {"type": "FeatureCollection", "features": all_tile_building},
            "addresses": {"type": "FeatureCollection", "features": all_tile_address},
        }, os.path.join(OUTPUT_DIR, "subdivisions", f"{sub_id}.json"))

        hierarchy_tree["children"].append(sub_node)

    # ── Handle unassigned plats ──
    unassigned_plats = plats[plats["_sub_id"].isna()]
    if len(unassigned_plats) > 0:
        print(f"\n  Unassigned plats: {len(unassigned_plats)}")
        unassigned_node = {
            "id": "unassigned",
            "name": "Unassigned Areas",
            "type": "subdivision",
            "subdivisionType": "Unassigned",
            "category": "Other",
            "platCount": len(unassigned_plats),
            "children": []
        }

        all_tile_plat = []
        all_tile_parcel = []
        all_tile_building = []
        all_tile_address = []

        for _, plat_row in unassigned_plats.iterrows():
            plat_oid = int(plat_row["OBJECTID"])
            plat_name = plat_row["Name"] if pd.notna(plat_row.get("Name")) else f"Plat {plat_oid}"

            plat_parcels = parcels[parcels["_plat_oid"] == plat_oid]
            if len(plat_parcels) == 0:
                continue
            plat_parcel_indices = set(plat_parcels.index)
            plat_addresses = addresses[addresses["_parcel_idx"].isin(plat_parcel_indices)]

            plat_node = {
                "id": plat_oid,
                "name": plat_name,
                "type": "plat",
                "parcelCount": len(plat_parcels),
                "addressCount": len(plat_addresses),
                "children": []
            }

            for p_idx, p_row in plat_parcels.iterrows():
                plat_node["children"].append(
                    _build_parcel_node(p_idx, p_row, addresses, buildings)
                )

            unassigned_node["children"].append(plat_node)

            tp, tpa, tb, ta = _build_tile_features(
                plat_parcels, plat_addresses, plat_oid, plat_name,
                plat_row, None, buildings, is_assigned=False
            )
            all_tile_plat.extend(tp)
            all_tile_parcel.extend(tpa)
            all_tile_building.extend(tb)
            all_tile_address.extend(ta)

        unassigned_node["parcelCount"] = len(all_tile_parcel)
        unassigned_node["buildingCount"] = len(all_tile_building)
        unassigned_node["addressCount"] = len(all_tile_address)

        write_json({
            "plats": {"type": "FeatureCollection", "features": all_tile_plat},
            "parcels": {"type": "FeatureCollection", "features": all_tile_parcel},
            "buildings": {"type": "FeatureCollection", "features": all_tile_building},
            "addresses": {"type": "FeatureCollection", "features": all_tile_address},
        }, os.path.join(OUTPUT_DIR, "subdivisions", "unassigned.json"))

        hierarchy_tree["children"].append(unassigned_node)

    # ── Orphan parcels ──
    all_assigned = set(parcels[parcels["_plat_oid"].notna()].index)
    orphan_parcels = parcels[~parcels.index.isin(all_assigned)]
    print(f"  Orphan parcels (no plat): {len(orphan_parcels)}")

    # ── Sort and finalize ──
    _sort_hierarchy(hierarchy_tree, subdivisions, plats, parcels)

    total_parcels = sum(c.get("parcelCount", 0) for c in hierarchy_tree["children"])
    total_addresses = sum(c.get("addressCount", 0) for c in hierarchy_tree["children"])
    hierarchy_tree["subdivisionCount"] = len(hierarchy_tree["children"])
    hierarchy_tree["totalParcels"] = total_parcels
    hierarchy_tree["totalAddresses"] = total_addresses

    write_json(hierarchy_tree, os.path.join(OUTPUT_DIR, "hierarchy.json"))

    print(f"\n=== Preprocessing complete! ===")
    print(f"  Subdivisions: {len(hierarchy_tree['children'])}")
    print(f"  Total parcels in hierarchy: {total_parcels}")
    print(f"  Total addresses in hierarchy: {total_addresses}")


def _sort_hierarchy(hierarchy_tree, subdivisions, plats, parcels):
    """Sort all children in the hierarchy tree alphabetically by name."""
    print("\nSorting hierarchy tree...")
    sub_acres_lookup = {}
    for idx, row in subdivisions.iterrows():
        sid = row.get("ID")
        if pd.notna(sid):
            sub_acres_lookup[int(sid)] = float(row.get("ACRE") or 0.0)

    plat_acres_lookup = {}
    for idx, row in plats.iterrows():
        poid = row.get("OBJECTID")
        if pd.notna(poid):
            plat_acres_lookup[int(poid)] = float(row.get("Acres") or row.get("ACRE") or 0.0)

    parcel_acres_lookup = {}
    for idx, row in parcels.iterrows():
        pid = row.get("PARCELID")
        if pid:
            parcel_acres_lookup[str(pid)] = float(row.get("ACREAGE") or 0.0)

    def sort_node(node):
        children = node.get("children", [])
        if not children:
            return

        for child in children:
            sort_node(child)

        child_type = children[0].get("type")

        if child_type == "subdivision":
            children.sort(key=lambda x: (
                x.get("name", "").lower(),
                -sub_acres_lookup.get(int(x.get("id")) if isinstance(x.get("id"), (int, float)) else 0, 0.0)
            ))
        elif child_type == "plat":
            children.sort(key=lambda x: (
                x.get("name", "").lower(),
                -plat_acres_lookup.get(int(x.get("id")) if isinstance(x.get("id"), (int, float)) else 0, 0.0)
            ))
        elif child_type == "parcel":
            children.sort(key=lambda x: (
                x.get("name", "").lower(),
                -parcel_acres_lookup.get(str(x.get("id")), 0.0)
            ))

    sort_node(hierarchy_tree)


def export_buildings_geojson(buildings):
    """Export all buildings as a single GeoJSON file for the 3D map layer.
    
    Properties include: height, class, name, housingLabel, address.
    Only height and class are always present; the rest are conditional.
    """
    print("\nExporting buildings.geojson...")
    features = []
    for _, b_row in buildings.iterrows():
        geom = b_row.geometry
        if geom is None or geom.is_empty:
            continue
        geom = geom.simplify(SIMPLIFY_BUILDING, preserve_topology=True)
        geom_dict = mapping(geom)
        geom_dict = round_coords(geom_dict)

        bldg_cls = int(safe_value(b_row.get("BUILDINGCL")) or 0)
        props = {
            "id": safe_value(b_row.get("GLOBALID")),
            "height": safe_value(b_row.get("_height")) or 8,
            "class": bldg_cls,
        }
        name = safe_value(b_row.get("NAME"))
        if name:
            props["name"] = name
        hui_label = safe_value(b_row.get("_hui_label"))
        if hui_label:
            props["housingLabel"] = hui_label
        addr = clean_address(safe_value(b_row.get("_parcel_address")) or safe_value(b_row.get("FULLADDRES")))
        if addr:
            props["address"] = addr

        features.append({"type": "Feature", "properties": props, "geometry": geom_dict})

    write_json(
        {"type": "FeatureCollection", "features": features},
        os.path.join(OUTPUT_DIR, "buildings.geojson")
    )
    print(f"  Exported {len(features)} buildings")
