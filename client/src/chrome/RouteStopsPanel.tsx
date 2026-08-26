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
import type { PaceEstimate } from '../lib/pace'
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
  /**
   * The leg's priced time WITH its baseline, or null when the leg is
   * unpriced (see the header note).
   *
   * A `PaceEstimate` rather than raw minutes, and that is the point: this
   * panel's times are the hiker's own pace applied to Naismith, and #851's
   * rule is that such a figure never renders without the line saying what it
   * was adjusted from. Holding the pair means a row cannot print one and
   * forget the other. The caller builds it with `priceLeg`.
   */
  estimate: PaceEstimate | null
}

export interface RouteStopsPanelProps {
  stops: readonly { mile: number; name?: string }[]
  /** Per-leg figures, in walk order - one fewer than stops. */
  legs: readonly RouteLegDisplay[]
  /**
   * The whole route's priced time, with its baseline - null when any leg is
   * unpriced, because a total summed around a missing leg silently omits
   * part of the route.
   *
   * Passed in rather than summed here, for two reasons that point the same
   * way. The baseline needs the STANDARD time for the whole route, which is
   * not recoverable from formatted leg strings; and pricing the summed terms
   * once is exactly what lib/route.ts asks callers to do, so this total
   * cannot drift from the legs above it.
   */
  total: PaceEstimate | null
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
  /**
   * Why the legs carry no times, when they carry none (#1039).
   *
   * The panel cannot tell from the nulls alone, and the two are different
   * facts: this download has no profile at all, or it has one with a hole in
   * the ground this route crosses. Saying the first when the second is true
   * would send somebody looking for a download that is already there.
   */
  unpriced?: 'no-profile' | 'unmeasured'
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
  total,
  direction,
  units,
  unpriced = 'no-profile',
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
  // of the route. The caller owes us that null; this re-checks rather than
  // trusting it, because the two arrive as separate props and a caller that
  // priced the sum while one leg was unpriced would print the omission.
  const shownTotal = legs.every((leg) => leg.estimate !== null) ? total : null

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
              {/* This leg's own baseline, and it has to be its own: the two
                  coefficients scale Naismith's two terms separately, so the
                  ratio is a property of the walk in front of you, not of the
                  hiker (lib/pace.ts's header). A flat leg and a staircase
                  under one profile read different multiples. Absent entirely
                  at the standard pace, which is most hikers - the line has
                  to keep its weight for the ones who moved a control. */}
              {index < legs.length && legs[index].estimate?.relativeLine != null && (
                <span className="route-stops__leg route-stops__leg--baseline">
                  {legs[index].estimate?.relativeLine}
                </span>
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

      {/* THE WHOLE BAR, or none of it (#973). Below two stops there is no
          route to total, nothing to break into days and nothing to record as
          walked - the shell's handlers refuse all three. A bar printing
          "0.0 mi · ≈0m walking" over two dead buttons states a measurement of
          nothing and then declines to act on it, which is the failure this
          panel is otherwise careful about everywhere else. */}
      {legs.length > 0 && (
        <div className="route-stops-bar">
          {shownTotal === null && (
            <p className="route-stops-bar__note" role="note">
              {unpriced === 'unmeasured'
                ? 'Part of this route has no elevation measured — distance only.'
                : 'No elevation profile in this download — distance only.'}
            </p>
          )}
          <div className="route-stops-bar__row">
            <span className="route-stops-bar__figures">
              {[
                direction,
                formatDistance(totalDistanceMi, units),
                shownTotal === null ? null : `${shownTotal.text} walking`,
              ]
                .filter((part) => part !== null)
                .join(' · ')}
            </span>
            <button
              type="button"
              className="route-stops-bar__break"
              onClick={onBreakIntoDays}
            >
              Break into days
            </button>
          </div>
          {/* The route's own baseline, priced from the summed terms rather
              than from the legs' printed times - the same figure, without
              the rounding each leg already did. */}
          {shownTotal?.relativeLine != null && (
            <p className="route-stops-bar__baseline">{shownTotal.relativeLine}</p>
          )}
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
      )}
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
  if (leg.ascentFt === null || leg.descentFt === null || leg.estimate === null) {
    return distance
  }
  return [
    distance,
    `${formatElevation(leg.ascentFt, units)} ↑`,
    `${formatElevation(leg.descentFt, units)} ↓`,
    leg.estimate.text,
  ].join(' · ')
}
