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
import { MAX_OFF_TRAIL_MILES } from '../lib/trailPosition'
import { distanceUnitLabel, formatDistance } from '../lib/units'
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
  /** The last trail tap was refused as too far off the corridor (#801) -
   *  the same 3-mile rule the stop picker's map door has always kept, said
   *  where the tap happened rather than silently doing nothing. */
  refusedTap: boolean
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
  /** Pick the far end explicitly, which changes the question this sheet
   *  asks (#804). */
  onPickEnd: () => void
  /** Clear an explicitly-picked end, going back to "how far". */
  onClearEnd: () => void
  /** The end the hiker NAMED, as opposed to the one the answers resolved
   *  to. When this is set the length is a fact rather than a question. */
  fixedEnd: { mile: number; name?: string } | null
  /** How long the trail is, from the download itself - the miles slider's
   *  far end. Null when nothing can say, and then a fallback is used. */
  trailMiles: number | null
  onUse: () => void
  /** Leave the builder, discarding the draft. */
  onClose: () => void
}

// The sliders are INPUT AFFORDANCES, not limits (#804). Each figure above
// them is a field that takes any number; the slider simply pegs at its end
// and the sheet says what will actually happen to an answer the trail
// cannot satisfy. A hiker planning the whole thing, or a long summer, must
// not have to fight the control that is supposed to help them.
const MILES_MIN = 5
/** Fallback only: the slider runs to the trail's own length when the
 *  download can say what that is, and to this when it cannot. */
const MILES_MAX_FALLBACK = 2200
const MILES_STEP = 5
const DAYS_MIN = 1
/** A leap year. Longer is typed rather than dragged. */
const DAYS_MAX = 366

/**
 * The day length the both-ends readout divides by, purely to turn a
 * distance into a number of days somebody can picture.
 *
 * @unvalidated 15 miles is the round number this planner already opens the
 * target sheet on, not a measurement of anybody. It is deliberately NOT the
 * hiker's own pace: nothing on this screen has their log, and the honest
 * figure comes one screen later where the target is set. This is an
 * ordering-of-magnitude aid and is labelled as one on screen - "at a
 * 15-mile day" - so it cannot be read as a prediction about them.
 */
const TYPICAL_DAY_MI = 15

