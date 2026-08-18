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

import type { HikeDirection } from './Header'
import { formatNaismithMinutes } from '../lib/naismith'
import { stopLabel } from '../lib/planDisplay'
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
  /** Carry this route into days - the plan flow (#756/#757). */
  onBreakIntoDays: () => void
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
  onBreakIntoDays,
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
                <span className="route-stops__leg">
                  {legs[index].ascentFt === null || legs[index].minutes === null
                    ? formatDistance(legs[index].distanceMi, units)
                    : `${formatDistance(legs[index].distanceMi, units)} · ${formatElevation(
                        legs[index].ascentFt as number,
                        units,
                      )} ↑ · ${formatNaismithMinutes(legs[index].minutes as number)}`}
                </span>
              )}
            </div>
          ))}
        </div>
        <button type="button" className="route-stops__add" onClick={onAddStop}>
          <span>Add a stop on the way</span>
          <span aria-hidden="true">+</span>
        </button>
      </div>

      <div className="route-stops-bar">
        {totalMinutes === null && (
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
          <button
            type="button"
            className="route-stops-bar__break"
            onClick={onBreakIntoDays}
          >
            Break into days
          </button>
        </div>
      </div>
    </>
  )
}
