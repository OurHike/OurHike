// The cascade (#758): when today changes, what happens to the rest of the
// plan - features/HIKE_PLANNING.md's Phase E, "the part that decides
// whether anyone uses this twice".
//
// Three named responses, never applied silently, each computed here so the
// choice sheet offers CONSEQUENCES rather than a "recalculate?" prompt:
//
//   ABSORB - the finish holds. Only the stretch between the hiker's real
//   position and the first barrier re-plans, over exactly the days that are
//   left in it (planDaysExact), so every date after today stays where it
//   was. Everything beyond the first barrier is untouched by construction.
//
//   SHIFT - the day sizes hold. The same stretch re-plans at the plan's own
//   target, the day count falls out, and every later day moves by that
//   delta. Blocked outright while any pinned day lies ahead: a pin is a
//   real-world commitment WITH A DATE (a booked hostel, a mail drop), and a
//   shift that moved it would be the exact silent betrayal pins exist to
//   prevent.
//
//   LEAVE - nothing after today changes. Tomorrow starts where the hiker
//   actually is, and is as long or short as that makes it.
//
// BARRIERS. A cascade re-plans between pins and never through one. Two
// things are barriers: a pinned day (its start boundary ends the stretch -
// the day itself does not move), and a resupply stop (the stretch runs TO
// it - the day into town may re-balance, the town does not move). Resupply
// stops barrier by default, answering the question the issue says must be
// settled here: re-balancing days is safe, silently moving which town
// someone buys food in is not - somebody may have mailed a box there.
//
// ZEROS survive re-planning at their positions: a zero is a rest with a
// date, and neither absorb nor shift has any business spending it.
//
// THE PAST IS A RECORD. callItADay is the only writer of `walked`, walked
// days form a prefix, and every operation here starts strictly after them.

import {
  candidateStops,
  planDays,
  planDaysExact,
  type CandidateStop,
  type PlannerOptions,
} from './dayPlanner'
import {
  keepingRest,
  walkedDayCount,
  type HikePlan,
  type PlanDayMeta,
  type PlanStop,
} from './plan'
import type { StoredPoi } from './trailData'

/** Where a day actually ended. */
export interface CalledEnd {
  mile: number
  name?: string
  poiId?: string
}

/**
 * Mark the current day walked, ending where the hiker says it ended.
 *
 * The end boundary is rewritten to the real place - which moves the next
 * day's start with it, because the two are one stop. An end at the planned
 * boundary's own mile keeps the planned stop, resupply flag and all; a new
 * place arrives with no resupply flag, because the flag described somewhere
 * else. Returns the plan unchanged if `index` is not the current day - days
 * are walked in order, and nothing else may be called.
 *
 * The end must lie between the day's own start and the boundary AFTER the
 * one it replaces: past that, tomorrow's leg would run backwards, and what
 * the hiker actually did is overtake a whole planned day - a structural
 * edit (consuming days) the cascade does not attempt yet. Refused rather
 * than half-recorded; the call sheet says so before offering the option.
 */
export function callItADay(plan: HikePlan, index: number, end: CalledEnd): HikePlan {
  if (index !== walkedDayCount(plan)) return plan
  if (!Number.isFinite(end.mile) || end.mile < 0) return plan
  if (!callableEnd(plan, index, end.mile)) return plan

  const planned = plan.stops[index + 1]
  const stop: PlanStop =
    end.mile === planned.mile
      ? planned
      : {
          mile: end.mile,
          ...(end.name === undefined ? {} : { name: end.name }),
          ...(end.poiId === undefined ? {} : { poiId: end.poiId }),
          resupply: false,
        }

  // Both days that touch the rewritten boundary change length: the one
  // being recorded, and tomorrow, which now starts where the hiker actually
  // is. So both have their rest flag re-examined - a nearo the hiker walked
  // straight past, or one that swallowed the miles they did not walk today,
  // is not the rest it still claims to be (#1031).
  const stops = plan.stops.map((existing, i) => (i === index + 1 ? stop : existing))
  return {
    ...plan,
    stops,
    days: plan.days.map((meta, i) => {
      if (i !== index && i !== index + 1) return meta
      const walked = i === index ? { ...meta, walked: true, generated: false } : meta
      return keepingRest(walked, stops[i].mile, stops[i + 1].mile)
    }),
  }
}

