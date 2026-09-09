// The Hike that groups trips, and the reason its ends are references (#788).
//
// SEGMENTS.md already had the shape and needs no second model: "a Hike is
// the root of a Segment tree, and a Segment is a node that can have child
// Segments", and - the line that makes this cheap - "there's no real
// difference between 'thru-hike' and 'section-hike' other than the Hike's
// overall start/end". A TRIP (lib/trips.ts) is a Segment; the days the
// timeline draws are its children; a Hike holds trips.
//
// WHY THE ENDS ARE REFERENCES AND NOT MILES. This is the case a section
// hiker IS: the hike stays open for years, and published mileages are not
// stable across them. The trail gets relocated, the pipeline republishes,
// and the miles move underneath. A hike whose ends were stored as
// `mi 470.8 → 1,025.0` may not mean in 2031 what it meant when it was
// written - and the failure is SILENT, because the numbers still parse and
// simply describe different ground. Everything downstream inherits it: the
// roll-ups below, and above all the gaps (#791), which are the feature this
// hiker is here for.
//
// So the boundary is the reference, and the mile is a CACHED HINT that is
// re-resolved from the reference whenever the POI is still in the download.
// SEGMENTS.md asks that boundaries "point at real trail geography, not free
// text"; this is that instruction one step further, because *stable*
// geography is what a multi-year hike needs and a mile number is not that.
//
// REASONED, NOT MEASURED: nobody has quantified how far a given POI's
// published mile actually moves between two releases. Worth measuring once
// (diff `StoredPoi.mile` for stable ids across two published releases)
// before anyone leans on the hint - but the direction of the fix does not
// depend on that number, and the hint is only ever load-bearing when the
// reference itself has gone (`from: 'missing'` below), which is the case
// the UI is required to say out loud.

import type { HikeDirection } from '../chrome/Header'
import { buildPlan, type HikePlan, type PlanStop } from './plan'
import type { StoredPoi } from './trailData'
import type { Trip } from './trips'

/**
 * A place a hike's end refers to.
 *
 * `poiId` is the stable half and `mile` is the perishable one. A place with
 * no `poiId` is a dropped point: its mile is all there has ever been, and
 * `resolvePlace` says so rather than pretending otherwise.
 */
export interface PlaceRef {
  poiId?: string
  /** Display name resolved when the place was chosen. */
  name?: string
  /** The published mile at the moment this was stored - a hint, re-resolved
   *  from `poiId` on every read that can. */
  mile: number
}

/** What a `PlaceRef` means against the download in hand. */
export interface ResolvedPlace {
  mile: number
  name?: string
  /**
   * How this mile was arrived at:
   *
   * - `reference` - the POI is in this download and its CURRENT mile is
   *   used. The stored hint is ignored, which is the whole point.
   * - `stored` - no reference was ever recorded (a dropped point), so the
   *   stored mile is all there is. Honest, and not drift-proof.
   * - `missing` - a reference was recorded and this download does not have
   *   it. The hint is used because there is nothing else, and **the caller
   *   must say so on screen** rather than resolving silently - it is the
   *   one path where a figure is computed against a mile nobody can
   *   currently confirm.
   */
  from: 'reference' | 'stored' | 'missing'
  /** How far the reference has moved since the hint was cached, in miles -
   *  null when there is nothing to compare against. Only ever non-null for
   *  `reference`, and the honest measure of the problem this file exists
   *  for: a real number, from real data, that nobody had before. */
  movedMi: number | null
}

export function resolvePlace(ref: PlaceRef, pois: readonly StoredPoi[]): ResolvedPlace {
  if (ref.poiId === undefined) {
    return {
      mile: ref.mile,
      ...(ref.name === undefined ? {} : { name: ref.name }),
      from: 'stored',
      movedMi: null,
    }
  }

  const poi = pois.find((candidate) => candidate.id === ref.poiId)
  if (poi === undefined || poi.mile === undefined) {
    // Either the POI is gone from this release, or it is here without a
    // published mile (a pre-#753 download). Both leave the hint as the only
    // number available, and both are the caller's cue to say so.
    return {
      mile: ref.mile,
      ...(ref.name === undefined ? {} : { name: ref.name }),
      from: 'missing',
      movedMi: null,
    }
  }

  return {
    mile: poi.mile,
    // The live name wins: a place that was renamed should read by the name
    // it has now, and the stored one is a fallback for a POI without one.
    name: poi.name !== '' ? poi.name : ref.name,
    from: 'reference',
    movedMi: poi.mile - ref.mile,
  }
}

