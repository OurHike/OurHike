// Which clubs' notices a hiker sees (#1805, decision 66).
//
// The maintainer's answer, by poll on 2026-10-04, in their own words: "Every
// notice that touches a planned hike in the next 7 days. for a long hike get
// everything along the planned hike in the next 7". conditions/notices.json
// carries every club's notices - 129 clubs once decision 53's phases land -
// and a list of all of them is the feed features/ORG_NOTICES.md §9 warns a
// warning surface turns into. This module is the rule that keeps it a
// warning: the notices that touch what the hiker is about to walk, and
// nothing else.
//
// THE WINDOW is today and the six days after it, by the phone's own calendar
// (lib/passedToday.ts's `localDay`) - seven days, `NOTICE_WINDOW_DAYS`. A day
// dated in it is planned "in the next 7 days"; the seventh day after today is
// not. The maintainer's number, so it is not tagged as a guess.
//
// WHAT IS A PLANNED HIKE, from what the phone already stores:
//
//  - a DAY HIKE (lib/dayHikes.ts) the hiker laid out (`recorded: 'planned'`)
//    and dated inside the window. Its route is the graph's own routing of its
//    tapped ends (lib/dayHikeCard.ts's `resolveDayHike`, handed in as a
//    `DayHikeRouter`) where this phone holds the graph cells, else the
//    tapped ends joined - which says so
//    (`routeResolved`), because a straight line between two taps is not where
//    the hiker walks;
//  - the DAYS OF A LONG HIKE's plans (lib/trips.ts, each trip a lib/plan.ts
//    plan on the A.T.'s mile axis) that are dated inside the window and not
//    yet walked. That is the maintainer's "for a long hike get everything
//    along the planned hike in the next 7": a thru-hike starting tomorrow is
//    the next seven days of it, never all 2,197 miles. A short trip that
//    falls inside the window whole is all of it, by the same rule.
//
// An UNDATED plan is not planned for any day, so it is not in the window:
// thru-hikers plan loosely and plan.ts makes the date optional for that
// reason. The panel says how many it skipped, rather than guessing a date.
//
// WHAT "TOUCHES" MEANS, from the notice's own place (ORG_NOTICES.md §3):
//
//  - `at_miles` (ATC): its miles overlap a long hike's planned miles, or its
//    stretch of the A.T. centerline meets a day hike's route;
//  - `geometry` (a club's own polygon, line or point, decision 67's hazard
//    areas among them): it meets the route within `NOTICE_REACH_FEET`;
//  - `unplaced` and `org_terms`: the club that posted it maintains a trail
//    the route uses. `org_terms` is read as unplaced on purpose - no reviewed
//    table maps NYNJTC's terms to features yet, and ORG_NOTICES.md §4's rule
//    is that "an unmapped term places nothing".
//
// AND IN TIME: a notice whose own start is after the hike's last planned day,
// or whose own end is before its first, does not touch it. Most notices state
// neither, and then only the place decides.
//
// WHICH CLUBS MAINTAIN THE ROUTE, from data the phone already has, never a
// name match:
//
//  - a day hike's legs carry the registry key of each trail line they walk
//    (`source`, and `concurrent_sources` where one tread carries two
//    designations, #1115); stewards.json (lib/stewards.ts) lists which
//    provider each key belongs to;
//  - a long hike walks the A.T.: the provider of the A.T. centerline's key
//    (`centerline`), plus every club ATC's own club-sections layer
//    (club_sections.json, lib/clubSections.ts) assigns a planned mile to,
//    where that club's acronym is the registry's provider for it - GMC on a
//    Vermont stretch, NYNJTC through Harriman. An acronym with no provider
//    of that spelling publishes no notice this phone could match, and is
//    skipped rather than fuzzily joined.
//
// A notice names its club by the `provider` notices.json carries, else by
// its source key through the same stewards.json.
//
// NOTHING IS PICKED WITH NO PLANNED HIKE IN THE WINDOW. The panel says why
// and how to change that (chrome/PlannedNoticeList.tsx). Showing every club
// instead is the feed this decision exists to avoid; the notices the map
// draws still open their own sheet when tapped.

import type { DayHike, DayHikeLeg } from './dayHikes'
import {
  geometryParts,
  linesMeetParts,
  type GeometryParts,
  type Position,
} from './noticeGeometry'
import type { TrailNotice } from './notices'
import { clubTimeline, type ClubSections } from './clubSections'
import type { Stewards } from './stewards'
import type { RouteLeg } from './trailGraph'
import { trailPointAtMile, trailSlice, type TrailIndex } from './trailPosition'
import type { Trip } from './trips'

