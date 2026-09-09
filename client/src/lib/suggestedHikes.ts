// Suggested hikes (#1284): what the Today shelf and the Find-a-hike screen
// derive from a list of routes somebody published.
//
// A suggested hike is a ROUTE SOMEBODY PUBLISHED - a maintaining club, a
// guidebook author, another OurHike hiker, or an OurHike editorial pick. The
// app surfaces it and names who wrote it; it never rates, ranks or scores a
// route itself. Every number on a card is either the publisher's own word
// (the difficulty, the transit) or arithmetic over the route's cached figures
// at this hiker's pace (the ≈time), and this module is where that line is
// kept: nothing in here invents a rating, and nothing prices a walk whose
// climb nobody measured.
//
// The pure half of the feature, mirroring lib/dayHikeShelf.ts: no React, no
// store reads, so the rules are testable without rendering anything and
// cannot drift into a component. What the screens do with these answers -
// which chip opens which sheet, when the results view is pushed - stays in
// screens/FindHike.tsx.
//
// THE FACET SHEETS ARE HONEST BECAUSE THEY COUNT. Each option says how many
// hikes it would leave, and the primary button says the number it is about to
// show, so a filter is never a promise the list then breaks. The count for an
// option is taken with every OTHER facet as the hiker has it and this facet
// set to that option alone - the number they would see if they picked it.
//
// NO DEAD CONTROLS, which is DayHikeList.tsx's rule for its three sorts and
// holds here for the facets too: a facet no route on the phone can answer
// (a time bucket when nothing can be priced, a transit switch when nobody
// published transit) is not offered, and a sort that cannot be honest is not
// rendered. `availableFacets` and `availableSorts` are the one place that is
// decided.

import type { DayHikeSegment } from './dayHikes'
import { straightLineMiles } from './dayHikeShelf'
import { paceEstimate, type PaceEstimate, type PaceProfile } from './pace'
import { isTown } from './searchPoi'
import type { LonLat, RouteClimb } from './trailGraph'

/**
 * The publisher's own difficulty scale, in order (#1290).
 *
 * FIVE LEVELS, AND THEY ARE NYNJTC'S. This shipped with three - easy,
 * moderate, strenuous - which was a guess at a common denominator made
 * before any publisher's data was in hand. The first one that arrived uses
 * five, tagged on every one of its twenty public hikes (easy 7,
 * easy-moderate 3, moderate 2, moderate-strenuous 4, strenuous 4, measured
 * 2026-09-09), and the maintainer's call was to adopt theirs as the app's
 * rather than flatten it: "we should probably keep their 5 and make 5 the
 * standard".
 *
 * FLATTENING WOULD HAVE BEEN A CLAIM, not a simplification. There is no
 * honest way to fold "Easy to Moderate" into either neighbour - it is a
 * publisher saying the answer is between the two - and rounding it either
 * way would put a word in their mouth on the field a hiker uses to decide
 * whether a walk is within them.
 *
 * The slugs are NYNJTC's own, so a badge quotes the publisher rather than a
 * mapping of them. A sixth word from some future publisher is not silently
 * admitted: lib/suggestedHikesData.ts drops a rating outside this list, and
 * absent means unrated rather than a badge nobody designed.
 */
export const DIFFICULTIES = [
  'easy',
  'easy-moderate',
  'moderate',
  'moderate-strenuous',
  'strenuous',
] as const
/** The publisher's own rating. Quoted, never computed - see the header. */
export type Difficulty = (typeof DIFFICULTIES)[number]

export const AUTHOR_KINDS = ['club', 'guidebook', 'hiker', 'ourhike'] as const
/** Who published a route. "OurHike pick" is a label on a route, never a
 *  score on it or on anybody. */
export type AuthorKind = (typeof AUTHOR_KINDS)[number]

export interface SuggestedHikeAuthor {
  kind: AuthorKind
  name: string
}

