// Search (WIREFRAMES.md Interactions, and `7c` for the empty state).
//
// Local only. There is no network path in this component or in
// lib/searchPoi.ts, and that is the design rather than an unfinished edge:
// search that needs signal fails exactly where someone needs it.
//
// The empty state is the part worth care. "No results" is a dead end;
// "that may exist just outside what you downloaded" tells someone what to do
// next. The component never suggests going online, because going online is
// not a thing that would help here.

import { useState } from 'react'
import { searchPois, type SearchablePoi } from '../lib/searchPoi'
import { typeLabel } from './legendLabels'

export interface SearchProps {
  open: boolean
  pois: SearchablePoi[]
  onSelect: (poi: SearchablePoi) => void
  onClose: () => void
}

export function Search({ open, pois, onSelect, onClose }: SearchProps) {
  const [query, setQuery] = useState('')

  if (!open) return null

  const results = searchPois(query, pois)
  const searched = query.trim() !== ''

  return (
    <div className="search">
      <div className="search__bar">
        <input
          type="search"
          className="search__input"
          // The header has been taken over specifically so someone can type
          // straight away.
          autoFocus
          value={query}
          placeholder="Search shelters, water, towns"
          aria-label="Search the downloaded map"
          onChange={(event) => setQuery(event.target.value)}
        />
        <button type="button" className="search__close" onClick={onClose}>
          Cancel
        </button>
      </div>

      {searched && results.length === 0 && (
        <p className="search__empty">
          Nothing here by that name. It may exist outside the part of the trail you
          downloaded.
        </p>
      )}

      {results.length > 0 && (
        <ul className="search__results">
          {results.map((poi) => (
            <li key={poi.id} className="search__result">
              <button
                type="button"
                className="search__result-button"
                onClick={() => onSelect(poi)}
              >
                <span className="search__result-name">{poi.name}</span>
                <span className="search__result-meta">
                  {`${typeLabel(poi.type)} · mi ${poi.mile.toLocaleString('en-US', {
                    minimumFractionDigits: 1,
                    maximumFractionDigits: 1,
                  })}`}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