/** Whether a mile is a recordable end for day `index` - between the day's
 *  own start and the boundary after the one being replaced, in the day's
 *  own direction. Exported so the call sheet can refuse an option with a
 *  reason instead of offering a tap that silently does nothing. */
export function callableEnd(plan: HikePlan, index: number, mile: number): boolean {
  const start = plan.stops[index]
  const planned = plan.stops[index + 1]
  const following = index + 2 < plan.stops.length ? plan.stops[index + 2] : null
  const northbound = planned.mile >= start.mile
  if (northbound) {
    if (mile < start.mile) return false
    return following === null || mile <= following.mile
  }
  if (mile > start.mile) return false
  return following === null || mile >= following.mile
}

/** The named stop nearest `mile`, within `withinMi` - so "call it a day"
 *  can say "at Wise Shelter" instead of a bare mile when the hiker stopped
 *  at a real place. Null when nothing named is that close. */
export function nearestStop(
  pois: readonly StoredPoi[],
  mile: number,
  withinMi = 0.5,
): CalledEnd | null {
  let best: CalledEnd | null = null
  let bestDistance = withinMi
  for (const poi of pois) {
    if (poi.mile === undefined) continue
    if (poi.type !== 'shelter' && poi.type !== 'campsite') continue
    const distance = Math.abs(poi.mile - mile)
    if (distance <= bestDistance) {
      bestDistance = distance
      best = { mile: poi.mile, name: poi.name, poiId: poi.id }
    }
  }
  return best
}

/** Day indices strictly after the walked prefix, and where the first
 *  barrier ends the re-plannable stretch. */
interface Stretch {
  /** First re-plannable day index. */
  firstDay: number
  /** One past the last re-plannable day index. */
  endDay: number
  /** The boundary stop index the stretch runs to. */
  endBoundary: number
  /** Why it ended: what the barrier was, or the plan just ended. */
  barrier: 'pin' | 'resupply' | 'end'
}

function replanStretch(plan: HikePlan): Stretch | null {
  const firstDay = walkedDayCount(plan)
  if (firstDay >= plan.days.length) return null

  for (let day = firstDay; day < plan.days.length; day++) {
    if (plan.days[day].pinned) {
      // The pinned day itself does not move; the stretch ends at its start.
      return { firstDay, endDay: day, endBoundary: day, barrier: 'pin' }
    }
    if (plan.stops[day + 1].resupply) {
      // The day INTO the resupply may re-balance; the town does not move.
      return { firstDay, endDay: day + 1, endBoundary: day + 1, barrier: 'resupply' }
    }
  }
  return {
    firstDay,
    endDay: plan.days.length,
    endBoundary: plan.stops.length - 1,
    barrier: 'end',
  }
}

/**
 * A zero day's own boundary: the stop the hiker is standing at, repeated.
 *
 * NEVER CARRYING THE RESUPPLY FLAG (#1037), which is the whole reason this
 * is a function rather than a spread. A rebuilt stretch runs TO its barrier,
 * and a barrier is frequently a resupply town - so a plain `{ ...boundary }`
 * gives that town a second stop at the same mile. `planSections` closes a
 * span at every resupply, so the zero is then cut out into a food carry of
 * its own and the day walking into town under-reports what to buy.
 *
 * `plan.ts`'s `insertZeroAfter` already refuses this for the same reason and
 * says so at length (#799); the cascade's three copies of the operation never
 * got the rule. Supplies are picked up once, at the stop the hiker walked
 * into.
 */