/** Today and the six days after it. The maintainer's number (decision 66). */
export const NOTICE_WINDOW_DAYS = 7

/**
 * How far from a route a placed notice may be and still touch it.
 *
 * @unvalidated 300 ft is picked, not measured. The notice and the route are
 * usually drawn by different organizations - a club's own closure point
 * against the trail graph's line, or ATC's centerline - and two maps of one
 * tread sit apart: the median ATC shelter is 21 m from its nearest CSI
 * shelter row (pipeline/build_water_distance.py's docstring), so 300 ft
 * (91 m) is about four of those, wide enough that a point published on the
 * club's own line still meets the same trail drawn by somebody else, and
 * short of the next trail over in most terrain. It errs toward showing: a
 * notice 250 ft off the route is shown, which is the cheap mistake. What
 * would settle it: the distance from each live placed notice to the nearest
 * network line, which nobody has measured.
 */
export const NOTICE_REACH_FEET = 300

/** The registry key of the A.T. centerline (pipeline/sources.json). */
export const AT_CENTERLINE_SOURCE_KEY = 'centerline'

/** One hike the hiker has planned inside the window, as the rule reads it. */
export interface PlannedStretch {
  /** Stable across renders: `trip:<id>` or `day-hike:<id>`. */
  id: string
  kind: 'day_hike' | 'long_hike'
  /** What the hiker calls it. */
  label: string
  /** The first and last planned day inside the window, ISO dates. */
  from: string
  to: string
  /** A long hike's planned A.T. miles, merged, each `[low, high]`. Empty for
   *  a day hike. */
  atSpans: Array<[number, number]>
  /** Where the route runs, as `[lon, lat]` lines. Empty when the phone holds
   *  neither the centerline nor the graph to draw it with. */
  lines: Position[][]
  /** False when `lines` is a day hike's tapped ends joined, because this
   *  phone could not route them; placed notices are then matched to that
   *  rougher line and the panel says so. */
  routeResolved: boolean
  /** The registry providers of the trails it walks. */
  providers: ReadonlySet<string>
}

/** What one planned hike is shown. */
export interface PlannedHikeNotices {
  stretch: PlannedStretch
  /** Placed notices that meet the route, closures first. */
  onRoute: TrailNotice[]
  /** Unplaced notices from the clubs that maintain its trails. */
  fromClubs: TrailNotice[]
}

export type NoPlannedHike =
  /** No day hike laid out and no long-hike plan at all. */
  | 'nothing_planned'
  /** Plans exist, and none has a day dated in the window. */
  | 'nothing_in_the_window'

export interface PlannedNotices {
  hikes: PlannedHikeNotices[]
  /** Null when at least one hike is planned in the window. */
  empty: NoPlannedHike | null
  /** Plans that carry no date at all, which no window can hold. */
  undated: number
}

/** ISO day `offset` days from `day`, in UTC date arithmetic as lib/plan.ts's
 *  `dateOfDay` does it, so the window does not move with a DST change. */
export function shiftDay(day: string, offset: number): string {
  const [year, month, date] = day.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, date + offset)).toISOString().slice(0, 10)
}

/** Whether an ISO day is inside the window that starts `today`. */
export function inNoticeWindow(day: string, today: string): boolean {
  return day >= today && day <= shiftDay(today, NOTICE_WINDOW_DAYS - 1)
}

function mergeSpans(spans: Array<[number, number]>): Array<[number, number]> {
  const sorted = spans
    .map(([a, b]): [number, number] => [Math.min(a, b), Math.max(a, b)])
    .sort((x, y) => x[0] - y[0])
  const merged: Array<[number, number]> = []
  for (const span of sorted) {
    const last = merged[merged.length - 1]
    if (last !== undefined && span[0] <= last[1]) last[1] = Math.max(last[1], span[1])
    else merged.push([span[0], span[1]])
  }
  return merged
}

/** The A.T. between two miles as lines, or a point where the span has no
 *  length - or nothing, before the centerline has loaded. */
function centerlineLines(
  index: TrailIndex | null,
  low: number,
  high: number,
): Position[][] {
  if (index === null) return []
  if (low === high) {
    const at = trailPointAtMile(index, low)
    return at === null ? [] : [[at, at]]
  }
  return trailSlice(index, low, high)
}

/** Provider of every registry key the stewards list names. */
function providersByKey(stewards: Stewards): Map<string, string> {
  const byKey = new Map<string, string>()
  for (const steward of stewards)
    for (const key of steward.keys) byKey.set(key, steward.provider)
  return byKey
}

