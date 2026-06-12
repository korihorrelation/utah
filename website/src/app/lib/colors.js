/**
 * Consistent color palette for map layers.
 * Each level of the hierarchy has a distinct hue.
 */

// Cities Skylines inspired zoning colors for subdivisions
const ZONING_COLORS = {
  // Residential (Green)
  'Subdivision': '#10b981',        // Emerald Green
  'Minor Subdivision': '#34d399',  // Medium Emerald Green
  'MDA': '#059669',                // Forest Green (Master Planned residential)
  'Multi Familyi': '#047857',      // Dark Forest Green (High density residential)

  // Commercial (Blue)
  'Commercial': '#2563eb',         // Royal Blue
  'RV Camp': '#0ea5e9',            // Sky Blue (Tourism commercial)

  // Mixed Use (Teal/Cyan)
  'Mixed Use': '#06b6d4',          // Cyan

  // Services/Civic (Purple/Indigo/Slate)
  'School': '#6366f1',             // Indigo (Educational Service)
  'CommunityPlan': '#64748b',      // Slate Gray (Civic Service)
  'Religious': '#fca5a5',          // Light Red
  'Unassigned': '#475569',         // Cool Gray
};

// Subdivision fill colors — 12 distinct hues cycling through (fallback)
const SUBDIVISION_COLORS = [
  '#7c8aff', // indigo
  '#a78bfa', // purple
  '#f472b6', // pink
  '#fb7185', // rose
  '#f97316', // orange
  '#fbbf24', // amber
  '#34d399', // emerald
  '#2dd4bf', // teal
  '#38bdf8', // sky
  '#818cf8', // violet
  '#c084fc', // fuchsia
  '#fb923c', // orange-light
];

export function getSubdivisionColor(typeOrIndex) {
  if (typeof typeOrIndex === 'number') {
    return SUBDIVISION_COLORS[typeOrIndex % SUBDIVISION_COLORS.length];
  }
  return ZONING_COLORS[typeOrIndex] || '#7c8aff';
}

export function getSubdivisionCategory(type) {
  switch (type) {
    case 'Subdivision':
    case 'Minor Subdivision':
    case 'MDA':
    case 'Multi Familyi':
      return 'Residential Communities';
    case 'Commercial':
    case 'RV Camp':
      return 'Commercial';
    case 'Mixed Use':
      return 'Mixed Housing';
    case 'School':
    case 'CommunityPlan':
      return 'Public';
    case 'Religious':
      return 'Religious';
    default:
      return 'Public';
  }
}

export const LAYER_COLORS = {
  cityBoundary: '#fb7185',
  subdivision: '#7c8aff',
  plat: '#a78bfa',
  parcel: '#2dd4bf',
  address: '#fbbf24',
  road: 'rgba(148, 153, 179, 0.4)',
  path: '#fb923c',
};

export const LAYER_STYLES = {
  cityBoundary: {
    color: '#fb7185',
    weight: 2.5,
    fillOpacity: 0,
    dashArray: '8, 4',
  },
  subdivision: (index) => ({
    color: getSubdivisionColor(index),
    weight: 1.5,
    fillColor: getSubdivisionColor(index),
    fillOpacity: 0.12,
  }),
  subdivisionHighlight: (index) => ({
    color: getSubdivisionColor(index),
    weight: 3,
    fillColor: getSubdivisionColor(index),
    fillOpacity: 0.25,
  }),
  plat: {
    color: '#a78bfa',
    weight: 1.2,
    fillColor: '#a78bfa',
    fillOpacity: 0.15,
  },
  platHighlight: {
    color: '#a78bfa',
    weight: 2.5,
    fillColor: '#a78bfa',
    fillOpacity: 0.3,
  },
  parcel: {
    color: '#2dd4bf',
    weight: 0.8,
    fillColor: '#2dd4bf',
    fillOpacity: 0.12,
  },
  parcelHighlight: {
    color: '#2dd4bf',
    weight: 2,
    fillColor: '#2dd4bf',
    fillOpacity: 0.3,
  },
  road: {
    color: 'rgba(148, 153, 179, 0.35)',
    weight: 1,
  },
  path: {
    color: '#fb923c',
    weight: 1.5,
    opacity: 0.7,
    dashArray: '6, 4',
  },
  park: {
    color: '#059669',
    weight: 1.5,
    fillColor: '#10b981',
    fillOpacity: 0.15,
  },
};