/** Public transport to the trailhead, AS PUBLISHED and with the source named.
 *  Absent on a hike means nothing was published - NOT "no transit exists". */
export interface SuggestedHikeTransit {
  line: string
  toStop: string
  /** From the stop to the trailhead, straight along the road as the
   *  publisher gave it. */
  walkMiles: number
  source: string
}

/** A photo is a data surface carrying its own credit and licence
 *  (features/POI_PHOTOS.md), never a bundled asset. */
export interface SuggestedHikePhoto {
  url: string
  credit: string
  licence: string
}

/** The publication line a page carries: who wrote the route up, and when
 *  they last stood behind it. `verifiedOn` absent means never re-verified,
 *  which is a fact about the write-up rather than about the trail. */
export interface SuggestedHikePublication {
  submittedBy: string
  submittedOn: string | null
  verifiedOn: string | null
}

/** Where the walk starts, as the publisher gives it. `basis` says how
 *  firmly: a placed marker, or the centre of a map they embedded, which is
 *  the weaker reading and is labelled as one. */
export interface SuggestedHikeStart {
  lat: number
  lon: number
  basis: string | null
}

/** Everything the hike detail screen prints beyond the card's own figures.
 *  All optional: absent is what the publisher did not say. */
export interface SuggestedHikeDetail {
  /** The publisher's page for this route - where "read it in their words"
   *  goes, and the provenance a card claims nothing without. */
  url?: string
  /** The publisher's OWN stated length, printed beside the miles this phone
   *  measures. The two disagree, sometimes by a fifth, and both ship so the
   *  disagreement is in front of the hiker rather than settled behind them. */
  publishedMiles?: number
  /** Their overview, paragraph by paragraph. */
  overview?: string[]
  /** Their turn-by-turn, paragraph by paragraph - folded behind a button on
   *  the screen, because it is a page of prose and not a figure. */
  description?: string[]
  publication?: SuggestedHikePublication
  start?: SuggestedHikeStart
  /** "Loop", "Out and Back" - the publisher's own word. */
  routeType?: string
  /** The park or preserve the walk is in, their own name for it. */
  park?: string
  /** The trails it uses, their own names, in no promised order. */
  trails?: string[]
  /**
   * One sentence to the HIKER about how this route differs from the
   * publisher's page - what is not drawn and why, where it starts if not at
   * their pin, a measured length well off theirs.
   *
   * Reviewed by a person before it ships (pipeline's
   * reference/nynjtc_hike_routes.json), which is what separates it from
   * anything the app could generate: it says what somebody checked.
   */
  hikerNote?: string
}

export interface SuggestedHike {
  id: string
  name: string
  /** Cached display figure - the same provenance caveat as
   *  DayHikeFigures.miles: computed when the route was published, against
   *  the graph the publisher held. */
  miles: number
  /**
   * All-or-nothing, exactly as DayHikeFigures.climb: `undefined` = never
   * asked, `null` = asked and the graph could not price it. Never 0 as a
   * stand-in, because a walk with one unmeasured edge priced at zero is a
   * flat-ground claim about real ground, and it fails SHORT - the direction
   * that gets somebody caught by the dark.
   */
  climb?: RouteClimb | null
  /** The publisher's own rating, or null. Never computed here. */
  difficulty: Difficulty | null
  author: SuggestedHikeAuthor
  transit?: SuggestedHikeTransit
  photo?: SuggestedHikePhoto
  /**
   * What the DETAIL screen prints and the shelf ignores (#1290).
   *
   * Every field here is optional and absent means the publisher did not
   * say - never a default, never a zero. The shelf and the finder were
   * built before any of them existed and read none of them, so a document
   * carrying only the shelf fields is a complete document rather than a
   * degraded one.
   */
  detail?: SuggestedHikeDetail
  /** The ends, never the route - lib/dayHikes.ts's CRITICAL rule: a
   *  coordinate re-resolves against whatever graph the phone holds, an
   *  edgeIndex silently lands on a different trail after a republish. */
  segments: DayHikeSegment[]
}

