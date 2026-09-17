// Saying where a report is - the one control every report surface shares
// (#1563).
//
// WHAT THIS REPLACES. The report window offered a list of the places walked
// past today, withheld unless the phone had walked miles AND had a fix; the
// long form offered a crosshair; the closure form a typed mile. Three answers
// to one question, and none of them could name a waypoint the report had not
// started from - so a hiker standing at a shelter who opened the report from
// Today had no way to say "at the shelter". This is the one answer, drawn
// once, handed a vocabulary by lib/reportLocation.ts and nothing else.
//
// THE ORDER IS THE PREFERENCE. A named place comes first because it is the
// answer a moderator can act on without a map: a report AT Bailey Gap Shelter
// is a report about a place with a name, a club and a maintainer. The fix
// comes second, with its radius and its age printed beside it, so a hiker can
// see a ±800 ft fix for what it is and pick the shelter instead. The map comes
// third, for the case the fix is wrong and no place is near. Words come last,
// and only when nothing else can place the report at all.
//
// NOTHING HERE IS HIDDEN BECAUSE IT WOULD BE EMPTY, AND NOTHING IS DRAWN
// DEAD. A row that cannot do anything is not drawn (D10): no fix, no "where
// you are"; no map to aim at, no map row; no candidates and no search, no
// places section. What IS drawn always works.
//
// CONTROLLED THROUGHOUT. The choice, the words and the candidates belong to
// the caller; this component holds only the text typed into its search box,
// which dies with it. That is what lets the window stand aside for the map
// and come back with the same choice, and what stops two surfaces holding two
// opinions about where one report is.

import { useId, useState } from 'react'
import {
  AT_THE_FIX,
  awayWords,
  fixWords,
  hasPlace,
  locationWords,
  type FixSnapshot,
  type LocationChoice,
  type NearbyPlace,
} from '../lib/reportLocation'
import { placeWords } from '../lib/placement'
import type { UnitSystem } from '../lib/units'
import './locationPicker.css'

/**
 * Past this many rows a filter beats a scroll; below it the box is a control
 * in the way. The report window's own line, carried over.
 *
 * @unvalidated - seven is the number the passed-places list used and nobody
 * measured it there either. What would settle it is the row count at which a
 * hiker starts typing rather than scrolling, which needs a hand on a phone.
 */
const FILTER_FROM_ROWS = 7

export interface LocationPickerProps {
  /** Where the report is now. The row that matches is marked pressed. */
  choice: LocationChoice
  /** The phone's fix, or null - which is when "where you are" is not drawn. */
  fix: FixSnapshot | null
  /**
   * Named places worth offering unasked - lib/reportLocation.ts's
   * `nearbyPlaces`, nearest first, already limited. Empty is ordinary: an
   * early start has passed nothing and a fixless phone is near nothing.
   */
  places: readonly NearbyPlace[]
  /**
   * Places found by name across everything on the phone, for the search box.
   * Absent draws a plain filter over `places` instead, and only past
   * {@link FILTER_FROM_ROWS} of them.
   */
  onSearch?: (query: string) => readonly NearbyPlace[]
  units: UnitSystem
  /** Whether a trail index is on the phone - what `placeWords` needs to tell
   *  "this spot" from "more than 3 mi off the trail". */
  knowsTrail: boolean
  onChoose: (choice: LocationChoice) => void
  /** Hand the hiker the map to aim at. Absent draws no map row: a control
   *  that opens nothing is worse than none. */
  onPointOnMap?: () => void
  /**
   * The hiker's own words for where this was, controlled by the caller.
   * Drawn only when nothing else can place the report - with a fix, a
   * waypoint or a marked spot the question is already answered, and asking
   * would collect prose nobody needs beside a location the report has.
   */
  words?: { value: string; onChange: (value: string) => void }
  /** Opened because the report has no place yet: leads with why. */
  needed?: boolean
  now?: Date
}