function atProviders(
  spans: Array<[number, number]>,
  clubSections: ClubSections,
  byKey: Map<string, string>,
  known: ReadonlySet<string>,
): Set<string> {
  const providers = new Set<string>()
  const atProvider = byKey.get(AT_CENTERLINE_SOURCE_KEY)
  if (atProvider !== undefined) providers.add(atProvider)
  for (const run of clubTimeline(clubSections)) {
    if (run.club === null || !known.has(run.club.acronym)) continue
    if (spans.some(([low, high]) => run.startMile <= high && run.endMile >= low)) {
      providers.add(run.club.acronym)
    }
  }
  return providers
}

/**
 * A day hike's route as the phone's graph routes it: the lines it walks and
 * the legs it walks them on, or null when this phone cannot route it (no
 * graph cells with their vertices, or ends the graph no longer connects).
 *
 * Handed in by the caller rather than imported, because the routing lives in
 * lib/dayHikeCard.ts and lib/trailGraph.ts, which the first frame already
 * holds, and this module loads behind import() (lib/noticeSelection.ts); an
 * import here would split those modules into a chunk of their own for both
 * to share, which the launch budget measured as bytes it does not have.
 */
export type DayHikeRouter = (
  hike: DayHike,
) => { lines: Position[][]; legs: ReadonlyArray<RouteLeg | DayHikeLeg> } | null

/** Every planned hike with a day inside the window. */
export function plannedStretches({
  trips,
  dayHikes,
  today,
  trailIndex,
  routeDayHike,
  clubSections,
  stewards,
}: {
  trips: readonly Trip[]
  dayHikes: readonly DayHike[]
  today: string
  trailIndex: TrailIndex | null
  routeDayHike: DayHikeRouter | null
  clubSections: ClubSections
  stewards: Stewards
}): PlannedStretch[] {
  const byKey = providersByKey(stewards)
  const known = new Set(stewards.map((steward) => steward.provider))
  const stretches: PlannedStretch[] = []

  for (const trip of trips) {
    if (trip.recorded === true) continue
    const { stops, days } = trip.plan
    const spans: Array<[number, number]> = []
    const dates: string[] = []
    days.forEach((day, index) => {
      if (day.walked === true || day.date === undefined) return
      if (!inNoticeWindow(day.date, today)) return
      const start = stops[index]
      const end = stops[index + 1]
      if (start === undefined || end === undefined) return
      spans.push([start.mile, end.mile])
      dates.push(day.date)
    })
    if (spans.length === 0) continue
    const atSpans = mergeSpans(spans)
    dates.sort()
    stretches.push({
      id: `trip:${trip.id}`,
      kind: 'long_hike',
      label: trip.name,
      from: dates[0],
      to: dates[dates.length - 1],
      atSpans,
      lines: atSpans.flatMap(([low, high]) => centerlineLines(trailIndex, low, high)),
      routeResolved: trailIndex !== null,
      providers: atProviders(atSpans, clubSections, byKey, known),
    })
  }

  for (const hike of dayHikes) {
    if (hike.recorded !== 'planned' || hike.date === null) continue
    if (!inNoticeWindow(hike.date, today)) continue
    const routed = routeDayHike === null ? null : routeDayHike(hike)
    const routeResolved = routed !== null && routed.lines.length > 0
    const lines: Position[][] = routeResolved
      ? routed.lines
      : hike.segments.map((segment) => segment.map((end) => end.coord))
    const legs = routed?.legs ?? hike.figures.legs
    const providers = new Set<string>()
    for (const leg of legs) {
      for (const key of [leg.source, ...(leg.concurrent_sources ?? [])]) {
        const provider = key === null ? undefined : byKey.get(key)
        if (provider !== undefined) providers.add(provider)
      }
    }
    stretches.push({
      id: `day-hike:${hike.id}`,
      kind: 'day_hike',
      label: hike.name,
      from: hike.date,
      to: hike.date,
      atSpans: [],
      lines,
      routeResolved,
      providers,
    })
  }

  return stretches.sort(
    (a, b) => a.from.localeCompare(b.from) || a.label.localeCompare(b.label),
  )
}

/** The parts a placed notice occupies, or null for one with no place. The
 *  A.T. ones come off the centerline, so they need it loaded. */
