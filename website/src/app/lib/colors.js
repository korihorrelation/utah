/**
 * Consistent color palette for map layers.
 * Each level of the hierarchy has a distinct hue.
 */

// Colors mapped directly to categories for strict consistency across tree and map
const CATEGORY_COLORS = {
  'Residential Communities': '#10b981', // Emerald Green
  'Mixed Housing': '#06b6d4',          // Cyan
  'Commercial': '#2563eb',             // Royal Blue
  'Religious': '#ff69b4',              // Lighter Bright Pink
  'Public': '#a855f7',                 // Purple
  'Other': '#64748b',                  // Slate Gray
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

export function getSubdivisionColor(categoryOrIndex) {
  if (typeof categoryOrIndex === 'number') {
    return SUBDIVISION_COLORS[categoryOrIndex % SUBDIVISION_COLORS.length];
  }
  return CATEGORY_COLORS[categoryOrIndex] || '#64748b';
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