/**
 * One point on a hike's way through (#1317).
 *
 * A `PlaceRef` with a date on it, and it is that rather than a bare mile
 * DELIBERATELY - the design handoff wrote this shape as `{ mile, name?,
 * date? }` and that is exactly the shape this file's header argues against
 * for a multi-year hike. The reasoning does not weaken by being applied to
 * a point in the middle instead of an end: a hike whose way through was
 * stored as bare miles describes different ground after a relocation, and
 * the failure is silent because the numbers still parse. So a point carries
 * its `poiId` and re-resolves through `resolvePlace` like the ends always
 * did, and the mile stays the perishable hint.
 *
 * The date is the handoff's own decision #10 and is genuinely optional: a
 * point with no date is normal, not incomplete. Days get planned as they
 * are walked, and nothing falls behind for want of one.
 */
export interface HikePoint extends PlaceRef {
  /** ISO date (YYYY-MM-DD), or absent. Absent means nobody has said when -
   *  never "unknown" on screen and never today's date by default. */
  date?: string
}

/**
 * Where a hike is in its life.
 *
 * - `planning` - set up, nothing walked on it yet.
 * - `walking` - the hiker is on it. The ordinary state.
 * - `paused` - stepped off deliberately, with `pausedAtMile` kept so
 *   resuming does not mean re-entering where you stopped. Dates stop
 *   moving; nothing is deleted.
 * - `finished` - closed, with `finishedOn` set. Keeps every section in it.
 *
 * Stored rather than derived, which is the opposite call from direction
 * below, and the difference is that none of these four is recoverable from
 * the miles. A hike with no walked section might be one a hiker set up this
 * morning or one they abandoned in 2019, and only they know which.
 */
export type HikeStatus = 'planning' | 'walking' | 'paused' | 'finished'

/**
 * The trail a hike with no stored `trailId` is on.
 *
 * Every hike written before #1317 is an A.T. hike by construction: this
 * client has had exactly one mile axis for its whole life (`StoredPoi.mile`
 * is NOBO miles from Springer), so there was no second trail a stored hike
 * could have meant.
 */
export const DEFAULT_TRAIL_ID = 'AT'

/**
 * Whether this build can measure a hike on `trailId` at all.
 *
 * Only the A.T. today, and this is a statement about the DATA rather than
 * about the trails: `lib/trails.ts` can name and badge four trails, but a
 * mile on a hike's points is a mile on one published axis, and the pipeline
 * publishes exactly one - `export_poi.attach_miles` projects onto the A.T.'s
 * ordered centerline and nothing else. The Long Path ships lines and
 * waypoints (#1288) and no mile axis, so a hike on it could be stored but
 * not measured, and every figure it produced would be an A.T. mileage
 * wearing a Long Path's name.
 *
 * So this gates CREATION, not reading. A hike already on a trail this build
 * cannot measure keeps its points and prints what it honestly can - the
 * same asymmetry `legLine` already applies to a leg on a download with no
 * elevation profile, and for the same reason: refusing to store is how you
 * lose somebody's record, refusing to compute is how you avoid inventing
 * one.
 *
 * @unvalidated as a permanent shape, not as a number. What would settle it
 * is the pipeline publishing a per-trail mile axis, at which point this
 * becomes a lookup over whatever it publishes rather than a literal.
 */
export function trailHasMileAxis(trailId: string): boolean {
  return trailId === DEFAULT_TRAIL_ID
}

/** A hike, as SEGMENTS.md models it. `type` is a label and a default
 *  suggestion, not a constraint - and it is read elsewhere: PRICING_MODEL.md
 *  scopes the thru-hike pass by exactly this field, so it is named
 *  deliberately rather than incidentally. */
export interface Hike {
  id: string
  name: string
  type: 'thru' | 'section' | 'day'
  /**
   * Which centerline this hike's miles are on. SEGMENTS.md's data model
   * has carried "trail reference (which centerline this hike is on)" since
   * it was written; nothing stored it until #1317.
   *
   * Never assumed - but see `trailHasMileAxis` for what this build can
   * actually do with a value other than the default.
   */
  trailId: string
  /**
   * The hike's way through, in walk order, at least two long.
   *
   * ORDER IS MEANING HERE, and that is what separates this list from
   * `tripIds` below. Two points are a straight there-and-that's-it; a third
   * can turn it around, which is how a flip-flop, a section skipped back
   * for, or simply more detail about the intended route is said without a
   * mode, a toggle or a second object.
   *
   * Shorter than two is stored rather than refused (`validateHike` keeps
   * it) and is unusable as an active hike (`isUsableHike`). Deleting a
   * hike to punish it for a bad write is how a hiker loses years.
   */
  points: HikePoint[]
  status: HikeStatus
  /** The trips walked, or planned, inside this hike. Order is not meaning:
   *  a flip-flopper walks the pieces in whatever order suits them (#791).
   *  Called SECTIONS in UI copy since #1317 - the model rename is a larger,
   *  separate change and is deliberately not required to ship the screens. */
  tripIds: string[]
  /** Set when status becomes 'paused': the mile the hiker stopped at, so
   *  coming back does not start by asking them where they were. */
  pausedAtMile?: number
  /** ISO date the pause began - what "paused 11 days" is counted from. */
  pausedOn?: string
  /** ISO date, set with status 'finished'. */
  finishedOn?: string
}