/** A saved walk priced from its cached figures, or null when it cannot be.
 *  lib/dayHikeShelf.ts's `cachedEstimate`, for this record: never falls back
 *  to distance alone, because Naismith without ascent understates. */
export function hikeEstimate(
  hike: SuggestedHike,
  pace: PaceProfile,
): PaceEstimate | null {
  const climb = hike.climb
  if (climb === undefined || climb === null) return null
  return paceEstimate(
    { distanceMi: hike.miles, ascentFt: climb.gainFt, descentFt: climb.lossFt },
    pace,
  )
}

export const TIME_BUCKETS = ['under2', '2to4', '4to6', 'allDay'] as const
/** "Time to complete", as the sheet offers it: four buckets of walking time
 *  at the hiker's own pace, never an arrival clock. */
export type TimeBucket = (typeof TIME_BUCKETS)[number]

const MINUTES_PER_HOUR = 60
/** naismith.ts's display step, so a bucket edge and the printed time agree. */
const ROUND_TO_MINUTES = 5

/**
 * The bucket a priced walk falls in.
 *
 * Decided on the ROUNDED minutes - the figure the row prints - rather than
 * the raw ones, so a walk that reads "≈2h" sits under "2 – 4 hours" and not
 * under "Under 2 hours" beside a time that says otherwise. Edges at 2, 4 and
 * 6 hours are the design's own; nobody has measured what a hiker means by
 * "a half day", so they are round numbers and say so.
 */
export function timeBucketOf(minutes: number): TimeBucket {
  const rounded = Math.round(minutes / ROUND_TO_MINUTES) * ROUND_TO_MINUTES
  if (rounded < 2 * MINUTES_PER_HOUR) return 'under2'
  if (rounded < 4 * MINUTES_PER_HOUR) return '2to4'
  if (rounded < 6 * MINUTES_PER_HOUR) return '4to6'
  return 'allDay'
}

/** Where the search is anchored: a picked town or trailhead, with its name. */
export interface HikePlace {
  label: string
  at: LonLat
}

export type HikeSort = 'nearest' | 'shortest' | 'easiest'

export interface HikeFacets {
  /** A picked place, or null for "near me" - which needs a fix to mean
   *  anything, and is the rule label's business (see `anchorOf`). */
  place: HikePlace | null
  /** Empty = any. */
  difficulty: Difficulty[]
  /** Null = any. One bucket rather than a ceiling, because the sheet's
   *  counts are per bucket and "2 – 4 hours" is what a hiker with an
   *  afternoon actually asks. */
  time: TimeBucket | null
  transitOnly: boolean
  /** Empty = any. */
  authors: AuthorKind[]
  /** Null = as published; the screen resolves it to the first honest sort
   *  (`effectiveSort`). */
  sort: HikeSort | null
}

export const NO_FACETS: HikeFacets = {
  place: null,
  difficulty: [],
  time: null,
  transitOnly: false,
  authors: [],
  sort: null,
}

/** The facets a chip can open. Location is the search field itself. */
export type FacetId = 'difficulty' | 'time' | 'transit' | 'author'

/**
 * Whether one hike passes the set facets. Location and sort are not filters
 * - see `findHikes` for why nothing here cuts by distance.
 */
export function matchesFacets(
  hike: SuggestedHike,
  facets: HikeFacets,
  pace: PaceProfile,
): boolean {
  if (
    facets.difficulty.length > 0 &&
    (hike.difficulty === null || !facets.difficulty.includes(hike.difficulty))
  ) {
    return false
  }
  if (facets.time !== null) {
    // A walk nobody can price is in NO bucket: it is listed without a time
    // and is excluded the moment a time is asked for, rather than being
    // guessed into "All day" or priced from distance alone.
    const estimate = hikeEstimate(hike, pace)
    if (estimate === null || timeBucketOf(estimate.minutes) !== facets.time) return false
  }
  if (facets.transitOnly && hike.transit === undefined) return false
  if (facets.authors.length > 0 && !facets.authors.includes(hike.author.kind))
    return false
  return true
}

