'use client';

import { useMemo, useCallback, useState, useEffect, useRef } from 'react';
import { getSubdivisionColor } from '../lib/colors';

/**
 * Recursive tree view for exploring the spatial hierarchy.
 *
 * Subdivisions are grouped into Residential / Commercial / Public categories.
 * Selection and expansion are driven entirely by the parent page.js:
 *   - `selection` determines which node is highlighted (and which ancestor chain is "active").
 *   - `expandedNodes` determines which tree branches are open.
 *   - `onNavigate` is the single callback; the hook handles expansion + breadcrumb.
 */
export default function HierarchyTree({ hierarchy, selection, expandedNodes, onNavigate, hiddenSubdivisionIds, onToggleVisibility, onToggleCategoryVisibility }) {
  const [expandedCategories, setExpandedCategories] = useState(new Set());

  const toggleCategory = useCallback((cat) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      next.has(cat) ? next.delete(cat) : next.add(cat);
      return next;
    });
  }, []);

  const grouped = useMemo(() => {
    const g = {
      'Residential Communities': [],
      'Mixed Housing': [],
      'Commercial': [],
      'Public': [],
      'Religious': [],
      'Other': []
    };
    (hierarchy?.children || []).forEach(sub => {
      const cat = sub.category || 'Other';
      if (g[cat]) {
        g[cat].push(sub);
      } else {
        g['Other'].push(sub);
      }
    });
    return g;
  }, [hierarchy]);

  // Auto-expand the category that contains the active subdivision.
  useEffect(() => {
    if (!selection?.subdivisionId || !hierarchy?.children) return;
    const sub = hierarchy.children.find(s => s.id === selection.subdivisionId);
    if (!sub) return;
    const cat = sub.category || 'Other';
    setExpandedCategories(prev => (prev.has(cat) ? prev : new Set(prev).add(cat)));
  }, [selection?.subdivisionId, hierarchy]);

  if (!hierarchy) return null;

  const CATEGORIES = [
    { name: 'Residential Communities', color: getSubdivisionColor('Residential Communities'), label: 'Residential Communities' },
    { name: 'Mixed Housing', color: getSubdivisionColor('Mixed Housing'), label: 'Mixed Housing' },
    { name: 'Commercial', color: getSubdivisionColor('Commercial'), label: 'Commercial' },
    { name: 'Religious', color: getSubdivisionColor('Religious'), label: 'Religious' },
    { name: 'Public', color: getSubdivisionColor('Public'), label: 'Public' },
    { name: 'Other', color: getSubdivisionColor('Other'), label: 'Other' },
  ];

  return (
    <div className="sidebar__tree" role="tree" aria-label="Spatial hierarchy">
      {CATEGORIES.map(cat => {
        const subs = grouped[cat.name];
        if (!subs.length) return null;
        return (
          <CategoryNode
            key={cat.name}
            label={cat.label}
            color={cat.color}
            subdivisions={subs}
            isExpanded={expandedCategories.has(cat.name)}
            onToggle={() => toggleCategory(cat.name)}
            selection={selection}
            expandedNodes={expandedNodes}
            onNavigate={onNavigate}
            hiddenSubdivisionIds={hiddenSubdivisionIds}
            onToggleVisibility={onToggleVisibility}
            onToggleCategoryVisibility={onToggleCategoryVisibility}
          />
        );
      })}
    </div>
  );
}

// ── Category folder ───────────────────────────────────────────────────────