/** The smallest a hike's point list can be and still describe a walk. */
export const MIN_HIKE_POINTS = 2

/**
 * Whether this hike can be the active one.
 *
 * Split from `validateHike` on purpose, and the handoff is explicit about
 * why: "points.length < 2 makes a hike unusable as an active hike but must
 * not delete it." A hike that cannot lead the app is still a hike whose
 * sections are the hiker's record.
 */
export function isUsableHike(hike: Hike): boolean {
  return hike.points.length >= MIN_HIKE_POINTS
}

export function validateHike(candidate: unknown): Hike | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const hike = candidate as Partial<Hike> & { start?: unknown; end?: unknown }
  if (typeof hike.id !== 'string' || hike.id.length === 0) return null
  if (typeof hike.name !== 'string') return null
  if (hike.type !== 'thru' && hike.type !== 'section' && hike.type !== 'day') return null
  const points = validateHikePoints(hike)
  if (points === null) return null
  if (!Array.isArray(hike.tripIds)) return null
  const tripIds = hike.tripIds.filter((id): id is string => typeof id === 'string')
  return {
    id: hike.id,
    name: hike.name,
    type: hike.type,
    // Kept as stored even when this build has never heard of it. A value
    // it does not recognise is a hike written by a later build, and
    // rewriting it to the default would move somebody's hike onto a trail
    // they did not choose - which is worse than being unable to measure it.
    trailId:
      typeof hike.trailId === 'string' && hike.trailId !== ''
        ? hike.trailId
        : DEFAULT_TRAIL_ID,
    points,
    // A hike stored before #1317 has no status, and 'walking' is the
    // assumption that costs least if wrong. Such a hike exists because the
    // hiker grouped sections they already had, so telling them they are
    // still 'planning' would deny a record they can see on the same screen;
    // the two states this could not honestly guess - paused and finished -
    // both carry their own dated field, and neither is set here.
    status: validateHikeStatus(hike.status),
    tripIds,
    ...(Number.isFinite(hike.pausedAtMile) ? { pausedAtMile: hike.pausedAtMile } : {}),
    ...(typeof hike.pausedOn === 'string' ? { pausedOn: hike.pausedOn } : {}),
    ...(typeof hike.finishedOn === 'string' ? { finishedOn: hike.finishedOn } : {}),
  }
}

function validateHikeStatus(candidate: unknown): HikeStatus {
  return candidate === 'planning' ||
    candidate === 'walking' ||
    candidate === 'paused' ||
    candidate === 'finished'
    ? candidate
    : 'walking'
}

/**
 * A hike's points, migrating the two-ended shape (#788) on read.
 *
 * The migration lives here rather than in a one-off pass over IndexedDB for
 * `loadTrips`' stated reason: every read goes through the validator, so a
 * shape converted here cannot be missed by a code path that loaded the
 * store some other way. A hike written by the #788 build has `start` and
 * `end` and no `points`, and those two ARE its point list - in that order,
 * which is the order they were stored in and the order the hiker walks.
 *
 * Null only when neither shape is present, which is not a hike.
 */
function validateHikePoints(hike: {
  points?: unknown
  start?: unknown
  end?: unknown
}): HikePoint[] | null {
  if (Array.isArray(hike.points)) {
    // ONE UNREADABLE POINT REFUSES THE WHOLE HIKE, which is the opposite of
    // what `validateTripStore` does with an unreadable trip, and the
    // difference is worth stating because it looks like an inconsistency.
    //
    // A store is a LIST OF SEPARATE THINGS: dropping one trip loses that
    // trip and leaves every other one exactly as it was. A point list is
    // ONE THING - the route - and dropping a point from it does not lose a
    // point, it silently describes different ground. A hike stored as
    // Springer, Harpers Ferry, Katahdin whose middle point cannot be read
    // would become Springer to Katahdin: still valid, still plausible, and
    // no longer the walk the hiker entered. That is the silent failure this
    // file's header exists to prevent, so it refuses instead.
    //
    // Refusing costs the GROUPING and nothing else. `validateTripStore`
    // drops the hike and keeps every trip in it, which is `removeHike`'s
    // rule arriving by another road: a hike is a way of looking at
    // sections, and losing the way of looking never loses the walking.
    //
    // An EMPTY list is different and is kept: zero points is unambiguous -
    // nobody said where - where a garbled point is a claim this build
    // cannot read. `isUsableHike` is what refuses to walk it.
    const points: HikePoint[] = []
    for (const entry of hike.points) {
      const point = validateHikePoint(entry)
      if (point === null) return null
      points.push(point)
    }
    return points
  }

  const start = validatePlaceRef(hike.start)
  const end = validatePlaceRef(hike.end)
  if (start === null || end === null) return null
  return [start, end]
}