/** The first tapped end of the first segment, or null for a record with no
 *  readable start. For a loop it is also the finish. */
export function startOf(hike: SuggestedHike): LonLat | null {
  const start = hike.segments[0]?.[0]
  if (start === undefined) return null
  return { lon: start.coord[0], lat: start.coord[1] }
}

/** Straight-line miles from a point to the start - across the ground, not
 *  trail walked, the same distinction dayHikeShelf.ts draws. */
export function milesToStart(hike: SuggestedHike, at: LonLat): number | null {
  const start = startOf(hike)
  return start === null ? null : straightLineMiles(at, start)
}

/** Where "nearest" is measured from: a picked place first, else the fix. */
export function anchorOf(facets: HikeFacets, fix: LonLat | null): LonLat | null {
  return facets.place?.at ?? fix
}

/**
 * A stable sort by a key that may be unknown. Unknowns go LAST rather than
 * vanishing: this is a sort, and a sort that drops rows is a filter wearing a
 * sort's label (dayHikeShelf.ts's `sortedByTime`, restated).
 */
function sortedByKey(
  hikes: readonly SuggestedHike[],
  keyOf: (hike: SuggestedHike) => number | null,
): SuggestedHike[] {
  return hikes
    .map((hike, index) => ({ hike, index, key: keyOf(hike) }))
    .sort((a, b) => {
      if (a.key === null && b.key === null) return a.index - b.index
      if (a.key === null) return 1
      if (b.key === null) return -1
      return a.key - b.key || a.index - b.index
    })
    .map(({ hike }) => hike)
}

export function sortedByStart(
  hikes: readonly SuggestedHike[],
  at: LonLat,
): SuggestedHike[] {
  return sortedByKey(hikes, (hike) => milesToStart(hike, at))
}

export function sortedByEstimate(
  hikes: readonly SuggestedHike[],
  pace: PaceProfile,
): SuggestedHike[] {
  return sortedByKey(hikes, (hike) => hikeEstimate(hike, pace)?.minutes ?? null)
}

/** Derived from DIFFICULTIES' own order rather than restated, so a level
 *  added there cannot be left out of the sort by being forgotten here. */
const DIFFICULTY_RANK: Record<Difficulty, number> = Object.fromEntries(
  DIFFICULTIES.map((level, at) => [level, at]),
) as Record<Difficulty, number>

/** Easiest first BY THE PUBLISHER'S OWN RATING - unrated last, never
 *  guessed from the climb. */
export function sortedByDifficulty(hikes: readonly SuggestedHike[]): SuggestedHike[] {
  return sortedByKey(hikes, (hike) =>
    hike.difficulty === null ? null : DIFFICULTY_RANK[hike.difficulty],
  )
}

export function sortHikes(
  hikes: readonly SuggestedHike[],
  sort: HikeSort | null,
  anchor: LonLat | null,
  pace: PaceProfile,
): SuggestedHike[] {
  if (sort === 'nearest' && anchor !== null) return sortedByStart(hikes, anchor)
  if (sort === 'shortest') return sortedByEstimate(hikes, pace)
  if (sort === 'easiest') return sortedByDifficulty(hikes)
  return [...hikes]
}

/**
 * The sorts that can be honest over these hikes, in the order the control
 * offers them. Nearest needs something to measure from AND a start to
 * measure to; shortest needs one walk that can be priced; easiest needs one
 * walk somebody rated.
 */
