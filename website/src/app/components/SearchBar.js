'use client';

import { useState, useRef, useEffect } from 'react';

/**
 * Address search bar with typeahead results.
 */
export default function SearchBar({ onSearch, searchResults, onSelectResult, searchQuery }) {
  const [focused, setFocused] = useState(false);
  const inputRef = useRef(null);
  const containerRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setFocused(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const showResults = focused && searchResults.length > 0;

  return (
    <div className="search-bar" ref={containerRef}>
      <svg className="search-bar__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.35-4.35" />
      </svg>
      <input
        ref={inputRef}
        className="search-bar__input"
        type="text"
        placeholder="Search addresses, parcels..."
        value={searchQuery}
        onChange={(e) => onSearch(e.target.value)}
        onFocus={() => setFocused(true)}
        id="global-search"
        autoComplete="off"
      />
      {showResults && (
        <div className="search-bar__results">
          {searchResults.slice(0, 20).map((result, i) => (
            <div
              key={`${result.type}-${result.id}-${i}`}
              className="search-bar__result"
              onClick={() => {
                onSelectResult(result);
                setFocused(false);
              }}
            >
              <div className="search-bar__result-address">{result.name}</div>
              <div className="search-bar__result-context">{result.context}</div>
            </div>
          ))}
          {searchResults.length > 20 && (
            <div className="search-bar__result" style={{ color: 'var(--text-muted)', cursor: 'default' }}>
              +{searchResults.length - 20} more results...
            </div>
          )}
        </div>
      )}
    </div>
  );
}
