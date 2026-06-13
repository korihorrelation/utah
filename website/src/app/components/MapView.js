import { useEffect, useRef, useMemo, useCallback, useState } from 'react';
import Map, { Source, Layer, Popup, NavigationControl } from 'react-map-gl/maplibre';
import { getSubdivisionColor } from '../lib/colors';
import 'maplibre-gl/dist/maplibre-gl.css';

const DEPTH = { subdivision: 1, plat: 2, parcel: 3, building: 4, address: 5 };

// Building class labels
const BUILDING_CLASS_LABELS = {
  1: 'Residential', 2: 'Commercial', 3: 'Industrial', 4: 'Government',
  6: 'Agricultural', 7: 'Religious', 8: 'Education', 11: 'Utility', 12: 'Other',
};

// POI color mapping
const POI_COLORS = {
  education: '#a78bfa',
  civic_community: '#fb7185',
  retail_food: '#fbbf24',
  healthcare: '#2dd4bf',
  other: '#9499b3',
};

/**
 * Interactive MapLibre GL map with 3D pitch/tilt and drill-down polygon layers.
 */
export default function MapView({
  cityBoundary,
  subdivisions,
  roads,
  paths,
  parks,
  pois,
  residentialAddresses,
  activeTile,
  activeSubdivisionId,
  selection,
  onNavigate,
  hiddenSubdivisionIds,
}) {
  const mapRef = useRef(null);
  const tooltipRef = useRef(null);
  const [showPaths, setShowPaths] = useState(false);
  const [showParks, setShowParks] = useState(false);
  const [showPois, setShowPois] = useState(false);
  const [showBuildings, setShowBuildings] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [buildingsData, setBuildingsData] = useState(null);
  const buildingsLoading = useRef(false);
  const [popupInfo, setPopupInfo] = useState(null);
  const lastSelectionKey = useRef(null);

  // ── Lazy-load buildings GeoJSON on first toggle ──
  useEffect(() => {
    if (showBuildings && !buildingsData && !buildingsLoading.current) {
      buildingsLoading.current = true;
      fetch('/data/buildings.geojson')
        .then(r => r.json())
        .then(data => setBuildingsData(data))
        .catch(err => console.error('Failed to load buildings:', err))
        .finally(() => { buildingsLoading.current = false; });
    }
  }, [showBuildings, buildingsData]);

  // ── Subdivision data: filter when drilled down or hidden ──
  const subdivisionData = useMemo(() => {
    if (!subdivisions) return null;
    const activeFeatures = subdivisions.features.filter(f => {
      const isSubHidden = hiddenSubdivisionIds?.has(f.properties.id);
      return !isSubHidden;
    });
    if (!activeSubdivisionId) {
      return {
        ...subdivisions,
        features: activeFeatures,
      };
    }
    return {
      ...subdivisions,
      features: activeFeatures.filter(f => f.properties.id === activeSubdivisionId),
    };
  }, [subdivisions, activeSubdivisionId, hiddenSubdivisionIds]);

  const isActiveSubdivisionHidden = useMemo(() => {
    if (activeSubdivisionId == null) return false;
    if (hiddenSubdivisionIds?.has(activeSubdivisionId)) return true;
    return false;
  }, [activeSubdivisionId, hiddenSubdivisionIds]);

  // ── Drill-down visibility ──
  const depth = DEPTH[selection?.type] ?? 0;
  const showPlats = activeTile?.plats?.features?.length > 0 && !isActiveSubdivisionHidden;
  const showParcels = depth >= 2 && !isActiveSubdivisionHidden;
  const showAddresses = depth >= 3 && !isActiveSubdivisionHidden;

  // ── Parcel data: filter to selected plat ──
  const filteredParcels = useMemo(() => {
    if (!activeTile?.parcels) return null;
    if (!selection?.platId) return activeTile.parcels;
    return {
      ...activeTile.parcels,
      features: activeTile.parcels.features.filter(f => f.properties.platId === selection.platId),
    };
  }, [activeTile?.parcels, selection?.platId]);

  // ── Address data: filter to selected parcel ──
  const filteredAddresses = useMemo(() => {
    if (!activeTile?.addresses) return null;
    if (!selection?.parcelId) return activeTile.addresses;
    return {
      ...activeTile.addresses,
      features: activeTile.addresses.features.filter(f => f.properties.parcelId === selection.parcelId),
    };
  }, [activeTile?.addresses, selection?.parcelId]);

  // ── Buildings data: use active tile's buildings when drilled down, otherwise the global buildings ──
  const displayBuildings = useMemo(() => {
    if (!showBuildings) return null;
    if (isActiveSubdivisionHidden) return null;
    if (activeTile?.buildings) return activeTile.buildings;
    return buildingsData;
  }, [showBuildings, activeTile?.buildings, buildingsData, isActiveSubdivisionHidden]);

  // ── Subdivision fill/line paint per feature ──
  // MapLibre can't do per-feature JS callbacks, so we add a _color property
  const coloredSubdivisions = useMemo(() => {
    if (!subdivisionData) return null;
    return {
      ...subdivisionData,
      features: subdivisionData.features.map(f => ({
        ...f,
        properties: {
          ...f.properties,
          _color: getSubdivisionColor(f.properties.category),
          _isActive: selection?.type === 'subdivision' && selection?.id === f.properties.id ? 1 : 0,
        },
      })),
    };
  }, [subdivisionData, selection?.type, selection?.id]);

  // ── POIs: add color property ──
  const coloredPois = useMemo(() => {
    if (!pois) return null;
    return {
      ...pois,
      features: pois.features.map(f => ({
        ...f,
        properties: {
          ...f.properties,
          _color: POI_COLORS[f.properties.group] || POI_COLORS.other,
        },
      })),
    };
  }, [pois]);

  // Building class labels for tooltips
  const BUILDING_CLASS_LABELS = useMemo(() => ({
    1: 'Residential', 2: 'Commercial', 3: 'Industrial', 4: 'Government',
    6: 'Agricultural', 7: 'Religious', 8: 'Education', 11: 'Utility', 12: 'Other',
  }), []);

  // ── Interactive layer IDs for click handling ──
  const interactiveLayerIds = useMemo(() => {
    const ids = [];
    if (coloredSubdivisions) ids.push('subdivisions-fill');
    if (showPlats) ids.push('plats-fill');
    if (showParcels && filteredParcels?.features?.length) ids.push('parcels-fill');
    if (showAddresses && filteredAddresses?.features?.length) ids.push('addresses-circle');
    if (showParks && parks) ids.push('parks-fill');
    if (showPois && coloredPois) ids.push('pois-circle');
    if (displayBuildings) ids.push('buildings-extrusion');
    return ids;
  }, [coloredSubdivisions, showPlats, showParcels, filteredParcels, showAddresses, filteredAddresses, showParks, parks, showPois, coloredPois, displayBuildings]);

  // ── Click handler ──
  const onClick = useCallback((event) => {
    const features = event.features;
    if (!features || features.length === 0) {
      // Clicked empty space → reset to city
      onNavigate('city', 'root', 'Saratoga Springs');
      setPopupInfo(null);
      return;
    }

    const f = features[0];
    const layerId = f.layer.id;
    const props = f.properties;

    if (layerId === 'subdivisions-fill') {
      onNavigate('subdivision', props.id, props.name);
      setPopupInfo(null);
    } else if (layerId === 'plats-fill') {
      onNavigate('plat', props.id, props.name);
      setPopupInfo(null);
    } else if (layerId === 'parcels-fill') {
      onNavigate('parcel', props.id, props.address || `Parcel ${props.id}`);
      setPopupInfo(null);
    } else if (layerId === 'addresses-circle') {
      onNavigate('address', props.id, props.fullAddress || 'Address');
      setPopupInfo({
        longitude: event.lngLat.lng,
        latitude: event.lngLat.lat,
        type: 'address',
        props,
      });
    } else if (layerId === 'buildings-extrusion') {
      const cls = BUILDING_CLASS_LABELS[props.class] || 'Building';
      let name;
      if (props.name) {
        name = props.name;
      } else if (props.housingLabel) {
        name = props.address ? `${props.housingLabel} at ${props.address}` : props.housingLabel;
      } else {
        name = props.address || cls;
      }

      // Determine the parcel closest to/under the click point
      let clickedParcelId = null;
      if (mapRef.current) {
        const parcelFeatures = mapRef.current.queryRenderedFeatures(event.point, { layers: ['parcels-fill'] });
        if (parcelFeatures && parcelFeatures.length > 0) {
          clickedParcelId = parcelFeatures[0].properties.id;
        }
      }

      onNavigate('building', props.id, name, clickedParcelId);
      setPopupInfo({
        longitude: event.lngLat.lng,
        latitude: event.lngLat.lat,
        type: 'building',
        props,
      });
    } else if (layerId === 'parks-fill') {
      // Parse amenities back from stringified JSON
      let amenities = {};
      try { amenities = JSON.parse(props.amenities || '{}'); } catch {}
      setPopupInfo({
        longitude: event.lngLat.lng,
        latitude: event.lngLat.lat,
        type: 'park',
        props: { ...props, amenities },
      });
    } else if (layerId === 'pois-circle') {
      setPopupInfo({
        longitude: event.lngLat.lng,
        latitude: event.lngLat.lat,
        type: 'poi',
        props,
      });
    }
  }, [onNavigate]);

  // ── Hover handler (imperative DOM tooltip — no React re-renders) ──
  const onMouseMove = useCallback((event) => {
    const tip = tooltipRef.current;
    const features = event.features;
    if (!features || features.length === 0) {
      if (tip) tip.style.display = 'none';
      if (mapRef.current) mapRef.current.getCanvas().style.cursor = '';
      return;
    }

    if (mapRef.current) mapRef.current.getCanvas().style.cursor = 'pointer';

    const f = features[0];
    const layerId = f.layer.id;
    const props = f.properties;
    let label = '';

    if (layerId === 'subdivisions-fill') {
      label = props.name || 'Unknown';
    } else if (layerId === 'plats-fill') {
      label = `${props.name}${props.label ? ` (${props.label})` : ''}`;
    } else if (layerId === 'parcels-fill') {
      label = props.address || `Parcel ${props.id}`;
    } else if (layerId === 'addresses-circle') {
      label = props.fullAddress || 'Address';
    } else if (layerId === 'parks-fill') {
      label = props.name;
    } else if (layerId === 'pois-circle') {
      label = props.name;
    } else if (layerId === 'buildings-extrusion') {
      // Priority: POI name → Housing label (+ address) → Address → Class code
      const cls = BUILDING_CLASS_LABELS[props.class] || 'Building';
      if (props.name) {
        label = props.name;
      } else if (props.housingLabel) {
        label = props.address ? `${props.housingLabel} at\n${props.address}` : props.housingLabel;
      } else {
        label = props.address || cls;
      }
    }

    if (label && tip) {
      tip.textContent = label;
      tip.style.display = 'block';
      tip.style.left = `${event.point.x}px`;
      tip.style.top = `${event.point.y - 12}px`;
    }
  }, []);

  const onMouseLeave = useCallback(() => {
    if (tooltipRef.current) tooltipRef.current.style.display = 'none';
    if (mapRef.current) mapRef.current.getCanvas().style.cursor = '';
  }, []);

  // ── Fly to selection ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const key = selection ? `${selection.type}-${selection.id}` : null;
    if (key === lastSelectionKey.current) return;
    lastSelectionKey.current = key;
    if (!selection) return;

    const sources = {
      subdivision: subdivisions,
      plat: activeTile?.plats,
      parcel: activeTile?.parcels,
      building: activeTile?.buildings,
      address: activeTile?.addresses,
    };
    const src = sources[selection.type];
    if (!src) return;

    const feat = src.features.find(f => f.properties.id === selection.id);
    if (!feat) return;

    if (selection.type === 'address') {
      const [lng, lat] = feat.geometry.coordinates;
      map.flyTo({ center: [lng, lat], zoom: 18, duration: 800 });
      return;
    }

    // Compute bounds from feature geometry
    const coords = getAllCoordinates(feat.geometry);
    if (coords.length === 0) return;

    let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
    for (const [lng, lat] of coords) {
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
    }

    map.fitBounds(
      [[minLng, minLat], [maxLng, maxLat]],
      { padding: 50, duration: 800, maxZoom: 17 }
    );
  }, [selection, subdivisions, activeTile]);

  // Close popup when selection changes
  useEffect(() => {
    setPopupInfo(null);
  }, [selection?.type, selection?.id]);

  // ── WASD + QE + RF keyboard navigation (Cities Skylines style) ──
  useEffect(() => {
    const keysDown = new Set();
    const PAN_SPEED = 0.0004;   // degrees per frame (scales with zoom)
    const ROTATE_SPEED = 1.2;   // degrees per frame
    const ZOOM_SPEED = 0.06;    // zoom levels per frame
    let rafId = null;

    const tick = () => {
      const map = mapRef.current;
      if (!map || keysDown.size === 0) { rafId = null; return; }

      const bearing = map.getBearing() * (Math.PI / 180);
      const zoom = map.getZoom();
      const center = map.getCenter();
      // Pan distance scales inversely with zoom (zoomed in = smaller steps)
      const panDist = PAN_SPEED * Math.pow(2, 14 - zoom);

      let dx = 0, dy = 0, dBearing = 0, dZoom = 0;

      // WASD: pan relative to camera bearing
      if (keysDown.has('w') || keysDown.has('arrowup'))    dy += 1;
      if (keysDown.has('s') || keysDown.has('arrowdown'))  dy -= 1;
      if (keysDown.has('a') || keysDown.has('arrowleft'))  dx -= 1;
      if (keysDown.has('d') || keysDown.has('arrowright')) dx += 1;

      // Q/E: rotate
      if (keysDown.has('q')) dBearing -= ROTATE_SPEED;
      if (keysDown.has('e')) dBearing += ROTATE_SPEED;

      // R/F: zoom
      if (keysDown.has('r')) dZoom += ZOOM_SPEED;
      if (keysDown.has('f')) dZoom -= ZOOM_SPEED;

      if (dx !== 0 || dy !== 0) {
        // Rotate pan vector by current bearing so movement is camera-relative
        const sinB = Math.sin(-bearing);
        const cosB = Math.cos(-bearing);
        const worldDx = (dx * cosB - dy * sinB) * panDist;
        const worldDy = (dx * sinB + dy * cosB) * panDist;
        map.setCenter([center.lng + worldDx, center.lat + worldDy]);
      }
      if (dBearing !== 0) map.setBearing(map.getBearing() + dBearing);
      if (dZoom !== 0) map.setZoom(Math.max(1, Math.min(20, zoom + dZoom)));

      rafId = requestAnimationFrame(tick);
    };

    const onKeyDown = (e) => {
      // Don't capture when typing in inputs
      const tag = e.target.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      const key = e.key.toLowerCase();
      if (['w', 'a', 's', 'd', 'q', 'e', 'r', 'f', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(key)) {
        e.preventDefault();
        keysDown.add(key);
        if (!rafId) rafId = requestAnimationFrame(tick);
      }
    };

    const onKeyUp = (e) => {
      keysDown.delete(e.key.toLowerCase());
    };

    // Clear keys if window loses focus
    const onBlur = () => keysDown.clear();

    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    window.addEventListener('blur', onBlur);

    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
      window.removeEventListener('blur', onBlur);
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, []);

  const isDrilledDown = !!activeSubdivisionId;

  return (
    <div className="map-container">
      <Map
        ref={mapRef}
        initialViewState={{
          longitude: -111.9,
          latitude: 40.35,
          zoom: 12,
          pitch: 45,
          bearing: -15,
        }}
        style={{ width: '100%', height: '100%' }}
        mapStyle={{
          version: 8,
          sources: {
            'carto-dark': {
              type: 'raster',
              tiles: [
                'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
                'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
                'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
              ],
              tileSize: 256,
              attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
            },
          },
          layers: [
            {
              id: 'carto-dark-layer',
              type: 'raster',
              source: 'carto-dark',
              minzoom: 0,
              maxzoom: 20,
            },
          ],
        }}
        interactiveLayerIds={interactiveLayerIds}
        onClick={onClick}
        onMouseMove={onMouseMove}
        onMouseLeave={onMouseLeave}
      >
        <NavigationControl position="top-left" showCompass visualizePitch />

        {/* ── Roads ── */}
        {roads && (
          <Source id="roads" type="geojson" data={roads}>
            <Layer
              id="roads-line"
              type="line"
              paint={{
                'line-color': 'rgba(148, 153, 179, 0.35)',
                'line-width': 1,
              }}
            />
          </Source>
        )}

        {/* ── Paths ── */}
        {paths && showPaths && (
          <Source id="paths" type="geojson" data={paths}>
            <Layer
              id="paths-line"
              type="line"
              paint={{
                'line-color': '#fb923c',
                'line-width': 1.5,
                'line-opacity': 0.7,
                'line-dasharray': [3, 2],
              }}
            />
          </Source>
        )}

        {/* ── Parks ── */}
        {parks && showParks && (
          <Source id="parks" type="geojson" data={parks}>
            <Layer
              id="parks-fill"
              type="fill"
              paint={{
                'fill-color': '#10b981',
                'fill-opacity': 0.15,
              }}
            />
            <Layer
              id="parks-outline"
              type="line"
              paint={{
                'line-color': '#059669',
                'line-width': 1.5,
              }}
            />
          </Source>
        )}

        {/* ═══ Hierarchy layers (bottom → top): City → Subdivision → Plat → Parcel → Building → Address ═══ */}

        {/* ── Address Heatmap ── */}
        {residentialAddresses && showHeatmap && (
          <Source id="address-heatmap" type="geojson" data={residentialAddresses}>
            <Layer
              id="address-heatmap-layer"
              type="heatmap"
              maxzoom={22}
              paint={{
                // Set weight low so a single house (1 point) is extremely faint
                'heatmap-weight': 0.02,
                'heatmap-intensity': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  11, 0.4,
                  14, 2,
                  16, 8,
                  19, 30
                ],
                'heatmap-color': [
                  'interpolate',
                  ['linear'],
                  ['heatmap-density'],
                  0, 'rgba(33,102,172,0)',
                  0.1, 'rgba(103,169,207,0.05)',  // Faint blue for isolated single-family
                  0.3, 'rgb(103,169,207)',          // Light blue for small townhome groups
                  0.5, 'rgb(209,229,240)',          // Soft gray/white for medium townhomes
                  0.7, 'rgb(253,219,199)',          // Peach for high density townhomes
                  0.85, 'rgb(239,138,98)',         // Orange for small apartment groups
                  1.0, 'rgb(178,24,43)'             // Red for large apartment complexes
                ],
                'heatmap-radius': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  11, 12,
                  14, 22,
                  16, 45,
                  19, 90
                ],
                'heatmap-opacity': 0.8
              }}
            />
          </Source>
        )}

        {/* ── City Boundary (broadest, renders lowest) ── */}
        {cityBoundary && (
          <Source id="city-boundary" type="geojson" data={cityBoundary}>
            <Layer
              id="city-boundary-line"
              type="line"
              paint={{
                'line-color': '#fb7185',
                'line-width': 2.5,
                'line-dasharray': [4, 2],
              }}
            />
          </Source>
        )}

        {/* ── Subdivisions ── */}
        {coloredSubdivisions && (
          <Source id="subdivisions" type="geojson" data={coloredSubdivisions}>
            <Layer
              id="subdivisions-fill"
              type="fill"
              paint={{
                'fill-color': ['get', '_color'],
                'fill-opacity': isDrilledDown
                  ? 0.03
                  : [
                      'case',
                      ['==', ['get', '_isActive'], 1], 0.25,
                      0.12,
                    ],
              }}
            />
            <Layer
              id="subdivisions-outline"
              type="line"
              layout={{
                ...(isDrilledDown ? { 'line-cap': 'butt' } : {}),
              }}
              paint={{
                'line-color': ['get', '_color'],
                'line-width': isDrilledDown
                  ? 2
                  : [
                      'case',
                      ['==', ['get', '_isActive'], 1], 3,
                      1.5,
                    ],
                ...(isDrilledDown ? { 'line-dasharray': [2, 2] } : {}),
              }}
            />
          </Source>
        )}

        {/* ── Plats ── */}
        {showPlats && (
          <Source id="plats" type="geojson" data={activeTile.plats}>
            <Layer
              id="plats-fill"
              type="fill"
              paint={{
                'fill-color': '#a78bfa',
                'fill-opacity': [
                  'case',
                  ['==', ['get', 'id'], selection?.platId ?? ''],  0.3,
                  0.15,
                ],
              }}
            />
            <Layer
              id="plats-outline"
              type="line"
              paint={{
                'line-color': '#a78bfa',
                'line-width': [
                  'case',
                  ['==', ['get', 'id'], selection?.platId ?? ''], 2.5,
                  1.2,
                ],
              }}
            />
          </Source>
        )}

        {/* ── Parcels ── */}
        {showParcels && filteredParcels?.features?.length > 0 && (
          <Source id="parcels" type="geojson" data={filteredParcels}>
            <Layer
              id="parcels-fill"
              type="fill"
              paint={{
                'fill-color': '#2dd4bf',
                'fill-opacity': [
                  'case',
                  ['==', ['get', 'id'], selection?.parcelId ?? ''], 0.3,
                  0.12,
                ],
              }}
            />
            <Layer
              id="parcels-outline"
              type="line"
              paint={{
                'line-color': '#2dd4bf',
                'line-width': [
                  'case',
                  ['==', ['get', 'id'], selection?.parcelId ?? ''], 2,
                  0.8,
                ],
              }}
            />
          </Source>
        )}

        {/* ── 3D Buildings ── */}
        {displayBuildings && (
          <Source id="buildings" type="geojson" data={displayBuildings}>
            <Layer
              id="buildings-extrusion"
              type="fill-extrusion"
              paint={{
                'fill-extrusion-color': [
                  'case',
                  ['==', ['get', 'id'], selection?.buildingId ?? ''], '#00f0ff', // Highlight selection
                  [
                    'match', ['get', 'class'],
                    1, '#34d399',    // Residential - green
                    2, '#c4a35a',    // Commercial - warm gold
                    3, '#a0a0a0',    // Industrial - neutral gray
                    4, '#7c8aff',    // Government - accent blue
                    7, '#d4a0ff',    // Religious - soft purple
                    8, '#6bc4a6',    // Education - soft teal
                    '#8899aa',       // Default
                  ]
                ],
                'fill-extrusion-height': ['get', 'height'],
                'fill-extrusion-base': 0,
                'fill-extrusion-opacity': 0.75,
              }}
            />
          </Source>
        )}

        {/* ── Addresses (most granular, renders highest) ── */}
        {showAddresses && filteredAddresses?.features?.length > 0 && (
          <Source id="addresses" type="geojson" data={filteredAddresses}>
            <Layer
              id="addresses-circle"
              type="circle"
              paint={{
                'circle-radius': [
                  'case',
                  ['==', ['get', 'id'], selection?.type === 'address' ? (selection?.id ?? '') : ''], 8,
                  5,
                ],
                'circle-color': '#fbbf24',
                'circle-opacity': [
                  'case',
                  ['==', ['get', 'id'], selection?.type === 'address' ? (selection?.id ?? '') : ''], 1,
                  0.8,
                ],
                'circle-stroke-color': [
                  'case',
                  ['==', ['get', 'id'], selection?.type === 'address' ? (selection?.id ?? '') : ''], '#fff',
                  '#f59e0b',
                ],
                'circle-stroke-width': [
                  'case',
                  ['==', ['get', 'id'], selection?.type === 'address' ? (selection?.id ?? '') : ''], 2,
                  1,
                ],
              }}
            />
          </Source>
        )}

        {/* ── POIs (overlay, always on top) ── */}
        {coloredPois && showPois && (
          <Source id="pois" type="geojson" data={coloredPois}>
            <Layer
              id="pois-circle"
              type="circle"
              paint={{
                'circle-radius': 6,
                'circle-color': ['get', '_color'],
                'circle-opacity': 0.85,
                'circle-stroke-color': '#fff',
                'circle-stroke-width': 1,
              }}
            />
          </Source>
        )}

        {/* Hover tooltip is rendered imperatively via tooltipRef — no React Popup here */}

        {/* ── Click Popup ── */}
        {popupInfo && (
          <Popup
            longitude={popupInfo.longitude}
            latitude={popupInfo.latitude}
            closeOnClick={false}
            onClose={() => setPopupInfo(null)}
            anchor="bottom"
            offset={16}
            className="click-popup"
          >
            <PopupContent info={popupInfo} />
          </Popup>
        )}
      </Map>

      {/* Imperative hover tooltip — positioned via DOM, never causes React re-renders */}
      <div ref={tooltipRef} className="map-hover-tooltip" />

      {/* Layer control panel */}
      <div
        className="map-layers-toggle"
        onClick={(e) => e.stopPropagation()}
        onDoubleClick={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.stopPropagation()}
        onWheel={(e) => e.stopPropagation()}
      >
        <div className="map-layers-toggle__title">Overlays</div>
        <label className="map-layers-toggle__item">
          <input type="checkbox" className="map-layers-toggle__checkbox" checked={showParks} onChange={(e) => setShowParks(e.target.checked)} />
          <span>Parks</span>
        </label>
        <label className="map-layers-toggle__item">
          <input type="checkbox" className="map-layers-toggle__checkbox" checked={showPaths} onChange={(e) => setShowPaths(e.target.checked)} />
          <span>Paths</span>
        </label>
        <label className="map-layers-toggle__item">
          <input type="checkbox" className="map-layers-toggle__checkbox" checked={showPois} onChange={(e) => setShowPois(e.target.checked)} />
          <span>POIs</span>
        </label>
        <label className="map-layers-toggle__item">
          <input type="checkbox" className="map-layers-toggle__checkbox" checked={showBuildings} onChange={(e) => setShowBuildings(e.target.checked)} />
          <span>Buildings 3D</span>
        </label>
        <label className="map-layers-toggle__item">
          <input type="checkbox" className="map-layers-toggle__checkbox" checked={showHeatmap} onChange={(e) => setShowHeatmap(e.target.checked)} />
          <span>Address Heatmap</span>
        </label>
      </div>

      {/* MapLegend removed by request */}
    </div>
  );
}

