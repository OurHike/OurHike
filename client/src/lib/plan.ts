// The multi-day plan: SEGMENTS.md's Hike → Segment tree carrying
// HIKE_PLANNING.md's three additions, and nothing else (#756).
//
// THE SHAPE, and how it maps onto the tree. SEGMENTS.md's leaves are days,
// and consecutive days are contiguous by construction - day N ends exactly
// where day N+1 starts, a zero being a day that ends where it started. So
// the storage is the boundaries themselves: n+1 stops carry n days, each
// day's own metadata rides in a parallel list, and the contiguity that a
// start/end-per-day shape would have to re-validate on every read is here
// unrepresentable instead. Sections are NOT stored - "a section is derived,
// not drawn" (HIKE_PLANNING.md, "The model") - they fall out of the resupply
// flags below. The hiker-override grouping that document also allows is not
// built yet; until it is, a section and a food carry are the same span.
//
// WHERE IT LIVES: the same IndexedDB as everything else, its own key, its
// own module - the plannedHike.ts pattern, and for plannedHike.ts's reasons
// (a plan is not a display preference, and preference keys are mirrored by a
// backend schema that rejects invented ones, #242). ~24 KB for a full
// thru-hike, which is why nothing here talks to a server (HIKE_PLANNING.md
// Q6). This does NOT replace `ourhike:hike`: the v1 pair keeps driving the
// direction-dependent safety surfaces, and wiring those to a plan instead is
// its own decision with its own review, not a side effect of saving one.
//
// THE GUARDRAIL, stated where the model is defined because the model is
// where it would be broken: nothing in this file computes "ahead", "behind",
// or any comparison of walked reality against planned intent. Value #1
// forbids prescriptive gamification, and a planner is two design decisions
// from a schedule that scolds. The plan is a hiker's own paper log with
// arithmetic attached.

import { del, get, set } from 'idb-keyval'
import type { HikeDirection } from '../chrome/Header'

export const PLAN_KEY = 'ourhike:plan'

/** A place a day starts or ends, on the pipeline's mile axis (#753) - the
 *  same measurement every figure in the plan is computed on. */
export interface PlanStop {
  mile: number
  /** Display name, resolved when the stop was chosen. Absent for a dropped
   *  point, which is named by its mile marker at render time. */
  name?: string
  /** The POI this stop is, when it is one. Kept so a later feature can
   *  follow the reference; display never requires it. */
  poiId?: string
  /**
   * Supplies are picked up here. A property of the STOP, not of a day: a
   * resupply happens at a place, and can land mid-walking-day as easily as
   * at the end of one (HIKE_PLANNING.md, "The model").
   */
  resupply: boolean
}

/** One day's own facts - everything about it that is not a boundary. */
export interface PlanDayMeta {
  /** Stable identity, for React keys today and SEGMENTS.md's completion
   *  model when the cascade arrives (#758). */
  id: string
  /** This day does not move - a booked hostel, a mail drop with a date on
   *  it. The cascade re-plans between pins and never through one. */
  pinned: boolean
  /** The app chose this day and the hiker has not touched it. Flips false on
   *  the first edit and never back - the timeline's quiet "auto" marker. */
  generated: boolean
}

/** What the generator aimed at. Two shapes rather than a number and a unit
 *  flag, so a target can never be read in the wrong unit. */
export type PlanTarget = { walkingHours: number } | { miles: number }

export interface HikePlan {
  target: PlanTarget
  /**
   * ISO date (yyyy-mm-dd) of the first day, or absent - thru-hikers plan
   * loosely, and SEGMENTS.md made the date optional for exactly that
   * reason. Every day's date derives from this and its position; a plan
   * with no start date has day numbers and no calendar.
   */
  startDate?: string
  /** n+1 boundaries carrying n days: days[i] runs stops[i] → stops[i+1]. */
  stops: PlanStop[]
  days: PlanDayMeta[]
}

/**
 * A plan, or null if this value cannot describe one. Refused rather than
 * corrected, exactly like plannedHike(): this validates values an earlier
 * build may have written, and a shape that cannot carry the invariants must
 * not reach the arithmetic that assumes them.
 */