function CategoryNode({ label, color, subdivisions, isExpanded, onToggle, selection, expandedNodes, onNavigate, hiddenSubdivisionIds, onToggleVisibility, onToggleCategoryVisibility }) {
  const isHidden = subdivisions.length > 0 && subdivisions.every(sub => hiddenSubdivisionIds?.has(sub.id));

  return (
    <div className="tree-node" role="treeitem" aria-expanded={isExpanded}>
      <div
        className="tree-node__row"
        onClick={onToggle}
        style={{
          paddingLeft: 12,
          fontWeight: 600,
          color: 'var(--text-primary)',
          opacity: isHidden ? 0.6 : 1,
        }}
      >
        <ToggleArrow expanded={isExpanded} />
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleCategoryVisibility(label);
          }}
          title={isHidden ? `Show all ${label}` : `Hide all ${label}`}
          className="tree-node__icon tree-node__icon-toggle"
          style={{
            background: isHidden ? 'transparent' : color,
            border: isHidden ? `1.5px dashed ${color}` : 'none',
            cursor: 'pointer',
            padding: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 12,
            height: 12,
            borderRadius: '50%',
            transition: 'background-color 0.2s, border-color 0.2s, opacity 0.2s',
            color: isHidden ? color : '#fff',
            position: 'relative',
            margin: '0 3px',
            flexShrink: 0,
          }}
        >
          {isHidden ? (
            <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
              <line x1="1" y1="1" x2="23" y2="23" />
            </svg>
          ) : (
            <span className="tree-node__icon-eye-hover">
              <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </span>
          )}
        </button>
        <span className="tree-node__label" style={{ letterSpacing: '0.01em' }}>{label}</span>
        <span className="tree-node__count" style={{ background: 'var(--bg-surface-hover)' }}>{subdivisions.length}</span>
      </div>
      {isExpanded && (
        <div className="tree-node__children" role="group">
          {subdivisions.map(sub => (
            <TreeNode
              key={sub.id}
              node={sub}
              depth={1}
              selection={selection}
              expandedNodes={expandedNodes}
              onNavigate={onNavigate}
              hiddenSubdivisionIds={hiddenSubdivisionIds}
              onToggleVisibility={onToggleVisibility}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Unified tree node ─────────────────────────────────────────────────────

const NODE_META = {
  subdivision: { indent: 28, iconCls: 'tree-node__icon--subdivision' },
  plat: { indent: 44, iconCls: 'tree-node__icon--plat' },
  parcel: { indent: 60, iconCls: 'tree-node__icon--parcel' },
  building: { indent: 76, iconCls: 'tree-node__icon--building' },
  address: { indent: 92, iconCls: 'tree-node__icon--address' },
};

function TreeNode({ node, depth, selection, expandedNodes, onNavigate, hiddenSubdivisionIds, onToggleVisibility }) {
  const type = node.type || nodeTypeFromDepth(depth);
  const meta = NODE_META[type];
  const nodeKey = `${type}-${node.id}`;
  const isExpanded = expandedNodes.has(nodeKey);
  const isSelected = selection?.type === type && selection?.id == node.id;
  const isInChain = isNodeInSelectionChain(type, node.id, selection);
  const hasChildren = node.children?.length > 0;
  const elementRef = useRef(null);

  const isHidden = type === 'subdivision' && hiddenSubdivisionIds?.has(node.id);

  // Auto-scroll when this node becomes the selected node.
  useEffect(() => {
    if (isSelected && elementRef.current) {
      elementRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [isSelected]);

  const handleClick = useCallback(() => {
    onNavigate(type, node.id, node.name);
  }, [onNavigate, type, node.id, node.name]);

  // Compute display label.
  const label = type === 'plat' && node.label ? `${node.name} (${node.label})` : node.name;
  const countBadge = type === 'parcel'
    ? (node.buildingCount > 0 ? node.buildingCount : (node.addressCount > 0 ? node.addressCount : null))
    : type === 'building'
    ? (node.addressCount > 0 ? node.addressCount : null)
    : (node.addressCount || node.children?.length || null);

  // Color dot for subdivisions.
  const subdivisionColor = type === 'subdivision' ? getSubdivisionColor(node.category) : undefined;
  const iconStyle = type === 'subdivision' ? { background: subdivisionColor } : undefined;

  // Limit children for performance. Ensure the selected child is always rendered even if beyond index 200.
  const displayChildren = useMemo(() => {
    if (!node.children) return [];
    if (node.children.length <= 200) return node.children;

    let activeChildIndex = -1;
    if (selection) {
      activeChildIndex = node.children.findIndex(child => {
        const childType = child.type || nodeTypeFromDepth(depth + 1);
        if (childType === 'subdivision') return selection.subdivisionId == child.id;
        if (childType === 'plat') return selection.platId == child.id;
        if (childType === 'parcel') return selection.parcelId == child.id;
        if (childType === 'building') return selection.buildingId == child.id;
        if (childType === 'address') return selection.id == child.id && selection.type === 'address';
        return false;
      });
    }

    if (activeChildIndex < 200) {
      return node.children.slice(0, 200);
    } else {
      const sliced = node.children.slice(0, 199);
      sliced.push(node.children[activeChildIndex]);
      return sliced;
    }
  }, [node.children, selection, depth]);

  return (
    <div className="tree-node" ref={elementRef} role="treeitem" aria-expanded={hasChildren ? isExpanded : undefined}>
      <div
        className={`tree-node__row ${isSelected ? 'tree-node__row--selected' : ''} ${isInChain && !isSelected ? 'tree-node__row--in-chain' : ''}`}
        onClick={handleClick}
        style={{
          paddingLeft: meta.indent,
          opacity: isHidden ? 0.6 : 1,
        }}
      >
        <ToggleArrow expanded={isExpanded} empty={!hasChildren} />
        {type === 'subdivision' ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleVisibility(node.id);
            }}
            title={isHidden ? "Show subdivision" : "Hide subdivision"}
            className="tree-node__icon tree-node__icon--subdivision tree-node__icon-toggle"
            style={{
              background: isHidden ? 'transparent' : subdivisionColor,
              border: isHidden ? `1.5px dashed ${subdivisionColor}` : 'none',
              cursor: 'pointer',
              padding: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 16,
              height: 16,
              borderRadius: '3px',
              transition: 'background-color 0.2s, border-color 0.2s, opacity 0.2s',
              color: isHidden ? subdivisionColor : '#fff',
              position: 'relative',
              flexShrink: 0,
            }}
          >
            {isHidden ? (
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                <line x1="1" y1="1" x2="23" y2="23" />
              </svg>
            ) : (
              <span className="tree-node__icon-eye-hover">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              </span>
            )}
          </button>
        ) : (
          <span className={`tree-node__icon ${meta.iconCls}`} style={iconStyle} />
        )}
        <span className="tree-node__label" title={node.name}>{label}</span>
        {countBadge != null && <span className="tree-node__count">{countBadge}</span>}
      </div>
      {isExpanded && displayChildren.length > 0 && (
        <div className="tree-node__children" role="group">
          {displayChildren.map((child, i) => (
            <TreeNode
              key={`${child.type || ''}-${child.id ?? i}-${i}`}
              node={child}
              depth={depth + 1}
              selection={selection}
              expandedNodes={expandedNodes}
              onNavigate={onNavigate}
              hiddenSubdivisionIds={hiddenSubdivisionIds}
              onToggleVisibility={onToggleVisibility}
            />
          ))}
          {node.children.length > 200 && (
            <div className="tree-node__row" style={{ paddingLeft: meta.indent + 16, color: 'var(--text-muted)', fontSize: 12, cursor: 'default' }}>
              +{node.children.length - 200} more…
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────

function ToggleArrow({ expanded, empty }) {
  return (
    <span className={`tree-node__toggle ${expanded ? 'tree-node__toggle--expanded' : ''} ${empty ? 'tree-node__toggle--empty' : ''}`}>
      &#9656;
    </span>
  );
}

function nodeTypeFromDepth(depth) {
  return ['subdivision', 'plat', 'parcel', 'building', 'address'][depth - 1] ?? 'address';
}

/** Check if the given (type, id) is an ancestor of the current selection. */
function isNodeInSelectionChain(type, id, selection) {
  if (!selection) return false;
  switch (type) {
    case 'subdivision': return selection.subdivisionId == id;
    case 'plat': return selection.platId == id;
    case 'parcel': return selection.parcelId == id;
    case 'building': return selection.buildingId == id;
    default: return false;
  }
}