function validateHikePoint(candidate: unknown): HikePoint | null {
  const ref = validatePlaceRef(candidate)
  if (ref === null) return null
  const date = (candidate as Partial<HikePoint>).date
  return { ...ref, ...(typeof date === 'string' ? { date } : {}) }
}

function validatePlaceRef(candidate: unknown): PlaceRef | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const ref = candidate as Partial<PlaceRef>
  if (!Number.isFinite(ref.mile) || (ref.mile as number) < 0) return null
  return {
    mile: ref.mile as number,
    ...(typeof ref.poiId === 'string' ? { poiId: ref.poiId } : {}),
    ...(typeof ref.name === 'string' ? { name: ref.name } : {}),
  }
}

// ---------------------------------------------------------------------------
// Legs. Derived on every read, stored nowhere (#1317).

/**
 * One pair of consecutive points, and which way it is walked.
 *
 * DIRECTION BELONGS TO THE LEG, NOT TO THE HIKE, and that is the whole
 * reason this type exists. A flip-flop reads northbound on one leg and
 * southbound on the next, so a hike-level direction would be wrong for at
 * least one of them and there would be no way to tell which.
 *
 * Nothing stores it. `lib/plannedHike.ts` keeps the rule this file inherits
 * - "whether a hike is NOBO or SOBO is fully determined by comparing the
 * references; storing a separate direction value would just be a second
 * source of truth that could drift" - and the only thing #1317 changed is
 * WHICH two miles get compared: this leg's own, rather than the hike's
 * outermost ends.
 */
export interface HikeLeg {
  /** Position in the point list: leg `i` runs points[i] to points[i + 1]. */
  index: number
  from: ResolvedPlace
  to: ResolvedPlace
  /** Always positive - a leg's length, not a signed difference. */
  distanceMi: number
  /**
   * Null for a leg between two points at the same mile, where there is no
   * direction to report. Printing one would be inventing a fact about
   * ground nobody covers.
   */
  direction: HikeDirection | null
}

/** A hike's legs, in walk order, each resolved against this download. */
export function hikeLegs(hike: Hike, pois: readonly StoredPoi[]): HikeLeg[] {
  const resolved = hike.points.map((point) => resolvePlace(point, pois))
  const legs: HikeLeg[] = []
  for (let index = 0; index < resolved.length - 1; index += 1) {
    const from = resolved[index]
    const to = resolved[index + 1]
    legs.push({
      index,
      from,
      to,
      distanceMi: Math.abs(to.mile - from.mile),
      direction: to.mile === from.mile ? null : to.mile > from.mile ? 'NOBO' : 'SOBO',
    })
  }
  return legs
}

/**
 * How far this hike's points describe WALKING, which is not the same as how
 * much trail it covers.
 *
 * A there-and-back over the same 1,023 miles is 2,046 miles of walking
 * across two legs, and both numbers are true of it. This is the one the
 * set-up screen totals, because a hiker laying out points is asking how far
 * they will walk. `hikeFigures`' `totalMi` is the other one - the extent -
 * because "what is left" is a question about ground, and ground walked
 * twice is not owed twice (see `mergeSpans`).
 */
export function hikeLegMiles(hike: Hike, pois: readonly StoredPoi[]): number {
  return hikeLegs(hike, pois).reduce((sum, leg) => sum + leg.distanceMi, 0)
}

/**
 * A hike's outermost points, low mile and high, resolved.
 *
 * Min and max across EVERY point rather than the first and the last, which
 * differ the moment a hike turns around: a flip-flop stored as Harpers
 * Ferry, Katahdin, Springer starts and ends in the middle of its own
 * extent, and taking `points[0]` and `points[n - 1]` for its ends would
 * describe a shorter trail than the one being walked.
 */
export function resolvedHikePoints(
  hike: Hike,
  pois: readonly StoredPoi[],
): ResolvedPlace[] {
  return hike.points.map((point) => resolvePlace(point, pois))
}

/**
 * The points at a hike's low and high mile, resolved.
 *
 * What a ribbon labels its two ends with, and NOT `points[0]` and
 * `points[n - 1]`: a hike that turns around starts and ends inside its own
 * extent, so the first point is not necessarily the southern one. Null on
 * a hike with no readable points.
 */
