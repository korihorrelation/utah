import { useEffect, useRef, useMemo, useCallback, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap, CircleMarker, Popup, useMapEvents } from 'react-leaflet';
import { LAYER_STYLES, getSubdivisionColor } from '../lib/colors';
import 'leaflet/dist/leaflet.css';

/**
 * Interactive Leaflet map with drill-down polygon layers.
 *
 * Visibility rules:
 *   - No active subdivision → show all subdivision polygons (full color).
 *   - Active subdivision → show only that subdivision as a dashed outline,
 *     plus its plats. Clicking a plat reveals its parcels; clicking a parcel
 *     reveals its addresses.
 */
export default function MapView({
  cityBoundary,
  subdivisions,
  roads,
  paths,
  parks,
  pois,
  activeTile,
  activeSubdivisionId,
  selection,
  onNavigate,
}) {
  const center = [40.35, -111.9];
  const [showPaths, setShowPaths] = useState(true);
  const [showParks, setShowParks] = useState(true);
  const [showPois, setShowPois] = useState(false);

  // When drilled into a subdivision, show only that one as an outline.
  // Otherwise show all subdivisions with full styling.
  const subdivisionData = useMemo(() => {
    if (!subdivisions) return null;
    if (!activeSubdivisionId) return subdivisions;
    return {
      ...subdivisions,
      features: subdivisions.features.filter(f => f.properties.id === activeSubdivisionId),
    };
  }, [subdivisions, activeSubdivisionId]);

  return (
    <div className="map-container">
      <MapContainer
        center={center}
        zoom={12}
        style={{ width: '100%', height: '100%' }}
        zoomControl={true}
        attributionControl={true}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>'
          maxZoom={19}
        />

        {/* City Boundary */}
        {cityBoundary && <GeoJSON data={cityBoundary} style={LAYER_STYLES.cityBoundary} />}

        {/* Roads & Paths (subtle) */}
        {roads && <GeoJSON data={roads} style={LAYER_STYLES.road} />}
        {paths && showPaths && <GeoJSON data={paths} style={LAYER_STYLES.path} />}

        {/* Parks & POIs (toggleable overlays) */}
        {parks && showParks && <ParksLayer data={parks} />}
        {pois && showPois && <PoisLayer data={pois} />}

        {/* Subdivision polygons */}
        {/* Subdivision polygons */}
        {subdivisionData && (
          <SubdivisionLayer
            data={subdivisionData}
            activeSubdivisionId={activeSubdivisionId}
            selection={selection}
            onNavigate={onNavigate}
          />
        )}

        {/* Drill-down layers: plats → parcels → addresses */}
        {activeTile && (
          <DrillDownLayers tile={activeTile} selection={selection} onNavigate={onNavigate} />
        )}

        {/* Fly to selection */}
        <FlyToSelection selection={selection} subdivisions={subdivisions} activeTile={activeTile} />

        {/* Click outside boundaries to reset */}
        <MapClickHandler onMapClick={() => onNavigate('city', 'root', 'Saratoga Springs')} />
      </MapContainer>

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
          <input
            type="checkbox"
            className="map-layers-toggle__checkbox"
            checked={showParks}
            onChange={(e) => setShowParks(e.target.checked)}
          />
          <span>Parks</span>
        </label>
        <label className="map-layers-toggle__item">
          <input
            type="checkbox"
            className="map-layers-toggle__checkbox"
            checked={showPaths}
            onChange={(e) => setShowPaths(e.target.checked)}
          />
          <span>Paths</span>
        </label>
        <label className="map-layers-toggle__item">
          <input
            type="checkbox"
            className="map-layers-toggle__checkbox"
            checked={showPois}
            onChange={(e) => setShowPois(e.target.checked)}
          />
          <span>POIs</span>
        </label>
      </div>

      <MapLegend
        activeSubdivisionId={activeSubdivisionId}
        selection={selection}
        showParks={showParks}
        showPaths={showPaths}
        showPois={showPois}
      />
    </div>
  );
}

// ── Subdivision polygons ──────────────────────────────────────────────────

