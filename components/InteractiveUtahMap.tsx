'use client';

import { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, Popup } from 'react-leaflet';
import type { Feature, FeatureCollection, Geometry } from 'geojson';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const metrics = [
  { id: 'total', label: '2024 Total Vote Estimate' },
  { id: 'President', label: '2024 President' },
  { id: 'U.S. Senate', label: '2024 U.S. Senate' },
  { id: 'Governor', label: '2024 Governor' },
  { id: 'Auditor', label: '2024 Auditor' },
  { id: 'Treasurer', label: '2024 Treasurer' },
  { id: 'Attorney General', label: '2024 Attorney General' },
];

const yearOrder = ['2016', '2018', '2020', '2022', '2024'];

function formatCount(value: number) {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value);
}

function getHazardColor(value: number) {
  if (value > 2800) return '#082567';
  if (value > 2200) return '#1f4cc8';
  if (value > 1600) return '#3b82f6';
  if (value > 1000) return '#60a5fa';
  if (value > 600) return '#93c5fd';
  if (value > 300) return '#bfdbfe';
  return '#e2e8f0';
}

function getMetricValue(feature: Feature<Geometry, any>, metric: string) {
  if (!feature || !feature.properties) return 0;
  const stats = feature.properties.voteStats;
  if (!stats) return 0;
  if (metric === 'total') {
    return stats.raceTotals?.['All races'] ?? stats.yearTotals?.['2024'] ?? 0;
  }
  return stats.raceTotals?.[metric] ?? 0;
}

export default function InteractiveUtahMap() {
  const [geoJson, setGeoJson] = useState<FeatureCollection<Geometry> | null>(null);
  const [selectedMetric, setSelectedMetric] = useState('total');
  const [hovered, setHovered] = useState<Feature<Geometry, any> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadGeoJson() {
      try {
        const response = await fetch('/data/utah-votes.geojson');
        const data = await response.json();
        setGeoJson(data);
      } catch (error) {
        console.error('Unable to load map data', error);
      } finally {
        setLoading(false);
      }
    }

    loadGeoJson();
  }, []);

  const chartData = useMemo(() => {
    if (!hovered) return [];
    const totals = hovered.properties?.voteStats?.yearTotals ?? {};
    return yearOrder.map((year) => ({ year, value: totals[year] ?? 0 }));
  }, [hovered]);

  const highlightedText = hovered?.properties?.displayName || 'Hover over a precinct';
  const highlightedMetricValue = hovered ? getMetricValue(hovered, selectedMetric) : 0;

  const styleFeature = (feature: Feature<Geometry, any> | undefined) => {
    const value = feature ? getMetricValue(feature, selectedMetric) : 0;
    return {
      fillColor: getHazardColor(value),
      weight: 1,
      opacity: 1,
      color: '#334155',
      fillOpacity: 0.8,
    };
  };

  const onEachFeature = (feature: Feature<Geometry, any>, layer: any) => {
    layer.on({
      mouseover: () => setHovered(feature),
      mouseout: () => setHovered((previous) => (previous === feature ? null : previous)),
    });
  };

  const mapFeatureCount = geoJson?.features?.length ?? 0;

  return (
    <div className="map-shell">
      <div className="card" style={{ position: 'relative', minHeight: '72vh' }}>
        <div className="control-row" style={{ justifyContent: 'space-between' }}>
          <div>
            <label htmlFor="metric">Color by</label>
            <select
              id="metric"
              className="select-control"
              value={selectedMetric}
              onChange={(event) => setSelectedMetric(event.target.value)}
            >
              {metrics.map((metric) => (
                <option key={metric.id} value={metric.id}>
                  {metric.label}
                </option>
              ))}
            </select>
          </div>
          <div style={{ textAlign: 'right' }}>
            <p style={{ margin: 0, color: '#64748b', fontSize: '0.9rem' }}>Precinct count</p>
            <strong style={{ fontSize: '1.1rem' }}>{formatCount(mapFeatureCount)}</strong>
          </div>
        </div>

        <div style={{ width: '100%', minHeight: '64vh' }}>
          {loading ? (
            <div style={{ padding: '2rem', textAlign: 'center' }}>Loading map data…</div>
          ) : geoJson ? (
            <MapContainer
              center={[40.563, -111.949]}
              zoom={9}
              scrollWheelZoom={true}
              style={{ width: '100%', minHeight: '64vh', borderRadius: '1rem', overflow: 'hidden' }}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <GeoJSON data={geoJson} style={styleFeature} onEachFeature={onEachFeature} />
            </MapContainer>
          ) : (
            <div style={{ padding: '2rem', textAlign: 'center' }}>
              Unable to load the GeoJSON map.
            </div>
          )}
        </div>
      </div>

      <aside className="panel">
        <div>
          <p style={{ margin: 0, color: '#64748b', fontSize: '0.9rem' }}>Selected area</p>
          <h2 style={{ margin: '0.25rem 0 1rem' }}>{highlightedText}</h2>
          <p style={{ margin: 0, color: '#475569' }}>
            {hovered
              ? `Estimated ${metrics.find((item) => item.id === selectedMetric)?.label?.toLowerCase()} for this precinct.`
              : 'Move your cursor over any precinct to see vote totals and the history chart.'}
          </p>
        </div>

        <div className="card">
          <h3>{metrics.find((item) => item.id === selectedMetric)?.label}</h3>
          <p style={{ margin: 0, fontSize: '1.85rem', fontWeight: 700 }}>
            {hovered ? formatCount(highlightedMetricValue) : '–'}
          </p>
        </div>

        <div className="card">
          <h3>Recent election trend</h3>
          <div style={{ width: '100%', height: 220 }}>
            {hovered ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 12, right: 16, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="year" tick={{ fill: '#475569' }} />
                  <YAxis tickFormatter={(value) => value >= 1000 ? `${Math.round(value / 1000)}k` : value} tick={{ fill: '#475569' }} />
                  <Tooltip formatter={(value: number) => formatCount(value)} />
                  <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={3} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ color: '#64748b', padding: '1rem 0' }}>Hover over a precinct to show the historical vote line chart.</div>
            )}
          </div>
        </div>

        <div className="legend card">
          <h3>Legend</h3>
          {['#082567', '#1f4cc8', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe', '#e2e8f0'].map((color, index) => (
            <div key={color} className="legend-item">
              <span className="legend-swatch" style={{ background: color }} />
              <span>
                {index === 0 && 'Highest values'}
                {index > 0 && index < 6 && 'Medium range'}
                {index === 6 && 'Lowest values'}
              </span>
            </div>
          ))}
        </div>

        <div className="card">
          <h3>Tips</h3>
          <ul style={{ margin: 0, paddingLeft: '1.25rem', color: '#475569', lineHeight: 1.8 }}>
            <li>Hover over shapes to inspect precinct-specific results.</li>
            <li>Switch the metric dropdown to compare 2024 races.</li>
            <li>Use the map zoom and pan controls to navigate Utah County precincts.</li>
          </ul>
        </div>
      </aside>
    </div>
  );
}
