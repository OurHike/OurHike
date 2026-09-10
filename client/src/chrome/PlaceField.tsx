// A field that resolves to a place this phone can name (#1373, first run's
// frame 1b, and More → You after it).
//
// "Where do you hike?" is answered by typing a town, a park or a trailhead
// and taking a row - the same shape as the finder's field
// (screens/FindHike.tsx), resolved against lib/places.ts's index and never
// the network. Each row prints what the index actually knows: the kind, the
// state, and - where the exporter measured it - the miles of published
// trail the app holds there. "no trail data held" is a true sentence a
// hiker who lives somewhere the app does not cover should be able to read
// before they choose; a row for a document that measured nothing prints no
// figure at all rather than a zero (D13, D14).
//
// THE EMPTY STATES ARE SENTENCES, NOT A GREYED FIELD (D10). Until the index
// has been read there is nothing to search; the field says which of three
// things is true - still looking, nothing on this phone and no signal to get
// it, or nothing published yet - and every one of them names the way out:
// skip, and set it in More → You. The field never blocks the flow it sits
// in.

import { useId, useState } from 'react'
import { HikeFinderIcon } from './HikeFinderIcon'
import {
  placeKindLabel,
  searchPlaces,
  type Place,
  type PlacesDocument,
} from '../lib/places'
import type { DefaultPlace } from '../lib/defaultPlace'
import { formatDistance, type UnitSystem } from '../lib/units'
import './placeField.css'

export interface PlaceFieldProps {
  places: PlacesDocument
  /** Whether every read the index can make has answered (lib/usePlaces.ts).
   *  False is "still looking"; true with no places is "there are none". */
  settled: boolean
  online: boolean
  units: UnitSystem
  /** The place already taken, if any - its row reads as pressed. */
  picked: DefaultPlace | null
  onPick: (place: Place) => void
  /** The field's accessible name. */
  label: string
  autoFocus?: boolean
}

/** The first line of a row: the name, and the state where one was published. */
export function placeTitle(place: Pick<Place, 'name' | 'state'>): string {
  return place.state === undefined ? place.name : `${place.name}, ${place.state}`
}

/**
 * The second line: the kind, then the one fact worth choosing on.
 *
 * A trailhead or a lot names the park it sits in when the exporter placed
 * it. Everything else prints the trail the app holds there - measured miles
 * as a figure, a measured nothing as "no trail data held", and an
 * unmeasured document as no clause at all, because "no trail data held"
 * would then be a claim about the exporter's run rather than the place.
 */
export function placeMeta(place: Place, units: UnitSystem, measured: boolean): string {
  const kind = placeKindLabel(place).toLowerCase()
  if (
    (place.kind === 'trailhead' || place.kind === 'parking') &&
    place.within !== undefined
  ) {
    return `${kind} · ${place.within}`
  }
  if (place.trailMiles !== undefined) {
    const miles = formatDistance(place.trailMiles, units, 'whole')
    return place.kind === 'trail'
      ? `${kind} · ${miles}`
      : `${kind} · ${miles} of trail held`
  }
  if (measured && place.kind !== 'trail') return `${kind} · no trail data held`
  return kind
}

export function PlaceField({
  places,
  settled,
  online,
  units,
  picked,
  onPick,
  label,
  autoFocus = false,
}: PlaceFieldProps) {
  const [query, setQuery] = useState('')
  const listId = useId()
  const matches = searchPlaces(places.places, query)
  const nothingToSearch = places.places.length === 0

  let empty: string | null = null
  if (nothingToSearch) {
    empty = !settled
      ? 'Looking for the list of parks and trailheads…'
      : online
        ? 'The list of places has not been published yet. Skip for now and set this in More → You.'
        : 'No list of places on this phone yet — it arrives with signal. Skip for now and set this in More → You.'
  } else if (query.trim() !== '' && matches.length === 0) {
    empty = 'Nothing here by that name. Try the park, or the nearest town.'
  }

  return (
    <div className="place-field">
      <label className="place-field__search">
        <HikeFinderIcon name="search" className="place-field__search-icon" />
        <span className="visually-hidden">{label}</span>
        <input
          className="place-field__input"
          type="search"
          placeholder="Town, park, or trailhead"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          autoComplete="off"
          autoFocus={autoFocus}
          aria-controls={listId}
          disabled={nothingToSearch && settled}
        />
      </label>

      {empty !== null ? (
        <p className="place-field__empty" role="status">
          {empty}
        </p>
      ) : (
        matches.length > 0 && (
          <ul id={listId} className="place-field__places" aria-label="Places">
            {matches.map((place) => (
              <li key={place.id}>
                <button
                  type="button"
                  className="place-field__place"
                  aria-pressed={picked !== null && picked.id === place.id}
                  onClick={() => onPick(place)}
                >
                  <span className="place-field__name">{placeTitle(place)}</span>
                  <span className="place-field__meta">
                    {placeMeta(place, units, places.trailMilesMeasured)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )
      )}
    </div>
  )
}