/**
 * A name for a hike that has none, from its own two ends.
 *
 * `renameTrip`'s rule at the hike's grain, and #1344's second pass is why it
 * exists: set-up now carries a name FIELD, and a field can be cleared. An
 * empty name is not stored as an empty name - it falls back to what the hike
 * already says about itself, so a cleared box cannot leave a blank heading
 * on Today, in the Plan band, in the sidebar and on the pick sheet at once.
 *
 * Falls back again where the ends cannot be resolved at all, because a hike
 * whose points this download cannot place still needs something to be called.
 */
export function hikeNameFromEnds(
  hike: Hike,
  pois: readonly StoredPoi[],
  fallback = 'A long hike',
): string {
  const { low, high } = hikeEnds(hike, pois)
  if (low === null || high === null) return fallback
  return `${placeLabel(low)} \u2192 ${placeLabel(high)}`
}

/** A resolved point's own word for itself - its name, or its mile as a
 *  MARKER (#986), never as a distance. `stopLabel`'s rule, kept here so
 *  lib/ does not reach into planDisplay for one string. */
function placeLabel(place: ResolvedPlace): string {
  if (place.name !== undefined && place.name !== '') return place.name
  return `mi ${place.mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}`
}

export function hikeEnds(
  hike: Hike,
  pois: readonly StoredPoi[],
): { low: ResolvedPlace | null; high: ResolvedPlace | null } {
  const resolved = resolvedHikePoints(hike, pois)
  if (resolved.length === 0) return { low: null, high: null }
  let low = resolved[0]
  let high = resolved[0]
  for (const point of resolved) {
    if (point.mile < low.mile) low = point
    if (point.mile > high.mile) high = point
  }
  return { low, high }
}

// ---------------------------------------------------------------------------
// Spans. The arithmetic every roll-up rests on, and what #791's gaps will
// take the complement of.

/** A stretch of trail, low mile to high, direction discarded - two hikers
 *  walking the same miles in opposite directions walked the same miles. */
export interface Span {
  from: number
  to: number
}

/**
 * The stretches a plan RECORDS as walked - one per walked day, and only
 * walked days. A planned day contributes nothing: a trip on the calendar
 * closes no gap and belongs in no walked total until it happens.
 */
export function walkedSpans(plan: HikePlan): Span[] {
  const spans: Span[] = []
  plan.days.forEach((day, index) => {
    if (day.walked !== true) return
    const a = plan.stops[index].mile
    const b = plan.stops[index + 1].mile
    if (a === b) return // a zero walked nothing
    spans.push({ from: Math.min(a, b), to: Math.max(a, b) })
  })
  return spans
}

/**
 * Overlapping and touching spans merged into the smallest set covering the
 * same ground.
 *
 * The union rather than the sum, deliberately: hikers repeat sections, and
 * a mile walked twice is still one mile of trail walked as far as "what is
 * left" is concerned. Summing would let a hiker who re-walked Georgia
 * appear to have finished more trail than exists.
 */
export function mergeSpans(spans: readonly Span[]): Span[] {
  if (spans.length === 0) return []
  const sorted = [...spans].sort((a, b) => a.from - b.from)
  const merged: Span[] = [{ ...sorted[0] }]
  for (const span of sorted.slice(1)) {
    const last = merged[merged.length - 1]
    if (span.from <= last.to) {
      if (span.to > last.to) last.to = span.to
    } else {
      merged.push({ ...span })
    }
  }
  return merged
}

/** The part of `spans` that falls inside `within`, clipped at both edges.
 *  A hike's roll-up counts miles walked INSIDE that hike; a trip that
 *  wandered past its ends does not lengthen it. */
export function clipSpans(spans: readonly Span[], within: Span): Span[] {
  const low = Math.min(within.from, within.to)
  const high = Math.max(within.from, within.to)
  return spans.flatMap((span) => {
    const from = Math.max(span.from, low)
    const to = Math.min(span.to, high)
    return to > from ? [{ from, to }] : []
  })
}

export function spanLength(spans: readonly Span[]): number {
  return spans.reduce((sum, span) => sum + (span.to - span.from), 0)
}

// ---------------------------------------------------------------------------
// The roll-up. Derived on every read, stored nowhere - SEGMENTS.md's rule
// for completion applied to its arithmetic: "Parent Segments are never
// marked complete directly. Their status is derived from children."

export interface HikeFigures {
  /** End to end, after resolution. */
  totalMi: number
  /** Walked, as a union clipped to the hike - never a sum (see mergeSpans). */
  walkedMi: number
  /** What is left. Planned-but-unwalked trips are NOT subtracted: a trip on
   *  the calendar closes nothing until it is walked. */
  leftMi: number
  /** Days recorded as walked across this hike's trips. */
  daysWalked: number
  tripCount: number
  /** An end resolved from a reference this download does not have, so these
   *  figures rest on a cached mile nobody can currently confirm. The screen
   *  is required to say so. */
  uncertain: boolean
}

