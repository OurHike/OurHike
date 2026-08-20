// Who maintains which stretch of the A.T., read from the artifact
// pipeline/export_club_sections.py has been publishing since #594 and nothing
// on the client has ever opened (features/CORRIDOR_VIEW.md, #598).
//
// WHY THE FIELD IS `stretches` AND THE TYPE HERE IS `runs`
//
// The published artifact spells a club's contiguous pieces of trail
// `stretches`, and that name is now spoken for: the maintainer's #552 decision
// (2026-08-18) gives `stretch` to the ~50-mile offline download unit that
// pipeline/cut_stretches.py cuts, and asked on 2026-08-19 that nothing else
// reuse the word. Renaming the published key is a schema change with its own
// cost; renaming it AT THE BOUNDARY costs one line of parsing and keeps the
// word meaning one thing everywhere above this file.
//
// WHAT THE NUMBERS ARE, AND WHERE THEY CAME FROM
//
// Measured by export_club_sections.py against the live ATC layers (#594):
// 30 clubs tiling 2,197.5 miles with no seams or overlaps, plus 38.5 miles in
// 27 runs that the fresh source cannot attribute - 47 centerline features
// carrying a digit string where a club acronym belongs, 1.90% of the corridor.
//
// The two dates a hiker may be shown are deliberately separate and two years
// apart: WHICH club comes from `centerline` (edited 2026-08-04), while HOW the
// club's name is spelled comes from the `trail_club_sections` polygons (edited
// 2024-08-15). The exporter publishes them under `sources` rather than as one
// "as of", and nothing here collapses them back together.
//
// ABSENT MEANS UNKNOWN
//
// A mile with no club is `null`, and every caller has to render that as "not
// recorded" rather than as "nobody maintains this". Somebody almost certainly
// does; ATC's own centerline cannot name them. This is CLAUDE.md's "omit
// rather than guess" applied to an attribution, and it is why the exporter
// publishes the unattributed runs explicitly instead of leaving gaps - a gap
// would read as "no trail here".

/** A half-open mile interval on the calibrated NOBO axis, `[startMile, endMile)`. */
export interface MileRange {
  startMile: number
  endMile: number
}

export interface ClubSection {
  /** ATC's own acronym, e.g. `GATC`. The stable key. */
  acronym: string
  /** Spelled as the polygon layer spells it, which is what keeps ATC's two
   *  known misspellings off a hiker's screen - see lib/club_sections.py. */
  name: string
  /** ATC region, or null where the polygon layer does not carry the club. */
  region: string | null
  /** The club's contiguous pieces of trail - the artifact's `stretches`. */
  runs: MileRange[]
  /** Total maintained miles, as published (already rounded to 0.1). */
  miles: number
}

/** Which upstream layer decided each half of the answer. */
export interface ClubSectionSources {
  attribution: string | null
  names: string | null
  miles: string | null
}

export interface ClubSections {
  clubs: ClubSection[]
  unattributed: MileRange[]
  sources: ClubSectionSources
}

/**
 * One piece of the corridor and who looks after it.
 *
 * `club: null` is the published unattributed case, not a lookup miss.
 */
export interface ClubRun extends MileRange {
  club: ClubSection | null
}

