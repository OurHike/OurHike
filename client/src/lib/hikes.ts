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

import type { HikePlan } from './plan'
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

/** A hike, as SEGMENTS.md models it. `type` is a label and a default
 *  suggestion, not a constraint - and it is read elsewhere: PRICING_MODEL.md
 *  scopes the thru-hike pass by exactly this field, so it is named
 *  deliberately rather than incidentally. */
export interface Hike {
  id: string
  name: string
  type: 'thru' | 'section' | 'day'
  start: PlaceRef
  end: PlaceRef
  /** The trips walked, or planned, inside this hike. Order is not meaning:
   *  a flip-flopper walks the pieces in whatever order suits them (#791). */
  tripIds: string[]
}

export function validateHike(candidate: unknown): Hike | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const hike = candidate as Partial<Hike>
  if (typeof hike.id !== 'string' || hike.id.length === 0) return null
  if (typeof hike.name !== 'string') return null
  if (hike.type !== 'thru' && hike.type !== 'section' && hike.type !== 'day') return null
  const start = validatePlaceRef(hike.start)
  const end = validatePlaceRef(hike.end)
  if (start === null || end === null) return null
  if (!Array.isArray(hike.tripIds)) return null
  const tripIds = hike.tripIds.filter((id): id is string => typeof id === 'string')
  return { id: hike.id, name: hike.name, type: hike.type, start, end, tripIds }
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
  const start = resolvePlace(hike.start, pois)
  const end = resolvePlace(hike.end, pois)
  const bounds: Span = {
    from: Math.min(start.mile, end.mile),
    to: Math.max(start.mile, end.mile),
  }

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
    uncertain: start.from === 'missing' || end.from === 'missing',
  }
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
    start: low,
    end: high,
    tripIds: trips.map((trip) => trip.id),
  }
}

/** The hike a trip belongs to, or null. A trip belongs to at most one -
 *  the tree has one parent per node (SEGMENTS.md). */
export function hikeOfTrip(hikes: readonly Hike[], tripId: string): Hike | null {
  return hikes.find((hike) => hike.tripIds.includes(tripId)) ?? null
}