export function hikeFigures(
  hike: Hike,
  trips: readonly Trip[],
  pois: readonly StoredPoi[],
): HikeFigures {
  const resolved = resolvedHikePoints(hike, pois)
  const bounds = boundsOf(resolved)

  const mine = trips.filter((trip) => hike.tripIds.includes(trip.id))
  const walked = mergeSpans(
    clipSpans(
      mine.flatMap((trip) => walkedSpans(trip.plan)),
      bounds,
    ),
  )
  const walkedMi = spanLength(walked)
  const totalMi = bounds.to - bounds.from

  return {
    totalMi,
    walkedMi,
    leftMi: Math.max(0, totalMi - walkedMi),
    daysWalked: mine.reduce(
      (sum, trip) => sum + trip.plan.days.filter((day) => day.walked === true).length,
      0,
    ),
    tripCount: mine.length,
    uncertain: resolved.some((point) => point.from === 'missing'),
  }
}

/** The extent a set of resolved points covers, low mile to high. Empty
 *  points give a zero-length span at mile 0 rather than NaN - a hike this
 *  build could read nothing out of still has to render without throwing. */
function boundsOf(resolved: readonly ResolvedPlace[]): Span {
  if (resolved.length === 0) return { from: 0, to: 0 }
  const miles = resolved.map((point) => point.mile)
  return { from: Math.min(...miles), to: Math.max(...miles) }
}

// ---------------------------------------------------------------------------
// Building one.

/**
 * A hike over the ground a set of trips already covers - the "group what I
 * have" door, which is how an existing hiker gets one without retyping
 * their own history.
 *
 * The ends are the outermost stops across those trips, carried as
 * references wherever the stop had one. Null when the trips describe no
 * ground at all (none of them, or all of them zero-length), because a hike
 * with one end is not a hike.
 */
export function hikeFromTrips(
  trips: readonly Trip[],
  name: string,
  type: Hike['type'] = 'section',
): Hike | null {
  let low: PlaceRef | null = null
  let high: PlaceRef | null = null

  for (const trip of trips) {
    for (const stop of trip.plan.stops) {
      const ref: PlaceRef = {
        mile: stop.mile,
        ...(stop.poiId === undefined ? {} : { poiId: stop.poiId }),
        ...(stop.name === undefined ? {} : { name: stop.name }),
      }
      if (low === null || stop.mile < low.mile) low = ref
      if (high === null || stop.mile > high.mile) high = ref
    }
  }

  if (low === null || high === null || low.mile === high.mile) return null
  return {
    id: crypto.randomUUID(),
    name,
    type,
    trailId: DEFAULT_TRAIL_ID,
    // Two points, low to high. Grouping trips a hiker already kept says
    // nothing about which way round they walked them - order here is trail
    // order, not a claim about a route - so this is deliberately the
    // shallowest possible point list and the set-up flow is where a hiker
    // says more.
    points: [low, high],
    // Trips that are already kept are trips already walked or planned, so
    // this is not a hike anybody is still setting up.
    status: 'walking',
    tripIds: trips.map((trip) => trip.id),
  }
}

/** The hike a trip belongs to, or null. A trip belongs to at most one -
 *  the tree has one parent per node (SEGMENTS.md). */
export function hikeOfTrip(hikes: readonly Hike[], tripId: string): Hike | null {
  return hikes.find((hike) => hike.tripIds.includes(tripId)) ?? null
}

// ---------------------------------------------------------------------------
// Recording ground already walked (#789).

/**
 * A plan describing a stretch the hiker walked BEFORE the app knew about it.
 *
 * Every day in it is walked on arrival, and `generated` is false because
 * nobody generated anything: these boundaries are what the hiker could
 * remember. One boundary pair is the common case ("Springer to Damascus");
 * more, when they remember more.
 *
 * THE TARGET IS A PLACEHOLDER AND NOT A TARGET. `HikePlan` requires one and
 * `validatePlan` refuses a plan without it, but nobody aimed at anything
 * here - the walking already happened. `Trip.recorded` is what tells every
 * reader to ignore it, and the screens that would print a target are
 * already inert on a walked plan (re-targeting refuses once anything is
 * walked). Making `PlanTarget` admit a third "no target" shape would be the
 * cleaner fix and would widen a validated shape that is already on phones,
 * so it is named here rather than done in passing.
 */
export function recordedPlan(stops: PlanStop[], walkedOn?: string): HikePlan {
  const plan = buildPlan(stops, { miles: PLACEHOLDER_TARGET_MI }, walkedOn)
  return {
    ...plan,
    days: plan.days.map((day) => ({ ...day, generated: false, walked: true })),
  }
}

