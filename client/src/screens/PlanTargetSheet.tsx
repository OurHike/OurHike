// "How long is a day?" - the plan target sheet (#756/#757, wireframe 2a
// frame 2), and the surface where two honesty rules from HIKE_PLANNING.md
// Finding 4 live or die:
//
//  - THE UNIT IS STATED. The target defaults to walking hours because the
//    app has the profile and a 15-mile day in Virginia is not a 15-mile day
//    in the Whites - and it says "walking" because Naismith is moving time.
//    The doc left hours-vs-miles open; the wireframes' proposal (hours
//    default, miles one tap away) is what is built. No arrival clock falls
//    out of any of this, and none is offered.
//
//  - THE CEILING IS REAL BUT NOT ABSOLUTE. The generator never schedules
//    past 25 miles while any stop inside the cap exists - and the trail has
//    stretches that offer none (#754 measured them), where the over-cap day
//    is shown rather than hidden. The copy says exactly that much, not
//    "never exceeded".
//
// The generated preview runs on every change: ~3,300 edges for a whole
// thru-hike (#754, measured), which is cheap enough to price a target
// before anyone commits to it. "Lay out 11 days" beats "Generate".

import { useMemo, useState } from 'react'
import {
  DEFAULT_CAP_MI,
  DEFAULT_WALKING_HOURS,
  planDaysVia,
  type CandidateStop,
  type ViaStop,
} from '../lib/dayPlanner'
import type { ElevationProfile } from '../lib/elevationProfile'
import { buildPlan, type HikePlan, type PlanTarget } from '../lib/plan'
import { legFigures } from '../lib/route'
import type { StoredPoi } from '../lib/trailData'
import { formatDistance, type UnitSystem } from '../lib/units'
import './plan.css'

export interface PlanTargetSheetProps {
  /** The route's stops in walk order - the two ends, plus any destinations
   *  the hiker added between them, on the pipeline's mile axis. Every
   *  intermediate stop is a forced day boundary (planDaysVia). */
  route: readonly ViaStop[]
  pois: readonly StoredPoi[]
  elevation: ElevationProfile | null
  units: UnitSystem
  /** Where the sheet starts when re-targeting an existing plan. */
  initialTarget?: PlanTarget
  initialStartDate?: string
  onCancel: () => void
  /** The laid-out plan, built and ready to keep. */
  onLayOut: (plan: HikePlan) => void
}

const DEFAULT_MILES = 15

