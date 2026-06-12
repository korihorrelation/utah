'use client';

import { useMemo, useCallback, useState, useEffect, useRef } from 'react';
import { getSubdivisionColor, getSubdivisionCategory } from '../lib/colors';

/**
 * Recursive tree view for exploring the spatial hierarchy.
 *
 * Subdivisions are grouped into Residential / Commercial / Public categories.
 * Selection and expansion are driven entirely by the parent page.js:
 *   - `selection` determines which node is highlighted (and which ancestor chain is "active").
 *   - `expandedNodes` determines which tree branches are open.
 *   - `onNavigate` is the single callback; the hook handles expansion + breadcrumb.
 */
export default function HierarchyTree({ hierarchy, selection, expandedNodes, onNavigate }) {
  const [expandedCategories, setExpandedCategories] = useState(
    new Set(['Residential', 'Commercial', 'Public'])
  );

  const toggleCategory = useCallback((cat) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      next.has(cat) ? next.delete(cat) : next.add(cat);
      return next;
    });
  }, []);

  const grouped = useMemo(() => {
    const g = { Residential: [], Commercial: [], Public: [] };
    (hierarchy?.children || []).forEach(sub => {
      const cat = getSubdivisionCategory(sub.subdivisionType);
      g[cat].push(sub);
    });
    return g;
  }, [hierarchy]);

  // Auto-expand the category that contains the active subdivision.
  useEffect(() => {
    if (!selection?.subdivisionId || !hierarchy?.children) return;
    const sub = hierarchy.children.find(s => s.id === selection.subdivisionId);
    if (!sub) return;
    const cat = getSubdivisionCategory(sub.subdivisionType);
    setExpandedCategories(prev => (prev.has(cat) ? prev : new Set(prev).add(cat)));
  }, [selection?.subdivisionId, hierarchy]);

  if (!hierarchy) return null;

  const CATEGORIES = [
    { name: 'Residential', color: '#10b981', label: 'Residential Zones' },
    { name: 'Commercial', color: '#2563eb', label: 'Commercial Zones' },
    { name: 'Public', color: '#6366f1', label: 'Civic & Public Zones' },
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
          />
        );
      })}
    </div>
  );
}

// ── Category folder ───────────────────────────────────────────────────────

function CategoryNode({ label, color, subdivisions, isExpanded, onToggle, selection, expandedNodes, onNavigate }) {
  return (
    <div className="tree-node" role="treeitem" aria-expanded={isExpanded}>
      <div className="tree-node__row" onClick={onToggle} style={{ paddingLeft: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
        <ToggleArrow expanded={isExpanded} />
        <span className="tree-node__icon" style={{ background: color, width: 10, height: 10, borderRadius: '50%', margin: '0 3px' }} />
        <span className="tree-node__label" style={{ letterSpacing: '0.01em' }}>{label}</span>
        <span className="tree-node__count" style={{ background: 'var(--bg-surface-hover)' }}>{subdivisions.length}</span>
      </div>
      {isExpanded && (
        <div className="tree-node__children" role="group">
          {subdivisions.map(sub => (
            <TreeNode key={sub.id} node={sub} depth={1} selection={selection} expandedNodes={expandedNodes} onNavigate={onNavigate} />
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

function TreeNode({ node, depth, selection, expandedNodes, onNavigate }) {
  const type = node.type || nodeTypeFromDepth(depth);
  const meta = NODE_META[type];
  const nodeKey = `${type}-${node.id}`;
  const isExpanded = expandedNodes.has(nodeKey);
  const isSelected = selection?.type === type && selection?.id === node.id;
  const isInChain = isNodeInSelectionChain(type, node.id, selection);
  const hasChildren = node.children?.length > 0;
  const elementRef = useRef(null);

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
    : (node.parcelCount || node.children?.length || null);

  // Color dot for subdivisions.
  const iconStyle = type === 'subdivision' ? { background: getSubdivisionColor(node.subdivisionType) } : undefined;

  // Limit children for performance.
  const displayChildren = useMemo(() => {
    if (!node.children) return [];
    return node.children.slice(0, 200);
  }, [node.children]);

  return (
    <div className="tree-node" ref={elementRef} role="treeitem" aria-expanded={hasChildren ? isExpanded : undefined}>
      <div
        className={`tree-node__row ${isSelected ? 'tree-node__row--selected' : ''} ${isInChain && !isSelected ? 'tree-node__row--in-chain' : ''}`}
        onClick={handleClick}
        style={{ paddingLeft: meta.indent }}
      >
        <ToggleArrow expanded={isExpanded} empty={!hasChildren} />
        <span className={`tree-node__icon ${meta.iconCls}`} style={iconStyle} />
        <span className="tree-node__label" title={node.name}>{label}</span>
        {countBadge != null && <span className="tree-node__count">{countBadge}</span>}
      </div>
      {isExpanded && displayChildren.length > 0 && (
        <div className="tree-node__children" role="group">
          {displayChildren.map((child, i) => (
            <TreeNode key={`${child.type || ''}-${child.id ?? i}-${i}`} node={child} depth={depth + 1} selection={selection} expandedNodes={expandedNodes} onNavigate={onNavigate} />
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
    case 'subdivision': return selection.subdivisionId === id;
    case 'plat': return selection.platId === id;
    case 'parcel': return selection.parcelId === id;
    case 'building': return selection.buildingId === id;
    default: return false;
  }
}
