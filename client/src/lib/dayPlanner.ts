// The auto-generated plan (#757): day boundaries chosen out of the real
// shelters and campsites, as a shortest path - the TypeScript half of
// pipeline/spike_day_planner.py, which measured the problem before this was
// built (#754: 512 candidate stops, ~3,299 edges for a whole thru-hike,
// which is less arithmetic than one frame of the map costs). If the two
// files ever disagree about the algorithm, the spike is a spike that went
// stale and this file is what ships.
//
// The judgement lives in the cost function, and each piece of it is the
// issue's own list:
//  - deviation from the target, SQUARED, so one badly wrong day costs more
//    than several slightly wrong ones - the behaviour a greedy "walk until
//    you pass the target" pass does not give;
//  - asymmetric, because the two failures are not alike: a hiker who
//    arrives early can walk on, and one two miles short of the shelter at
//    dusk cannot;
//  - a hard ceiling never exceeded while any stop inside it exists - a plan
//    is allowed to be short, it is not allowed to quietly schedule a
//    31-mile day because the spacing was awkward;
//  - a tie-break toward shelters over campsites. The water half of that
//    tie-break ("toward stops with water") is deliberately NOT built:
//    HIKE_PLANNING.md ties it to TRIP_PLANNING.md's precomputed
//    shelter-to-water distance, which does not ship yet, and a tie-break
//    improvised off a field whose absence means "unknown" would quietly
//    punish missing data as if it were missing water.

import type { StoredPoi } from './trailData'

/** The longest day the planner may schedule. Not a fitness opinion - the
 *  point past which a generated day stops being a suggestion and becomes a
 *  thing that gets someone benighted. The trail still forces longer days in
 *  real places (#754 measured a 21.5-mile worst case with campsites, one
 *  34.4-mile shelters-only gap); where nothing inside the cap exists, the
 *  over-cap day is returned as it is rather than hidden. */
export const DEFAULT_CAP_MI = 25.0

/** How much worse overshooting the target is than undershooting by the same
 *  amount. 2.25 = 1.5², i.e. overshooting by two miles costs what
 *  undershooting by three does. Same value as the spike, same reasoning. */
export const OVER_TARGET_WEIGHT = 2.25

/**
 * The shelters-over-campsites tie-break, as a deviation-equivalent margin:
 * ending a day at a campsite costs what missing the target by 2% of it
 * would. Proportional so one number serves both target units.
 *
 * @unvalidated 2% is picked, not measured. What would settle it: re-running
 * spike_day_planner.py with this nudge over the real spacing (#754's data)
 * and counting how many boundaries flip - a margin that flips none is
 * decoration, one that flips short-target plans onto over-cap days is harm.
 */
export const CAMPSITE_MARGIN = 0.02

/** A place a generated day may end, in walk order along the route. */
export interface CandidateStop {
  /** Pipeline-axis mile (#753) - the planner refuses to run on any other
   *  scale; see candidateStops below. */
  mile: number
  name?: string
  poiId?: string
  /** Termini are the route's own ends - forced boundaries, exempt from the
   *  campsite nudge because nothing chose them. */
  kind: 'shelter' | 'campsite' | 'terminus'
}

/** A day of `size` in target units, priced against the target. */
export function dayCost(
  size: number,
  target: number,
  overWeight: number = OVER_TARGET_WEIGHT,
): number {
  const deviation = size - target
  const weight = deviation > 0 ? overWeight : 1
  return weight * deviation * deviation
}

export interface PlannerOptions {
  capMi?: number
  overWeight?: number
  /**
   * A day's size in whatever unit `target` is in, walked from `from` to
   * `to`. Distance by default; pass Naismith minutes-over-sixty to plan by
   * walking hours (Finding 4). `capMi` stays in miles regardless - the
   * ceiling is physical.
   */
  effort?: (from: CandidateStop, to: CandidateStop) => number
}

/**
 * Day boundaries out of the candidate stops: the first and last stops are
 * the route's own ends and always kept, everything between is chosen.
 *
 * A shortest path rather than a greedy walk, and the difference is the
 * point: greedy takes the best-looking first day and pays for it at the far
 * end, where the trail has run out and the last day is two miles long. The
 * DP spreads the unavoidable error across every day instead.
 */
export function planDays(
  stops: readonly CandidateStop[],
  target: number,
  {
    capMi = DEFAULT_CAP_MI,
    overWeight = OVER_TARGET_WEIGHT,
    effort,
  }: PlannerOptions = {},
): CandidateStop[] {
  if (stops.length < 2) return []

  const size = effort ?? ((from: CandidateStop, to: CandidateStop) => walkMiles(from, to))
  const nudge = CAMPSITE_MARGIN * target
  const campsiteCost = nudge * nudge

  const best = [0, ...Array.from({ length: stops.length - 1 }, () => Infinity)]
  const previous = new Array<number>(stops.length).fill(0)

  for (let j = 1; j < stops.length; j++) {
    let reachable: number[] = []
    for (let i = 0; i < j; i++) {
      if (walkMiles(stops[i], stops[j]) <= capMi) reachable.push(i)
    }
    // Nowhere to stop inside the cap: the day is as long as the trail makes
    // it. Planned rather than refused - refusing would be refusing to
    // describe a stretch of trail that exists.
    if (reachable.length === 0) reachable = [j - 1]

    for (const i of reachable) {
      const candidate =
        best[i] +
        dayCost(size(stops[i], stops[j]), target, overWeight) +
        (stops[j].kind === 'campsite' ? campsiteCost : 0)
      if (candidate < best[j]) {
        best[j] = candidate
        previous[j] = i
      }
    }
  }

  const boundaries = [stops.length - 1]
  while (boundaries[boundaries.length - 1] !== 0) {
    boundaries.push(previous[boundaries[boundaries.length - 1]])
  }
  boundaries.reverse()

  return boundaries.map((index) => stops[index])
}