// ── Popup content renderer ────────────────────────────────────────────────

function PopupContent({ info }) {
  const { type, props } = info;

  if (type === 'address') {
    return (
      <div className="popup-content">
        <strong>{props.fullAddress}</strong>
        <div className="popup-content__meta">{props.city} {props.zipCode}</div>
        <div className="popup-content__detail">{props.structureType} · {props.pointType}</div>
      </div>
    );
  }

  if (type === 'park') {
    const amenitiesList = Object.entries(props.amenities || {})
      .filter(([, v]) => v)
      .map(([k]) => k.charAt(0).toUpperCase() + k.slice(1))
      .join(', ');

    return (
      <div className="popup-content">
        <h4 className="popup-content__park-name">{props.name}</h4>
        {props.address && <div className="popup-content__meta">{props.address}</div>}
        <div className="popup-content__detail-grid">
          {props.acres && <div><strong>Acres:</strong> {props.acres}</div>}
          {props.status && <div><strong>Status:</strong> {props.status}</div>}
          {amenitiesList && <div className="popup-content__amenities"><strong>Amenities:</strong> {amenitiesList}</div>}
        </div>
      </div>
    );
  }

  if (type === 'poi') {
    const catFormatted = (props.category || '').replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
    return (
      <div className="popup-content">
        <span className="popup-content__poi-category">{catFormatted}</span>
        <h4 className="popup-content__poi-name">{props.name}</h4>
        {props.address && <div className="popup-content__meta">{props.address}</div>}
        {props.details && <div className="popup-content__detail">{props.details}</div>}
      </div>
    );
  }

  return null;
}



// ── Helpers ────────────────────────────────────────────────────────────────

/** Recursively extract all [lng, lat] coordinates from a GeoJSON geometry. */
function getAllCoordinates(geometry) {
  if (!geometry) return [];
  const { type, coordinates } = geometry;
  if (type === 'Point') return [coordinates];
  if (type === 'MultiPoint' || type === 'LineString') return coordinates;
  if (type === 'MultiLineString' || type === 'Polygon') return coordinates.flat();
  if (type === 'MultiPolygon') return coordinates.flat(2);
  if (type === 'GeometryCollection') return geometry.geometries.flatMap(getAllCoordinates);
  return [];
}