export const EMPTY_CLUB_SECTIONS: ClubSections = {
  clubs: [],
  unattributed: [],
  sources: { attribution: null, names: null, miles: null },
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function finiteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function optionalString(value: unknown): string | null {
  return typeof value === 'string' && value !== '' ? value : null
}

/** One `{start_mile, end_mile}` record, or null if either end is unusable.
 *
 *  A range whose ends are equal is dropped too: it covers no trail, and a
 *  zero-width run would show up as a boundary tick standing on nothing. */
function parseRange(value: unknown): MileRange | null {
  if (!isRecord(value)) return null
  const startMile = finiteNumber(value.start_mile)
  const endMile = finiteNumber(value.end_mile)
  if (startMile === null || endMile === null) return null
  if (endMile <= startMile) return null
  return { startMile, endMile }
}

function parseRanges(value: unknown): MileRange[] {
  if (!Array.isArray(value)) return []
  return value.map(parseRange).filter((range): range is MileRange => range !== null)
}

function parseClub(value: unknown): ClubSection | null {
  if (!isRecord(value)) return null
  const acronym = optionalString(value.acronym)
  if (acronym === null) return null
  const runs = parseRanges(value.stretches)
  if (runs.length === 0) return null
  return {
    acronym,
    // Falling back to the acronym rather than to an empty string: the polygon
    // layer is two years stale and may not carry a club the fresh centerline
    // names, and "GATC" on a sheet is a worse answer than the full name but a
    // far better one than a blank heading.
    name: optionalString(value.name) ?? acronym,
    region: optionalString(value.region),
    runs,
    miles:
      finiteNumber(value.miles) ??
      runs.reduce((sum, r) => sum + (r.endMile - r.startMile), 0),
  }
}

/**
 * Parses `club_sections.json`.
 *
 * Never throws and never rejects a whole release over one bad row: anything
 * unreadable becomes an absence, which the app already renders honestly. The
 * same restraint lib/trailData.ts's fetchSpurs applies, for the same reason -
 * a corridor the map cannot attribute is still a corridor worth drawing.
 */
export function parseClubSections(raw: unknown): ClubSections {
  if (!isRecord(raw)) return EMPTY_CLUB_SECTIONS
  const sources = isRecord(raw.sources) ? raw.sources : {}
  const clubs = Array.isArray(raw.clubs)
    ? raw.clubs.map(parseClub).filter((club): club is ClubSection => club !== null)
    : []
  return {
    clubs,
    unattributed: parseRanges(raw.unattributed),
    sources: {
      attribution: optionalString(sources.attribution),
      names: optionalString(sources.names),
      miles: optionalString(sources.miles),
    },
  }
}

/**
 * What IndexedDB handed back, or nothing when it is not the shape this version
 * stores.
 *
 * NOT parseClubSections. What is stored is the DOMAIN shape - a club's pieces
 * are `runs` by the time they are written - while the parser reads the
 * ARTIFACT shape, where they are `stretches`. Running the artifact parser over
 * a stored value finds no `stretches` on any club and yields an empty
 * corridor, which looks exactly like a release that publishes no attribution.
 * That bug existed for the length of one test run and is the reason this
 * function is named rather than inlined as a cast.
 */
export function storedClubSections(value: unknown): ClubSections {
  if (
    !isRecord(value) ||
    !Array.isArray(value.clubs) ||
    !Array.isArray(value.unattributed)
  ) {
    return EMPTY_CLUB_SECTIONS
  }
  return value as unknown as ClubSections
}

/**
 * Every published run in mile order, attributed and unattributed alike.
 *
 * The exporter's whole guarantee is that these TILE the trail - Springer to
 * Katahdin, no seams and no overlaps - so this is the corridor read end to
 * end, and the boundaries between entries are exactly the places a tick mark
 * belongs.
 *
 * Sorted here rather than trusted from the artifact. The clubs arrive grouped
 * by club, so their runs interleave in mile terms the moment a club maintains
 * two separate pieces (four of the thirty do), and every consumer below wants
 * the corridor's order rather than the file's.
 */
export function clubTimeline(sections: ClubSections): ClubRun[] {
  const runs: ClubRun[] = []
  for (const club of sections.clubs) {
    for (const range of club.runs) runs.push({ ...range, club })
  }
  for (const range of sections.unattributed) runs.push({ ...range, club: null })
  return runs.sort((a, b) => a.startMile - b.startMile)
}

/**
 * The run covering a mile, or null past either end of the published corridor.
 *
 * Half-open, `[startMile, endMile)`, so the mile two runs share resolves to
 * the NORTHBOUND one and never to both. The exception is the far end: the last
 * run includes its own `endMile`, or Katahdin itself - mile 2,197.5, a real
 * place a hiker can stand - would answer "not recorded" when the artifact
 * plainly attributes it to MATC.
 *
 * Linear rather than bisected on purpose. The timeline is 57 entries for the
 * whole A.T. (30 clubs' runs plus 27 unattributed), so a scan is a handful of
 * comparisons; a binary search here would be arithmetic nobody can check
 * against a bug nobody has.
 */
export function clubRunAtMile(
  timeline: readonly ClubRun[],
  mile: number,
): ClubRun | null {
  if (!Number.isFinite(mile)) return null
  for (let i = 0; i < timeline.length; i += 1) {
    const run = timeline[i]
    if (mile < run.startMile) return null
    const last = i === timeline.length - 1
    if (mile < run.endMile || (last && mile === run.endMile)) return run
  }
  return null
}

/** Who maintains the trail at a mile, or null where the source cannot say. */
export function clubAtMile(
  timeline: readonly ClubRun[],
  mile: number,
): ClubSection | null {
  return clubRunAtMile(timeline, mile)?.club ?? null
}

/**
 * The miles where one run gives way to the next.
 *
 * The corridor's two outer ends are NOT boundaries and are left out: Springer
 * and Katahdin are where the trail stops, not where responsibility changes
 * hands, and a tick drawn there would say something false about both.
 */
export function clubBoundaryMiles(timeline: readonly ClubRun[]): number[] {
  return timeline.slice(1).map((run) => run.startMile)
}

/** Total miles the fresh source cannot attribute, and how many runs they fall
 *  in - the two numbers the legend and the "not recorded" sheet both quote. */
export function unattributedTotal(sections: ClubSections): {
  miles: number
  runs: number
} {
  const miles = sections.unattributed.reduce(
    (sum, range) => sum + (range.endMile - range.startMile),
    0,
  )
  return { miles, runs: sections.unattributed.length }
}