export function validatePlan(candidate: unknown): HikePlan | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const plan = candidate as Partial<HikePlan>

  if (!Array.isArray(plan.stops) || !Array.isArray(plan.days)) return null
  if (plan.days.length !== Math.max(0, plan.stops.length - 1)) return null
  if (plan.stops.length === 1) return null

  for (const stop of plan.stops) {
    if (typeof stop !== 'object' || stop === null) return null
    if (!Number.isFinite(stop.mile) || stop.mile < 0) return null
    if (typeof stop.resupply !== 'boolean') return null
  }
  for (const day of plan.days) {
    if (typeof day !== 'object' || day === null) return null
    if (typeof day.id !== 'string' || day.id.length === 0) return null
    if (typeof day.pinned !== 'boolean' || typeof day.generated !== 'boolean') return null
  }

  const target = plan.target as PlanTarget | undefined
  if (typeof target !== 'object' || target === null) return null
  const hours = (target as { walkingHours?: unknown }).walkingHours
  const targetMiles = (target as { miles?: unknown }).miles
  const validHours = typeof hours === 'number' && Number.isFinite(hours) && hours > 0
  const validMiles =
    typeof targetMiles === 'number' && Number.isFinite(targetMiles) && targetMiles > 0
  if (!validHours && !validMiles) return null

  if (plan.startDate !== undefined && !/^\d{4}-\d{2}-\d{2}$/.test(plan.startDate)) {
    return null
  }

  return {
    target: validHours
      ? { walkingHours: hours as number }
      : { miles: targetMiles as number },
    ...(plan.startDate === undefined ? {} : { startDate: plan.startDate }),
    stops: plan.stops as PlanStop[],
    days: plan.days as PlanDayMeta[],
  }
}

/** Re-validated on the way out rather than trusted - the same call
 *  loadPlannedHike makes about the same class of value. */
export async function loadPlan(): Promise<HikePlan | null> {
  const stored = await get(PLAN_KEY)
  if (stored === undefined || stored === null) return null
  return validatePlan(stored)
}

export async function savePlan(plan: HikePlan): Promise<void> {
  await set(PLAN_KEY, plan)
}

/** A first-class action, like clearPlannedHike: abandoning a plan must never
 *  mean clearing the app's data, and no-plan is a state every screen
 *  already handles - it is where every hiker starts. */
export async function clearPlan(): Promise<void> {
  await del(PLAN_KEY)
}

/** A fresh plan over generated day boundaries, every day marked as the
 *  generator's own until the hiker touches it. */
export function buildPlan(
  stops: PlanStop[],
  target: PlanTarget,
  startDate?: string,
): HikePlan {
  return {
    target,
    ...(startDate === undefined ? {} : { startDate }),
    stops,
    days: Array.from({ length: Math.max(0, stops.length - 1) }, () => ({
      id: crypto.randomUUID(),
      pinned: false,
      generated: true,
    })),
  }
}

/** Which way this plan runs, from its ends alone - the plannedHike.ts rule,
 *  for the plannedHike.ts reason. Null for an empty plan. */
export function planDirection(plan: HikePlan): HikeDirection | null {
  if (plan.stops.length < 2) return null
  const first = plan.stops[0].mile
  const last = plan.stops[plan.stops.length - 1].mile
  if (first === last) return null
  return last > first ? 'NOBO' : 'SOBO'
}

/** One day as the timeline reads it - the derived view over the stored
 *  boundaries. */
export interface PlanDayView {
  id: string
  /** Position in the plan, 0-based - the index every mutator below takes. */
  index: number
  /**
   * Walking-day number, 1-based, or null for a zero. Zeros hold a date and
   * a row and eat a day of food, and are still not a day anybody walked -
   * "DAY 24" on the wireframes counts the walking.
   */
  dayNumber: number | null
  /** yyyy-mm-dd, or null when the plan has no start date. */
  date: string | null
  start: PlanStop
  end: PlanStop
  zero: boolean
  pinned: boolean
  generated: boolean
}

/** `startDate` plus `index` days, in plain date arithmetic - UTC throughout
 *  so a plan reads the same in every timezone a phone wanders through. */
export function dateOfDay(startDate: string, index: number): string {
  const [year, month, day] = startDate.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day + index))
  return date.toISOString().slice(0, 10)
}