function walkMiles(from: CandidateStop, to: CandidateStop): number {
  return Math.abs(to.mile - from.mile)
}

/**
 * Day boundaries with the DAY COUNT fixed - the cascade's "absorb" (#758),
 * where the finish date holds and the remaining route re-balances into
 * exactly the days that are left. Same cost function, same cap, same
 * campsite nudge; the target each day is priced against is implied by the
 * count rather than asked for.
 *
 * The DP gains one dimension (stop × days used): ~512 stops × a three-digit
 * day count is still less arithmetic than a map frame. Null when the count
 * cannot be walked over these stops at all - more days than there are
 * boundaries to end them at, or no in-cap path with exactly that many.
 */
export function planDaysExact(
  stops: readonly CandidateStop[],
  dayCount: number,
  {
    capMi = DEFAULT_CAP_MI,
    overWeight = OVER_TARGET_WEIGHT,
    effort,
  }: PlannerOptions = {},
): CandidateStop[] | null {
  if (stops.length < 2 || dayCount < 1 || dayCount > stops.length - 1) return null

  const size = effort ?? ((from: CandidateStop, to: CandidateStop) => walkMiles(from, to))
  const target = size(stops[0], stops[stops.length - 1]) / dayCount
  const nudge = CAMPSITE_MARGIN * target
  const campsiteCost = nudge * nudge

  // best[j][d]: cheapest way to stand at stop j having walked exactly d days.
  const best = stops.map(() => new Array<number>(dayCount + 1).fill(Infinity))
  const previous = stops.map(() => new Array<number>(dayCount + 1).fill(-1))
  best[0][0] = 0

  for (let j = 1; j < stops.length; j++) {
    let reachable: number[] = []
    for (let i = 0; i < j; i++) {
      if (walkMiles(stops[i], stops[j]) <= capMi) reachable.push(i)
    }
    if (reachable.length === 0) reachable = [j - 1]

    for (const i of reachable) {
      const edge =
        dayCost(size(stops[i], stops[j]), target, overWeight) +
        (stops[j].kind === 'campsite' ? campsiteCost : 0)
      for (let d = 1; d <= dayCount; d++) {
        const candidate = best[i][d - 1] + edge
        if (candidate < best[j][d]) {
          best[j][d] = candidate
          previous[j][d] = i
        }
      }
    }
  }

  if (!Number.isFinite(best[stops.length - 1][dayCount])) return null

  const boundaries: number[] = []
  let at = stops.length - 1
  for (let d = dayCount; d > 0; d--) {
    boundaries.push(at)
    at = previous[at][d]
  }
  boundaries.push(0)
  boundaries.reverse()

  return boundaries.map((index) => stops[index])
}

/**
 * The candidate stops for a route from `fromMile` to `toMile`, in walk
 * order, with the route's own ends first and last.
 *
 * Shelters AND campsites, and that is load-bearing rather than generous:
 * #754 measured one shelters-only gap at 34.4 miles, which no 25-mile cap
 * survives; with campsites in, every target from 10 to 20 mi/day schedules
 * zero over-cap days.
 *
 * Null - not empty - when no POI in this download carries a published mile:
 * that is a data release from before #753, and there is no honest way to
 * position stops on the axis the profile is sampled on. The caller says
 * "this needs a newer download" (HIKE_PLANNING.md Finding 2's degradation),
 * rather than this module quietly re-measuring geometry locally.
 */
export function candidateStops(
  pois: readonly StoredPoi[],
  fromMile: number,
  toMile: number,
): CandidateStop[] | null {
  if (!pois.some((poi) => poi.mile !== undefined)) return null

  const low = Math.min(fromMile, toMile)
  const high = Math.max(fromMile, toMile)
  const between = pois.flatMap((poi): CandidateStop[] => {
    if (poi.mile === undefined) return []
    if (
      (poi.type !== 'shelter' && poi.type !== 'campsite') ||
      poi.mile <= low ||
      poi.mile >= high
    ) {
      return []
    }
    return [
      {
        mile: poi.mile,
        name: poi.name,
        poiId: poi.id,
        kind: poi.type,
      },
    ]
  })

  const forward = toMile >= fromMile
  between.sort((a, b) => (forward ? a.mile - b.mile : b.mile - a.mile))

  return [
    { mile: fromMile, kind: 'terminus' },
    ...between,
    { mile: toMile, kind: 'terminus' },
  ]
}
