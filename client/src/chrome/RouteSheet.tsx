// The route builder's card: drop points, get numbers back (#755, wireframe
// 2a frame 1).
//
// Numbers only, and honest ones. Every figure here is ≈-prefixed moving time
// or a distance/climb pair computed from the published profile - no arrival
// clock, no calories, no difficulty score. The one qualifier that matters is
// "walking" on the total: Naismith knows nothing about lunch, water or forty
// minutes at a shelter, and a card that printed a bare duration would be
// claiming an elapsed day it cannot know (HIKE_PLANNING.md Finding 4).
//
// The centerline-only note is a limitation stated where the limitation
// bites, not buried in a doc: blue-blazed side trails and the road walk into
// town cannot carry a route yet, and a hiker planning a resupply day is
// exactly the person who needs to know that.

import type { HikeDirection } from './Header'
import { formatNaismithMinutes } from '../lib/naismith'
import { MAX_OFF_TRAIL_MILES } from '../lib/trailPosition'
import { formatDistance, formatElevation, type UnitSystem } from '../lib/units'

/**
 * One leg as this card shows it. Climb and time are null on a download that
 * has no elevation profile - the distance is still a fact (it comes off the
 * mile axis), while a time computed with the ascent quietly missing would be
 * an optimistic number wearing an honest one's ≈ (HIKE_PLANNING.md Finding
 * 4). Null means the card says so instead.
 */
export interface RouteLegDisplay {
  distanceMi: number
  ascentFt: number | null
  descentFt: number | null
  minutes: number | null
}

export interface RouteSheetProps {
  /** Per-leg figures, in walk order. Empty until two points exist. */
  legs: readonly RouteLegDisplay[]
  pointCount: number
  /** Null until two points exist - one point has no direction, and the card
   *  does not invent one (lib/route.ts's routeDirection). */
  direction: HikeDirection | null
  units: UnitSystem
  /** The last tap was refused: more than 3 miles from any centerline vertex,
   *  so there is no honest mile to give it (lib/trailPosition.ts). */
  refusedTap: boolean
  /** Remove the most recently dropped point. */
  onUndo: () => void
  /** Leave the builder, discarding the draft. */
  onCancel: () => void
  /** Carry this route into days - the plan flow (#756/#757). */
  onBreakIntoDays: () => void
}

export function RouteSheet({
  legs,
  pointCount,
  direction,
  units,
  refusedTap,
  onUndo,
  onCancel,
  onBreakIntoDays,
}: RouteSheetProps) {
  const totalDistanceMi = legs.reduce((sum, leg) => sum + leg.distanceMi, 0)
  // A total time exists only when every leg has one - summing around a
  // missing leg would print a whole-route figure that silently omits part of
  // the route.
  const totalMinutes = legs.every((leg) => leg.minutes !== null)
    ? legs.reduce((sum, leg) => sum + (leg.minutes as number), 0)
    : null
  const missingProfile = legs.some((leg) => leg.minutes === null)

  return (
    <div className="route-sheet" role="dialog" aria-label="Route builder">
      <div className="legend__head">
        <h2 className="legend__title">
          {pointCount === 0
            ? 'Plan a route'
            : pointCount === 1
              ? '1 point'
              : `${pointCount} points · ${legs.length} ${legs.length === 1 ? 'leg' : 'legs'}`}
        </h2>
        {direction !== null && (
          <span className="route-sheet__direction">{direction}</span>
        )}
        <button type="button" className="legend__close" onClick={onCancel}>
          <span className="visually-hidden">Close the route builder</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {refusedTap && (
        <p className="route-sheet__refused" role="status">
          {/* The gate itself (lib/trailPosition.ts's MAX_OFF_TRAIL_MILES),
              through units.ts so a metric hiker reads the same fact. */}
          That tap is more than {formatDistance(MAX_OFF_TRAIL_MILES, units, 'trimmed')}{' '}
          from the trail &mdash; there&rsquo;s no honest mile to give it.
        </p>
      )}

      {pointCount === 0 && (
        <p className="route-sheet__hint">
          Tap the trail to drop a point. The first tap is the start, the last is the end,
          and a tap between two points slots in between them.
        </p>
      )}

      {pointCount === 1 && (
        <p className="route-sheet__hint">Tap where this stretch should end.</p>
      )}

      {legs.length > 0 && (
        <dl className="route-sheet__legs">
          {legs.map((leg, index) => (
            // Index as key is safe here: legs are derived positionally from
            // the point list and re-derived whole whenever it changes.
            <div className="route-sheet__leg" key={index}>
              <dt>Leg {index + 1}</dt>
              <dd>
                {leg.ascentFt === null || leg.descentFt === null || leg.minutes === null
                  ? formatDistance(leg.distanceMi, units)
                  : `${formatDistance(leg.distanceMi, units)} · ${formatElevation(leg.ascentFt, units)} ↑ · ${formatElevation(leg.descentFt, units)} ↓ · ${formatNaismithMinutes(leg.minutes)}`}
              </dd>
            </div>
          ))}
          <div className="route-sheet__leg route-sheet__leg--total">
            <dt>Total</dt>
            <dd>
              {totalMinutes === null
                ? formatDistance(totalDistanceMi, units)
                : `${formatDistance(totalDistanceMi, units)} · ${formatNaismithMinutes(totalMinutes)} walking`}
            </dd>
          </div>
        </dl>
      )}

      {missingProfile && (
        <p className="route-sheet__hint" role="note">
          This download has no elevation profile, so climb and time can&rsquo;t be
          computed &mdash; newer trail data carries it.
        </p>
      )}

      <p className="route-sheet__limit" role="note">
        Only the AT centerline can carry a route. Side trails and the road walk into town
        aren&rsquo;t routable yet.
      </p>

      <div className="route-sheet__actions">
        <button
          type="button"
          className="route-sheet__break"
          onClick={onBreakIntoDays}
          disabled={legs.length === 0}
        >
          Break into days
        </button>
        <button
          type="button"
          className="route-sheet__undo"
          onClick={onUndo}
          disabled={pointCount === 0}
        >
          <span aria-hidden="true">&#8634;</span> Undo point
        </button>
      </div>
    </div>
  )
}