/** See recordedPlan: a number the shape demands and nothing reads. */
const PLACEHOLDER_TARGET_MI = 1

// ---------------------------------------------------------------------------
// The gaps (#790's rows; #791's screen).
//
// A gap is DERIVED and never stored: what is left when the walked stretches
// are subtracted from the hike's own ends. Same discipline that already
// derives a plan's sections from where resupply happens - and it means a gap
// cannot go stale against the record it describes.

/**
 * How short a leftover has to be before it stops being a gap worth showing.
 *
 * @unvalidated 0.2 mi is picked, not measured. The problem it answers is
 * real and named in #791: miles get walked slightly differently than they
 * get recorded - a stretch recalled from memory years later, a day that
 * ended a few hundred feet short of the shelter it was planned to - and the
 * subtraction leaves slivers nobody skipped. Showing them is noise that
 * makes the screen look broken; hiding them quietly calls a hike finished
 * that is not.
 *
 * What would settle it: the distribution of leftover lengths across real
 * recorded hikes, once there are any. Until then this is deliberately on
 * the SMALL side - it hides a rounding artefact and cannot hide a stretch
 * anybody would notice walking, which is the direction that errs toward
 * telling a hiker they still owe something rather than that they do not.
 */
export const MIN_GAP_MI = 0.2

/**
 * The stretches of a hike nobody has walked yet, in trail order.
 *
 * Planned trips are NOT subtracted: a trip on the calendar closes no gap
 * until it is walked, which is the same rule the roll-up follows and the
 * one that keeps "what's left" honest about the difference between an
 * intention and a record.
 */
export function gapSpans(
  hike: Hike,
  trips: readonly Trip[],
  pois: readonly StoredPoi[],
  minGapMi: number = MIN_GAP_MI,
): Span[] {
  const bounds = boundsOf(resolvedHikePoints(hike, pois))

  const walked = mergeSpans(
    clipSpans(
      trips
        .filter((trip) => hike.tripIds.includes(trip.id))
        .flatMap((trip) => walkedSpans(trip.plan)),
      bounds,
    ),
  )

  const gaps: Span[] = []
  let at = bounds.from
  for (const span of walked) {
    if (span.from > at) gaps.push({ from: at, to: span.from })
    at = Math.max(at, span.to)
  }
  if (at < bounds.to) gaps.push({ from: at, to: bounds.to })

  return gaps.filter((gap) => gap.to - gap.from >= minGapMi)
}

/** The ground one trip covers, walked or not - what a row on the hike zoom
 *  spans. Null for a trip describing no ground (every stop at one mile). */
export function tripSpan(trip: Trip): Span | null {
  const miles = trip.plan.stops.map((stop) => stop.mile)
  if (miles.length === 0) return null
  const from = Math.min(...miles)
  const to = Math.max(...miles)
  return to > from ? { from, to } : null
}

/** Where a span sits inside a hike, as fractions from 0 to 1 - what the
 *  ribbon positions its bands by. Clamped, so a trip wandering past the
 *  hike's ends paints inside the ribbon rather than outside it. */
export function spanFraction(
  span: Span,
  bounds: Span,
): { start: number; length: number } {
  const total = bounds.to - bounds.from
  if (total <= 0) return { start: 0, length: 0 }
  const from = Math.min(Math.max(span.from, bounds.from), bounds.to)
  const to = Math.min(Math.max(span.to, bounds.from), bounds.to)
  return { start: (from - bounds.from) / total, length: (to - from) / total }
}

/** A hike's own extent, resolved - the ribbon's and the gaps' frame. */
export function hikeBounds(hike: Hike, pois: readonly StoredPoi[]): Span {
  return boundsOf(resolvedHikePoints(hike, pois))
}

/**
 * A hike's contents in trail order: the trips, and the gaps between them.
 *
 * One list rather than two, because a gap is only meaningful in the company
 * of the pieces on either side of it - and because the hike zoom and the
 * ribbon must not be able to disagree about what a hike contains.
 *
 * A trip covering no ground inside the hike is not here. It has nothing to
 * draw on a trail-ordered list and no honest place between two neighbours;
 * it is still in the trip switcher, which is a list of what a hiker kept
 * rather than a picture of where they walked.
 */
export type HikePiece =
  | {
      kind: 'trip'
      id: string
      trip: Trip
      /** The trip's ground, clipped to the hike. */
      span: Span
      /** The walked parts of it, so the ribbon can ink what happened and
       *  hatch what is only intended - inside one piece as well as between
       *  pieces. */
      walked: Span[]
      state: 'walked' | 'part' | 'planned'
    }
  | { kind: 'gap'; id: string; span: Span; from: PlaceRef; to: PlaceRef }

