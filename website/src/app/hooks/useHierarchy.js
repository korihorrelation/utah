'use client';

import { useState, useCallback, useEffect, useRef } from 'react';

/**
 * Central hook for hierarchy data loading, navigation, and tree expansion state.
 *
 * Navigation model:
 *   - selection: { type, id, subdivisionId?, platId?, parcelId?, buildingId? }
 *     Represents the currently focused item. The optional parent IDs
 *     record the full ancestry so any component can check containment.
 *   - expandedNodes: Set of tree‑node keys that are open in the sidebar.
 *     On fresh navigation the set is *replaced* with exactly the ancestor
 *     chain (accordion behaviour). Re‑clicking the same node toggles it.
 *   - drillPath: breadcrumb array built from the ancestor chain.
 */
export function useHierarchy() {
  // ── GIS data ──
  const [hierarchy, setHierarchy] = useState(null);
  const [subdivisions, setSubdivisions] = useState(null);
  const [cityBoundary, setCityBoundary] = useState(null);
  const [roads, setRoads] = useState(null);
  const [paths, setPaths] = useState(null);
  const [parks, setParks] = useState(null);
  const [pois, setPois] = useState(null);
  const [residentialAddresses, setResidentialAddresses] = useState(null);

  // ── Drill‑down tile ──
  const [activeTile, setActiveTile] = useState(null);
  const [activeSubdivisionId, setActiveSubdivisionId] = useState(null);
  const [tileLoading, setTileLoading] = useState(false);
  const tileCache = useRef({});

  // ── Selection / navigation ──
  const [selection, setSelection] = useState(null);
  const [drillPath, setDrillPath] = useState([ROOT_CRUMB]);
  const [expandedNodes, setExpandedNodes] = useState(new Set());

  // ── UI ──
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);

  // Keep a ref to selection so navigateTo never re‑creates due to selection changes.
  const selectionRef = useRef(selection);
  useEffect(() => { selectionRef.current = selection; }, [selection]);

  // ── Load initial data ──
  useEffect(() => {
    (async () => {
      try {
        const [hierRes, subdivRes, boundaryRes, roadsRes, pathsRes, parksRes, poisRes, heatmapRes] = await Promise.all([
          fetch('/data/hierarchy.json'),
          fetch('/data/subdivisions.json'),
          fetch('/data/city_boundary.json'),
          fetch('/data/roads.json'),
          fetch('/data/paths.json'),
          fetch('/data/parks.json'),
          fetch('/data/pois.json'),
          fetch('/data/residential_addresses.json'),
        ]);
        const [hierData, subdivData, boundaryData, roadsData, pathsData, parksData, poisData, heatmapData] = await Promise.all([
          hierRes.json(), subdivRes.json(), boundaryRes.json(), roadsRes.json(), pathsRes.json(), parksRes.json(), poisRes.json(), heatmapRes.json(),
        ]);
        setHierarchy(hierData);
        setSubdivisions(subdivData);
        setCityBoundary(boundaryData);
        setRoads(roadsData);
        setPaths(pathsData);
        setParks(parksData);
        setPois(poisData);
        setResidentialAddresses(heatmapData);
      } catch (err) {
        console.error('Failed to load initial data:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // ── Tile loader ──
  const loadTile = useCallback(async (subId) => {
    if (tileCache.current[subId]) {
      setActiveTile(tileCache.current[subId]);
      setActiveSubdivisionId(subId);
      return;
    }
    setTileLoading(true);
    try {
      const res = await fetch(`/data/subdivisions/${subId}.json`);
      const data = await res.json();
      tileCache.current[subId] = data;
      setActiveTile(data);
      setActiveSubdivisionId(subId);
    } catch (err) {
      console.error(`Failed to load tile for subdivision ${subId}:`, err);
    } finally {
      setTileLoading(false);
    }
  }, []);

  // ── Central navigation function ──
  const navigateTo = useCallback(async (type, id, name, parentId = null) => {
    const prev = selectionRef.current;
    const isSame = prev?.type === type && prev?.id === id;

    if (type === 'city') {
      setSelection(null);
      setDrillPath([ROOT_CRUMB]);
      setActiveTile(null);
      setActiveSubdivisionId(null);
      setExpandedNodes(new Set());
      return;
    }

    // Resolve full ancestry from the hierarchy tree, falling back to standard lookup if parentId context is not found
    const ctx = resolveContext(hierarchy, type, id, parentId) || (parentId != null ? resolveContext(hierarchy, type, id) : null);
    if (!ctx) return; // item not found

    // Build selection object with full ancestry.
    const sel = { type, id, ...ctx.ids };

    // When switching to a different subdivision, immediately clear stale map
    // layers so the intermediate render (before loadTile resolves) doesn't
    // show the old subdivision's boundaries and plats.
    const newSubId = ctx.ids.subdivisionId;
    const prevSubId = prev?.subdivisionId;
    if (newSubId != null && newSubId !== prevSubId) {
      setActiveTile(null);
      setActiveSubdivisionId(newSubId);
    }

    setSelection(sel);

    // Build breadcrumb path.
    setDrillPath([ROOT_CRUMB, ...ctx.crumbs, { type, id, name }]);

    // Load tile if needed.
    if (newSubId != null) {
      await loadTile(newSubId);
    }

    // Accordion expansion: on re‑click toggle the leaf node; otherwise
    // replace the whole set with just the ancestor chain.
    setExpandedNodes(() => {
      const chain = new Set(ctx.expandKeys);
      if (isSame) {
        // Toggle: if the node's own key is already open, close it.
        const selfKey = `${type}-${id}`;
        if (chain.has(selfKey)) chain.delete(selfKey);
        else chain.add(selfKey);
      }
      return chain;
    });
  }, [hierarchy, loadTile]);

  // ── Search ──
  const performSearch = useCallback((query) => {
    setSearchQuery(query);
    if (!query || query.length < 3 || !hierarchy) {
      setSearchResults([]);
      return;
    }
    const results = [];
    const q = query.toLowerCase();
    for (const sub of hierarchy.children || []) {
      for (const plat of sub.children || []) {
        for (const parcel of plat.children || []) {
          if (parcel.name && parcel.name.toLowerCase().includes(q)) {
            results.push({ type: 'parcel', id: parcel.id, name: parcel.name, context: `${sub.name} › ${plat.name}` });
          }
          for (const child of parcel.children || []) {
            if (child.type === 'building') {
              if (child.name && child.name.toLowerCase().includes(q)) {
                results.push({ type: 'building', id: child.id, name: child.name, context: `${sub.name} › ${parcel.name}` });
              }
              for (const addr of child.children || []) {
                if (addr.name && addr.name.toLowerCase().includes(q)) {
                  results.push({ type: 'address', id: addr.id, name: addr.name, context: `${sub.name} › ${plat.name}` });
                }
              }
            } else if (child.type === 'address') {
              if (child.name && child.name.toLowerCase().includes(q)) {
                results.push({ type: 'address', id: child.id, name: child.name, context: `${sub.name} › ${plat.name}` });
              }
            }
          }
          if (results.length >= 50) break;
        }
        if (results.length >= 50) break;
      }
      if (results.length >= 50) break;
    }
    setSearchResults(results);
  }, [hierarchy]);

  return {
    hierarchy, subdivisions, cityBoundary, roads, paths, parks, pois, residentialAddresses,
    activeTile, activeSubdivisionId, selection, drillPath,
    loading, tileLoading, searchQuery, searchResults, expandedNodes,
    navigateTo, performSearch,
  };
}

// ── Constants ──
const ROOT_CRUMB = { type: 'city', id: 'root', name: 'Saratoga Springs' };

// ── Hierarchy traversal ──
// Returns { ids, crumbs, expandKeys } for a given (type, id) by walking the tree once.
function resolveContext(hierarchy, type, id, parentId = null) {
  if (!hierarchy) return null;

  if (type === 'subdivision') {
    const sub = (hierarchy.children || []).find(s => s.id == id);
    if (!sub) return null;
    return {
      ids: { subdivisionId: sub.id },
      crumbs: [],
      expandKeys: [`subdivision-${sub.id}`],
    };
  }

  for (const sub of hierarchy.children || []) {
    if (type === 'plat') {
      const plat = (sub.children || []).find(p => p.id == id);
      if (plat) {
        return {
          ids: { subdivisionId: sub.id, platId: plat.id },
          crumbs: [{ type: 'subdivision', id: sub.id, name: sub.name }],
          expandKeys: [`subdivision-${sub.id}`, `plat-${plat.id}`],
        };
      }
      continue;
    }

    for (const plat of sub.children || []) {
      if (type === 'parcel') {
        const parcel = (plat.children || []).find(p => p.id == id);
        if (parcel) {
          return {
            ids: { subdivisionId: sub.id, platId: plat.id, parcelId: parcel.id },
            crumbs: [
              { type: 'subdivision', id: sub.id, name: sub.name },
              { type: 'plat', id: plat.id, name: plat.name },
            ],
            expandKeys: [`subdivision-${sub.id}`, `plat-${plat.id}`, `parcel-${parcel.id}`],
          };
        }
        continue;
      }

      for (const parcel of plat.children || []) {
        if (parentId != null && parcel.id != parentId) continue;
        // Search for building or address among parcel's children
        for (const child of parcel.children || []) {
          if (type === 'building' && child.type === 'building' && child.id == id) {
            return {
              ids: { subdivisionId: sub.id, platId: plat.id, parcelId: parcel.id, buildingId: child.id },
              crumbs: [
                { type: 'subdivision', id: sub.id, name: sub.name },
                { type: 'plat', id: plat.id, name: plat.name },
                { type: 'parcel', id: parcel.id, name: parcel.name },
              ],
              expandKeys: [`subdivision-${sub.id}`, `plat-${plat.id}`, `parcel-${parcel.id}`, `building-${child.id}`],
            };
          }

          if (type === 'address') {
            // Address directly under parcel
            if (child.type === 'address' && child.id == id) {
              return {
                ids: { subdivisionId: sub.id, platId: plat.id, parcelId: parcel.id },
                crumbs: [
                  { type: 'subdivision', id: sub.id, name: sub.name },
                  { type: 'plat', id: plat.id, name: plat.name },
                  { type: 'parcel', id: parcel.id, name: parcel.name },
                ],
                expandKeys: [`subdivision-${sub.id}`, `plat-${plat.id}`, `parcel-${parcel.id}`],
              };
            }
            // Address under a building
            if (child.type === 'building') {
              const addr = (child.children || []).find(a => a.id == id);
              if (addr) {
                return {
                  ids: { subdivisionId: sub.id, platId: plat.id, parcelId: parcel.id, buildingId: child.id },
                  crumbs: [
                    { type: 'subdivision', id: sub.id, name: sub.name },
                    { type: 'plat', id: plat.id, name: plat.name },
                    { type: 'parcel', id: parcel.id, name: parcel.name },
                    { type: 'building', id: child.id, name: child.name },
                  ],
                  expandKeys: [`subdivision-${sub.id}`, `plat-${plat.id}`, `parcel-${parcel.id}`, `building-${child.id}`],
                };
              }
            }
          }
        }
      }
    }
  }
  return null;
}
