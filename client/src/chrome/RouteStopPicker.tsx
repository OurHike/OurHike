// One search screen behind every stop field (#755, the chosen "route by
// destination" flow): the app's existing waypoint search wearing a route
// hat - same matching, same honesty about miles - plus the two other doors
// as rows at the bottom: choose on the map, or a distance from the previous
// stop. Name FIRST, because "users should be allowed to lookup by name
// first" was the design's own brief; the map and the slider are one tap
// further, never gone.
//
// Only POIs that carry a published pipeline mile are offered (the caller
// filters): a stop with no mile cannot join the axis every figure and every
// day boundary is computed on, and offering it here would manufacture the
// mixed-scale arithmetic lib/route.ts exists to prevent.

import { useMemo, useState } from 'react'
import { nearestStopBeyond } from '../lib/dayPlanner'
import { isTown, parseMileQuery, searchNearMile, searchPois } from '../lib/searchPoi'
import type { StoredPoi } from '../lib/trailData'
import { formatDistance, type UnitSystem } from '../lib/units'
import { typeLabel } from './legendLabels'
import '../screens/plan.css'

/** A POI that can be a stop: its PIPELINE mile is known. */
export interface RouteStopChoice {
  id: string
  name: string
  type: string
  mile: number
  /** Which pipeline layer published it - the only thing that separates a
   *  town from an outfitter, both of which are `resupply` (#802). */
  source?: string
}

/**
 * What the filter chips offer.
 *
 * `town` is not a `poi_type`: it is `resupply` published by ATC's
 * Communities layer, which is a real distinction the export records and the
 * hiker cares about (a town is where you sleep in a bed; an outfitter is
 * where you buy a stove).
 */
type StopFilter = 'all' | 'town' | 'shelter' | 'campsite' | 'water' | 'crossing'

const FILTERS: { key: StopFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'town', label: 'Towns' },
  { key: 'shelter', label: 'Shelters' },
  { key: 'campsite', label: 'Camps' },
  { key: 'water', label: 'Water' },
  { key: 'crossing', label: 'Roads' },
]

function matchesFilter(poi: RouteStopChoice, filter: StopFilter): boolean {
  if (filter === 'all') return true
  if (filter === 'town') return isTown(poi)
  return poi.type === filter
}

/** What a door hands back - enough to become a draft stop. */
export interface PickedStop {
  mile: number
  name?: string
  poiId?: string
}

export interface RouteStopPickerProps {
  choices: readonly RouteStopChoice[]
  /** For the distance door's snap - the full store, so the snap sees the
   *  same shelters and campsites the day planner will. */
  pois: readonly StoredPoi[]
  /** The stop before the slot being filled, or null when there is none
   *  (picking the start) - the distance door needs somewhere to measure
   *  from. */
  previous: { mile: number; label: string } | null
  /** Which way the route walks, for the distance door's direction. */
  south: boolean
  /** True when the slot is a destination between the ends - the one kind of
   *  stop that can be removed outright. */
  removable: boolean
  units: UnitSystem
  onPick: (stop: PickedStop) => void
  onMapPick: () => void
  onRemove: () => void
  onClose: () => void
}

// An input affordance like the entrance's sliders: a day, maybe two, past
// the previous stop. A destination further out is named or mapped instead.
const DISTANCE_MIN = 1
const DISTANCE_MAX = 30
const DISTANCE_DEFAULT = 8

