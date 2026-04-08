import mapboxgl from 'mapbox-gl';

/**
 * Common name field candidates across all GeoJSON datasets.
 * Ordered by likelihood — first match wins.
 */
const NAME_CANDIDATES = [
  'name', 'Name', 'NAME',
  'label_federal', 'label_state',
  'linename', 'stationnam', 'stopname', 'routename', 'SITE_NAME',
  'PARK_NAME', 'park_name', 'ParkName',
  'station_name', 'StationName', 'STATION_NAME',
  'route_name', 'RouteName', 'ROUTE_NAME',
  'DIST', 'DISTRICT', 'MINNAME',
  'title', 'Title', 'TITLE',
  'lineabbr',
];

/**
 * Common description / detail field candidates.
 */
const DESC_CANDIDATES = [
  'desig', 'Type', 'type', 'TYPE',
  'agency', 'admin',
  'function_', 'frequency',
  'DENSITY', 'POP100',
  'POP_LASTCENSUS', 'POP_CURRESTIMATE', 'POPLASTCENSUS', 'POPLASTESTIMATE',
  'SHORTDESC', 'COUNTYSEAT',
  'Address', 'address', 'ADDRESS',
  'City', 'city', 'CITY',
  'County', 'county', 'COUNTY',
  'routetype', 'status',
  'Primary_Th', 'Sec_Th',
  'Commemorat',
  'region',
  'parknride', 'p_and_r',
];

/** Category-based fallback descriptions */
const FALLBACKS = {
  recreation: 'Utah recreation landmark',
  transportation: 'Utah transit feature',
  political: 'Utah political boundary',
  demographics: 'Utah census area',
};

/**
 * Extract the best-guess display name from feature properties.
 */
export function getFeatureName(properties) {
  if (!properties) return 'Unknown';

  // Special case: census demographics — show GEOID + density
  if (properties.DENSITY != null && properties.POP100 != null) {
    const geoid = properties.GEOID || 'Unknown';
    return `Block Group ${geoid}`;
  }

  for (const key of NAME_CANDIDATES) {
    const val = properties[key];
    if (val != null && String(val).trim()) {
      const str = String(val).trim();
      // Format district numbers nicely
      if ((key === 'DIST' || key === 'DISTRICT') && !isNaN(val)) {
        return `District ${str}`;
      }
      return str;
    }
  }
  return 'Unnamed Feature';
}

/**
 * Build a short description from available property fields.
 * Returns an array of { label, value } pairs for display.
 */
export function getFeatureDescription(properties, category = 'recreation') {
  if (!properties) return [{ label: '', value: FALLBACKS[category] || FALLBACKS.recreation }];

  const details = [];

  for (const key of DESC_CANDIDATES) {
    const val = properties[key];
    if (val != null && String(val).trim()) {
      const label = prettifyFieldName(key);
      let display = String(val).trim();
      // Format population numbers with commas
      if (key.includes('POP') && !isNaN(val)) {
        display = Number(val).toLocaleString();
      }
      details.push({ label, value: display });
      if (details.length >= 3) break;
    }
  }

  if (details.length === 0) {
    details.push({ label: '', value: FALLBACKS[category] || FALLBACKS.recreation });
  }

  return details;
}

/**
 * Make truncated field names human-readable.
 */
function prettifyFieldName(field) {
  const map = {
    'function_': 'Function',
    'stationnam': 'Station',
    'routename': 'Route',
    'linename': 'Line',
    'lineabbr': 'Abbreviation',
    'routetype': 'Route Type',
    'parknride': 'Park & Ride',
    'p_and_r': 'Park & Ride',
    'Primary_Th': 'Theme',
    'Sec_Th': 'Secondary Theme',
    'Commemorat': 'Commemorates',
    'desig': 'Designation',
    'agency': 'Agency',
    'admin': 'Managed by',
    'label_federal': 'Federal Land',
    'POP_LASTCENSUS': 'Census Pop.',
    'POP_CURRESTIMATE': 'Est. Pop.',
    'POPLASTCENSUS': 'Census Pop.',
    'POPLASTESTIMATE': 'Est. Pop.',
    'SHORTDESC': 'Description',
    'COUNTYSEAT': 'County Seat',
    'DIST': 'District',
    'DISTRICT': 'District',
    'frequency': 'Frequency',
    'status': 'Status',
    'region': 'Region',
  };
  return map[field] || field.charAt(0).toUpperCase() + field.slice(1);
}

/**
 * Fly the map to a feature based on its geometry type.
 * Points → flyTo; Lines/Polygons → fitBounds.
 */
export function flyToFeature(map, feature) {
  if (!feature || !feature.geometry) return;

  const { type, coordinates } = feature.geometry;

  if (type === 'Point') {
    map.flyTo({
      center: coordinates,
      zoom: 13,
      duration: 1400,
      essential: true,
    });
  } else {
    // For lines, polygons, multi-geometries — compute bounding box
    const bounds = getBounds(coordinates, type);
    if (bounds) {
      map.fitBounds(bounds, {
        padding: 80,
        duration: 1400,
        maxZoom: 14,
      });
    }
  }
}

/**
 * Compute a LngLatBounds from any coordinate structure.
 */
function getBounds(coordinates, type) {
  const bounds = new mapboxgl.LngLatBounds();
  const flatCoords = flattenCoordinates(coordinates, type);

  if (flatCoords.length === 0) return null;

  for (const coord of flatCoords) {
    bounds.extend(coord);
  }

  return bounds;
}

/**
 * Recursively flatten coordinates to [lng, lat] pairs.
 */
function flattenCoordinates(coords, type) {
  if (type === 'LineString' || type === 'MultiPoint') {
    return coords; // already [[lng,lat], ...]
  }
  if (type === 'MultiLineString' || type === 'Polygon') {
    return coords.flat(); // [[...], [...]] → [...]
  }
  if (type === 'MultiPolygon') {
    return coords.flat(2);
  }
  // Fallback: try to interpret
  if (Array.isArray(coords[0]) && Array.isArray(coords[0][0])) {
    return coords.flat(10).reduce((acc, _, i, arr) => {
      if (i % 2 === 0 && i + 1 < arr.length) acc.push([arr[i], arr[i + 1]]);
      return acc;
    }, []);
  }
  return [coords]; // single point
}

/**
 * Load a GeoJSON file with error handling.
 * Returns the parsed data or null if the file is missing/broken.
 */
export async function loadGeoJSON(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.warn(`[Explore Utah] Could not load ${url}: ${res.status}`);
      return null;
    }
    const data = await res.json();
    // Validate it's a FeatureCollection
    if (!data || !data.features) {
      console.warn(`[Explore Utah] Invalid GeoJSON at ${url}`);
      return null;
    }
    return data;
  } catch (err) {
    console.warn(`[Explore Utah] Error loading ${url}:`, err);
    return null;
  }
}
