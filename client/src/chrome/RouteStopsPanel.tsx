// The editable route (#755, the chosen "route by destination" flow's second
// screen): destination fields stacked over the map, the anatomy every phone
// already knows. Every stop is a field, tapping one opens the stop picker,
// "Add a stop on the way" joins a destination between the ends - and the
// days later plan THROUGH it (lib/dayPlanner.ts's planDaysVia).
//
// Numbers only, and honest ones - the rules the old route card carried,
// kept: every figure is ≈-prefixed moving time or a distance/climb pair
// computed from the published profile; no arrival clock, no difficulty
// score; "walking" qualifies the total because Naismith knows nothing about
// lunch, water or forty minutes at a shelter (HIKE_PLANNING.md Finding 4).
// A leg on a download with no profile shows its distance alone - the
// distance is still a fact, a time with the climbs quietly missing would
// be an optimistic number wearing an honest one's ≈ - and the bar says why.
//
// CLIMB AND DESCENT, BOTH (#973). The frame prints `2,900↑ · 1,750↓` and
// this panel printed only the first for its whole life, while legFigures
// computed the second and threw it away. On a surface somebody plans a day
// on, the descent is the half their knees are asking about - and it is the
// half Naismith gives no credit for, so a leg that reads as easy on time can
// still be the one that hurts. Both numbers or neither.
//
// ONE POINT IS A START, NOT A ROUTE. Since the editor can be opened empty
// and filled by tapping, every figure here has to survive a stop list of
// zero or one - which is why the counts line says what is there rather than
// printing a total of nothing, and why the bar's break button is absent
// below two stops instead of present and dead.

import type { HikeDirection } from './Header'
import { formatNaismithMinutes } from '../lib/naismith'
import { stopLabel } from '../lib/planDisplay'
import { MAX_OFF_TRAIL_MILES } from '../lib/trailPosition'
import { formatDistance, formatElevation, type UnitSystem } from '../lib/units'

/**
 * One leg as this surface shows it. Climb and time are null on a download
 * that has no elevation profile - see the header note.
 */
export interface RouteLegDisplay {
  distanceMi: number
  ascentFt: number | null
  descentFt: number | null
  minutes: number | null
}

export interface RouteStopsPanelProps {
  stops: readonly { mile: number; name?: string }[]
  /** Per-leg figures, in walk order - one fewer than stops. */
  legs: readonly RouteLegDisplay[]
  direction: HikeDirection | null
  units: UnitSystem
  /** Open the stop picker over stop `index`. */
  onEditStop: (index: number) => void
  /** Open the stop picker for a new destination. */
  onAddStop: () => void
  /** Step back one edit, or null when there is nothing to step back to -
   *  absent rather than disabled, because a dead control is a promise. */
  onUndo: (() => void) | null
  /** The last trail tap was refused as too far off the corridor (#973). */
  refusedTap: boolean
  /** Carry this route into days - the plan flow (#756/#757). */
  onBreakIntoDays: () => void
  /** Keep this stretch as ground already walked (#789) - the same two ends,
   *  said in the past tense. */
  onRecordWalked: () => void
  /** Leave the builder, discarding the draft. */
  onClose: () => void
}

