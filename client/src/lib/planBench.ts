// The plan bench (#971, wireframe 3a): the arithmetic behind the Plan tab's
// wide-screen layout, and the one edit that layout exists to make.
//
// THE NAME. `desktop.css` already has a "planning station" (#1054) - the
// Today journal docked beside the map - and a second thing under that name in
// the same stylesheet would be unreadable a month from now. This surface is
// the BENCH: the whole section laid out flat with room to work on it, three
// panes over one selection and a chart you can move a day boundary on. The
// station is where a hiker reads today; the bench is where they lay the trip
// out and change it.
//
// WHAT THIS MODULE OWNS, and it is deliberately narrow: which boundaries may
// be taken, how far each may travel, and what moving one does to the plan.
// The drawing is chrome/ElevationChart.tsx and the composition is
// screens/Plan.tsx; neither of them may decide any of the below.
//
// ---------------------------------------------------------------------------
// A NEW WRITER OF `plan.stops`, and why that sentence needed writing
//
// #971's body says the drag "has to land on the existing mutators, not a new
// path", because "cascade.ts already owns what happens to the days either
// side". Checked against the code on 2026-08-27: it does not. Every mutator
// in lib/plan.ts and lib/cascade.ts either adds a boundary (`insertZeroAfter`),
// drops one (`removeDay`), flips a flag on one (`toggleResupply`,
// `togglePinned`), writes prose (`setDayNote`), or moves the ONE boundary at
// the end of the day being closed (`callItADay`). Nothing moves an arbitrary
// boundary in the middle of a plan. So this is a new writer, and it is written
// as one rather than smuggled in behind an existing name.
//
// That makes it a hiker-safety path under CLAUDE.md's four-ways rule - "unable
// to get off the trail quickly" is the one it touches. Moving one boundary
// changes the miles AND the climb of the two days that meet at it, and a hiker
// who does not notice has two days that are not the days they planned. Three
// commitments follow, and each is enforced below rather than remembered:
//
//   1. TWO DAYS, NEVER MORE. The drag does not cascade. `absorbPlan` and
//      `shiftPlan` re-lay everything after the day they are given, which is
//      right for "I stopped early today" - the hiker asked a question and the
//      cascade sheet gives them three answers to pick from. A drag asks no
//      question: the handle promises that THIS line moves, and re-laying the
//      next fortnight off a gesture nobody confirmed is exactly the silent
//      re-plan HIKE_PLANNING.md's cascade design exists to prevent. A hiker
//      who wants the rest to follow still has the cascade.
//   2. BOTH CHANGED DAYS SAY SO. Each carries `wasDistanceMi` out of this,
//      so the timeline prints "was 17.1 mi" on both of them - the mechanism
//      #758 already built for exactly this, reused rather than reinvented.
//   3. IT IS UNDOABLE. This returns the plan it was given alongside the new
//      one (`was`), so the screen can offer one tap back. A destructive edit
//      behind a gesture with no undo is not something to ship on a surface a
//      hiker plans water carries on.
//
// WHAT A MOVED BOUNDARY IS CALLED. A stop dragged off "Lost Mountain Shelter"
// is not Lost Mountain Shelter any more, so the name and the POI reference are
// DROPPED unless the new mile lands on a real stop - `nearestStop`'s existing
// half-mile window, the same one "call it a day" uses to decide whether the
// hiker stopped somewhere with a name. Omit rather than guess: a bare mile
// marker is honest, and a shelter name over ground three miles from the
// shelter is the display outrunning its source.

import { nearestStop } from './cascade'
import {
  keepingRest,
  walkedDayCount,
  type HikePlan,
  type PlanDayMeta,
  type PlanStop,
} from './plan'
import type { StoredPoi } from './trailData'

/** A stretch of the profile, low mile first - structurally the chart's own
 *  `ChartStretch`, restated here so lib/ does not import chrome/. */
export interface BenchStretch {
  startMile: number
  endMile: number
}

/** Why a boundary cannot be taken. Each one is a rule stated elsewhere in the
 *  plan model, applied here so the handle is never drawn as movable and then
 *  refused on release. */
