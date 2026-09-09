// Setting up a long hike (#1317): two ends on one trail, and everything else
// optional.
//
// THE POINTS ARE THE WHOLE FORM. There is no "whole trail or a section?"
// toggle and no "do you have dates?" step, and both absences are decisions
// rather than omissions. A hiker who says Springer and Katahdin has said
// "the whole trail"; one who says Damascus and Harpers Ferry has said "a
// section"; and a third point says "and then I turned around" without any of
// them being asked which kind of hiker they are. Dates live on the points
// for the same reason - some points have one, most do not, and a step that
// asked would make a hike with no dates feel unfinished when it is the
// ordinary case.
//
// IT REUSES `RouteStopsPanel`'s ANATOMY rather than importing the component.
// The classes are that panel's, down to the dotted rail between the dots,
// because a second stop editor that looked almost the same would be the
// worse outcome - but the panel itself prices legs from an elevation profile
// and totals moving time, and a hike's legs are hundreds of miles long and
// years apart. Pricing them would print an "≈" time for a walk nobody walks
// in one go. So: the same anatomy, and figures this screen can stand behind.
//
// WHAT IT REFUSES, AND WHY IT REFUSES RATHER THAN CORRECTS. A point past the
// end of the trail is not rounded down to the terminus - `plannedHike()`'s
// rule, and the reason is that a corrected value is a number the hiker never
// entered, presented as though they had.

import { hikeLegs, isUsableHike, trailHasMileAxis, type Hike } from '../lib/hikes'
import { pointMeta } from '../lib/hikeText'
import type { StoredPoi } from '../lib/trailData'
import type { Trip } from '../lib/trips'
import { formatDistance, type UnitSystem } from '../lib/units'
import { stopLabel } from '../lib/planDisplay'
import './plan.css'

export interface HikeSetupProps {
  /** The hike being set up - a draft held by the shell, so a tap into the
   *  stop picker and back does not lose it. */
  hike: Hike
  /** Every stretch the hiker has recorded from memory (#789), for the
   *  "already walked some of it?" shelf. */
  recorded: readonly Trip[]
  pois: readonly StoredPoi[]
  units: UnitSystem
  /** The trail's published length, where this download knows it - a point
   *  past it is refused. Null when the download cannot say, and then
   *  nothing is refused for being too far along: an unknown bound is not a
   *  bound. */
  totalMiles: number | null
  onEditPoint: (index: number) => void
  onAddPoint: () => void
  onUndo: (() => void) | null
  onRecordStretch: () => void
  onOpenRecorded: (tripId: string) => void
  onStart: () => void
  onCancel: () => void
}