export function availableSorts(
  hikes: readonly SuggestedHike[],
  anchor: LonLat | null,
  pace: PaceProfile,
): HikeSort[] {
  const sorts: HikeSort[] = []
  if (anchor !== null && hikes.some((hike) => startOf(hike) !== null))
    sorts.push('nearest')
  if (hikes.some((hike) => hikeEstimate(hike, pace) !== null)) sorts.push('shortest')
  if (hikes.some((hike) => hike.difficulty !== null)) sorts.push('easiest')
  return sorts
}

/** The sort the list actually uses: what was asked for if it is honest, else
 *  the first honest one, else the published order. */
export function effectiveSort(
  requested: HikeSort | null,
  available: readonly HikeSort[],
): HikeSort | null {
  if (requested !== null && available.includes(requested)) return requested
  return available[0] ?? null
}

/**
 * The results: filtered by the facets, ordered by the sort.
 *
 * LOCATION ORDERS, IT NEVER CUTS. "Near Pearisburg" over the list means the
 * list is ordered from Pearisburg, not that routes past some radius were
 * dropped - a radius nobody has picked would hide routes behind a number no
 * hiker can see, and the honest version of "near" with a few dozen published
 * routes on a phone is nearest-first. If a radius is ever wanted, it is a
 * facet with a count like the others, not a silent floor under this one.
 */
export function findHikes(
  hikes: readonly SuggestedHike[],
  facets: HikeFacets,
  pace: PaceProfile,
  fix: LonLat | null,
): SuggestedHike[] {
  const anchor = anchorOf(facets, fix)
  const matched = hikes.filter((hike) => matchesFacets(hike, facets, pace))
  const sort = effectiveSort(facets.sort, availableSorts(hikes, anchor, pace))
  return sortHikes(matched, sort, anchor, pace)
}

export interface FacetCounts {
  difficulty: Record<Difficulty, number>
  time: Record<TimeBucket, number>
  /** How many the transit switch would leave. */
  transit: number
  authors: Record<AuthorKind, number>
}

function countMatching(
  hikes: readonly SuggestedHike[],
  facets: HikeFacets,
  pace: PaceProfile,
): number {
  return hikes.filter((hike) => matchesFacets(hike, facets, pace)).length
}

/**
 * What each option would leave, given every OTHER facet as set. This is what
 * makes the sheets honest: a count is the number the hiker will see if they
 * pick that option next, not a total over the whole phone.
 */
export function facetCounts(
  hikes: readonly SuggestedHike[],
  facets: HikeFacets,
  pace: PaceProfile,
): FacetCounts {
  const difficulty = {} as Record<Difficulty, number>
  for (const level of DIFFICULTIES) {
    difficulty[level] = countMatching(hikes, { ...facets, difficulty: [level] }, pace)
  }
  const time = {} as Record<TimeBucket, number>
  for (const bucket of TIME_BUCKETS) {
    time[bucket] = countMatching(hikes, { ...facets, time: bucket }, pace)
  }
  const authors = {} as Record<AuthorKind, number>
  for (const kind of AUTHOR_KINDS) {
    authors[kind] = countMatching(hikes, { ...facets, authors: [kind] }, pace)
  }
  return {
    difficulty,
    time,
    transit: countMatching(hikes, { ...facets, transitOnly: true }, pace),
    authors,
  }
}

/**
 * The facets a chip may open at all: one no route on the phone can answer is
 * not offered. Author is offered whenever there is anything to search,
 * because every published route names who published it.
 */
export function availableFacets(
  hikes: readonly SuggestedHike[],
  pace: PaceProfile,
): FacetId[] {
  if (hikes.length === 0) return []
  const facets: FacetId[] = []
  if (hikes.some((hike) => hike.difficulty !== null)) facets.push('difficulty')
  if (hikes.some((hike) => hikeEstimate(hike, pace) !== null)) facets.push('time')
  if (hikes.some((hike) => hike.transit !== undefined)) facets.push('transit')
  facets.push('author')
  return facets
}

