import { useEffect, useRef, useState, useCallback } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

import { CATEGORIES, getLayerIds, getAllInteractiveLayerIds } from './config/layers';
import { getFeatureName, getFeatureDescription, flyToFeature, loadGeoJSON } from './utils/mapHelpers';
import './App.css';

// ---------- Mapbox token ----------
mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN || '';

// ---------- Constants ----------
const UTAH_CENTER = [-111.65, 39.32];
const UTAH_ZOOM = 6.2;
const FADE_DURATION = 400; // ms for layer fade transitions

export default function App() {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);
  const popupRef = useRef(null);
  const [activeCategory, setActiveCategory] = useState('recreation');
  const [mapLoaded, setMapLoaded] = useState(false);
  const [popupData, setPopupData] = useState(null); // { lng, lat, name, details }
  const [sublayerState, setSublayerState] = useState(() => {
    // Initialize sublayer visibility from config defaults
    const state = {};
    for (const [catKey, cat] of Object.entries(CATEGORIES)) {
      if (cat.sublayers) {
        for (const sl of cat.sublayers) {
          state[sl.id] = sl.defaultOn;
        }
      }
    }
    return state;
  });

  // ---- Initialize the map ----
  useEffect(() => {
    if (mapRef.current) return;

    const map = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/dark-v11',
      center: UTAH_CENTER,
      zoom: UTAH_ZOOM,
      pitch: 0,
      bearing: 0,
      antialias: true,
    });

    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'bottom-right');

    map.on('load', async () => {
      mapRef.current = map;

      // Add Utah mask — dark fill covering everything outside Utah
      // Rendered FIRST so it sits below all data layers
      const maskData = await loadGeoJSON('/data/utah_mask.geojson');
      if (maskData) {
        map.addSource('utah-mask', { type: 'geojson', data: maskData });
        map.addLayer({
          id: 'utah-mask-fill',
          type: 'fill',
          source: 'utah-mask',
          paint: {
            'fill-color': '#0f1117',
            'fill-opacity': 0.92,
          },
        });
      }

      // Load all GeoJSON sources and add layers (on top of mask)
      for (const [catKey, catConfig] of Object.entries(CATEGORIES)) {
        for (const source of catConfig.sources) {
          const data = await loadGeoJSON(source.url);
          if (!data) continue;

          map.addSource(source.id, { type: 'geojson', data });

          for (const layer of source.layers) {
            map.addLayer({
              id: layer.id,
              type: layer.type,
              source: source.id,
              ...(layer.filter ? { filter: layer.filter } : {}),
              paint: layer.paint,
              layout: {
                ...(layer.layout || {}),
                visibility: catKey === 'recreation' ? 'visible' : 'none',
              },
            });
          }
        }
      }

      // Add 3D terrain (DEM source + dramatic sky + hillshade)
      map.addSource('mapbox-dem', {
        type: 'raster-dem',
        url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
        tileSize: 512,
        maxzoom: 14,
      });
      map.setTerrain({ source: 'mapbox-dem', exaggeration: 2.5 });

      // Dramatic sky — golden hour sun
      map.addLayer({
        id: 'sky',
        type: 'sky',
        paint: {
          'sky-type': 'atmosphere',
          'sky-atmosphere-sun': [200, 75],
          'sky-atmosphere-sun-intensity': 20,
          'sky-atmosphere-color': 'rgba(135, 206, 235, 0.6)',
          'sky-atmosphere-halo-color': 'rgba(255, 183, 77, 0.4)',
        },
      });

      // Hillshade for dramatic depth and shadow
      map.addSource('hillshade-dem', {
        type: 'raster-dem',
        url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
        tileSize: 512,
        maxzoom: 14,
      });
      map.addLayer(
        {
          id: 'hillshade',
          type: 'hillshade',
          source: 'hillshade-dem',
          paint: {
            'hillshade-exaggeration': 0.6,
            'hillshade-shadow-color': '#1a1a2e',
            'hillshade-highlight-color': '#ffecd2',
            'hillshade-illumination-direction': 335,
            'hillshade-illumination-anchor': 'viewport',
          },
        },
        // Insert hillshade below the mask
        'utah-mask-fill'
      );

      // Start with top-down view
      map.flyTo({
        center: UTAH_CENTER,
        zoom: UTAH_ZOOM,
        pitch: 0,
        bearing: 0,
        duration: 2000,
      });

      setMapLoaded(true);
    });

    return () => map.remove();
  }, []);

  // ---- Toggle category visibility with fade ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    // Toggle 3D terrain + hillshade + sky for recreation only
    if (activeCategory === 'recreation') {
      map.setTerrain({ source: 'mapbox-dem', exaggeration: 2.5 });
      if (map.getLayer('hillshade')) map.setLayoutProperty('hillshade', 'visibility', 'visible');
      if (map.getLayer('sky')) map.setLayoutProperty('sky', 'visibility', 'visible');
    } else {
      map.setTerrain(null);
      if (map.getLayer('hillshade')) map.setLayoutProperty('hillshade', 'visibility', 'none');
      if (map.getLayer('sky')) map.setLayoutProperty('sky', 'visibility', 'none');
      map.easeTo({ pitch: 0, bearing: 0, duration: 800 });
    }

    // Reset all sublayer toggles to "on" when switching categories
    setSublayerState((prev) => {
      const reset = { ...prev };
      for (const cat of Object.values(CATEGORIES)) {
        if (cat.sublayers) {
          for (const sl of cat.sublayers) {
            reset[sl.id] = true;
          }
        }
      }
      return reset;
    });

    for (const [catKey, catConfig] of Object.entries(CATEGORIES)) {
      const layerIds = getLayerIds(catKey);
      const isActive = catKey === activeCategory;

      for (const lid of layerIds) {
        if (!map.getLayer(lid)) continue;

        if (isActive) {
          // Show: set visible then fade opacity in
          map.setLayoutProperty(lid, 'visibility', 'visible');
          const layerDef = catConfig.sources
            .flatMap((s) => s.layers)
            .find((l) => l.id === lid);
          if (layerDef) {
            const opacityProp = getOpacityProperty(layerDef.type);
            const targetOpacity = layerDef.paint[opacityProp] ?? 1;
            // Start from 0 and transition
            map.setPaintProperty(lid, opacityProp, 0);
            setTimeout(() => {
              map.setPaintProperty(lid, opacityProp, targetOpacity, {
                duration: FADE_DURATION,
              });
            }, 30);
          }
        } else {
          // Hide: fade out then set invisible
          const layerDef = catConfig.sources
            .flatMap((s) => s.layers)
            .find((l) => l.id === lid);
          if (layerDef) {
            const opacityProp = getOpacityProperty(layerDef.type);
            map.setPaintProperty(lid, opacityProp, 0);
            setTimeout(() => {
              map.setLayoutProperty(lid, 'visibility', 'none');
            }, FADE_DURATION + 50);
          }
        }
      }
    }

    // Close popup when switching categories
    setPopupData(null);
  }, [activeCategory, mapLoaded]);

  // ---- Interactive hover & click ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    const allInteractive = getAllInteractiveLayerIds();

    // Hover: pointer cursor
    const onMouseEnter = () => {
      map.getCanvas().style.cursor = 'pointer';
    };
    const onMouseLeave = () => {
      map.getCanvas().style.cursor = '';
    };

    // Click: show popup immediately and fly to feature
    let clickedFeature = false; // flag to prevent map-level click from closing popup

    const onClick = (e) => {
      if (!e.features || e.features.length === 0) return;

      clickedFeature = true; // mark that a feature was clicked

      const feature = e.features[0];
      const props = feature.properties;
      const name = getFeatureName(props);
      const details = getFeatureDescription(props, activeCategory);
      const lngLat = e.lngLat;

      // Show popup immediately
      setPopupData({
        lng: lngLat.lng,
        lat: lngLat.lat,
        name,
        details,
        category: activeCategory,
      });

      // Fly to the feature (popup persists through animation)
      flyToFeature(map, feature);
    };

    for (const lid of allInteractive) {
      if (!map.getLayer(lid)) continue;
      map.on('mouseenter', lid, onMouseEnter);
      map.on('mouseleave', lid, onMouseLeave);
      map.on('click', lid, onClick);
    }

    // Click outside features to close popup (but not when a feature was just clicked)
    const onMapClick = () => {
      if (clickedFeature) {
        clickedFeature = false;
        return;
      }
      setPopupData(null);
    };
    map.on('click', onMapClick);

    return () => {
      for (const lid of allInteractive) {
        if (!map.getLayer(lid)) continue;
        map.off('mouseenter', lid, onMouseEnter);
        map.off('mouseleave', lid, onMouseLeave);
        map.off('click', lid, onClick);
      }
      map.off('click', onMapClick);
    };
  }, [mapLoaded, activeCategory]);

  // ---- Mapbox popup sync ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Remove existing popup — detach close listener first to avoid wiping new popupData
    if (popupRef.current) {
      popupRef.current.off('close', popupRef.current._onCloseHandler);
      popupRef.current.remove();
      popupRef.current = null;
    }

    if (!popupData) return;

    const detailsHtml = popupData.details
      .map(
        (d) =>
          `<div class="popup-detail">${d.label ? `<span class="popup-label">${d.label}:</span> ` : ''}${d.value}</div>`
      )
      .join('');

    const categoryIcon = CATEGORIES[activeCategory]?.icon || '📍';

    const html = `
      <div class="popup-card">
        <div class="popup-header">
          <span class="popup-icon">${categoryIcon}</span>
          <span class="popup-name">${popupData.name}</span>
        </div>
        <div class="popup-body">${detailsHtml}</div>
      </div>
    `;

    const popup = new mapboxgl.Popup({
      closeButton: true,
      closeOnClick: false,
      closeOnMove: false,
      maxWidth: '280px',
      className: 'explore-popup',
      offset: 12,
    })
      .setLngLat([popupData.lng, popupData.lat])
      .setHTML(html)
      .addTo(map);

    // Named handler so we can detach it before programmatic removal
    const onClose = () => setPopupData(null);
    popup._onCloseHandler = onClose;
    popup.on('close', onClose);
    popupRef.current = popup;

    return () => {
      if (popupRef.current) {
        popupRef.current.off('close', popupRef.current._onCloseHandler);
        popupRef.current.remove();
        popupRef.current = null;
      }
    };
  }, [popupData, activeCategory]);

  // ---- Reset view ----
  const handleReset = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    map.flyTo({
      center: UTAH_CENTER,
      zoom: UTAH_ZOOM,
      duration: 1200,
    });
    setPopupData(null);
  }, []);

  // ---- Toggle individual sublayers ----
  const handleSublayerToggle = useCallback((sublayerId) => {
    const map = mapRef.current;
    if (!map) return;

    setSublayerState((prev) => {
      const newState = { ...prev, [sublayerId]: !prev[sublayerId] };
      const visible = newState[sublayerId] ? 'visible' : 'none';

      // Find all layers matching this sublayer
      // Check source-level sublayerGroup OR layer-level sublayerGroup
      for (const cat of Object.values(CATEGORIES)) {
        for (const source of cat.sources) {
          const sourceMatch = source.id === sublayerId || source.sublayerGroup === sublayerId;
          for (const layer of source.layers) {
            const layerMatch = layer.sublayerGroup === sublayerId;
            if ((sourceMatch || layerMatch) && map.getLayer(layer.id)) {
              // If layer has its own sublayerGroup, only toggle if it matches
              if (layer.sublayerGroup && !layerMatch) continue;
              map.setLayoutProperty(layer.id, 'visibility', visible);
            }
          }
        }
      }

      return newState;
    });
  }, []);

  return (
    <div className="app">
      {/* Map container */}
      <div ref={mapContainer} className="map-container" />

      {/* Header bar */}
      <header className="header">
        <h1 className="title" onClick={handleReset}>
          Explore Utah
        </h1>

        <div className="menu-column">
          <nav className="category-toggle" role="tablist">
            {Object.entries(CATEGORIES).map(([key, config]) => (
              <button
                key={key}
                role="tab"
                aria-selected={activeCategory === key}
                className={`category-btn ${activeCategory === key ? 'active' : ''}`}
                onClick={() => setActiveCategory(key)}
              >
                <span className="btn-icon">{config.icon}</span>
                <span className="btn-label">{config.label}</span>
              </button>
            ))}
          </nav>

          {/* Sublayer toggles for categories that support them */}
          {CATEGORIES[activeCategory]?.sublayers && (
            <div className="sublayer-panel">
              {CATEGORIES[activeCategory].sublayers.map((sl) => (
                <button
                  key={sl.id}
                  className={`sublayer-btn ${sublayerState[sl.id] ? 'on' : 'off'}`}
                  onClick={() => handleSublayerToggle(sl.id)}
                  style={{ '--sl-color': sl.color }}
                >
                  <span className="sublayer-dot" />
                  <span className="sublayer-label">{sl.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </header>

      {/* Loading overlay */}
      {!mapLoaded && (
        <div className="loading-overlay">
          <div className="loading-spinner" />
          <p className="loading-text">Loading map…</p>
        </div>
      )}
    </div>
  );
}

/**
 * Map layer type → opacity property name for Mapbox GL.
 */
function getOpacityProperty(layerType) {
  switch (layerType) {
    case 'circle':
      return 'circle-opacity';
    case 'line':
      return 'line-opacity';
    case 'fill':
      return 'fill-opacity';
    case 'symbol':
      return 'text-opacity';
    default:
      return 'circle-opacity';
  }
}