export function HikeSetup({
  hike,
  recorded,
  pois,
  units,
  totalMiles,
  onEditPoint,
  onAddPoint,
  onUndo,
  onRecordStretch,
  onOpenRecorded,
  onStart,
  onCancel,
}: HikeSetupProps) {
  const legs = hikeLegs(hike, pois)
  const walkingMi = legs.reduce((sum, leg) => sum + leg.distanceMi, 0)
  const refusal = setupRefusal(hike, totalMiles)

  return (
    <div className="hike-setup">
      <header className="plan-band plan-band--trips">
        <div className="plan-band__words">
          <span className="plan-band__eyebrow">setting up</span>
          <h1 className="plan-band__word">{hike.name}</h1>
        </div>
        <button type="button" className="plan-band__switch" onClick={onCancel}>
          Cancel
        </button>
      </header>

      <div className="hike-setup__body">
        <p className="hike-setup__lede">
          Two ends is the whole requirement. Direction comes from the miles; everything
          below is optional and editable later.
        </p>

        <div className="hike-setup__points">
          <div className="route-stops__head">
            <span className="route-stops__count">
              {[
                'Its points',
                `${hike.points.length} ${hike.points.length === 1 ? 'point' : 'points'}`,
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
            {hike.points.map((point, index) => (
              // Index as key: rows are positional and re-derived whole.
              <div className="route-stops__entry" key={index}>
                <span
                  className={
                    index === hike.points.length - 1
                      ? 'route-stops__dot route-stops__dot--end'
                      : 'route-stops__dot'
                  }
                  aria-hidden="true"
                />
                <button
                  type="button"
                  className="route-stops__field"
                  onClick={() => onEditPoint(index)}
                >
                  <span className="route-stops__name">{stopLabel(point)}</span>
                  <span className="route-stops__mile">
                    {pointMeta(point.mile, point.date)}
                  </span>
                </button>
                {index < legs.length && (
                  <span className="route-stops__leg">
                    {/* The LEG's direction, never the hike's. A flip-flop
                        reads northbound here and southbound one row down,
                        and there is no hike-level answer that is true of
                        both. A leg covering no ground says no direction at
                        all rather than inventing one. */}
                    {[
                      formatDistance(legs[index].distanceMi, units),
                      legs[index].direction === null
                        ? null
                        : legs[index].direction === 'NOBO'
                          ? 'northbound'
                          : 'southbound',
                    ]
                      .filter((part) => part !== null)
                      .join(' · ')}
                  </span>
                )}
              </div>
            ))}
          </div>

          <button type="button" className="route-stops__add" onClick={onAddPoint}>
            <span>Add a point on the way</span>
            <span aria-hidden="true">+</span>
          </button>

          <p className="hike-setup__note">
            Two points is a straight there-and-that&rsquo;s-it. A third turns it around —
            a flip-flop, a section you skip back for, or just more detail about the route
            you mean to walk. Any point can carry a date, or none of them can: days get
            planned as you walk them, and nothing falls behind.
          </p>

          {legs.length > 0 && (
            <p className="hike-setup__total">
              {/* The WALKING, not the ground. A there-and-back over the same
                  1,023 miles is 2,046 miles of walking, and this is the
                  screen where a hiker is asking how far they will walk.
                  "What's left" counts ground, because a mile walked twice is
                  not owed twice. */}
              {formatDistance(walkingMi, units)} across {legs.length}{' '}
              {legs.length === 1 ? 'leg' : 'legs'}
            </p>
          )}
        </div>

        <section className="hike-setup__section">
          <h2 className="plan-home__title">Already walked some of it?</h2>
          <button type="button" className="plan-kind__door" onClick={onRecordStretch}>
            <span className="plan-kind__door-name">Add a stretch you remember</span>
            <span className="plan-kind__door-note">
              Springer → Damascus, 2024 — two ends and a year is enough.
            </span>
          </button>
          {recorded.map((trip) => (
            <button
              type="button"
              className="plan-home__row"
              key={trip.id}
              onClick={() => onOpenRecorded(trip.id)}
            >
              <span className="plan-home__row-name">{trip.name}</span>
              <span className="plan-home__meta">{recordedMeta(trip, units)}</span>
            </button>
          ))}
        </section>

        {refusal !== null && (
          <p className="route-stops__limit" role="status">
            {refusal}
          </p>
        )}

        <button
          type="button"
          className="plan__primary"
          disabled={refusal !== null}
          onClick={onStart}
        >
          Start this long hike
        </button>
      </div>
    </div>
  )
}

/**
 * Why this hike cannot be started yet, or null.
 *
 * Exported so the refusal can be argued with directly, and so the shell can
 * ask the same question this screen prints - one answer, not two that can
 * disagree about whether a button should be pressable.
 */
export function setupRefusal(hike: Hike, totalMiles: number | null): string | null {
  if (!isUsableHike(hike)) {
    return 'A long hike needs two ends before it can be walked.'
  }
  if (!trailHasMileAxis(hike.trailId)) {
    // Storing it is fine; measuring it is not. `trailHasMileAxis` carries
    // the reasoning - one published mile axis, and a figure on any other
    // trail would be an A.T. mileage wearing somebody else's name.
    return 'This build can only measure a hike on the Appalachian Trail.'
  }
  if (totalMiles !== null) {
    const past = hike.points.find((point) => point.mile > totalMiles)
    if (past !== undefined) {
      return `A point at mi ${past.mile.toLocaleString('en-US', {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })} is past the end of the trail in this download.`
    }
  }
  return null
}

/** `walked · 2024 · 469.5 mi` - a recorded stretch's provenance and size.
 *  The year rather than a date, because a stretch recalled from memory is
 *  remembered to about that precision and printing a day would claim more. */
function recordedMeta(trip: Trip, units: UnitSystem): string {
  const miles = trip.plan.stops.map((stop) => stop.mile)
  const spanMi = miles.length < 2 ? 0 : Math.max(...miles) - Math.min(...miles)
  const year = trip.plan.days.find((day) => day.date !== undefined)?.date?.slice(0, 4)
  return ['walked', year, formatDistance(spanMi, units)]
    .filter((part) => part !== undefined)
    .join(' · ')
}