function zeroAt(boundary: PlanStop): PlanStop {
  return { ...boundary, resupply: false }
}

/** Rebuild the stretch's days over new walking boundaries, weaving each
 *  zero back at its original position and keeping every meta's identity and
 *  date. `wasDistanceMi` records what a re-planned walking day used to
 *  cover - a fact about the plan, not a verdict on the hiker. */
function weave(
  plan: HikePlan,
  stretch: Stretch,
  chosen: readonly CandidateStop[],
  endStop: PlanStop,
): { stops: PlanStop[]; days: PlanDayMeta[] } {
  const stops: PlanStop[] = []
  const days: PlanDayMeta[] = []

  let walkingOrdinal = 0
  let boundary = plan.stops[stretch.firstDay]
  for (let day = stretch.firstDay; day < stretch.endDay; day++) {
    const meta = plan.days[day]
    const zero = plan.stops[day].mile === plan.stops[day + 1].mile
    if (zero) {
      stops.push(zeroAt(boundary))
      days.push(meta)
      continue
    }

    walkingOrdinal += 1
    const isLast = walkingOrdinal === chosen.length - 1
    const next = chosen[walkingOrdinal]
    const nextStop: PlanStop = isLast
      ? endStop
      : {
          mile: next.mile,
          ...(next.name === undefined ? {} : { name: next.name }),
          ...(next.poiId === undefined ? {} : { poiId: next.poiId }),
          resupply: false,
        }

    const oldDistance = Math.abs(plan.stops[day + 1].mile - plan.stops[day].mile)
    const newDistance = Math.abs(nextStop.mile - boundary.mile)
    const changed = Math.abs(newDistance - oldDistance) > 0.05

    stops.push(nextStop)
    days.push(
      keepingRest(
        {
          ...meta,
          generated: true,
          ...(changed ? { wasDistanceMi: oldDistance } : {}),
        },
        boundary.mile,
        nextStop.mile,
      ),
    )
    boundary = nextStop
  }

  return { stops, days }
}

export interface AbsorbOutcome {
  plan: HikePlan
  /** The re-planned walking days, and their new average length in miles. */
  days: number
  averageMi: number
}

/**
 * The finish holds: re-plan the stretch over exactly its remaining walking
 * days. Null when that count cannot be walked over the real stops - a
 * stretch with more days left than places to stop, or no candidates at all
 * (a pre-#753 download).
 */
export function absorbPlan(
  plan: HikePlan,
  pois: readonly StoredPoi[],
  options: PlannerOptions = {},
): AbsorbOutcome | null {
  const stretch = replanStretch(plan)
  if (stretch === null) return null

  const from = plan.stops[stretch.firstDay]
  const to = plan.stops[stretch.endBoundary]
  const walking = countWalkingDays(plan, stretch)
  if (walking === 0) return null

  const candidates = candidateStops(pois, from.mile, to.mile)
  if (candidates === null) return null

  const chosen = planDaysExact(candidates, walking, options)
  if (chosen === null) return null

  const woven = weave(plan, stretch, chosen, to)
  const next: HikePlan = {
    ...plan,
    stops: [
      ...plan.stops.slice(0, stretch.firstDay + 1),
      // The same correction as shiftPlan's below, for the same reason: keep
      // every woven stop and take the tail from strictly past the barrier.
      // `weave` already ends its last walking day on `endStop`, so identity
      // is preserved without dropping whatever a trailing zero put after it
      // (#1037).
      ...woven.stops,
      ...plan.stops.slice(stretch.endBoundary + 1),
    ],
    days: [
      ...plan.days.slice(0, stretch.firstDay),
      ...woven.days,
      ...plan.days.slice(stretch.endDay),
    ],
  }

  const spans = chosen.slice(1).map((stop, i) => Math.abs(stop.mile - chosen[i].mile))
  return {
    plan: next,
    days: walking,
    averageMi: spans.reduce((sum, span) => sum + span, 0) / spans.length,
  }
}

