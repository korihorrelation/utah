'use client';

/**
 * Breadcrumb navigation showing the current drill path.
 */
export default function BreadcrumbBar({ drillPath, onNavigate }) {
  return (
    <div className="sidebar__breadcrumb">
      <nav className="breadcrumb" aria-label="Hierarchy breadcrumb">
        {drillPath.map((item, index) => (
          <span key={`${item.type}-${item.id}`} style={{ display: 'contents' }}>
            {index > 0 && <span className="breadcrumb__separator">&#9656;</span>}
            <button
              className={`breadcrumb__item ${index === drillPath.length - 1 ? 'breadcrumb__item--active' : ''}`}
              onClick={() => {
                if (index < drillPath.length - 1) {
                  onNavigate(item.type, item.id, item.name);
                }
              }}
              title={item.name}
            >
              {item.name}
            </button>
          </span>
        ))}
      </nav>
    </div>
  );
}
