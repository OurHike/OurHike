// The route builder's front door (#755, reworked to the chosen "route by
// destination" flow): where from, then how far or how long - the hiker's
// real first question, asked before any map gesture is required of them.
// "Use this stretch" lands the resolved pair on the editable stop surface
// (RouteStopsPanel); the tap-to-drop builder this replaces made the same
// journey start with a ritual nothing on screen explained.
//
// The honesty rules carried over from the sheet this grew out of
// (PlanTargetSheet):
//  - "How long" converts days to trail THROUGH the default walking-hours
//    target, and the callout says so in words, with the number - days are
//    the unit hikers think in, and the assumption is theirs to change, not
//    a hidden constant.
//  - Sizing by days needs the elevation profile; without one the toggle is
//    disabled and says why, rather than pricing every climb at zero.
//  - The end SNAPS to a real place to sleep, and the row shows the snapped
//    stop's own name and mile - the drift from the asked-for distance is
//    visible before anything is kept.

import type { UnitSystem } from '../lib/units'
import { formatDistance } from '../lib/units'
import { stopLabel } from '../lib/planDisplay'
import { typeLabel } from './legendLabels'
// The entrance deliberately wears the target sheet's control anatomy - the
// unit toggle, the big figure over a slider, the primary button - because
// the two are consecutive screens of one flow and a hiker should not have
// to learn the controls twice.
import '../screens/plan.css'

/** The resolved far end of the stretch, or what stands in for one. */
export interface EntranceEnd {
  mile: number
  name?: string
  /** Set when the end snapped to a real stop; absent on the bare-mile
   *  fallback a stop-less stretch of data leaves behind. */
  kind?: 'shelter' | 'campsite'
}

export interface RouteEntranceSheetProps {
  start: { mile: number; name?: string } | null
  ask: 'far' | 'long'
  miles: number
  days: number
  south: boolean
  /** The stretch's resolved end for the current answers, or null when there
   *  is none to offer (no start yet, or nothing that way in the data). */
  end: EntranceEnd | null
  /** The raw reach of the "How long" answer in miles, before snapping - the
   *  callout's figure. Null in "How far" mode. */
  reachMi: number | null
  /** The walking-hours target the days conversion assumes. */
  hoursTarget: number
  /** False without an elevation profile - days cannot be priced. */
  daysUsable: boolean
  /** False without a GPS fix that can be carried onto the pipeline axis. */
  gpsUsable: boolean
  /** No POI in this download carries a published mile (pre-#753): nothing
   *  here can run honestly, and the sheet says so instead of rendering
   *  controls that would lie. */
  refused: boolean
  units: UnitSystem
  onAsk: (ask: 'far' | 'long') => void
  onMiles: (miles: number) => void
  onDays: (days: number) => void
  onSouth: (south: boolean) => void
  onPickStart: (door: 'gps' | 'search' | 'map') => void
  onUse: () => void
  /** Leave the builder, discarding the draft. */
  onClose: () => void
}

// Input affordances, not findings: the miles slider covers an overnight
// through a strong two-week stretch, the days slider a weekend through a
// two-week section. A hiker whose answer lies past either end names their
// endpoint through the search or map doors instead - the sliders bound the
// question, never the route.
const MILES_MIN = 5
const MILES_MAX = 150
const MILES_STEP = 5
const DAYS_MIN = 1
const DAYS_MAX = 14