export function LocationPicker({
  choice,
  fix,
  places,
  onSearch,
  units,
  knowsTrail,
  onChoose,
  onPointOnMap,
  words,
  needed = false,
  now = new Date(),
}: LocationPickerProps) {
  const headingId = useId()
  const [query, setQuery] = useState('')
  const needle = query.trim()

  const searchable = onSearch !== undefined || places.length >= FILTER_FROM_ROWS
  const shown: readonly NearbyPlace[] =
    needle === ''
      ? places
      : onSearch !== undefined
        ? onSearch(needle)
        : places.filter((place) =>
            place.name.toLowerCase().includes(needle.toLowerCase()),
          )

  const placesSection =
    places.length === 0 && onSearch === undefined ? null : (
      <section className="location-picker__section" aria-labelledby={headingId}>
        <h3 className="location-picker__heading" id={headingId}>
          A named place
        </h3>
        {searchable && (
          <input
            type="search"
            className="location-picker__search"
            data-testid="location-search"
            value={query}
            placeholder="Find a place by name"
            aria-label="Find a place by name"
            onChange={(event) => setQuery(event.target.value)}
          />
        )}
        {/* NO COUNT, ANYWHERE - lib/passedToday.ts's rule, kept on the one
          surface that could most easily break it. */}
        <ul className="location-picker__places" aria-label="Places">
          {shown.map((place) => {
            const chosen = choice.kind === 'poi' && choice.poiId === place.id
            const marker =
              place.mile === undefined ? null : placeWords(place.mile, true, units)
            const away =
              place.awayMiles === null ? null : awayWords(place.awayMiles, units)
            const meta = [away, marker].filter((part): part is string => part !== null)
            return (
              <li key={place.id}>
                <button
                  type="button"
                  className="location-picker__row"
                  data-testid={`location-place-${place.id}`}
                  aria-pressed={chosen}
                  onClick={() =>
                    onChoose({
                      kind: 'poi',
                      poiId: place.id,
                      name: place.name,
                      lat: place.lat,
                      lon: place.lon,
                      ...(place.mile !== undefined ? { mile: place.mile } : {}),
                    })
                  }
                >
                  <span className="location-picker__name">{place.name}</span>
                  {meta.length > 0 && (
                    <span className="location-picker__meta">{meta.join(' · ')}</span>
                  )}
                </button>
              </li>
            )
          })}
          {shown.length === 0 && (
            <li className="location-picker__empty">
              {/* "Not found" and "outside what you downloaded" are different
                answers (lib/searchPoi.ts), and this one is the second. */}
              {needle === ''
                ? 'Nothing nearby to offer — find one by name.'
                : 'Nothing by that name on this phone.'}
            </li>
          )}
        </ul>
      </section>
    )

  const pointLabel =
    choice.kind === 'point'
      ? locationWords(choice, fix, units, knowsTrail, now).label
      : 'Tap the spot, then keep it'

  return (
    <div className="location-picker" data-testid="location-picker">
      {needed && (
        <p className="location-picker__needed" role="alert" data-testid="location-needed">
          Say where this is first — a place nearby, where you are, or a spot on the map.
        </p>
      )}

      {placesSection}

      {(fix !== null || onPointOnMap !== undefined) && (
        <ul className="location-picker__options" aria-label="Other ways to say where">
          {fix !== null && (
            <li>
              <button
                type="button"
                className="location-picker__row"
                data-testid="location-fix"
                aria-pressed={choice.kind === 'fix'}
                onClick={() => onChoose(AT_THE_FIX)}
              >
                <span className="location-picker__name">Where you are</span>
                {/* The radius and the age, so a ±800 ft fix from twelve
                    minutes ago reads as exactly that before anybody files
                    under it. */}
                <span className="location-picker__meta">{fixWords(fix, units, now)}</span>
              </button>
            </li>
          )}
          {onPointOnMap !== undefined && (
            <li>
              <button
                type="button"
                className="location-picker__row location-picker__row--door"
                data-testid="location-map"
                aria-pressed={choice.kind === 'point'}
                onClick={onPointOnMap}
              >
                <span className="location-picker__name">Mark it on the map</span>
                <span className="location-picker__meta">{pointLabel}</span>
                <span className="location-picker__chevron" aria-hidden="true">
                  ›
                </span>
              </button>
            </li>
          )}
        </ul>
      )}

      {words !== undefined && !hasPlace(choice, fix) && (
        <label className="location-picker__words">
          <span className="location-picker__heading">Or say where in words</span>
          <textarea
            className="location-picker__textarea"
            data-testid="location-words"
            rows={2}
            value={words.value}
            onChange={(event) => words.onChange(event.target.value)}
          />
          {/* Prose that stays prose. A typed name turned into coordinates
              would be a confident wrong dot on every phone that downloads
              the report; a moderator places it, the app does not guess. */}
          <span className="location-picker__hint">
            A landmark, a road, a shelter you passed — however you would say it to
            somebody. It travels as your words; nobody turns it into a pin.
          </span>
        </label>
      )}
    </div>
  )
}