export function RouteStopPicker({
  choices,
  pois,
  previous,
  south,
  removable,
  units,
  onPick,
  onMapPick,
  onRemove,
  onClose,
}: RouteStopPickerProps) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<StopFilter>('all')
  const [byDistance, setByDistance] = useState(false)
  const [distanceMi, setDistanceMi] = useState(DISTANCE_DEFAULT)

  const filtered = choices.filter((poi) => matchesFilter(poi, filter))
  // A mile is a query too (#802). Read BOTH ways rather than either: a
  // place named "500" would otherwise disappear the moment the number was
  // recognised, so names come first and the mile results sit under them.
  const askedMile = parseMileQuery(query)
  // searchPois hands back a subset of the very objects it was given, so the
  // stronger choice type survives the trip.
  const results = searchPois(query, [...filtered]) as RouteStopChoice[]
  const nearMile = askedMile === null ? [] : searchNearMile(askedMile, filtered)
  const searched = query.trim() !== ''

  // Where the distance answer lands: snapped to a real place to sleep when
  // one lies that way, the bare mile (clamped to the data's own reach)
  // when none does - shown before it is kept, never silently.
  const landing = useMemo(() => {
    if (!byDistance || previous === null) return null
    const raw = previous.mile + (south ? -distanceMi : distanceMi)
    const snapped = nearestStopBeyond(pois, previous.mile, raw)
    if (snapped !== null) {
      return {
        mile: snapped.mile,
        name: snapped.name,
        poiId: snapped.poiId,
        kind: snapped.kind as 'shelter' | 'campsite',
      }
    }
    let low = Infinity
    let high = -Infinity
    for (const choice of choices) {
      if (choice.mile < low) low = choice.mile
      if (choice.mile > high) high = choice.mile
    }
    if (low > high) return null
    const clamped = Math.min(high, Math.max(low, raw))
    if (clamped === previous.mile) return null
    return { mile: clamped, name: undefined, poiId: undefined, kind: undefined }
  }, [byDistance, previous, south, distanceMi, pois, choices])

  if (byDistance && previous !== null) {
    return (
      <div className="stop-picker" role="dialog" aria-label="A distance from here">
        <div className="stop-picker__bar">
          <button
            type="button"
            className="stop-picker__back"
            onClick={() => setByDistance(false)}
          >
            <span className="visually-hidden">Back to the search</span>
            <span aria-hidden="true">&larr;</span>
          </button>
          <h2 className="stop-picker__title">A distance from {previous.label}</h2>
        </div>

        <div className="stop-picker__distance">
          <div className="plan-target__value">
            <span className="plan-target__figure">
              {formatDistance(distanceMi, units, 'trimmed')}
            </span>
            <span className="plan-target__unit-note">
              {south ? 'south' : 'north'} of {previous.label}
            </span>
            <input
              type="range"
              className="plan-target__slider"
              min={DISTANCE_MIN}
              max={DISTANCE_MAX}
              step={1}
              value={distanceMi}
              aria-label={`Miles from ${previous.label}`}
              onChange={(event) => setDistanceMi(Number(event.target.value))}
            />
          </div>

          <div className="route-entrance__end">
            <span className="route-entrance__end-label">Lands near</span>
            {landing === null ? (
              <span className="route-entrance__end-note">
                nothing that way in this download
              </span>
            ) : (
              <span className="route-entrance__end-stop">
                <span className="route-entrance__end-name">
                  {landing.name ??
                    `mi ${landing.mile.toLocaleString('en-US', {
                      minimumFractionDigits: 1,
                      maximumFractionDigits: 1,
                    })}`}
                </span>
                <span className="route-entrance__end-meta">
                  {landing.kind === undefined
                    ? 'no shelter or campsite nearby - the bare mile'
                    : `${typeLabel(landing.kind)} · mi ${landing.mile.toLocaleString(
                        'en-US',
                        { minimumFractionDigits: 1, maximumFractionDigits: 1 },
                      )}`}
                </span>
              </span>
            )}
          </div>

          <button
            type="button"
            className="plan__primary"
            disabled={landing === null}
            onClick={() => {
              if (landing === null) return
              onPick({
                mile: landing.mile,
                ...(landing.name === undefined ? {} : { name: landing.name }),
                ...(landing.poiId === undefined ? {} : { poiId: landing.poiId }),
              })
            }}
          >
            Use this stop
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="stop-picker" role="dialog" aria-label="Choose a stop">
      <div className="stop-picker__bar">
        <button type="button" className="stop-picker__back" onClick={onClose}>
          <span className="visually-hidden">Back</span>
          <span aria-hidden="true">&larr;</span>
        </button>
        <input
          type="search"
          className="stop-picker__input"
          autoFocus
          value={query}
          placeholder="Shelter, town, or “mi 500”"
          aria-label="Search for a stop"
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      <div className="stop-picker__filters" role="group" aria-label="Kind of place">
        {FILTERS.map((option) => (
          <button
            key={option.key}
            type="button"
            className={
              option.key === filter
                ? 'stop-picker__filter stop-picker__filter--on'
                : 'stop-picker__filter'
            }
            aria-pressed={option.key === filter}
            onClick={() => setFilter(option.key)}
          >
            {option.label}
          </button>
        ))}
      </div>

      {searched &&
        results.length === 0 &&
        nearMile.length === 0 &&
        askedMile === null && (
          <p className="stop-picker__empty">
            Nothing here by that name. It may exist outside the part of the trail you
            downloaded.
          </p>
        )}

      {results.length > 0 && (
        <ul className="stop-picker__results">
          {results.map((poi) => (
            <li key={poi.id} className="stop-picker__result">
              <button
                type="button"
                className="stop-picker__result-button"
                onClick={() => onPick({ mile: poi.mile, name: poi.name, poiId: poi.id })}
              >
                <span className="stop-picker__result-name">{poi.name}</span>
                <span className="stop-picker__result-meta">
                  {isTown(poi) ? 'town' : typeLabel(poi.type)} · mi{' '}
                  {poi.mile.toLocaleString('en-US', {
                    minimumFractionDigits: 1,
                    maximumFractionDigits: 1,
                  })}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {askedMile !== null && (
        <>
          <p className="stop-picker__near-title">
            Around mile {askedMile.toLocaleString('en-US', { maximumFractionDigits: 1 })}
          </p>
          <ul className="stop-picker__results">
            {nearMile.map((poi) => {
              const offset = poi.mile - askedMile
              return (
                <li key={poi.id} className="stop-picker__result">
                  <button
                    type="button"
                    className="stop-picker__result-button"
                    onClick={() =>
                      onPick({ mile: poi.mile, name: poi.name, poiId: poi.id })
                    }
                  >
                    <span className="stop-picker__result-name">{poi.name}</span>
                    <span className="stop-picker__result-meta">
                      {isTown(poi) ? 'town' : typeLabel(poi.type)} ·{' '}
                      {offset === 0
                        ? 'on it'
                        : `${formatDistance(Math.abs(offset), units, 'trimmed')} ${
                            offset > 0 ? 'north' : 'south'
                          }`}
                    </span>
                  </button>
                </li>
              )
            })}
            {/* Sometimes the answer really is the number: a road a shuttle
                meets, a point somebody was given. Every other row here is a
                real place with a name. */}
            <li className="stop-picker__result">
              <button
                type="button"
                className="stop-picker__result-button"
                onClick={() => onPick({ mile: askedMile })}
              >
                <span className="stop-picker__result-name">
                  Just mile{' '}
                  {askedMile.toLocaleString('en-US', {
                    minimumFractionDigits: 1,
                    maximumFractionDigits: 1,
                  })}
                </span>
                <span className="stop-picker__result-meta">
                  no place, just the number
                </span>
              </button>
            </li>
          </ul>
        </>
      )}

      <div className="stop-picker__doors">
        <button type="button" className="stop-picker__door" onClick={onMapPick}>
          Choose on the map
        </button>
        {previous !== null && (
          <button
            type="button"
            className="stop-picker__door"
            onClick={() => setByDistance(true)}
          >
            A distance from {previous.label}&hellip;
          </button>
        )}
        {removable && (
          <button
            type="button"
            className="stop-picker__door stop-picker__door--remove"
            onClick={onRemove}
          >
            Remove this stop
          </button>
        )}
        <p className="stop-picker__limit" role="note">
          Only the AT centerline can carry a route. Side trails and the road walk into
          town aren&rsquo;t routable yet.
        </p>
      </div>
    </div>
  )
}
