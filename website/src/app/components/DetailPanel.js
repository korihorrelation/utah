'use client';

/**
 * Detail panel showing properties of the selected item.
 */
export default function DetailPanel({ selection, activeTile, hierarchy }) {
  if (!selection) return null;

  const details = getDetails(selection, activeTile, hierarchy);
  if (!details) return null;

  return (
    <div className="sidebar__detail">
      <div className="detail-panel">
        <div className="detail-panel__header">
          <span className="detail-panel__type" data-type={details.type}>{details.type}</span>
          <span className="detail-panel__title">{details.title}</span>
        </div>
        <div className="detail-panel__grid">
          {details.fields.map((field, i) => (
            <div className="detail-panel__field" key={i}>
              <span className="detail-panel__field-label">{field.label}</span>
              <span className="detail-panel__field-value">{field.value ?? '—'}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function getDetails(selection, activeTile, hierarchy) {
  if (!selection) return null;

  switch (selection.type) {
    case 'subdivision': {
      const sub = hierarchy?.children?.find(s => s.id === selection.id);
      if (!sub) return null;
      return {
        type: 'Subdivision',
        title: sub.name,
        fields: [
          { label: 'Zoning Type', value: sub.subdivisionType || 'Subdivision' },
          { label: 'Plats', value: sub.platCount },
          { label: 'Parcels', value: sub.parcelCount },
          { label: 'Addresses', value: sub.addressCount },
        ],
      };
    }

    case 'plat': {
      if (!activeTile?.plats) return null;
      const feat = activeTile.plats.features.find(f => f.properties.id === selection.id);
      if (!feat) return null;
      return {
        type: 'Plat',
        title: feat.properties.name,
        fields: [
          { label: 'Label', value: feat.properties.label },
          { label: 'Acres', value: feat.properties.acres?.toFixed(2) },
          { label: 'Subdivision', value: feat.properties.subdivision },
        ],
      };
    }

    case 'parcel': {
      if (!activeTile?.parcels) return null;
      const feat = activeTile.parcels.features.find(f => f.properties.id === selection.id);
      if (!feat) return null;
      return {
        type: 'Parcel',
        title: feat.properties.address || `Parcel ${feat.properties.id}`,
        fields: [
          { label: 'Parcel ID', value: feat.properties.id },
          { label: 'Owner', value: feat.properties.owner },
          { label: 'Acreage', value: feat.properties.acreage?.toFixed(3) },
          { label: 'Market Value', value: feat.properties.marketValue ? `$${Number(feat.properties.marketValue).toLocaleString()}` : null },
        ],
      };
    }

    case 'address': {
      if (!activeTile?.addresses) return null;
      const feat = activeTile.addresses.features.find(f => f.properties.id === selection.id);
      if (!feat) return null;
      return {
        type: 'Address',
        title: feat.properties.fullAddress,
        fields: [
          { label: 'City', value: feat.properties.city },
          { label: 'ZIP', value: feat.properties.zipCode },
          { label: 'Parcel ID', value: feat.properties.parcelId },
          { label: 'Structure', value: feat.properties.structureType },
          { label: 'Point Type', value: feat.properties.pointType },
        ],
      };
    }

    default:
      return null;
  }
}