function stretchDays(miles: number): number {
  return Math.max(1, Math.round(miles / TYPICAL_DAY_MI))
}

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
  refusedTap,
  units,
  onAsk,
  onMiles,
  onDays,
  onSouth,
  onPickStart,
  onPickEnd,
  onClearEnd,
  fixedEnd,
  trailMiles,
  onUse,
  onClose,
}: RouteEntranceSheetProps) {
  const effectiveAsk = daysUsable ? ask : 'far'
  const milesMax = trailMiles ?? MILES_MAX_FALLBACK
  // Both ends named: the distance is arithmetic, so asking "how far" would
  // be asking a question the sheet can already answer (#804).
  const bothEnds = start !== null && fixedEnd !== null
  const fixedMi = bothEnds
    ? Math.abs((fixedEnd as { mile: number }).mile - (start as { mile: number }).mile)
    : null

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
          {/* A FIELD, not a dashed box with three small words under it
              (#801). The old row of "where I am · search · map" was the
              same size and weight as its own caption, sat on a hairline,
              and never moved - everything about it read as a label, and it
              was missed outright in a walkthrough. */}
          <span className="route-entrance__label">Start</span>
          <button
            type="button"
            className={
              start === null
                ? 'route-entrance__field route-entrance__field--empty'
                : 'route-entrance__field'
            }
            onClick={() => onPickStart('search')}
          >
            <span aria-hidden="true">🔍</span>
            <span className="route-entrance__field-text">
              {start === null ? 'Shelter, town, or “mi 500”' : stopLabel(start)}
            </span>
            {start !== null && start.name !== undefined && (
              <span className="route-entrance__field-mile">
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
              className="route-entrance__chip"
              disabled={!gpsUsable}
              onClick={() => onPickStart('gps')}
            >
              <span aria-hidden="true">📍</span> Where I am
            </button>
            <button
              type="button"
              className="route-entrance__chip"
              onClick={() => onPickStart('map')}
            >
              <span aria-hidden="true">🗺</span> Pick on the map
            </button>
          </div>
          {/* The tap that used to do nothing until a button had been pressed
              first (#801). */}
          <p className="route-entrance__hint" role="note">
            {refusedTap ? (
              <>
                That tap is more than{' '}
                {formatDistance(MAX_OFF_TRAIL_MILES, units, 'trimmed')} off the trail, so
                nothing moved. Tap nearer the blazes.
              </>
            ) : (
              '…or just tap the trail on the map. No button first.'
            )}
          </p>

          <span className="route-entrance__label">
            End <span className="route-entrance__label-note">— optional</span>
          </span>
          <button
            type="button"
            className={
              fixedEnd === null
                ? 'route-entrance__field route-entrance__field--empty'
                : 'route-entrance__field'
            }
            onClick={fixedEnd === null ? onPickEnd : onClearEnd}
          >
            <span aria-hidden="true">🏁</span>
            <span className="route-entrance__field-text">
              {fixedEnd === null
                ? 'Somewhere particular? Otherwise say how far'
                : stopLabel(fixedEnd)}
            </span>
            {fixedEnd !== null && (
              <span className="route-entrance__field-mile">clear</span>
            )}
          </button>

          {!bothEnds && (
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
          )}

          {bothEnds && (
            // Both ends named, so the length is arithmetic and asking for it
            // would be asking a question this sheet can already answer
            // (#804). It states the distance instead - and the days become
            // the plan's own target when the timeline is laid out.
            <div className="route-entrance__fixed">
              <span className="route-entrance__fixed-figure">
                {formatDistance(fixedMi as number, units, 'trimmed')}
              </span>
              <span className="route-entrance__fixed-note">
                {stopLabel(start as { mile: number; name?: string })} →{' '}
                {stopLabel(fixedEnd as { mile: number; name?: string })} ·{' '}
                {(fixedEnd as { mile: number }).mile > (start as { mile: number }).mile
                  ? 'north'
                  : 'south'}
              </span>
              <span className="route-entrance__fixed-note">
                {stretchDays(fixedMi as number)} days at a {TYPICAL_DAY_MI}-mile day — the
                days you actually have are the next screen&rsquo;s question.
              </span>
            </div>
          )}

          {!bothEnds && effectiveAsk === 'far' ? (
            <div className="plan-target__value">
              {/* The figure is a FIELD (#804). Anything can be typed into
                  it, including a number past the end of the slider - the
                  answer is never silently reduced, and the note below says
                  what will actually happen to it. */}
              <span className="route-entrance__number">
                <input
                  type="number"
                  className="route-entrance__number-input"
                  min={0}
                  value={miles}
                  aria-label="Miles of trail"
                  onChange={(event) => onMiles(Number(event.target.value))}
                />
                <span className="route-entrance__number-unit">
                  {distanceUnitLabel(units)}
                </span>
              </span>
              <span className="plan-target__unit-note">of trail — type it, or drag</span>
              <input
                type="range"
                className="plan-target__slider"
                min={MILES_MIN}
                max={milesMax}
                step={MILES_STEP}
                value={Math.min(miles, milesMax)}
                aria-label="Miles of trail, slider"
                onChange={(event) => onMiles(Number(event.target.value))}
              />
              {miles > milesMax && (
                <p className="plan-target__note" role="note">
                  Past the end of the trail. The stretch will run as far as the trail does
                  — I haven&rsquo;t shortened your answer, there just isn&rsquo;t more of
                  it.
                </p>
              )}
            </div>
          ) : bothEnds ? null : (
            <div className="plan-target__value">
              <span className="route-entrance__number">
                <input
                  type="number"
                  className="route-entrance__number-input"
                  min={1}
                  value={days}
                  aria-label="Days on trail"
                  onChange={(event) => onDays(Number(event.target.value))}
                />
                <span className="route-entrance__number-unit">
                  {days === 1 ? 'day' : 'days'}
                </span>
              </span>
              <span className="plan-target__unit-note">on trail — type it, or drag</span>
              <input
                type="range"
                className="plan-target__slider"
                min={DAYS_MIN}
                max={DAYS_MAX}
                step={1}
                value={Math.min(days, DAYS_MAX)}
                aria-label="Days on trail, slider"
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