function countWalkingDays(plan: HikePlan, stretch: Stretch): number {
  let count = 0
  for (let day = stretch.firstDay; day < stretch.endDay; day++) {
    if (plan.stops[day].mile !== plan.stops[day + 1].mile) count += 1
  }
  return count
}

export interface ShiftOutcome {
  plan: HikePlan
  /** How many days the calendar moved - negative when the walk got ahead. */
  deltaDays: number
  /** The new final day's date, or null on an undated plan. */
  finishDate: string | null
}

/**
 * The day sizes hold: re-plan the stretch at the plan's own per-day target
 * and let the count fall out; every day after the stretch keeps its stops
 * and slides by the delta. Null while any pinned day lies ahead - a pin is
 * a dated commitment and a shifted date is a moved pin - or when the
 * stretch cannot be planned at all.
 */
export function shiftPlan(
  plan: HikePlan,
  pois: readonly StoredPoi[],
  target: number,
  options: PlannerOptions = {},
): ShiftOutcome | null {
  const stretch = replanStretch(plan)
  if (stretch === null) return null
  for (let day = stretch.firstDay; day < plan.days.length; day++) {
    if (plan.days[day].pinned) return null
  }

  const from = plan.stops[stretch.firstDay]
  const to = plan.stops[stretch.endBoundary]
  const candidates = candidateStops(pois, from.mile, to.mile)
  if (candidates === null) return null

  const chosen = planDays(candidates, target, options)
  if (chosen.length < 2) return null

  const oldWalking = countWalkingDays(plan, stretch)
  const newWalking = chosen.length - 1
  const deltaDays = newWalking - oldWalking

  // Rebuild the stretch: zeros keep their ordinal place among the walking
  // days; a stretch that grew gains fresh generated days at its end, one
  // that shrank drops from its end.
  const zeros: number[] = []
  let ordinal = 0
  for (let day = stretch.firstDay; day < stretch.endDay; day++) {
    if (plan.stops[day].mile === plan.stops[day + 1].mile) zeros.push(ordinal)
    else ordinal += 1
  }

  const stops: PlanStop[] = []
  const days: PlanDayMeta[] = []
  const oldMetas = plan.days.slice(stretch.firstDay, stretch.endDay)
  let boundary = from
  let metaAt = 0
  const takeMeta = (): PlanDayMeta => {
    const meta = oldMetas[metaAt]
    metaAt += 1
    return meta ?? { id: crypto.randomUUID(), pinned: false, generated: true }
  }
  for (let walk = 1; walk <= newWalking; walk++) {
    while (zeros.length > 0 && zeros[0] === walk - 1) {
      zeros.shift()
      stops.push(zeroAt(boundary))
      days.push(takeMeta())
    }
    const next = chosen[walk]
    const nextStop: PlanStop =
      walk === newWalking
        ? to
        : {
            mile: next.mile,
            ...(next.name === undefined ? {} : { name: next.name }),
            ...(next.poiId === undefined ? {} : { poiId: next.poiId }),
            resupply: false,
          }
    const meta = takeMeta()
    const oldDistance =
      meta.wasDistanceMi !== undefined ? undefined : distanceOfMeta(plan, meta)
    const newDistance = Math.abs(nextStop.mile - boundary.mile)
    stops.push(nextStop)
    days.push(
      keepingRest(
        {
          ...meta,
          generated: true,
          ...(oldDistance !== undefined && Math.abs(newDistance - oldDistance) > 0.05
            ? { wasDistanceMi: oldDistance }
            : {}),
        },
        boundary.mile,
        nextStop.mile,
      ),
    )
    boundary = nextStop
  }
  // Zeros that sat at the stretch's very end.
  while (zeros.length > 0) {
    zeros.shift()
    stops.push(zeroAt(boundary))
    days.push(takeMeta())
  }

  const tail = plan.days.slice(stretch.endDay)
  const rebuilt: HikePlan = {
    ...plan,
    stops: [
      ...plan.stops.slice(0, stretch.firstDay + 1),
      // Every rebuilt stop, INCLUDING a zero that trails the barrier. This
      // used to drop the last one and append `to` in its place, to guarantee
      // the stretch ended on the barrier's own stop - but the loop above
      // already pushes `to` itself for the last walking day, so the append
      // was redundant when nothing trailed and wrong when something did: a
      // zero sitting after the last walking day had its flag-free copy
      // replaced by the town, resupply flag and all (#1037).
      ...stops,
      ...plan.stops.slice(stretch.endBoundary + 1),
    ],
    days: [...plan.days.slice(0, stretch.firstDay), ...days, ...tail],
  }

  const redated = redateFrom(rebuilt, stretch.firstDay)
  const lastDate = redated.days[redated.days.length - 1]?.date ?? null
  return { plan: redated, deltaDays, finishDate: lastDate }
}