/** The publishers under each kind, distinct, in published order - what the
 *  author sheet lists under its four rows. */
export function publishersByKind(
  hikes: readonly SuggestedHike[],
): Record<AuthorKind, string[]> {
  const byKind = {} as Record<AuthorKind, string[]>
  for (const kind of AUTHOR_KINDS) byKind[kind] = []
  for (const hike of hikes) {
    const names = byKind[hike.author.kind]
    if (!names.includes(hike.author.name)) names.push(hike.author.name)
  }
  return byKind
}

/**
 * How many cards the Today shelf holds.
 *
 * @unvalidated Three is the design's own frame (two to three cards, the third
 * cut by the screen edge so the rail reads as scrollable). Nobody has watched
 * a hiker flick it; what would settle it is whether the third card ever gets
 * tapped.
 */
export const SHELF_SIZE = 3

/**
 * The shelf's picks: the nearest starts when there is a fix, the first
 * published otherwise. No fix makes no distance claim - the rule above the
 * shelf reads "Suggested hikes", not "near you".
 */
export function shelfPicks(
  hikes: readonly SuggestedHike[],
  at: LonLat | null,
  size: number = SHELF_SIZE,
): SuggestedHike[] {
  const ordered = at === null ? [...hikes] : sortedByStart(hikes, at)
  return ordered.slice(0, size)
}

/** One applied filter, as a removable chip on the results screen. */
export interface AppliedFilter {
  facet: FacetId
  /** The option inside the facet - a difficulty, a bucket, an author kind,
   *  or 'transit' for the switch. */
  id: string
  label: string
}

export function appliedFilters(facets: HikeFacets): AppliedFilter[] {
  const applied: AppliedFilter[] = []
  if (facets.time !== null) {
    applied.push({ facet: 'time', id: facets.time, label: timeBucketChip(facets.time) })
  }
  if (facets.transitOnly)
    applied.push({ facet: 'transit', id: 'transit', label: 'By transit' })
  for (const level of facets.difficulty) {
    applied.push({ facet: 'difficulty', id: level, label: difficultyLabel(level) })
  }
  for (const kind of facets.authors) {
    applied.push({ facet: 'author', id: kind, label: authorKindLabel(kind) })
  }
  return applied
}

/** The facets with one applied filter dropped - a chip's ✕. */
export function withoutFilter(facets: HikeFacets, filter: AppliedFilter): HikeFacets {
  switch (filter.facet) {
    case 'time':
      return { ...facets, time: null }
    case 'transit':
      return { ...facets, transitOnly: false }
    case 'difficulty':
      return { ...facets, difficulty: facets.difficulty.filter((d) => d !== filter.id) }
    case 'author':
      return { ...facets, authors: facets.authors.filter((a) => a !== filter.id) }
  }
}

/** The facets with one whole facet cleared - a sheet's Clear. */
export function withoutFacet(facets: HikeFacets, facet: FacetId): HikeFacets {
  switch (facet) {
    case 'time':
      return { ...facets, time: null }
    case 'transit':
      return { ...facets, transitOnly: false }
    case 'difficulty':
      return { ...facets, difficulty: [] }
    case 'author':
      return { ...facets, authors: [] }
  }
}

/** Whether a facet has anything set - the chip's "set" styling. */
export function facetIsSet(facets: HikeFacets, facet: FacetId): boolean {
  switch (facet) {
    case 'time':
      return facets.time !== null
    case 'transit':
      return facets.transitOnly
    case 'difficulty':
      return facets.difficulty.length > 0
    case 'author':
      return facets.authors.length > 0
  }
}

// ---------- Places ----------

/** Somewhere a search can be anchored: a town or a trailhead the phone
 *  already holds. Nothing here needs signal, and nothing here geocodes. */
export interface HikePlaceOption {
  id: string
  name: string
  kind: 'town' | 'trailhead'
  at: LonLat
}

