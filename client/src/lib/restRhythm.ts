// A rest every n walking days (#798).
//
// The generator plans walking days and nothing else, which makes it very
// good at describing a stretch of trail and bad at describing a trip. A
// hiker who takes a zero every Sunday has to add seven by hand to a
// fifty-day plan, and loses all seven the next time the plan is laid out -
// so the plan the app produces is not the plan anybody is going to walk.
//
// WHAT THIS DOES NOT DO, and the omission is the design:
//
//  - **It does not re-plan.** A rest lands at a boundary the generator
//    already chose, and the day after a nearo is shorter by whatever the
//    nearo walked. Re-planning the remainder after each insertion would
//    move boundaries the hiker can see on the timeline and did not ask to
//    move - and would quietly undo a pin.
//  - **It has no opinion.** Nothing here suggests a rhythm, warns that a
//    fortnight without one is a lot, or counts the rests taken. A planner
//    that scores rest days is two decisions from a streak
//    (OurHikeValues.md #1).
//  - **It never touches a walked day.** The record is a record. Rests land
//    only in the unwalked remainder, though the count that decides where
//    they land runs over the whole plan - so a rhythm stays in step across
//    a trip that is half-walked.

import { nearestStopBeyond } from './dayPlanner'
import {
  NEARO_MAX_MI,
  shiftDate,
  type HikePlan,
  type PlanDayMeta,
  type PlanStop,
} from './plan'
import type { StoredPoi } from './trailData'

/**
 * The plan with its rhythm's rest days inserted.
 *
 * Returns the plan untouched when there is no rhythm, when there is nothing
 * left to rest in, or when the plan is too short for a rest to mean
 * anything.
 */
export function applyRhythm(plan: HikePlan, pois: readonly StoredPoi[]): HikePlan {
  const rhythm = plan.rhythm
  if (rhythm === undefined || rhythm.everyDays < 1) return plan
  if (plan.days.length === 0) return plan

  const stops: PlanStop[] = [plan.stops[0]]
  const days: PlanDayMeta[] = []
  let sinceRest = 0
  // Every insertion pushes the calendar of everything after it by a day.
  let dateShift = 0

  for (let index = 0; index < plan.days.length; index++) {
    const meta = plan.days[index]
    const from = plan.stops[index]
    const to = plan.stops[index + 1]

    days.push(shifted(meta, dateShift))
    stops.push(to)

    // A zero walks nothing and a rest is not a walking day either, so
    // neither moves the count on - otherwise one rest would trigger the
    // next, and a plan with a rhythm of 1 would never terminate.
    const walking = from.mile !== to.mile && meta.rest !== true
    if (walking) sinceRest += 1
    if (sinceRest < rhythm.everyDays) continue

    // Never at the very end: a rest day on the day you go home is a day
    // nobody is resting. Never on top of the record either.
    if (index === plan.days.length - 1) continue
    if (meta.walked === true || plan.days[index + 1].walked === true) continue

    sinceRest = 0
    const landing = restLanding(rhythm.kind, to, plan.stops[index + 2], pois)
    stops.push(landing)
    days.push({
      id: crypto.randomUUID(),
      ...(days[days.length - 1].date === undefined
        ? {}
        : { date: shiftDate(days[days.length - 1].date as string, 1) }),
      pinned: false,
      // Nobody generated this in the sense the planner means - it is the
      // hiker's own standing instruction, placed rather than chosen.
      generated: false,
      rest: true,
    })
    dateShift += 1
  }

  return { ...plan, stops, days }
}

/**
 * Where a rest day ends.
 *
 * A zero ends where it started. A nearo walks to the first place to sleep
 * inside NEARO_MAX_MI, provided that place is short of the next boundary -
 * walking PAST tomorrow's stop would not be a rest, it would be tomorrow.
 * With nothing inside the window it is a zero, which is still a rest, and
 * the timeline shows a zero rather than claiming a nearo happened.
 */
function restLanding(
  kind: 'zero' | 'nearo',
  at: PlanStop,
  next: PlanStop | undefined,
  pois: readonly StoredPoi[],
): PlanStop {
  const zero: PlanStop = { ...at, resupply: false }
  if (kind === 'zero' || next === undefined) return zero

  const forward = next.mile > at.mile
  const window = at.mile + (forward ? NEARO_MAX_MI : -NEARO_MAX_MI)
  const candidate = nearestStopBeyond(pois, at.mile, window)
  if (candidate === null) return zero
  if (Math.abs(candidate.mile - at.mile) > NEARO_MAX_MI) return zero
  if (forward ? candidate.mile >= next.mile : candidate.mile <= next.mile) return zero

  return {
    mile: candidate.mile,
    ...(candidate.name === undefined ? {} : { name: candidate.name }),
    ...(candidate.poiId === undefined ? {} : { poiId: candidate.poiId }),
    resupply: false,
  }
}

function shifted(meta: PlanDayMeta, byDays: number): PlanDayMeta {
  if (byDays === 0 || meta.date === undefined) return meta
  return { ...meta, date: shiftDate(meta.date, byDays) }
}
