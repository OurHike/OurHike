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
//
// SINCE #1373 (FRAME 14D) IT ALSO SEARCHES THE PLACES INDEX - the parks,
// towns, trailheads, lots and long trails #1371 publishes - under the
// waypoint matches, so the map can be MOVED to a place rather than opened
// on a pin. The frame asked for it on the volunteer map, where the
// workday pins are already drawn and moving the map to a park is what finds
// the workdays in it; it is offered on every mode for lib/hikerMode.ts's
// reason (a mode never hides a feature). Still local: the index is a kept
// copy (lib/placesData.ts), and a phone that holds none is a phone this
// box offers nothing extra on, said by what the placeholder names.

import { useState } from 'react'
import { searchPois, type SearchablePoi } from '../lib/searchPoi'
import { searchPlaces, placeKindLabel, type Place } from '../lib/places'
import { placeTitle } from './PlaceField'
import { typeLabel } from './legendLabels'

export interface SearchProps {
  open: boolean
  pois: SearchablePoi[]
  onSelect: (poi: SearchablePoi) => void
  onClose: () => void
  /**
   * The places index (#1373, frame 14d), offered under the waypoint
   * matches. Absent, or empty, on a phone that holds no index - and then
   * nothing here mentions parks, because a placeholder promising what the
   * box cannot find is a refusal dressed as a door (D10).
   */
  places?: readonly Place[]
  /** What a place row does. Without it the rows are not drawn at all. */
  onSelectPlace?: (place: Place) => void
}

/** The second line of a place row: its kind, and the park a trailhead or a
 *  lot sits in where the exporter placed it. No trail miles here - the
 *  first-run field prints those where a hiker is choosing a home; a search
 *  result is a place to go, and the map beside it shows what is there. */
function placeLine(place: Place): string {
  const kind = placeKindLabel(place)
  return (place.kind === 'trailhead' || place.kind === 'parking') &&
    place.within !== undefined
    ? `${kind} · ${place.within}`
    : kind
}

export function Search({
  open,
  pois,
  onSelect,
  onClose,
  places,
  onSelectPlace,
}: SearchProps) {
  const [query, setQuery] = useState('')

  if (!open) return null

  const results = searchPois(query, pois)
  const placesOffered =
    places !== undefined && places.length > 0 && onSelectPlace !== undefined
  const placeResults = placesOffered ? searchPlaces(places, query) : []
  const searched = query.trim() !== ''

  return (
    /* Escape closes it (#315). The panel covers the map opaquely and its only
       other exit was the Cancel button, which on a phone means finding a
       target with a thumb; with nothing downloaded yet the panel is a blank
       page over the map, so "how do I get out of this" is a real question a
       hiker can arrive at with no obvious answer.

       On the container rather than on the input, because the input is not the
       only thing that can hold focus here - tabbing into the results list
       used to leave Escape doing nothing, which is the state somebody
       scrolling results is actually in. `onKeyDown` bubbles from either. */
    <div className="search" onKeyDown={(event) => event.key === 'Escape' && onClose()}>
      <div className="search__bar">
        <input
          type="search"
          className="search__input"
          // The header has been taken over specifically so someone can type
          // straight away.
          autoFocus
          value={query}
          placeholder={
            placesOffered
              ? 'Search shelters, water, parks, towns'
              : 'Search shelters, water, towns'
          }
          aria-label="Search the downloaded map"
          onChange={(event) => setQuery(event.target.value)}
        />
        <button type="button" className="search__close" onClick={onClose}>
          Cancel
        </button>
      </div>

      {searched && results.length === 0 && placeResults.length === 0 && (
        <p className="search__empty">
          Nothing here by that name. It may exist outside the part of the trail you
          downloaded.
        </p>
      )}

      {results.length > 0 && (
        <ul className="search__results" aria-label="Waypoints">
          {results.map((poi) => (
            <li key={poi.id} className="search__result">
              <button
                type="button"
                className="search__result-button"
                onClick={() => onSelect(poi)}
              >
                <span className="search__result-name">{poi.name}</span>
                <span className="search__result-meta">
                  {poi.mile === undefined
                    ? typeLabel(poi.type)
                    : `${typeLabel(poi.type)} · mi ${poi.mile.toLocaleString('en-US', {
                        minimumFractionDigits: 1,
                        maximumFractionDigits: 1,
                      })}`}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Under the waypoints, never mixed in: a waypoint opens a card and a
          place moves the map, and a list that did both with no seam would
          have a hiker guessing which row does which. The heading is what
          makes the seam readable; it is drawn only when there is something
          under it. */}
      {placeResults.length > 0 && (
        <>
          <h2 className="search__group">Places</h2>
          <ul className="search__results" aria-label="Places">
            {placeResults.map((place) => (
              <li key={place.id} className="search__result">
                <button
                  type="button"
                  className="search__result-button"
                  onClick={() => onSelectPlace?.(place)}
                >
                  <span className="search__result-name">{placeTitle(place)}</span>
                  <span className="search__result-meta">{placeLine(place)}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