function SubdivisionLayer({ data, activeSubdivisionId, selection, onNavigate }) {
  const isDrilledDown = !!activeSubdivisionId;
  const isSubSelected = selection?.type === 'subdivision';

  const onEachFeature = useCallback((feature, layer) => {
    const props = feature.properties;
    layer.on('click', (e) => {
      if (e.originalEvent) e.originalEvent.stopPropagation();
      onNavigate('subdivision', props.id, props.name);
    });
    layer.bindTooltip(props.name || 'Unknown', { sticky: true, className: 'subdivision-tooltip' });
  }, [onNavigate]);

  const style = useCallback((feature) => {
    const type = feature.properties.type;
    const color = getSubdivisionColor(type);

    // When drilled down, show a subtle dashed outline.
    if (isDrilledDown) {
      return { color, weight: 2, fillColor: color, fillOpacity: 0.03, dashArray: '4, 4' };
    }
    // Full view: highlight selected, normal for others.
    if (isSubSelected && selection?.id === feature.properties.id) {
      return LAYER_STYLES.subdivisionHighlight(type);
    }
    return LAYER_STYLES.subdivision(type);
  }, [isDrilledDown, isSubSelected, selection?.id]);

  // Key includes activeSubdivisionId so the GeoJSON layer remounts whenever
  // the underlying polygon data changes (react-leaflet GeoJSON ignores prop updates).
  const key = `subdiv-${activeSubdivisionId ?? 'all'}-${isSubSelected ? selection?.id : 'none'}`;

  return <GeoJSON key={key} data={data} style={style} onEachFeature={onEachFeature} bubblingMouseEvents={false} />;
}

// ── Drill-down layers ─────────────────────────────────────────────────────

function DrillDownLayers({ tile, selection, onNavigate }) {
  // Plats: always visible when drilled into a subdivision.
  // Parcels: visible when a plat is selected (or deeper).
  // Addresses: visible when a parcel is selected (or deeper).
  const depth = DEPTH[selection?.type] ?? 0;
  const showParcels = depth >= 2;
  const showAddresses = depth >= 3;

  return (
    <>
      {/* Plat polygons */}
      {tile.plats?.features.length > 0 && (
        <PlatLayer plats={tile.plats} selection={selection} onNavigate={onNavigate} />
      )}

      {/* Parcel polygons — scoped to selected plat */}
      {showParcels && tile.parcels?.features.length > 0 && (
        <ParcelLayer parcels={tile.parcels} selection={selection} onNavigate={onNavigate} />
      )}

      {/* Address points — scoped to selected parcel */}
      {showAddresses && tile.addresses?.features.length > 0 && (
        <AddressLayer addresses={tile.addresses} selection={selection} onNavigate={onNavigate} />
      )}
    </>
  );
}

const DEPTH = { subdivision: 1, plat: 2, parcel: 3, address: 4 };

// ── Plat layer ────────────────────────────────────────────────────────────

function PlatLayer({ plats, selection, onNavigate }) {
  const onEachFeature = useCallback((feature, layer) => {
    const props = feature.properties;
    layer.on('click', (e) => {
      if (e.originalEvent) e.originalEvent.stopPropagation();
      onNavigate('plat', props.id, props.name);
    });
    layer.bindTooltip(`${props.name}${props.label ? ` (${props.label})` : ''}`, { sticky: true });
  }, [onNavigate]);

  const style = useCallback((feature) => {
    const isActive = selection?.platId === feature.properties.id;
    return isActive ? LAYER_STYLES.platHighlight : LAYER_STYLES.plat;
  }, [selection?.platId]);

  const key = `plats-${selection?.subdivisionId}-${selection?.platId ?? 'none'}`;
  return <GeoJSON key={key} data={plats} style={style} onEachFeature={onEachFeature} bubblingMouseEvents={false} />;
}

// ── Parcel layer ──────────────────────────────────────────────────────────

function ParcelLayer({ parcels, selection, onNavigate }) {
  const filtered = useMemo(() => {
    if (!selection?.platId) return parcels;
    return { ...parcels, features: parcels.features.filter(f => f.properties.platId === selection.platId) };
  }, [parcels, selection?.platId]);

  const onEachFeature = useCallback((feature, layer) => {
    const props = feature.properties;
    layer.on('click', (e) => {
      if (e.originalEvent) e.originalEvent.stopPropagation();
      onNavigate('parcel', props.id, props.address || `Parcel ${props.id}`);
    });
    layer.bindTooltip(props.address || `Parcel ${props.id}`, { sticky: true });
  }, [onNavigate]);

  const style = useCallback((feature) => {
    const isActive = selection?.parcelId === feature.properties.id;
    return isActive ? LAYER_STYLES.parcelHighlight : LAYER_STYLES.parcel;
  }, [selection?.parcelId]);

  if (filtered.features.length === 0) return null;
  const key = `parcels-${selection?.platId}-${selection?.parcelId ?? 'none'}`;
  return <GeoJSON key={key} data={filtered} style={style} onEachFeature={onEachFeature} bubblingMouseEvents={false} />;
}

// ── Address layer ─────────────────────────────────────────────────────────