function placedParts(
  notice: TrailNotice,
  trailIndex: TrailIndex | null,
): GeometryParts | null {
  const { place } = notice
  if (place.kind === 'geometry') return geometryParts(place.geometry)
  if (place.kind === 'at_miles') {
    const low = Math.min(place.start, place.end)
    const high = Math.max(place.start, place.end)
    const lines = centerlineLines(trailIndex, low, high)
    return lines.length === 0
      ? null
      : { points: [], lines: lines.map((line) => [...line]), polygons: [] }
  }
  return null
}

/** Whether a notice's own dates overlap the planned days. Absent dates are
 *  no constraint: most notices state neither. */
function overlapsInTime(notice: TrailNotice, stretch: PlannedStretch): boolean {
  if (notice.starts_on && notice.starts_on > stretch.to) return false
  if (notice.ends_on && notice.ends_on < stretch.from) return false
  return true
}

function noticeProvider(
  notice: TrailNotice,
  byKey: Map<string, string>,
): string | undefined {
  return notice.provider ?? byKey.get(notice.source_key)
}

/** Closures first, then the most recently updated. */
function byWeight(a: TrailNotice, b: TrailNotice): number {
  if (a.obstructs_trail !== b.obstructs_trail) return a.obstructs_trail ? -1 : 1
  return (b.updated_at ?? '').localeCompare(a.updated_at ?? '')
}

/** Whether one notice touches one planned hike (the module comment's rule). */
export function noticeTouches(
  notice: TrailNotice,
  stretch: PlannedStretch,
  trailIndex: TrailIndex | null,
  byKey: Map<string, string>,
): 'on_route' | 'from_club' | null {
  if (!overlapsInTime(notice, stretch)) return null
  const { place } = notice
  if (place.kind === 'unplaced' || place.kind === 'org_terms') {
    const provider = noticeProvider(notice, byKey)
    return provider !== undefined && stretch.providers.has(provider) ? 'from_club' : null
  }
  if (place.kind === 'at_miles') {
    const low = Math.min(place.start, place.end)
    const high = Math.max(place.start, place.end)
    if (stretch.atSpans.some(([a, b]) => low <= b && high >= a)) return 'on_route'
  }
  if (stretch.lines.length === 0) return null
  const parts = placedParts(notice, trailIndex)
  if (parts === null) return null
  return linesMeetParts(stretch.lines, parts, NOTICE_REACH_FEET) ? 'on_route' : null
}

/** The panel's whole answer: each planned hike in the window and the notices
 *  that touch it, or why there is nothing to show. */
export function plannedNotices({
  notices,
  trips,
  dayHikes,
  today,
  trailIndex,
  routeDayHike,
  clubSections,
  stewards,
}: {
  notices: readonly TrailNotice[]
  trips: readonly Trip[]
  dayHikes: readonly DayHike[]
  today: string
  trailIndex: TrailIndex | null
  routeDayHike: DayHikeRouter | null
  clubSections: ClubSections
  stewards: Stewards
}): PlannedNotices {
  const stretches = plannedStretches({
    trips,
    dayHikes,
    today,
    trailIndex,
    routeDayHike,
    clubSections,
    stewards,
  })
  const plannedDayHikes = dayHikes.filter((hike) => hike.recorded === 'planned')
  const plannedTrips = trips.filter((trip) => trip.recorded !== true)
  const undated =
    plannedDayHikes.filter((hike) => hike.date === null).length +
    plannedTrips.filter((trip) => trip.plan.days.every((day) => day.date === undefined))
      .length

  if (stretches.length === 0) {
    const anything = plannedDayHikes.length + plannedTrips.length > 0
    return {
      hikes: [],
      empty: anything ? 'nothing_in_the_window' : 'nothing_planned',
      undated,
    }
  }

  const byKey = providersByKey(stewards)
  const hikes = stretches.map((stretch) => {
    const onRoute: TrailNotice[] = []
    const fromClubs: TrailNotice[] = []
    for (const notice of notices) {
      const touch = noticeTouches(notice, stretch, trailIndex, byKey)
      if (touch === 'on_route') onRoute.push(notice)
      else if (touch === 'from_club') fromClubs.push(notice)
    }
    onRoute.sort(byWeight)
    fromClubs.sort(byWeight)
    return { stretch, onRoute, fromClubs }
  })
  return { hikes, empty: null, undated }
}

/** Every notice the panel shows, once, across its hikes - what the "new
 *  notices" dot counts and what opening the panel silences. */
export function shownNotices(planned: PlannedNotices): TrailNotice[] {
  const seen = new Map<string, TrailNotice>()
  for (const hike of planned.hikes) {
    for (const notice of [...hike.onRoute, ...hike.fromClubs])
      seen.set(notice.notice_id, notice)
  }
  return [...seen.values()]
}