function distanceOfMeta(plan: HikePlan, meta: PlanDayMeta): number | undefined {
  const index = plan.days.findIndex((candidate) => candidate.id === meta.id)
  if (index === -1) return undefined
  return Math.abs(plan.stops[index + 1].mile - plan.stops[index].mile)
}

/** Re-date every day from `firstDay` on as consecutive days after the day
 *  before it - what a shifted calendar means. Undated plans pass through.
 *  With no day before (nothing walked - defensive; the cascade always has a
 *  walked prefix), the first day keeps its own date as the anchor. */
function redateFrom(plan: HikePlan, firstDay: number): HikePlan {
  const anchor = firstDay === 0 ? plan.days[0]?.date : plan.days[firstDay - 1]?.date
  if (anchor === undefined) return plan
  const [year, month, day] = anchor.split('-').map(Number)
  const dateAt = (offset: number) =>
    new Date(Date.UTC(year, month - 1, day + offset)).toISOString().slice(0, 10)
  const offsetOf = (index: number) => (firstDay === 0 ? index : index - (firstDay - 1))
  return {
    ...plan,
    days: plan.days.map((meta, index) =>
      index < firstDay ? meta : { ...meta, date: dateAt(offsetOf(index)) },
    ),
  }
}

export interface CascadeChoices {
  absorb: AbsorbOutcome | null
  shift: ShiftOutcome | null
  /** Tomorrow's length if nothing changes, null when the plan ends today,
   *  and 0 for a zero. */
  leaveTomorrowMi: number | null
  /** How many pinned days lie ahead - the sheet's "nothing re-plans
   *  through those" note, and why shift may be null. */
  pinnedAhead: number
}

/**
 * Every choice, with its consequences computed, so the sheet can offer
 * three concrete outcomes instead of one abstract question.
 *
 * `target` null means the plan's own target cannot be priced honestly - a
 * walking-hours target on a download with no elevation profile - and shift
 * is simply not offered, the same refusal the target sheet makes for the
 * same reason. Absorb still runs: balancing by distance needs no target.
 */
export function cascadeChoices(
  plan: HikePlan,
  pois: readonly StoredPoi[],
  target: number | null,
  options: PlannerOptions = {},
): CascadeChoices {
  const firstDay = walkedDayCount(plan)
  const leaveTomorrowMi =
    firstDay < plan.days.length
      ? Math.abs(plan.stops[firstDay + 1].mile - plan.stops[firstDay].mile)
      : null

  let pinnedAhead = 0
  for (let day = firstDay; day < plan.days.length; day++) {
    if (plan.days[day].pinned) pinnedAhead += 1
  }

  return {
    absorb: absorbPlan(plan, pois, options),
    shift: target === null ? null : shiftPlan(plan, pois, target, options),
    leaveTomorrowMi,
    pinnedAhead,
  }
}