export type BoundaryFixed =
  /** The plan's first or last stop. These are what the trip IS, not a day
   *  boundary inside it - moving one re-routes the walk, which is the route
   *  builder's job and not a drag on a chart. */
  | 'end'
  /** At or behind the walked prefix. The past is a record (SEGMENTS.md's
   *  completion model): where a walked day ended is a fact, not a plan. */
  | 'walked'
  /** One of the two days meeting here is pinned. "Nothing re-plans through a
   *  pin" (lib/cascade.ts) - and a pinned day whose miles a drag could change
   *  is a pin that does not hold. */
  | 'pinned'
  /**
   * One of the two days meeting here is a zero, so another stop sits on
   * exactly this mile.
   *
   * TWO REASONS, and the second is the one that matters. The first is that
   * two boundaries at one mile draw as one line: a hiker cannot see which of
   * them they are about to take, and a control that cannot show what it will
   * do should not be offered. The second is what taking either one DOES -
   * a zero's length is what makes it a zero, so moving either edge turns a
   * rest day into a walking day of four miles, off a gesture nobody
   * confirmed. Zeros are added and removed by named actions ("Add a zero day
   * after this", "Remove this zero"), which is where that decision belongs.
   *
   * WHAT IT COSTS, stated because it is not small: every zero freezes the two
   * boundaries around it, so a twenty-day plan with three rest days has six
   * of its nineteen boundaries fixed. What would settle it: moving BOTH
   * coincident stops together, so the drag relocates the rest day along the
   * trail and it stays a zero. That is a better answer and a bigger one - it
   * is one gesture writing two stops - and it is not what this ships.
   */
  | 'zero'

export type BoundaryState =
  | { movable: true; minMile: number; maxMile: number }
  | { movable: false; why: BoundaryFixed }

/**
 * Whether stop `stopIndex` may be dragged, and how far.
 *
 * The travel limits are its two neighbours, taken as a min/max pair rather
 * than as "before" and "after" so a southbound plan - whose stop miles
 * descend - needs no second branch. A boundary dragged onto a neighbour makes
 * a day of zero miles, which the timeline already draws as a zero and says so;
 * it is a real edit and an undoable one, not a corrupt plan.
 */
export function boundaryState(plan: HikePlan, stopIndex: number): BoundaryState {
  if (stopIndex <= 0 || stopIndex >= plan.stops.length - 1) {
    return { movable: false, why: 'end' }
  }
  if (stopIndex <= walkedDayCount(plan)) return { movable: false, why: 'walked' }
  if (plan.days[stopIndex - 1]?.pinned || plan.days[stopIndex]?.pinned) {
    return { movable: false, why: 'pinned' }
  }
  const a = plan.stops[stopIndex - 1].mile
  const b = plan.stops[stopIndex + 1].mile
  const here = plan.stops[stopIndex].mile
  if (a === here || b === here) return { movable: false, why: 'zero' }
  return { movable: true, minMile: Math.min(a, b), maxMile: Math.max(a, b) }
}

/** One day boundary as the chart draws it. */
export interface BenchBoundary {
  /** The plan's own stop index - handed straight back to a move. */
  stopIndex: number
  mile: number
  /** What to call it in a control's accessible name - the stop's own name, or
   *  its mile marker where it has none. */
  label: string
  movable: boolean
  /** Present only while `movable`. */
  minMile?: number
  maxMile?: number
  why?: BoundaryFixed
  /** Why it is fixed, in a sentence a hiker can read - see {@link FIXED_BECAUSE}.
   *  Present only while it is. */
  fixedReason?: string
}

/**
 * What a dashed boundary means, said rather than left to be guessed at.
 *
 * #1049's lesson applied to this surface: a refusal that does not name WHICH
 * absence it is sends somebody looking for a fix that does not exist. Each of
 * these also names the thing that WOULD move the boundary, because three of
 * the four are undoable states rather than facts about the trail.
 */
const FIXED_BECAUSE: Record<BoundaryFixed, string> = {
  end: 'Where the trip starts and ends — change it on the map, not here.',
  walked: 'This day is walked. Where it ended is a record, not a plan.',
  pinned:
    'A pinned day meets here, and a pin means the day does not move. Unpin it to move this.',
  zero: 'A zero day meets here, so two stops sit on this mile. Remove the zero to move this.',
}

/**
 * Every stop as a boundary, ends included.
 *
 * The ends are RETURNED rather than filtered out, marked immovable. A chart
 * that drew only the movable ones would show a 166-mile section whose first
 * and last days have no visible edge, and a hiker would read that as the plan
 * running off both sides of the picture.
 */
export function planBoundaries(plan: HikePlan): BenchBoundary[] {
  return plan.stops.map((stop, stopIndex) => {
    const state = boundaryState(plan, stopIndex)
    return {
      stopIndex,
      mile: stop.mile,
      label: stop.name ?? `mi ${stop.mile.toFixed(1)}`,
      ...(state.movable
        ? { movable: true, minMile: state.minMile, maxMile: state.maxMile }
        : { movable: false, why: state.why, fixedReason: FIXED_BECAUSE[state.why] }),
    }
  })
}

/** The plan's own miles, low first - the chart's resting window on this
 *  screen. Null for a plan with no extent to show. */