function AddressLayer({ addresses, selection, onNavigate }) {
  const filtered = useMemo(() => {
    if (!selection?.parcelId) return addresses;
    return { ...addresses, features: addresses.features.filter(f => f.properties.parcelId === selection.parcelId) };
  }, [addresses, selection?.parcelId]);

  if (filtered.features.length === 0) return null;

  return (
    <>
      {filtered.features.map((feature, i) => {
        const [lng, lat] = feature.geometry.coordinates;
        const props = feature.properties;
        const isActive = selection?.type === 'address' && selection?.id === props.id;

        return (
          <CircleMarker
            key={props.id || i}
            center={[lat, lng]}
            radius={isActive ? 8 : 5}
            fillColor="#fbbf24"
            fillOpacity={isActive ? 1 : 0.8}
            color={isActive ? '#fff' : '#f59e0b'}
            weight={isActive ? 2 : 1}
            bubblingMouseEvents={false}
            eventHandlers={{
              click: (e) => {
                if (e.originalEvent) e.originalEvent.stopPropagation();
                onNavigate('address', props.id, props.fullAddress || 'Address');
              }
            }}
          >
            <Popup>
              <div style={{ fontFamily: 'Inter, sans-serif' }}>
                <strong>{props.fullAddress}</strong><br />
                {props.city} {props.zipCode}<br />
                <span style={{ color: '#9499b3', fontSize: '12px' }}>
                  {props.structureType} &middot; {props.pointType}
                </span>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </>
  );
}

// ── Fly to selection ──────────────────────────────────────────────────────

function FlyToSelection({ selection, subdivisions, activeTile }) {
  const map = useMap();
  const lastKeyRef = useRef(null);

  useEffect(() => {
    const key = selection ? `${selection.type}-${selection.id}` : null;
    if (key === lastKeyRef.current) return;
    lastKeyRef.current = key;
    if (!selection) return;

    let bounds = null;
    const L = require('leaflet');

    const sources = {
      subdivision: subdivisions,
      plat: activeTile?.plats,
      parcel: activeTile?.parcels,
      address: activeTile?.addresses,
    };
    const src = sources[selection.type];
    if (!src) return;

    const feat = src.features.find(f => f.properties.id === selection.id);
    if (!feat) return;

    if (selection.type === 'address') {
      const [lng, lat] = feat.geometry.coordinates;
      map.flyTo([lat, lng], 18, { duration: 0.8 });
      return;
    }

    bounds = L.geoJSON(feat).getBounds();
    if (bounds?.isValid()) {
      map.flyToBounds(bounds, { padding: [50, 50], duration: 0.8, maxZoom: 17 });
    }
  }, [selection, subdivisions, activeTile, map]);

  return null;
}

// ── Map legend ────────────────────────────────────────────────────────────

function MapLegend({ activeSubdivisionId, selection, showParks, showPaths, showPois }) {
  const depth = DEPTH[selection?.type] ?? 0;

  return (
    <div 
      className="map-legend"
      onClick={(e) => e.stopPropagation()}
      onDoubleClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
      onWheel={(e) => e.stopPropagation()}
    >
      <div className="map-legend__title">Zoning & Layers</div>

      <LegendItem color="#fb7185" border="1px dashed #fb7185" label="City Boundary" />
      <LegendItem color="rgba(16, 185, 129, 0.15)" border="1px solid #10b981" label="Residential" />
      <LegendItem color="rgba(37, 99, 235, 0.15)" border="1px solid #2563eb" label="Commercial" />
      <LegendItem color="rgba(6, 182, 212, 0.15)" border="1px solid #06b6d4" label="Mixed Use" />
      <LegendItem color="rgba(99, 102, 241, 0.15)" border="1px solid #6366f1" label="Civic / Public" />

      {activeSubdivisionId && (
        <LegendItem color="rgba(167, 139, 250, 0.3)" border="1px solid #a78bfa" label="Plats" />
      )}
      {depth >= 2 && (
        <LegendItem color="rgba(45, 212, 191, 0.3)" border="1px solid #2dd4bf" label="Parcels" />
      )}
      {depth >= 3 && (
        <LegendItem color="#fbbf24" border="none" label="Addresses" circle />
      )}

      <LegendItem color="rgba(148, 153, 179, 0.4)" label="Roads" line />
      
      {showPaths && (
        <LegendItem color="#fb923c" label="Paths" line />
      )}
      {showParks && (
        <LegendItem color="rgba(16, 185, 129, 0.15)" border="1px solid #059669" label="Parks" />
      )}
      {showPois && (
        <div style={{ borderTop: '1px solid var(--border-subtle)', marginTop: '8px', paddingTop: '8px' }}>
          <div className="map-legend__title" style={{ fontSize: '10px', marginBottom: '4px' }}>POI Groups</div>
          <LegendItem color="#a78bfa" border="none" label="Education" circle />
          <LegendItem color="#fb7185" border="none" label="Civic & Worship" circle />
          <LegendItem color="#fbbf24" border="none" label="Retail & Food" circle />
          <LegendItem color="#2dd4bf" border="none" label="Healthcare" circle />
          <LegendItem color="#9499b3" border="none" label="Other POIs" circle />
        </div>
      )}
    </div>
  );
}

function LegendItem({ color, border, label, line, circle }) {
  const cls = `map-legend__swatch${line ? ' map-legend__swatch--line' : ''}${circle ? ' map-legend__swatch--circle' : ''}`;
  return (
    <div className="map-legend__item">
      <span className={cls} style={{ background: color, border: border || 'none' }} />
      {label}
    </div>
  );
}

// ── Parks & POIs Layer Components ──────────────────────────────────────────

function ParksLayer({ data }) {
  const onEachFeature = useCallback((feature, layer) => {
    const props = feature.properties;
    const amenitiesList = Object.entries(props.amenities || {})
      .filter(([_, value]) => value)
      .map(([key]) => key.charAt(0).toUpperCase() + key.slice(1))
      .join(', ');

    const popupContent = `
      <div style="font-family: 'Inter', sans-serif; min-width: 200px; color: #e8eaf0;">
        <h4 style="margin: 0 0 6px 0; color: #34d399; font-weight: 600; font-size: 14px;">${props.name}</h4>
        ${props.address ? `<p style="margin: 0 0 8px 0; font-size: 11px; color: #9499b3;">${props.address}</p>` : ''}
        <div style="border-top: 1px solid rgba(148, 153, 179, 0.12); padding-top: 6px; font-size: 11px;">
          ${props.acres ? `<div style="margin-bottom: 4px;"><strong>Acres:</strong> ${props.acres}</div>` : ''}
          ${props.status ? `<div style="margin-bottom: 4px;"><strong>Status:</strong> ${props.status}</div>` : ''}
          ${amenitiesList ? `<div style="margin-top: 6px; color: #34d399;"><strong>Amenities:</strong> ${amenitiesList}</div>` : ''}
        </div>
      </div>
    `;

    layer.on('click', (e) => {
      if (e.originalEvent) e.originalEvent.stopPropagation();
    });
    layer.bindPopup(popupContent);
    layer.bindTooltip(props.name, { sticky: true, className: 'park-tooltip' });
  }, []);

  return <GeoJSON data={data} style={LAYER_STYLES.park} onEachFeature={onEachFeature} bubblingMouseEvents={false} />;
}

function PoisLayer({ data }) {
  const L = typeof window !== 'undefined' ? require('leaflet') : null;

  const pointToLayer = useCallback((feature, latlng) => {
    if (!L) return null;
    const group = feature.properties.group;
    let color = '#9499b3';
    
    if (group === 'education') color = '#a78bfa';
    else if (group === 'civic_community') color = '#fb7185';
    else if (group === 'retail_food') color = '#fbbf24';
    else if (group === 'healthcare') color = '#2dd4bf';

    return L.circleMarker(latlng, {
      radius: 6,
      fillColor: color,
      fillOpacity: 0.85,
      color: '#fff',
      weight: 1,
    });
  }, [L]);

  const onEachFeature = useCallback((feature, layer) => {
    const props = feature.properties;
    const catFormatted = props.category.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
    
    const popupContent = `
      <div style="font-family: 'Inter', sans-serif; min-width: 180px; color: #e8eaf0;">
        <span style="font-size: 9px; text-transform: uppercase; font-weight: 700; color: #7c8aff; display: inline-block; margin-bottom: 2px;">
          ${catFormatted}
        </span>
        <h4 style="margin: 0 0 6px 0; color: #e8eaf0; font-weight: 600; font-size: 13px;">${props.name}</h4>
        ${props.address ? `<p style="margin: 0 0 6px 0; font-size: 11px; color: #9499b3;">${props.address}</p>` : ''}
        ${props.details ? `
          <div style="border-top: 1px solid rgba(148, 153, 179, 0.12); padding-top: 6px; font-size: 10px; color: #9499b3;">
            ${props.details}
          </div>
        ` : ''}
      </div>
    `;

    layer.on('click', (e) => {
      if (e.originalEvent) e.originalEvent.stopPropagation();
    });
    layer.bindPopup(popupContent);
    layer.bindTooltip(props.name, { sticky: true });
  }, []);

  if (!L) return null;
  return <GeoJSON data={data} pointToLayer={pointToLayer} onEachFeature={onEachFeature} bubblingMouseEvents={false} />;
}

// ── Map Events handler for click outside reset ─────────────────────────────

function MapClickHandler({ onMapClick }) {
  useMapEvents({
    click() {
      onMapClick();
    },
  });
  return null;
}