export function RouteEntranceSheet({
  start,
  ask,
  miles,
  days,
  south,
  end,
  reachMi,
  hoursTarget,
  daysUsable,
  gpsUsable,
  refused,
  units,
  onAsk,
  onMiles,
  onDays,
  onSouth,
  onPickStart,
  onUse,
  onClose,
}: RouteEntranceSheetProps) {
  const effectiveAsk = daysUsable ? ask : 'far'

  return (
    <div className="route-entrance" role="dialog" aria-label="Plan a route">
      <div className="legend__head">
        <h2 className="legend__title">Where from?</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close the route builder</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {refused ? (
        <p className="route-entrance__note" role="note">
          This download predates trail miles on waypoints, so a route can&rsquo;t be
          planned along the profile honestly. Newer trail data carries them.
        </p>
      ) : (
        <>
          <button
            type="button"
            className={
              start === null
                ? 'route-entrance__start route-entrance__start--empty'
                : 'route-entrance__start'
            }
            onClick={() => onPickStart('search')}
          >
            <span className="route-entrance__start-name">
              {start === null ? 'Pick a start' : stopLabel(start)}
            </span>
            {start !== null && start.name !== undefined && (
              <span className="route-entrance__start-mile">
                mi{' '}
                {start.mile.toLocaleString('en-US', {
                  minimumFractionDigits: 1,
                  maximumFractionDigits: 1,
                })}
              </span>
            )}
          </button>
          <div className="route-entrance__doors">
            <button
              type="button"
              className="route-entrance__door"
              disabled={!gpsUsable}
              onClick={() => onPickStart('gps')}
            >
              where I am
            </button>
            <button
              type="button"
              className="route-entrance__door"
              onClick={() => onPickStart('search')}
            >
              search
            </button>
            <button
              type="button"
              className="route-entrance__door"
              onClick={() => onPickStart('map')}
            >
              map
            </button>
          </div>

          <div className="plan-target__units" role="group" aria-label="Stretch size">
            <button
              type="button"
              className="plan-target__unit"
              aria-pressed={effectiveAsk === 'far'}
              onClick={() => onAsk('far')}
            >
              How far
            </button>
            <button
              type="button"
              className="plan-target__unit"
              aria-pressed={effectiveAsk === 'long'}
              disabled={!daysUsable}
              onClick={() => onAsk('long')}
            >
              How long
            </button>
          </div>

          {effectiveAsk === 'far' ? (
            <div className="plan-target__value">
              <span className="plan-target__figure">
                {formatDistance(miles, units, 'trimmed')}
              </span>
              <span className="plan-target__unit-note">of trail</span>
              <input
                type="range"
                className="plan-target__slider"
                min={MILES_MIN}
                max={MILES_MAX}
                step={MILES_STEP}
                value={miles}
                aria-label="Miles of trail"
                onChange={(event) => onMiles(Number(event.target.value))}
              />
            </div>
          ) : (
            <div className="plan-target__value">
              <span className="plan-target__figure">
                {days} {days === 1 ? 'day' : 'days'}
              </span>
              <span className="plan-target__unit-note">on trail</span>
              <input
                type="range"
                className="plan-target__slider"
                min={DAYS_MIN}
                max={DAYS_MAX}
                step={1}
                value={days}
                aria-label="Days on trail"
                onChange={(event) => onDays(Number(event.target.value))}
              />
            </div>
          )}

          {!daysUsable && (
            <p className="plan-target__note" role="note">
              Sizing by days needs the elevation profile, which this download
              doesn&rsquo;t carry &mdash; miles it is.
            </p>
          )}

          {effectiveAsk === 'long' && reachMi !== null && (
            <p className="route-entrance__reach" role="note">
              {days} {days === 1 ? 'day' : 'days'} at your {hoursTarget}h-walking target
              reaches{' '}
              <strong>≈ {formatDistance(Math.round(reachMi), units, 'trimmed')}</strong>.
              The target is yours to change when the days are laid out.
            </p>
          )}

          <div
            className="plan-target__units"
            role="group"
            aria-label="Which way this hike walks"
          >
            <button
              type="button"
              className="plan-target__unit"
              aria-pressed={!south}
              onClick={() => onSouth(false)}
            >
              North
            </button>
            <button
              type="button"
              className="plan-target__unit"
              aria-pressed={south}
              onClick={() => onSouth(true)}
            >
              South
            </button>
          </div>

          <div className="route-entrance__end">
            <span className="route-entrance__end-label">Ends near</span>
            {start === null ? (
              <span className="route-entrance__end-note">pick a start first</span>
            ) : end === null ? (
              <span className="route-entrance__end-note">
                nothing that way in this download
              </span>
            ) : (
              <span className="route-entrance__end-stop">
                <span className="route-entrance__end-name">{stopLabel(end)}</span>
                <span className="route-entrance__end-meta">
                  {end.kind === undefined
                    ? 'no shelter or campsite nearby - the bare mile'
                    : `${typeLabel(end.kind)} · mi ${end.mile.toLocaleString('en-US', {
                        minimumFractionDigits: 1,
                        maximumFractionDigits: 1,
                      })}`}
                </span>
              </span>
            )}
          </div>

          <button
            type="button"
            className="plan__primary"
            disabled={start === null || end === null}
            onClick={onUse}
          >
            Use this stretch
          </button>
        </>
      )}
    </div>
  )
}