export function planStretch(plan: HikePlan): BenchStretch | null {
  if (plan.stops.length < 2) return null
  const miles = plan.stops.map((stop) => stop.mile)
  const startMile = Math.min(...miles)
  const endMile = Math.max(...miles)
  return startMile === endMile ? null : { startMile, endMile }
}

/**
 * How far a day's distance must move before the timeline says "was".
 *
 * REASONED, and not a new number: lib/cascade.ts's `weave` and `shiftPlan`
 * both compare old against new distance with this same 0.05 mi and record
 * `wasDistanceMi` only past it. A drag that changed a day by 260 ft would
 * otherwise print a "was" line identical to the figure beside it, which is
 * noise where the whole point of the line is that a hiker notices it.
 */
const WAS_THRESHOLD_MI = 0.05

/** The result of moving one boundary. `was` is the plan as it stood, so the
 *  screen can offer an undo without keeping its own shadow copy. */
export interface BoundaryMove {
  plan: HikePlan
  was: HikePlan
  /** The two day indices that changed - `stopIndex - 1` and `stopIndex`. */
  days: readonly [number, number]
  /** Their distances before and after, in miles, in the same order. */
  before: readonly [number, number]
  after: readonly [number, number]
  /** Where the boundary ended up, after clamping and any snap. */
  mile: number
  /** The stop it snapped to, when it landed on a named place. */
  snappedTo: string | null
}

/**
 * Move day boundary `stopIndex` to `mile`.
 *
 * Null when the boundary is fixed, when the plan cannot carry the index, or
 * when the move is a no-op - a caller that gets null has nothing to write and
 * nothing to undo.
 *
 * `pois` is optional and only ever ADDS a name: with none supplied the
 * boundary keeps its clamped mile and loses its old name, which is the honest
 * fallback rather than a degraded one.
 */
export function moveBoundary(
  plan: HikePlan,
  stopIndex: number,
  mile: number,
  pois: readonly StoredPoi[] = [],
): BoundaryMove | null {
  const state = boundaryState(plan, stopIndex)
  if (!state.movable) return null
  if (!Number.isFinite(mile)) return null

  const clamped = Math.min(state.maxMile, Math.max(state.minMile, mile))
  // A named place within the half-mile window "call it a day" already uses,
  // and only inside the travel this boundary is allowed - a snap that jumped
  // past a neighbour would reorder the plan's stops.
  const landing = nearestStop(pois, clamped)
  const snapped =
    landing !== null && landing.mile >= state.minMile && landing.mile <= state.maxMile
      ? landing
      : null
  const to = snapped?.mile ?? clamped
  if (to === plan.stops[stopIndex].mile) return null

  const stop: PlanStop = {
    mile: to,
    // Name and reference come from the snap or not at all - see the header.
    ...(snapped?.name === undefined ? {} : { name: snapped.name }),
    ...(snapped?.poiId === undefined ? {} : { poiId: snapped.poiId }),
    // The resupply flag rides with the boundary. It is the hiker's own claim
    // that they pick supplies up where this day ends, and a drag of a few
    // miles is them moving where that is - not them cancelling the resupply.
    resupply: plan.stops[stopIndex].resupply,
  }

  const stops = plan.stops.map((existing, i) => (i === stopIndex ? stop : existing))
  const days: readonly [number, number] = [stopIndex - 1, stopIndex]
  const before: readonly [number, number] = [
    Math.abs(plan.stops[stopIndex].mile - plan.stops[stopIndex - 1].mile),
    Math.abs(plan.stops[stopIndex + 1].mile - plan.stops[stopIndex].mile),
  ]
  const after: readonly [number, number] = [
    Math.abs(to - stops[stopIndex - 1].mile),
    Math.abs(stops[stopIndex + 1].mile - to),
  ]

  return {
    plan: {
      ...plan,
      stops,
      days: plan.days.map((meta, i) => {
        const at = days.indexOf(i)
        if (at === -1) return meta
        return keepingRest(
          recordWas(meta, before[at], after[at]),
          stops[i].mile,
          stops[i + 1].mile,
        )
      }),
    },
    was: plan,
    days,
    before,
    after,
    mile: to,
    snappedTo: snapped?.name ?? null,
  }
}

/**
 * A day marked as the hiker's own, carrying what it used to be.
 *
 * `wasDistanceMi` is written ONCE and never overwritten, matching
 * `shiftPlan`'s rule: it answers "what did the app lay out for me", and a
 * hiker who nudges the same boundary four times wants that original figure
 * back, not the one from three seconds ago.
 */
function recordWas(meta: PlanDayMeta, before: number, after: number): PlanDayMeta {
  const changed = Math.abs(after - before) > WAS_THRESHOLD_MI
  return {
    ...meta,
    generated: false,
    ...(changed && meta.wasDistanceMi === undefined ? { wasDistanceMi: before } : {}),
  }
}
