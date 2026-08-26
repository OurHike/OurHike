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
import {
  buildPlan,
  NEARO_MAX_MI,
  type HikePlan,
  type PlanTarget,
  type RestRhythm,
} from '../lib/plan'
import { applyRhythm } from '../lib/restRhythm'
import { legFigures } from '../lib/route'
import type { StoredPoi } from '../lib/trailData'
import { formatDistance, type UnitSystem } from '../lib/units'
import { STANDARD_PACE, type PaceProfile } from '../lib/pace'
import './plan.css'

export interface PlanTargetSheetProps {
  /** The route's stops in walk order - the two ends, plus any destinations
   *  the hiker added between them, on the pipeline's mile axis. Every
   *  intermediate stop is a forced day boundary (planDaysVia). */
  route: readonly ViaStop[]
  pois: readonly StoredPoi[]
  elevation: ElevationProfile | null
  units: UnitSystem
  /** The hiker's own pace (#880), so a target in walking hours means THEIR
   *  hours rather than a generic walker's. */
  pace?: PaceProfile
  /** Where the sheet starts when re-targeting an existing plan. */
  initialTarget?: PlanTarget
  initialStartDate?: string
  /** The rhythm this plan already carries, so re-laying it keeps the rest
   *  days the hiker asked for rather than quietly dropping them (#798). */
  initialRhythm?: RestRhythm
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
  pace = STANDARD_PACE,
  initialTarget,
  initialStartDate,
  initialRhythm,
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
  // 0 means no rhythm at all, which is what a plan has unless somebody asks
  // for one - the app does not suggest rest days (#798).
  const [restEvery, setRestEvery] = useState(initialRhythm?.everyDays ?? 0)
  const [restKind, setRestKind] = useState<'zero' | 'nearo'>(
    initialRhythm?.kind ?? 'zero',
  )

  // Planning by hours without a profile would price every climb at zero and
  // wear an honest ≈ while doing it - so hours are simply not offered then.
  //
  // A DEM HOLE IS THAT SAME FAULT ON A STRETCH (#1039), which is why it is
  // the same refusal rather than a warning. Every edge of the planner's DP is
  // priced by `legFigures(...).minutes`, so unmeasured ground inside the
  // route understates the effort of any day crossing it - and the planner
  // answers by making those days LONGER to reach the target. That is the
  // wrong direction on the one control whose whole job is to keep a day
  // walkable, and unlike a printed figure nobody would see it happen.
  const routeMeasured = useMemo(() => {
    if (elevation === null || route.length < 2) return false
    const miles = route.map((stop) => stop.mile)
    return (
      legFigures(elevation, Math.min(...miles), Math.max(...miles)).unmeasuredMi === 0
    )
  }, [elevation, route])

  const hoursAvailable = elevation !== null && routeMeasured
  const effectiveUnit = hoursAvailable ? unit : 'miles'

  const preview = useMemo(() => {
    if (effectiveUnit === 'hours') {
      const profile = elevation as ElevationProfile
      return planDaysVia(pois, route, hours, {
        effort: (from: CandidateStop, to: CandidateStop) =>
          legFigures(profile, from.mile, to.mile, pace).minutes / 60,
      })
    }
    return planDaysVia(pois, route, miles)
  }, [pois, route, effectiveUnit, hours, miles, elevation])

  /**
   * The plan this sheet would actually lay out, built once and both counted
   * and committed from - rather than counted from the generator's boundaries
   * and built separately in the handler (#1040).
   *
   * The button used to print `preview.length - 1`, which is walking days
   * only. `layOut` then ran `applyRhythm`, which inserts one more day per
   * rest - so "Lay out 20 days" laid out 23, and that number is the only
   * figure on the sheet. Building the plan here makes the count a fact
   * about the plan rather than about one stage of making it, and removes
   * the second copy of the pipeline that let the two drift.
   */
  const laidOut = useMemo(() => {
    if (preview === null || preview.length < 2) return null
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
    const pinned =
      viaMiles.size === 0
        ? plan
        : {
            ...plan,
            days: plan.days.map((meta, index) =>
              viaMiles.has(plan.stops[index + 1].mile) ? { ...meta, pinned: true } : meta,
            ),
          }
    // The rhythm rides on the plan so a re-lay reproduces it, and is applied
    // last - rest days are inserted between boundaries the generator has
    // already chosen, never planned instead of them (#798).
    return restEvery < 1
      ? pinned
      : applyRhythm({ ...pinned, rhythm: { everyDays: restEvery, kind: restKind } }, pois)
  }, [preview, effectiveUnit, hours, miles, startDate, route, restEvery, restKind, pois])

  const dayCount = laidOut === null ? 0 : laidOut.days.length

  const layOut = () => {
    if (laidOut !== null) onLayOut(laidOut)
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

          {elevation === null && (
            <p className="plan-target__note" role="note">
              Planning by hours needs the elevation profile, which this download
              doesn&rsquo;t carry - miles it is.
            </p>
          )}
          {elevation !== null && !routeMeasured && (
            <p className="plan-target__note" role="note">
              Part of this stretch has no elevation measured, so an hours target would
              quietly ask for longer days over it - miles it is.
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

          {/* A rest every n days (#798). Nothing here suggests one: the
              default is none, and a plan without rests is not marked
              incomplete. It plans the rhythm the hiker asked for. */}
          <div className="plan-target__rest">
            <div className="plan-target__rest-head">
              <span>A rest day</span>
              <span className="plan-target__rest-figure">
                {restEvery < 1
                  ? 'none'
                  : `every ${restEvery} ${restEvery === 1 ? 'day' : 'days'}`}
              </span>
            </div>
            <input
              type="range"
              className="plan-target__slider"
              min={0}
              max={14}
              step={1}
              value={restEvery}
              aria-label="A rest day every how many walking days"
              onChange={(event) => setRestEvery(Number(event.target.value))}
            />
            {restEvery >= 1 && (
              <>
                <div className="plan-target__units" role="group" aria-label="Rest day">
                  <button
                    type="button"
                    className="plan-target__unit"
                    aria-pressed={restKind === 'zero'}
                    onClick={() => setRestKind('zero')}
                  >
                    Zero
                  </button>
                  <button
                    type="button"
                    className="plan-target__unit"
                    aria-pressed={restKind === 'nearo'}
                    onClick={() => setRestKind('nearo')}
                  >
                    Nearo
                  </button>
                </div>
                <p className="plan-target__note" role="note">
                  {restKind === 'zero'
                    ? 'A zero walks nothing and still eats a day of food.'
                    : `A nearo walks up to ${formatDistance(NEARO_MAX_MI, units, 'trimmed')} to the next place to sleep — and is a zero where there isn’t one.`}
                </p>
              </>
            )}
          </div>

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
