'use client';

import { useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { useHierarchy } from './hooks/useHierarchy';
import BreadcrumbBar from './components/BreadcrumbBar';
import HierarchyTree from './components/HierarchyTree';
import DetailPanel from './components/DetailPanel';
import SearchBar from './components/SearchBar';

// Dynamic import of MapView to disable SSR (Leaflet requires window)
const MapView = dynamic(() => import('./components/MapView'), {
  ssr: false,
  loading: () => (
    <div className="map-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="loading-spinner" />
    </div>
  ),
});

export default function HomePage() {
  const {
    hierarchy,
    subdivisions,
    cityBoundary,
    roads,
    paths,
    parks,
    pois,
    residentialAddresses,
    activeTile,
    activeSubdivisionId,
    selection,
    drillPath,
    loading,
    tileLoading,
    searchQuery,
    searchResults,
    expandedNodes,
    navigateTo,
    performSearch,
  } = useHierarchy();

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [hiddenSubdivisionIds, setHiddenSubdivisionIds] = useState(new Set());
  const [hiddenCategories, setHiddenCategories] = useState(new Set());

  const toggleSubdivisionVisibility = useCallback((subdivisionId) => {
    setHiddenSubdivisionIds((prev) => {
      const next = new Set(prev);
      if (next.has(subdivisionId)) {
        next.delete(subdivisionId);
      } else {
        next.add(subdivisionId);
      }
      return next;
    });
  }, []);

  const toggleCategoryVisibility = useCallback((categoryName) => {
    setHiddenCategories((prev) => {
      const next = new Set(prev);
      if (next.has(categoryName)) {
        next.delete(categoryName);
      } else {
        next.add(categoryName);
      }
      return next;
    });
  }, []);

  // ── Escape key listener: go back a layer in hierarchy ──
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Don't capture when typing in inputs
      const tag = e.target.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      if (e.key === 'Escape') {
        if (drillPath.length > 1) {
          e.preventDefault();
          const parent = drillPath[drillPath.length - 2];
          navigateTo(parent.type, parent.id, parent.name);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [drillPath, navigateTo]);

  if (loading) {
    return (
      <div className="app-layout">
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '16px' }}>
          <div className="loading-spinner" />
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Loading Saratoga Springs GIS data...</p>
        </div>
      </div>
    );
  }

  const handleSearchSelect = (result) => {
    navigateTo(result.type, result.id, result.name);
    setSidebarOpen(true);
  };

  return (
    <div className="app-layout">
      {/* Header */}
      <header className="app-header" id="app-header">
        <div className="app-header__logo">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l5.447 2.724A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
          <div>
            <div className="app-header__title">Saratoga Springs Map</div>
          </div>
        </div>

        <div className="app-header__search">
          <SearchBar
            onSearch={performSearch}
            searchResults={searchResults}
            onSelectResult={handleSearchSelect}
            searchQuery={searchQuery}
          />
        </div>
      </header>

      {/* Body */}
      <div className="app-body">
        {/* Sidebar overlay for mobile */}
        <div
          className={`sidebar-overlay ${sidebarOpen ? 'sidebar-overlay--visible' : ''}`}
          onClick={() => setSidebarOpen(false)}
        />

        {/* Sidebar */}
        <aside className={`sidebar ${sidebarOpen ? 'sidebar--open' : ''}`} id="hierarchy-sidebar">
          <BreadcrumbBar drillPath={drillPath} onNavigate={navigateTo} />
          <HierarchyTree
            hierarchy={hierarchy}
            selection={selection}
            expandedNodes={expandedNodes}
            onNavigate={navigateTo}
            hiddenSubdivisionIds={hiddenSubdivisionIds}
            onToggleVisibility={toggleSubdivisionVisibility}
            hiddenCategories={hiddenCategories}
            onToggleCategoryVisibility={toggleCategoryVisibility}
          />
          <DetailPanel
            selection={selection}
            activeTile={activeTile}
            hierarchy={hierarchy}
          />
        </aside>

        {/* Map */}
        <MapView
          cityBoundary={cityBoundary}
          subdivisions={subdivisions}
          roads={roads}
          paths={paths}
          parks={parks}
          pois={pois}
          residentialAddresses={residentialAddresses}
          activeTile={activeTile}
          activeSubdivisionId={activeSubdivisionId}
          selection={selection}
          onNavigate={navigateTo}
          hiddenSubdivisionIds={hiddenSubdivisionIds}
          hiddenCategories={hiddenCategories}
        />

        {/* Tile loading indicator */}
        {tileLoading && (
          <div className="loading-overlay">
            <div className="loading-spinner" />
          </div>
        )}
      </div>
    </div>
  );
}
