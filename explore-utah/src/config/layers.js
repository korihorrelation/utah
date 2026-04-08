/**
 * Layer configuration for Explore Utah.
 * Each category has a list of data sources and their visual layers.
 */

export const CATEGORIES = {
  recreation: {
    label: 'Recreation',
    icon: '🏔️',
    sublayers: [
      { id: 'national-parks', label: 'Nat\'l Parks', color: '#EC4899', defaultOn: true },
      { id: 'national-forests', label: 'Nat\'l Forests', color: '#22C55E', defaultOn: true },
      { id: 'other-federal', label: 'Other Federal', color: '#9CA3AF', defaultOn: true },
      { id: 'utah-state-parks', label: 'State Parks', color: '#F59E0B', defaultOn: true },
      { id: 'monuments-markers', label: 'Monuments', color: '#FB923C', defaultOn: true },
    ],
    sources: [
      // --- National Parks (filtered from federal_lands) ---
      {
        id: 'federal-lands',
        url: '/data/federal_lands.geojson',
        layers: [
          {
            id: 'national-parks-fill',
            type: 'fill',
            sublayerGroup: 'national-parks',
            filter: ['==', ['get', 'desig'], 'National Park'],
            paint: {
              'fill-color': '#EC4899',
              'fill-opacity': 0.2,
            },
          },
          {
            id: 'national-parks-outline',
            type: 'line',
            sublayerGroup: 'national-parks',
            filter: ['==', ['get', 'desig'], 'National Park'],
            paint: {
              'line-color': '#F472B6',
              'line-width': 1.5,
              'line-opacity': 0.6,
            },
          },
          // --- National Forests (filtered) ---
          {
            id: 'national-forests-fill',
            type: 'fill',
            sublayerGroup: 'national-forests',
            filter: ['==', ['get', 'desig'], 'National Forest'],
            paint: {
              'fill-color': '#22C55E',
              'fill-opacity': 0.12,
            },
          },
          {
            id: 'national-forests-outline',
            type: 'line',
            sublayerGroup: 'national-forests',
            filter: ['==', ['get', 'desig'], 'National Forest'],
            paint: {
              'line-color': '#4ADE80',
              'line-width': 1,
              'line-opacity': 0.4,
            },
          },
          // --- Other Federal Lands (everything else) ---
          {
            id: 'other-federal-fill',
            type: 'fill',
            sublayerGroup: 'other-federal',
            filter: ['!', ['in', ['get', 'desig'], ['literal', ['National Park', 'National Forest']]]],
            paint: {
              'fill-color': '#D3D3D3',
              'fill-opacity': 0.08,
            },
          },
          {
            id: 'other-federal-outline',
            type: 'line',
            sublayerGroup: 'other-federal',
            filter: ['!', ['in', ['get', 'desig'], ['literal', ['National Park', 'National Forest']]]],
            paint: {
              'line-color': ['match', ['get', 'desig'], 'National Monument', '#F97316', '#9CA3AF'],
              'line-width': 1,
              'line-opacity': 0.35,
            },
          },
        ],
      },
      {
        id: 'utah-state-parks',
        sublayerGroup: 'utah-state-parks',
        url: '/data/utah_state_parks.geojson',
        layers: [
          {
            id: 'utah-state-parks-glow',
            type: 'circle',
            paint: {
              'circle-radius': 12,
              'circle-color': '#F59E0B',
              'circle-opacity': 0.2,
              'circle-blur': 1,
            },
          },
          {
            id: 'utah-state-parks-points',
            type: 'circle',
            paint: {
              'circle-radius': 6,
              'circle-color': '#F59E0B',
              'circle-stroke-color': '#FDE68A',
              'circle-stroke-width': 1.5,
              'circle-opacity': 0.9,
            },
          },
        ],
      },
      {
        id: 'monuments-markers',
        sublayerGroup: 'monuments-markers',
        url: '/data/monuments_and_markers.geojson',
        layers: [
          {
            id: 'monuments-markers-glow',
            type: 'circle',
            paint: {
              'circle-radius': 10,
              'circle-color': ['case', ['==', ['get', 'Type'], 'Monument/Marker Exterior'], '#9CA3AF', '#FB923C'],
              'circle-opacity': 0.15,
              'circle-blur': 1,
            },
          },
          {
            id: 'monuments-markers-points',
            type: 'circle',
            paint: {
              'circle-radius': 4,
              'circle-color': ['case', ['==', ['get', 'Type'], 'Monument/Marker Exterior'], '#9CA3AF', '#FB923C'],
              'circle-stroke-color': ['case', ['==', ['get', 'Type'], 'Monument/Marker Exterior'], '#D1D5DB', '#FDBA74'],
              'circle-stroke-width': 1,
              'circle-opacity': 0.85,
            },
          },
        ],
      },
    ],
  },

  transportation: {
    label: 'Transportation',
    icon: '🚆',
    sublayers: [
      { id: 'highways', label: 'Highways', color: '#D1D5DB', defaultOn: true },
      { id: 'railroads', label: 'Railroads', color: '#B45309', defaultOn: true },
      { id: 'frontrunner', label: 'FrontRunner', color: '#A78BFA', defaultOn: true },
      { id: 'trax', label: 'TRAX', color: '#06B6D4', defaultOn: true },
      { id: 'bus', label: 'Bus', color: '#34D399', defaultOn: true },
      { id: 'airports', label: 'Airports', color: '#F472B6', defaultOn: true },
    ],
    sources: [
      // --- Bus (back) ---
      {
        id: 'bus-routes',
        sublayerGroup: 'bus',
        url: '/data/bus_routes.geojson',
        layers: [
          {
            id: 'bus-routes-glow',
            type: 'line',
            paint: {
              'line-color': '#10B981',
              'line-width': 4,
              'line-opacity': 0.15,
              'line-blur': 3,
            },
          },
          {
            id: 'bus-routes-line',
            type: 'line',
            paint: {
              'line-color': '#10B981',
              'line-width': 1.5,
              'line-opacity': 0.7,
            },
          },
        ],
      },
      {
        id: 'bus-stops',
        sublayerGroup: 'bus',
        url: '/data/bus_stops.geojson',
        layers: [
          {
            id: 'bus-stops-points',
            type: 'circle',
            paint: {
              'circle-radius': 2.5,
              'circle-color': '#34D399',
              'circle-stroke-color': '#6EE7B7',
              'circle-stroke-width': 0.5,
              'circle-opacity': 0.6,
            },
          },
        ],
      },
      // --- Highways (above bus, below TRAX) ---
      {
        id: 'highways',
        sublayerGroup: 'highways',
        url: '/data/highways.geojson',
        layers: [
          {
            id: 'highways-line',
            type: 'line',
            paint: {
              'line-color': '#E5E7EB',
              'line-width': 2,
              'line-opacity': 0.7,
            },
          },
        ],
      },
      // --- Railroads (above highways) ---
      {
        id: 'railroads',
        sublayerGroup: 'railroads',
        url: '/data/railroads.geojson',
        layers: [
          {
            id: 'railroads-line',
            type: 'line',
            layout: {
              'line-cap': 'round',
              'line-dasharray': [4, 3],
            },
            paint: {
              'line-color': '#B45309',
              'line-width': 2,
              'line-opacity': 0.7,
            },
          },
        ],
      },
      // --- TRAX (middle) ---
      {
        id: 'trax-routes',
        sublayerGroup: 'trax',
        url: '/data/trax_routes.geojson',
        layers: [
          {
            id: 'trax-routes-glow',
            type: 'line',
            paint: {
              'line-color': '#3B82F6',
              'line-width': 6,
              'line-opacity': 0.25,
              'line-blur': 3,
            },
          },
          {
            id: 'trax-routes-line',
            type: 'line',
            paint: {
              'line-color': '#3B82F6',
              'line-width': 2.5,
              'line-opacity': 0.9,
            },
          },
        ],
      },
      {
        id: 'trax-stations',
        sublayerGroup: 'trax',
        url: '/data/trax_stations.geojson',
        layers: [
          {
            id: 'trax-stations-glow',
            type: 'circle',
            paint: {
              'circle-radius': 10,
              'circle-color': '#06B6D4',
              'circle-opacity': 0.2,
              'circle-blur': 1,
            },
          },
          {
            id: 'trax-stations-points',
            type: 'circle',
            paint: {
              'circle-radius': 5,
              'circle-color': '#06B6D4',
              'circle-stroke-color': '#67E8F9',
              'circle-stroke-width': 1.5,
              'circle-opacity': 0.9,
            },
          },
        ],
      },
      // --- FrontRunner (top) ---
      {
        id: 'frontrunner-routes',
        sublayerGroup: 'frontrunner',
        url: '/data/frontrunner_routes.geojson',
        layers: [
          {
            id: 'frontrunner-routes-glow',
            type: 'line',
            paint: {
              'line-color': '#8B5CF6',
              'line-width': 6,
              'line-opacity': 0.25,
              'line-blur': 3,
            },
          },
          {
            id: 'frontrunner-routes-line',
            type: 'line',
            paint: {
              'line-color': '#8B5CF6',
              'line-width': 2.5,
              'line-opacity': 0.9,
            },
          },
        ],
      },
      {
        id: 'frontrunner-stations',
        sublayerGroup: 'frontrunner',
        url: '/data/frontrunner_stations.geojson',
        layers: [
          {
            id: 'frontrunner-stations-glow',
            type: 'circle',
            paint: {
              'circle-radius': 10,
              'circle-color': '#A78BFA',
              'circle-opacity': 0.2,
              'circle-blur': 1,
            },
          },
          {
            id: 'frontrunner-stations-points',
            type: 'circle',
            paint: {
              'circle-radius': 5,
              'circle-color': '#A78BFA',
              'circle-stroke-color': '#C4B5FD',
              'circle-stroke-width': 1.5,
              'circle-opacity': 0.9,
            },
          },
        ],
      },
      // --- Airports (top) ---
      {
        id: 'airports',
        sublayerGroup: 'airports',
        url: '/data/airports.geojson',
        layers: [
          {
            id: 'airports-glow',
            type: 'line',
            paint: {
              'line-color': '#EC4899',
              'line-width': 6,
              'line-opacity': 0.25,
              'line-blur': 3,
            },
          },
          {
            id: 'airports-line',
            type: 'line',
            paint: {
              'line-color': '#F472B6',
              'line-width': 2,
              'line-opacity': 0.9,
            },
          },
        ],
      },
    ],
  },

  political: {
    label: 'Political',
    icon: '🏛️',
    // Sublayer toggle config — allows user to show/hide individual layers
    sublayers: [
      { id: 'county-boundaries', label: 'Counties', color: '#9CA3AF', defaultOn: true },
      { id: 'congress-districts', label: 'Congress', color: '#2DD4BF', defaultOn: true },
      { id: 'house-districts', label: 'House', color: '#F472B6', defaultOn: true },
      { id: 'municipal-boundaries', label: 'Cities', color: '#F9A8D4', defaultOn: true },
    ],
    sources: [
      // Counties — rendered first (back)
      {
        id: 'county-boundaries',
        url: '/data/county_boundaries.geojson',
        layers: [
          {
            id: 'county-boundaries-fill',
            type: 'fill',
            paint: {
              'fill-color': '#6B7280',
              'fill-opacity': 0.06,
            },
          },
          {
            id: 'county-boundaries-outline',
            type: 'line',
            paint: {
              'line-color': '#4B5563',
              'line-width': 1.5,
              'line-opacity': 0.5,
            },
          },
        ],
      },
      // Congressional districts
      {
        id: 'congress-districts',
        url: '/data/congress_districts.geojson',
        layers: [
          {
            id: 'congress-districts-fill',
            type: 'fill',
            paint: {
              'fill-color': '#14B8A6',
              'fill-opacity': 0.08,
            },
          },
          {
            id: 'congress-districts-outline',
            type: 'line',
            paint: {
              'line-color': '#2DD4BF',
              'line-width': 2,
              'line-opacity': 0.6,
            },
          },
        ],
      },
      // House districts
      {
        id: 'house-districts',
        url: '/data/house_districts.geojson',
        layers: [
          {
            id: 'house-districts-fill',
            type: 'fill',
            paint: {
              'fill-color': '#EC4899',
              'fill-opacity': 0.08,
            },
          },
          {
            id: 'house-districts-outline',
            type: 'line',
            paint: {
              'line-color': '#F472B6',
              'line-width': 1,
              'line-opacity': 0.5,
            },
          },
        ],
      },
      // Municipalities — rendered last (front) with labels
      {
        id: 'municipal-boundaries',
        url: '/data/municipal_boundaries.geojson',
        layers: [
          {
            id: 'municipal-boundaries-fill',
            type: 'fill',
            paint: {
              'fill-color': [
                'match', ['%', ['get', 'OBJECTID'], 8],
                0, '#F9A8D4',  // pink
                1, '#C4B5FD',  // lavender
                2, '#93C5FD',  // baby blue
                3, '#A7F3D0',  // mint
                4, '#FDE68A',  // buttercup
                5, '#FDBA74',  // peach
                6, '#F0ABFC',  // orchid
                7, '#99F6E4',  // aqua
                '#F9A8D4'
              ],
              'fill-opacity': 0.12,
            },
          },
          {
            id: 'municipal-boundaries-outline',
            type: 'line',
            paint: {
              'line-color': [
                'match', ['%', ['get', 'OBJECTID'], 8],
                0, '#F472B6',
                1, '#A78BFA',
                2, '#60A5FA',
                3, '#6EE7B7',
                4, '#FCD34D',
                5, '#FB923C',
                6, '#E879F9',
                7, '#5EEAD4',
                '#F472B6'
              ],
              'line-width': 1,
              'line-opacity': 0.5,
            },
          },
          {
            id: 'municipal-boundaries-labels',
            type: 'symbol',
            layout: {
              'text-field': ['get', 'NAME'],
              'text-size': 11,
              'text-anchor': 'center',
              'text-allow-overlap': false,
              'text-ignore-placement': false,
              'text-padding': 4,
              'text-font': ['DIN Pro Medium', 'Arial Unicode MS Regular'],
            },
            paint: {
              'text-color': '#E5E7EB',
              'text-halo-color': 'rgba(15, 17, 23, 0.85)',
              'text-halo-width': 1.5,
              'text-opacity': 0.85,
            },
          },
        ],
      },
    ],
  },

  demographics: {
    label: 'Demographics',
    icon: '👥',
    sublayers: [
      { id: 'pop-density', label: 'Pop. Density', color: '#F97316', defaultOn: true },
    ],
    sources: [
      {
        id: 'pop-density',
        sublayerGroup: 'pop-density',
        url: '/data/population_density.geojson',
        layers: [
          {
            id: 'pop-density-fill',
            type: 'fill',
            paint: {
              'fill-color': [
                'interpolate', ['linear'], ['get', 'DENSITY'],
                0, '#1a1a2e',
                50, '#16213e',
                200, '#0f3460',
                500, '#533483',
                1000, '#e94560',
                2000, '#F97316',
                4000, '#FBBF24',
                8000, '#FDE68A',
              ],
              'fill-opacity': 0.6,
            },
          },
          {
            id: 'pop-density-outline',
            type: 'line',
            paint: {
              'line-color': '#ffffff',
              'line-width': 0.3,
              'line-opacity': 0.15,
            },
          },
        ],
      },
    ],
  },
};

/**
 * Get all layer IDs for a given category.
 */
export function getLayerIds(categoryKey) {
  const cat = CATEGORIES[categoryKey];
  if (!cat) return [];
  return cat.sources.flatMap((s) => s.layers.map((l) => l.id));
}

/**
 * Get all interactive (clickable) layer IDs for a given category.
 * We exclude glow layers since they're decorative.
 */
export function getInteractiveLayerIds(categoryKey) {
  const cat = CATEGORIES[categoryKey];
  if (!cat) return [];
  return cat.sources.flatMap((s) =>
    s.layers.filter((l) => !l.id.endsWith('-glow')).map((l) => l.id)
  );
}

/**
 * Get all interactive layer IDs across ALL categories.
 */
export function getAllInteractiveLayerIds() {
  return Object.keys(CATEGORIES).flatMap(getInteractiveLayerIds);
}