/**
 * The places the search field can resolve, from the downloaded waypoints.
 *
 * Towns and trailheads only - "Town, trailhead, or near me" is the field's
 * own promise, and a shelter is a place to search NEAR rather than a place
 * a hiker sets out from. Towns are what lib/searchPoi.ts already calls
 * towns: ATC's designated Communities, which is the only town point the
 * phone holds.
 */
export function hikePlaces(
  pois: readonly {
    id: string
    name: string
    type: string
    source?: string
    lat: number
    lon: number
  }[],
): HikePlaceOption[] {
  const places: HikePlaceOption[] = []
  for (const poi of pois) {
    const kind = poi.type === 'trailhead' ? 'trailhead' : isTown(poi) ? 'town' : null
    if (kind === null) continue
    places.push({ id: poi.id, name: poi.name, kind, at: { lon: poi.lon, lat: poi.lat } })
  }
  return places
}

/**
 * How many place matches the field offers under itself.
 *
 * @unvalidated Six is what fits under the field above the chip row on a
 * 390px phone without pushing the first result off screen; nobody has typed
 * into this field yet. What would settle it is whether a hiker ever scrolls
 * a longer list rather than typing one more letter.
 */
export const PLACE_MATCH_LIMIT = 6

/** Places whose name contains the query, earliest match first then by name -
 *  lib/searchPoi.ts's own ordering, over this narrower set. */
export function searchPlaces(
  places: readonly HikePlaceOption[],
  query: string,
  limit: number = PLACE_MATCH_LIMIT,
): HikePlaceOption[] {
  const needle = query.trim().toLowerCase()
  if (needle === '') return []
  return places
    .map((place) => ({ place, at: place.name.toLowerCase().indexOf(needle) }))
    .filter(({ at }) => at !== -1)
    .sort((a, b) => a.at - b.at || a.place.name.localeCompare(b.place.name))
    .slice(0, limit)
    .map(({ place }) => place)
}

// ---------- Words ----------

/** NYNJTC's own words for their own levels, spelled as their pages spell
 *  them - "Easy to Moderate", not "Easy-moderate". */
export function difficultyLabel(level: Difficulty): string {
  return {
    easy: 'Easy',
    'easy-moderate': 'Easy to Moderate',
    moderate: 'Moderate',
    'moderate-strenuous': 'Moderate to Strenuous',
    strenuous: 'Strenuous',
  }[level]
}

export function timeBucketLabel(bucket: TimeBucket): string {
  return {
    under2: 'Under 2 hours',
    '2to4': '2 – 4 hours',
    '4to6': '4 – 6 hours',
    allDay: 'All day',
  }[bucket]
}

/** The chip's shorter form. */
export function timeBucketChip(bucket: TimeBucket): string {
  return { under2: 'Under 2 h', '2to4': '2–4 h', '4to6': '4–6 h', allDay: 'All day' }[
    bucket
  ]
}

export function authorKindLabel(kind: AuthorKind): string {
  return {
    club: 'Clubs',
    guidebook: 'Guidebooks',
    hiker: 'Hikers',
    ourhike: 'OurHike picks',
  }[kind]
}

/** The line under a card that names who wrote the route - the publisher's
 *  name, in the voice that says what kind of publisher they are. */
export function authorLine(author: SuggestedHikeAuthor): string {
  switch (author.kind) {
    case 'club':
      return author.name
    case 'guidebook':
      return `Guidebook route · ${author.name}`
    case 'hiker':
      return `Published by ${author.name}`
    case 'ourhike':
      // A label on the route, and the route's own author still named: a
      // pick is a thing OurHike chose, not a thing OurHike wrote.
      return `OurHike pick · route by ${author.name}`
  }
}

export function sortLabel(sort: HikeSort): string {
  return {
    nearest: 'nearest first',
    shortest: 'shortest first',
    easiest: 'easiest first',
  }[sort]
}