export function planDayViews(plan: HikePlan): PlanDayView[] {
  let walkingDays = 0
  return plan.days.map((meta, index) => {
    const start = plan.stops[index]
    const end = plan.stops[index + 1]
    const zero = start.mile === end.mile
    if (!zero) walkingDays += 1
    return {
      id: meta.id,
      index,
      dayNumber: zero ? null : walkingDays,
      date: plan.startDate === undefined ? null : dateOfDay(plan.startDate, index),
      start,
      end,
      zero,
      pinned: meta.pinned,
      generated: meta.generated,
    }
  })
}

/**
 * A span of days between two resupplies - the derived section, which is
 * also the food carry while hiker-overridden grouping remains unbuilt.
 *
 * `foodDays` counts every day in the span, zeros included. Whether a zero
 * in town should count against the carry is HIKE_PLANNING.md's open
 * question, explicitly not decided there; the wireframes bracket zeros
 * inside the carry, and counting them is the direction that errs toward a
 * hiker carrying enough rather than short - so that is the answer built,
 * as a decision a reviewer can reverse in one place.
 */
export interface PlanSection {
  days: PlanDayView[]
  distanceMi: number
  foodDays: number
}

export function planSections(views: PlanDayView[]): PlanSection[] {
  const sections: PlanSection[] = []
  let current: PlanDayView[] = []

  const close = () => {
    if (current.length === 0) return
    sections.push({
      days: current,
      distanceMi: current.reduce(
        (sum, day) => sum + Math.abs(day.end.mile - day.start.mile),
        0,
      ),
      foodDays: current.length,
    })
    current = []
  }

  for (const day of views) {
    current.push(day)
    // A resupply at a day's end closes the span: the next day walks out of
    // that town on what was bought there.
    if (day.end.resupply) close()
  }
  close()

  return sections
}

// ---------------------------------------------------------------------------
// Edits. Each returns a new plan and leaves the argument alone; each marks
// the days it touched as no longer the generator's.

function touched(meta: PlanDayMeta): PlanDayMeta {
  return meta.generated ? { ...meta, generated: false } : meta
}

/**
 * A zero after day `index`: a new day from that day's end stop to itself.
 * It needs no kind field - a day with a date, a place and no distance, which
 * is the whole reason a zero has to be IN the tree rather than a gap
 * between days: a gap has no date and eats no food (HIKE_PLANNING.md).
 */
export function insertZeroAfter(plan: HikePlan, index: number): HikePlan {
  if (index < 0 || index >= plan.days.length) return plan
  const boundary = plan.stops[index + 1]
  return {
    ...plan,
    stops: [
      ...plan.stops.slice(0, index + 2),
      { ...boundary },
      ...plan.stops.slice(index + 2),
    ],
    days: [
      ...plan.days.slice(0, index + 1),
      { id: crypto.randomUUID(), pinned: false, generated: false },
      ...plan.days.slice(index + 1),
    ],
  }
}

/**
 * Remove day `index`, dropping its END boundary - so a removed zero simply
 * vanishes (its two boundaries were the same stop), a removed walking day
 * folds its miles into the day after it, and removing the last day shortens
 * the route to end where that day began. The day that absorbed the miles is
 * marked touched: it no longer covers the stretch the generator chose.
 */
export function removeDay(plan: HikePlan, index: number): HikePlan {
  if (index < 0 || index >= plan.days.length) return plan
  if (plan.days.length === 1) return plan
  const zero = plan.stops[index].mile === plan.stops[index + 1].mile
  const days = plan.days.filter((_, i) => i !== index)
  const absorber = zero || index >= days.length ? null : index
  return {
    ...plan,
    stops: plan.stops.filter((_, i) => i !== index + 1),
    days: days.map((meta, i) => (i === absorber ? touched(meta) : meta)),
  }
}

/** Flip the resupply flag on stop `stopIndex` - one write, because a stop
 *  is stored once however many days meet at it. */
export function toggleResupply(plan: HikePlan, stopIndex: number): HikePlan {
  if (stopIndex < 0 || stopIndex >= plan.stops.length) return plan
  return {
    ...plan,
    stops: plan.stops.map((stop, i) =>
      i === stopIndex ? { ...stop, resupply: !stop.resupply } : stop,
    ),
  }
}

export function togglePinned(plan: HikePlan, index: number): HikePlan {
  if (index < 0 || index >= plan.days.length) return plan
  return {
    ...plan,
    days: plan.days.map((meta, i) =>
      i === index ? touched({ ...meta, pinned: !meta.pinned }) : meta,
    ),
  }
}