export function PlanTargetSheet({
  route,
  pois,
  elevation,
  units,
  initialTarget,
  initialStartDate,
  onCancel,
  onLayOut,
}: PlanTargetSheetProps) {
  const [unit, setUnit] = useState<'hours' | 'miles'>(
    initialTarget !== undefined && 'miles' in initialTarget ? 'miles' : 'hours',
  )
  const [hours, setHours] = useState(
    initialTarget !== undefined && 'walkingHours' in initialTarget
      ? initialTarget.walkingHours
      : DEFAULT_WALKING_HOURS,
  )
  const [miles, setMiles] = useState(
    initialTarget !== undefined && 'miles' in initialTarget
      ? initialTarget.miles
      : DEFAULT_MILES,
  )
  const [startDate, setStartDate] = useState(initialStartDate ?? '')

  // Planning by hours without a profile would price every climb at zero and
  // wear an honest ≈ while doing it - so hours are simply not offered then.
  const hoursAvailable = elevation !== null
  const effectiveUnit = hoursAvailable ? unit : 'miles'

  const preview = useMemo(() => {
    if (effectiveUnit === 'hours') {
      const profile = elevation as ElevationProfile
      return planDaysVia(pois, route, hours, {
        effort: (from: CandidateStop, to: CandidateStop) =>
          legFigures(profile, from.mile, to.mile).minutes / 60,
      })
    }
    return planDaysVia(pois, route, miles)
  }, [pois, route, effectiveUnit, hours, miles, elevation])

  const dayCount = preview === null ? 0 : Math.max(0, preview.length - 1)

  const layOut = () => {
    if (preview === null || dayCount === 0) return
    const target: PlanTarget =
      effectiveUnit === 'hours' ? { walkingHours: hours } : { miles }
    const plan = buildPlan(
      preview.map((stop) => ({
        mile: stop.mile,
        ...(stop.name === undefined ? {} : { name: stop.name }),
        ...(stop.poiId === undefined ? {} : { poiId: stop.poiId }),
        resupply: false,
      })),
      target,
      startDate === '' ? undefined : startDate,
    )
    // A destination the hiker added themselves is a decision, not a
    // suggestion: the day arriving there is born pinned, so the cascade
    // (#758) re-plans around it rather than through it - unpinning it on
    // the timeline is one tap if they stop caring. `generated` stays true:
    // the day's SPAN between the fixed ends is still the generator's
    // choice. Matched by mile, which is exact - planDaysVia carries the
    // via's own mile value through untouched.
    const viaMiles = new Set(route.slice(1, -1).map((via) => via.mile))
    onLayOut(
      viaMiles.size === 0
        ? plan
        : {
            ...plan,
            days: plan.days.map((meta, index) =>
              viaMiles.has(plan.stops[index + 1].mile) ? { ...meta, pinned: true } : meta,
            ),
          },
    )
  }

  return (
    <div className="plan-target" role="dialog" aria-label="How long is a day?">
      <div className="legend__head">
        <h2 className="legend__title">How long is a day?</h2>
        <button type="button" className="legend__close" onClick={onCancel}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {preview === null ? (
        <p className="plan-target__note" role="note">
          This download predates trail miles on waypoints, so days can&rsquo;t be laid out
          along the profile honestly. Newer trail data carries them.
        </p>
      ) : (
        <>
          <div className="plan-target__units" role="group" aria-label="Target unit">
            <button
              type="button"
              className="plan-target__unit"
              aria-pressed={effectiveUnit === 'hours'}
              disabled={!hoursAvailable}
              onClick={() => setUnit('hours')}
            >
              Walking hours
            </button>
            <button
              type="button"
              className="plan-target__unit"
              aria-pressed={effectiveUnit === 'miles'}
              onClick={() => setUnit('miles')}
            >
              Miles
            </button>
          </div>

          {effectiveUnit === 'hours' ? (
            <div className="plan-target__value">
              <span className="plan-target__figure">{formatHours(hours)}</span>
              <span className="plan-target__unit-note">per day, moving</span>
              <input
                type="range"
                className="plan-target__slider"
                min={3}
                max={12}
                step={0.5}
                value={hours}
                aria-label="Walking hours per day"
                onChange={(event) => setHours(Number(event.target.value))}
              />
            </div>
          ) : (
            <div className="plan-target__value">
              <span className="plan-target__figure">
                {formatDistance(miles, units, 'trimmed')}
              </span>
              <span className="plan-target__unit-note">per day</span>
              <input
                type="range"
                className="plan-target__slider"
                min={5}
                max={25}
                step={1}
                value={miles}
                aria-label="Miles per day"
                onChange={(event) => setMiles(Number(event.target.value))}
              />
            </div>
          )}

          {!hoursAvailable && (
            <p className="plan-target__note" role="note">
              Planning by hours needs the elevation profile, which this download
              doesn&rsquo;t carry - miles it is.
            </p>
          )}

          <p className="plan-target__caveat" role="note">
            Naismith counts walking - not lunch, not water, not the forty minutes
            you&rsquo;ll spend at the shelter. A 7-hour walking day is longer than 7
            hours.
          </p>

          <p className="plan-target__ceiling">
            <span>Hard ceiling</span>
            <span className="plan-target__ceiling-value">
              {formatDistance(DEFAULT_CAP_MI, units, 'trimmed')} — longer only where the
              trail offers no stop inside it
            </span>
          </p>

          <label className="plan-target__date">
            <span>First day (optional)</span>
            <input
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
            />
          </label>

          <button
            type="button"
            className="plan__primary"
            disabled={dayCount === 0}
            onClick={layOut}
          >
            {dayCount === 0
              ? 'Nothing to lay out'
              : `Lay out ${dayCount} ${dayCount === 1 ? 'day' : 'days'}`}
          </button>
          <p className="plan-target__reassure">
            you can move every one of them afterwards
          </p>
        </>
      )}
    </div>
  )
}

function formatHours(hours: number): string {
  const whole = Math.floor(hours)
  const minutes = Math.round((hours - whole) * 60)
  return minutes === 0 ? `${whole}h 00` : `${whole}h ${String(minutes).padStart(2, '0')}`
}