export function hikePieces(
  hike: Hike,
  trips: readonly Trip[],
  pois: readonly StoredPoi[],
  /** Below this, a leftover is arithmetic rather than trail (MIN_GAP_MI).
   *  Zero asks for every one of them, which is how #791 counts the
   *  remainder it then says out loud rather than dropping. */
  minGapMi: number = MIN_GAP_MI,
): HikePiece[] {
  const bounds = hikeBounds(hike, pois)
  const mine = hike.tripIds
    .map((id) => trips.find((trip) => trip.id === id))
    .filter((trip): trip is Trip => trip !== undefined)

  const pieces: HikePiece[] = []

  for (const trip of mine) {
    const span = tripSpan(trip)
    if (span === null) continue
    const clipped = clipSpans([span], bounds)
    if (clipped.length === 0) continue
    const walked = mergeSpans(clipSpans(walkedSpans(trip.plan), bounds))
    const walkedMi = spanLength(walked)
    const spanMi = spanLength(clipped)
    pieces.push({
      kind: 'trip',
      id: trip.id,
      trip,
      span: clipped[0],
      walked,
      // The comparison is against the trip's own ground, so a trip walked
      // end to end reads walked even where a rounding artefact is left
      // behind - the same threshold the gaps use, for the same reason.
      state:
        walkedMi <= 0 ? 'planned' : spanMi - walkedMi < MIN_GAP_MI ? 'walked' : 'part',
    })
  }

  // A GAP ROW IS NOT THE SAME THING AS A GAP.
  //
  // `gapSpans` is what is left to WALK, so a trip on the calendar does not
  // close one - that is the arithmetic behind "70 mi to go" and it stays
  // that way.
  //
  // A row, though, has to be somewhere on a list, and a gap row overlapping
  // a planned trip's row would put the same ground in two places with two
  // different labels on it. So the rows partition the hike: ground with a
  // trip on it gets that trip's row, which already says whether it was
  // walked; ground with nothing on it at all gets a gap row. The two add up
  // to the same "to go" the ribbon prints - split into "you have a plan for
  // this" and "you have nothing here", which is the split a hiker deciding
  // what to do next is actually making.
  const covered = mergeSpans(pieces.map((piece) => piece.span))
  let at = bounds.from
  const bare: Span[] = []
  for (const span of covered) {
    if (span.from > at) bare.push({ from: at, to: span.from })
    at = Math.max(at, span.to)
  }
  if (at < bounds.to) bare.push({ from: at, to: bounds.to })

  for (const span of bare) {
    if (span.to - span.from < minGapMi) continue
    pieces.push({
      kind: 'gap',
      id: `gap-${span.from}-${span.to}`,
      span,
      from: refAtMile(span.from, hike, mine, pois),
      to: refAtMile(span.to, hike, mine, pois),
    })
  }

  return pieces.sort((a, b) => a.span.from - b.span.from || a.span.to - b.span.to)
}

/**
 * The place a gap begins or ends at.
 *
 * Only places the hike already knows are consulted: its own ends, and the
 * stops of its trips - which is where every gap boundary comes from, since
 * a gap is exactly the complement of what those trips cover. A reference
 * rather than a name, so tapping "plan this stretch" hands the route
 * builder the same place the row named rather than a bare mile that then
 * has to be recognised again.
 *
 * DELIBERATELY NOT a search of the download for whatever POI is nearest.
 * The nearest POI to a gap's end is not necessarily anywhere a hiker could
 * start or finish - naming the ends by somewhere you can actually get to is
 * #791's job, and doing half of it here would put a name on the screen that
 * looks like an access point and is not. A boundary nobody named stays a
 * mile marker, which is a real shared reference rather than a guess.
 */
function refAtMile(
  mile: number,
  hike: Hike,
  trips: readonly Trip[],
  pois: readonly StoredPoi[],
): PlaceRef {
  // Float noise only - a gap boundary is a stop's mile carried through
  // Math.min/max and clipping, never arithmetic on it.
  const EPS = 0.01

  for (const point of hike.points) {
    const resolved = resolvePlace(point, pois)
    if (Math.abs(resolved.mile - mile) < EPS && resolved.name !== undefined) {
      return {
        mile,
        name: resolved.name,
        ...(point.poiId === undefined ? {} : { poiId: point.poiId }),
      }
    }
  }
  for (const trip of trips) {
    for (const stop of trip.plan.stops) {
      if (
        Math.abs(stop.mile - mile) < EPS &&
        stop.name !== undefined &&
        stop.name !== ''
      ) {
        return {
          mile,
          name: stop.name,
          ...(stop.poiId === undefined ? {} : { poiId: stop.poiId }),
        }
      }
    }
  }
  return { mile }
}