export function RouteStopsPanel({
  stops,
  legs,
  direction,
  units,
  onEditStop,
  onAddStop,
  onUndo,
  refusedTap,
  onBreakIntoDays,
  onRecordWalked,
  onClose,
}: RouteStopsPanelProps) {
  const totalDistanceMi = legs.reduce((sum, leg) => sum + leg.distanceMi, 0)
  // A total time exists only when every leg has one - summing around a
  // missing leg would print a whole-route figure that silently omits part
  // of the route.
  const totalMinutes = legs.every((leg) => leg.minutes !== null)
    ? legs.reduce((sum, leg) => sum + (leg.minutes as number), 0)
    : null

  return (
    <>
      <div className="route-stops" role="dialog" aria-label="Your route">
        <button type="button" className="route-stops__close" onClick={onClose}>
          <span className="visually-hidden">Close the route builder</span>
          <span aria-hidden="true">×</span>
        </button>

        <div className="route-stops__head">
          <span className="route-stops__count">
            {[
              direction,
              `${stops.length} ${stops.length === 1 ? 'point' : 'points'}`,
              legs.length === 0
                ? null
                : `${legs.length} ${legs.length === 1 ? 'leg' : 'legs'}`,
            ]
              .filter((part) => part !== null)
              .join(' · ')}
          </span>
          {onUndo !== null && (
            <button type="button" className="route-stops__undo" onClick={onUndo}>
              <span className="visually-hidden">Undo the last change</span>
              <span aria-hidden="true">↺</span>
            </button>
          )}
        </div>

        <div className="route-stops__list">
          {stops.map((stop, index) => (
            // Index as key is safe here: rows are derived positionally from
            // the stop list and re-derived whole whenever it changes.
            <div className="route-stops__entry" key={index}>
              <span
                className={
                  index === stops.length - 1
                    ? 'route-stops__dot route-stops__dot--end'
                    : 'route-stops__dot'
                }
                aria-hidden="true"
              />
              <button
                type="button"
                className="route-stops__field"
                onClick={() => onEditStop(index)}
              >
                <span className="route-stops__name">{stopLabel(stop)}</span>
                {stop.name !== undefined && (
                  <span className="route-stops__mile">
                    mi{' '}
                    {stop.mile.toLocaleString('en-US', {
                      minimumFractionDigits: 1,
                      maximumFractionDigits: 1,
                    })}
                  </span>
                )}
              </button>
              {index < legs.length && (
                <span className="route-stops__leg">{legLine(legs[index], units)}</span>
              )}
            </div>
          ))}
        </div>
        {stops.length < 2 && (
          <p className="route-stops__hint">
            {stops.length === 0
              ? 'Tap the trail to drop a point.'
              : 'Tap the trail again for where this stretch ends.'}
          </p>
        )}

        <button type="button" className="route-stops__add" onClick={onAddStop}>
          <span>Add a stop on the way</span>
          <span aria-hidden="true">+</span>
        </button>

        {/* Stated in the UI and not only in the doc, which is what
            HIKE_PLANNING.md asks for: a hiker whose tap on the road walk into
            town does nothing is owed the reason, and owed it before they tap
            rather than after. The refusal message replaces it rather than
            joining it - one sentence about the same limitation, said in the
            tense that matches what just happened. */}
        <p className="route-stops__limit" role={refusedTap ? 'status' : undefined}>
          {refusedTap
            ? `That tap is more than ${formatDistance(MAX_OFF_TRAIL_MILES, units, 'trimmed')} from the trail — there’s no honest mile to give it.`
            : 'Only the A.T. centerline can carry a route. Side trails, alternates and the road walks into town aren’t routable yet.'}
        </p>
      </div>

      <div className="route-stops-bar">
        {legs.length > 0 && totalMinutes === null && (
          <p className="route-stops-bar__note" role="note">
            No elevation profile in this download &mdash; distance only.
          </p>
        )}
        <div className="route-stops-bar__row">
          <span className="route-stops-bar__figures">
            {[
              direction,
              formatDistance(totalDistanceMi, units),
              totalMinutes === null
                ? null
                : `${formatNaismithMinutes(totalMinutes)} walking`,
            ]
              .filter((part) => part !== null)
              .join(' · ')}
          </span>
          {/* Absent below two stops rather than present and dead: there is
              no route to break, and a button that refuses when pressed
              teaches a hiker to distrust the next one. */}
          {legs.length > 0 && (
            <button
              type="button"
              className="route-stops-bar__break"
              onClick={onBreakIntoDays}
            >
              Break into days
            </button>
          )}
        </div>
        {/* The same stretch, said in the past tense. A section hiker's own
            history mostly predates this app, and without a door for it the
            roll-up opens on somebody who has walked 600 miles and tells
            them the whole trail is ahead of them (#789). */}
        <div className="route-stops-bar__row">
          <button
            type="button"
            className="route-stops-bar__recorded"
            onClick={onRecordWalked}
          >
            I already walked this
          </button>
        </div>
      </div>
    </>
  )
}

/**
 * One leg's figures: distance always, then climb, descent and the ≈time
 * together or not at all.
 *
 * They travel as a set because they come from one slice of the profile - a
 * download with no profile has none of the three, and printing a subset
 * would leave a reader guessing which of the missing ones was zero.
 */
function legLine(leg: RouteLegDisplay, units: UnitSystem): string {
  const distance = formatDistance(leg.distanceMi, units)
  if (leg.ascentFt === null || leg.descentFt === null || leg.minutes === null) {
    return distance
  }
  return [
    distance,
    `${formatElevation(leg.ascentFt, units)} ↑`,
    `${formatElevation(leg.descentFt, units)} ↓`,
    formatNaismithMinutes(leg.minutes),
  ].join(' · ')
}
