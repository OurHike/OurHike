// conditions/notices.json, read and checked (#1805).
//
// Its own module, imported by lib/useConditions.ts behind import(), for the
// launch budget's reason (lib/noticeSelection.ts's header has the numbers):
// the read waits for the first frame anyway, so its checking code need not
// be parsed before it. The fetch, the cache and the refusals are
// lib/publishedConditions.ts's `fetchPublished`, the same path every other
// conditions file takes (its `readPublished`, which also says whether an
// empty answer means the bucket serves no such file).
//
// ONLY ONCE A HIKE IS PLANNED (the maintainer's poll of
// 2026-10-05): the file was 24,966,662 bytes, 6,203,870 gzipped, on soak run
// 536, and every phone fetched it on each conditions refresh.
// `readPublishedNotices` downloads it only for a phone with a hike planned;
// any other phone asks the bucket whether it serves the file, and no more.
//
// AND THE STATES' SHAPES BESIDE IT: conditions/notice_states.json,
// read here in the same breath and attached to each state-wide notice as its
// `state_areas`, so lib/plannedNotices.ts can ask whether a planned route is
// in one of its states. Here, behind the same import(), rather than one more
// file the conditions hook asks for: the hook is on the first frame's path,
// and this adds no launch byte. Its key is here too, for the same reason;
// pipeline/tests/test_published_key_contract.py reads this file for it.
//
// AND THE HAZARD AREAS AT LAUNCH, WHATEVER IS PLANNED (the
// maintainer's poll of 2026-10-05: "Their own small file, read at
// launch"): conditions/hazard_areas.json, the rows of notices.json that carry
// the hazard areas' `hazard`, written by pipeline/dbt's
// pub_conditions_hazard_areas. Fetching notices.json only for a plan left a
// phone with nothing planned
// without notices.json, and so without the hunting areas, shooting sites and
// burned areas the map draws from it. `fetchPublishedHazardAreas` reads this
// file, and lib/useConditions.ts calls it on every read, planned or not, as
// every phone read notices.json before it waited on a plan, on a promise of its own
// so that nothing about notices.json holds it back; its key is here for the
// reason the states' key is.
//
// AND EVERY CLUB CLOSURE AT LAUNCH, FOR THE MAP (the maintainer's polls of
// 2026-10-11: "Build the map file now", and the closure-map standard as drawn):
// conditions/trail_closures.json, the rows of notices.json that close a
// trail, each with the shape the map crosses it out as, or, for an area no
// mapped trail runs inside, shades it as. Read like the
// hazard areas, whatever is planned, by `fetchPublishedTrailClosures`; ATC's
// rows are not in it, because ATC's own band already draws them.

import {
  fetchPublished,
  PUBLISHED_NOTICES_KEY,
  readPublished,
  type ClosureShape,
  type NoticeHazard,
  type NoticeParkArea,
  type NoticePlace,
  type NoticeStateArea,
  type OrgNotice,
  type PublishedConditions,
  type PublishedRead,
  type PublishedReadOptions,
  type TrailClosure,
} from './publishedConditions'
import type { NoticeGeometryValue } from './noticeGeometry'
import { DATA_CONFIGURED, dataUrl } from './config'
import { MANIFEST_READ_TIMEOUT_MS } from './dataManifest'
import { ATC_SOURCE_KEY } from './notices'

/**
 * How long a planned hike's download of conditions/notices.json may take
 * before the copy this phone kept answers instead.
 *
 * @unvalidated - three times lib/dataManifest.ts's MANIFEST_READ_TIMEOUT_MS,
 * the 20 s this file's other two requests wait, for that constant's reason: a
 * request with no deadline hangs on a captive portal or one bar rather than
 * failing, and until it fails `fetchPublished` cannot reach the kept copy.
 * Three times, because this request carries a body: UA's file gzips to
 * 2,139,070 bytes (level 6, measured 2026-10-09), which 20 s would cut on any
 * link slower than 856 kbps, and a minute lets through above 285 kbps. Longer
 * lets a slow link bring a first copy; shorter shows a phone stuck on a
 * captive portal its kept copy sooner. What would settle it: timings of this
 * download at trailheads, which nothing records.
 */
export const NOTICES_DOWNLOAD_TIMEOUT_MS = 3 * MANIFEST_READ_TIMEOUT_MS

/**
 * A signal that aborts after `ms`, and the clear that stops its timer once
 * the request is over. Not `AbortSignal.timeout()`: Safari 16 is the first
 * with it (MDN's compatibility table), and the iOS shell deploys to iOS 15
 * (client/ios/App/App.xcodeproj's IPHONEOS_DEPLOYMENT_TARGET), where calling
 * it throws.
 */
function deadline(
  ms: number,
  cancel?: AbortSignal,
): { signal: AbortSignal; clear: () => void } {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), ms)
  // `cancel` is the caller giving up (#1870): the same abort as the timer,
  // reached early. Listened to by hand because AbortSignal.any() is newer
  // than the Safari 16 floor the comment above already rules out.
  const giveUp = () => controller.abort()
  if (cancel?.aborted) giveUp()
  else cancel?.addEventListener('abort', giveUp, { once: true })
  return {
    signal: controller.signal,
    clear: () => {
      clearTimeout(timer)
      cancel?.removeEventListener('abort', giveUp)
    },
  }
}

/** The shapes of the states a state-wide notice names: written
 *  by pipeline/dbt's pub_conditions_notice_states, on the dbt path only, so
 *  a bucket without it serves a 404 and no state-wide notice shows - as
 *  before state shapes existed. */
export const PUBLISHED_NOTICE_STATES_KEY = 'conditions/notice_states.json'

/** The hazard notices in a file of their own: on the
 *  dbt path only, so a bucket without it (production until the cutover)
 *  serves a 404, and the map draws the areas from notices.json where that
 *  file has reached this phone, as it did before this file existed. */
export const PUBLISHED_HAZARD_AREAS_KEY = 'conditions/hazard_areas.json'

/** Every club closure the map crosses out (the maintainer's closure-map standard, 2026-10-11),
 *  rewritten hourly. On the dbt path only, like the two keys above, so a
 *  bucket without it serves a 404 and the map draws no club closure, as
 *  before this file existed. */
export const PUBLISHED_TRAIL_CLOSURES_KEY = 'conditions/trail_closures.json'

const HAZARDS: ReadonlySet<string> = new Set(['hunting', 'shooting', 'burned_area'])

const STATE_CODE = /^[A-Z]{2}$/

function textOrNull(value: unknown): string | null {
  return typeof value === 'string' && value !== '' ? value : null
}

/**
 * A real ISO day ("2026-10-01"), or null: `current_until` as
 * lib/noticeCurrency.ts can compare it. A day no calendar has, such as
 * "2026-04-31", which V8 rolls over to May 1, is null too.
 *
 * Restated rather than imported from lib/noticeCurrency.ts (whose `isIsoDay`
 * is the same three lines), for validPlace's reason below: that module rides
 * in the chunk the panel and the sheets share, and importing it here would
 * tie this lazy chunk to that one, and the eager entry's preload map to both.
 */
function isoDayOrNull(value: unknown): string | null {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const at = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(at.getTime()) && at.toISOString().slice(0, 10) === value
    ? value
    : null
}

/**
 * Category values that stand for no category, compared whole after trimming
 * and ignoring case, never as a part of a longer value.
 *
 * The panel shows a notice's category under its title, so a source's blank
 * spelled as a word read as a category it chose. Reviewed against soak run
 * 536's file on 2026-10-05: Midpen's preserve-access layer sends "None" (2
 * rows) and Santa Clara County Parks' closed areas send "na" (4 rows). "n/a"
 * and "null" are in no row there, and are listed as the same blank spelled
 * the other usual ways. NOT "unknown": it is one of USFS's recreation-site
 * `openstatus` values, the Forest Service's own status for a site, as
 * "unreachable" and "not cleared" are, and the panel shows it as sent.
 */
const NO_CATEGORY: ReadonlySet<string> = new Set(['none', 'na', 'n/a', 'null'])

function categoryOrNull(value: unknown): string | null {
  const text = textOrNull(value)
  return text !== null && NO_CATEGORY.has(text.trim().toLowerCase()) ? null : text
}

/**
 * The source's page as an absolute http or https URL, or null.
 *
 * Stricter than lib/safeLink.ts's `isSafeLink`, which every row's link still
 * passes at the sink: that one resolves a relative string against the page,
 * so a sentence reads as a path on OurHike's own origin. Soak run 536 carried
 * one on all 111 nysdec_hab_reports rows ("Learn how to Know it, Avoid it,
 * Report it at https://www.dec.ny.gov/…"), and the planned-hike row linked
 * "Read NYS DEC's notice" to OurHike itself. A URL inside the prose is not
 * pulled out: the link is the source's own field as it came, or none.
 */
function pageUrlOrNull(value: unknown): string | null {
  if (typeof value !== 'string') return null
  try {
    const { protocol } = new URL(value)
    return protocol === 'http:' || protocol === 'https:' ? value : null
  } catch {
    return null
  }
}

/** The park areas a reviewed park term maps to, or null for none: absent, empty, or
 *  any one unreadable. All or nothing, because the areas narrow which hikes
 *  are shown the notice, and a list missing one park would hide it from a
 *  hike in that park; with none it shows as an unmapped notice does. */
function validParkAreas(value: unknown): NoticeParkArea[] | null {
  if (!Array.isArray(value) || value.length === 0) return null
  const areas: NoticeParkArea[] = []
  for (const item of value) {
    if (typeof item !== 'object' || item === null) return null
    const row = item as Record<string, unknown>
    const box = row.bbox
    if (
      typeof row.place_id !== 'string' ||
      !Array.isArray(box) ||
      box.length !== 4 ||
      !box.every((n) => typeof n === 'number' && Number.isFinite(n))
    ) {
      return null
    }
    const [west, south, east, north] = box as number[]
    if (!(west < east && south < north)) return null
    areas.push({
      place_id: row.place_id,
      name: typeof row.name === 'string' ? row.name : row.place_id,
      bbox: [west, south, east, north],
    })
  }
  return areas
}

/** A place this build can read, or `unplaced` - a notice nobody can place is
 *  still one a hiker is told about (ORG_NOTICES.md §3). A geometry with no
 *  coordinate this build can read is kept as it came: lib/plannedNotices.ts's
 *  `noticeTouches` reads it as unplaced, and lib/hazardAreas.ts draws no area
 *  for it. The check lives there and not here because this module is its own
 *  lazy chunk: importing lib/noticeGeometry.ts here split that module into a
 *  chunk of its own, whose name the eager entry then carried in its preload
 *  map, 45 bytes compressed over the launch budget (preview build of
 *  f608fe42, 2026-10-05). */
function validPlace(value: unknown): NoticePlace {
  if (typeof value !== 'object' || value === null) return { kind: 'unplaced' }
  const place = value as Record<string, unknown>
  if (
    place.kind === 'at_miles' &&
    typeof place.start === 'number' &&
    typeof place.end === 'number' &&
    Number.isFinite(place.start) &&
    Number.isFinite(place.end)
  ) {
    return { kind: 'at_miles', start: place.start, end: place.end }
  }
  if (place.kind === 'org_terms' && Array.isArray(place.terms)) {
    const terms = place.terms.filter((term): term is string => typeof term === 'string')
    const areas = validParkAreas(place.areas)
    return areas === null
      ? { kind: 'org_terms', terms }
      : { kind: 'org_terms', terms, areas }
  }
  if (
    place.kind === 'geometry' &&
    typeof place.geometry === 'object' &&
    place.geometry !== null &&
    typeof (place.geometry as { type?: unknown }).type === 'string'
  ) {
    return { kind: 'geometry', geometry: place.geometry as NoticeGeometryValue }
  }
  return { kind: 'unplaced' }
}

/** A state-wide notice's `states`: the two-letter codes a row carries, or nothing -
 *  an unreadable code is left out, and a row left with none is an ordinary
 *  unplaced notice. */
function validStates(value: unknown): { states?: string[] } {
  if (!Array.isArray(value)) return {}
  const states = value.filter(
    (code): code is string => typeof code === 'string' && STATE_CODE.test(code),
  )
  return states.length > 0 ? { states } : {}
}

/** One conditions/notice_states.json state, or null for one this build
 *  cannot use: no code, no positive margin, or a shape with no polygon. */
export function validStateArea(value: unknown): NoticeStateArea | null {
  if (typeof value !== 'object' || value === null) return null
  const row = value as Record<string, unknown>
  if (typeof row.state !== 'string' || !STATE_CODE.test(row.state)) return null
  const margin = row.edge_margin_m
  if (typeof margin !== 'number' || !Number.isFinite(margin) || margin <= 0) return null
  const geometry = row.geometry as { type?: unknown } | null
  if (
    typeof geometry !== 'object' ||
    geometry === null ||
    (geometry.type !== 'Polygon' && geometry.type !== 'MultiPolygon')
  ) {
    return null
  }
  return {
    state: row.state,
    name: typeof row.name === 'string' && row.name !== '' ? row.name : row.state,
    edge_margin_m: margin,
    geometry: geometry as NoticeGeometryValue,
  }
}

/** Each state-wide notice with the shapes of its states this phone holds,
 *  as `state_areas`; a notice none of whose states has a shape is left as
 *  it came. */
export function withStateAreas(
  notices: OrgNotice[],
  areas: readonly NoticeStateArea[],
): OrgNotice[] {
  if (areas.length === 0) return notices
  const byState = new Map(areas.map((area) => [area.state, area]))
  return notices.map((notice) => {
    const found = (notice.states ?? []).flatMap((state) => byState.get(state) ?? [])
    return found.length > 0 ? { ...notice, state_areas: found } : notice
  })
}

/**
 * One conditions/notices.json row, read defensively, or null for one with no
 * id or no source - the two things every surface keys on.
 *
 * Everything else repairs to its honest empty value rather than costing the
 * row: an unreadable place is `unplaced`, an unknown hazard is none, a
 * missing title is '' (the list then names the organization instead), and a
 * missing date is null. One malformed field must not take a closure off a
 * phone.
 */
export function validNotice(value: unknown): OrgNotice | null {
  if (typeof value !== 'object' || value === null) return null
  const row = value as Record<string, unknown>
  if (typeof row.notice_id !== 'string' || row.notice_id === '') return null
  if (typeof row.source_key !== 'string' || row.source_key === '') return null
  return {
    notice_id: row.notice_id,
    source_key: row.source_key,
    title: typeof row.title === 'string' ? row.title : '',
    category: categoryOrNull(row.category),
    locality: typeof row.locality === 'string' ? row.locality : '',
    place: validPlace(row.place),
    obstructs_trail: row.obstructs_trail === true,
    updated_at: textOrNull(row.updated_at),
    source_url: pageUrlOrNull(row.source_url),
    review_state: row.review_state === 'reviewed' ? 'reviewed' : 'unreviewed',
    ...(typeof row.club === 'string' ? { club: row.club } : {}),
    provider: textOrNull(row.provider),
    steward_kind:
      row.steward_kind === 'club' || row.steward_kind === 'agency'
        ? row.steward_kind
        : null,
    ...validStates(row.states),
    hazard:
      typeof row.hazard === 'string' && HAZARDS.has(row.hazard)
        ? (row.hazard as NoticeHazard)
        : null,
    starts_on: textOrNull(row.starts_on),
    ends_on: textOrNull(row.ends_on),
    // Absent stays absent: a file from before the field makes no claim, and
    // lib/noticeCurrency.ts reads that as current. Present, a value that is
    // not a real ISO day is no date, which never reads as current - absent
    // means unknown, never "still fine".
    ...('current_until' in row ? { current_until: isoDayOrNull(row.current_until) } : {}),
    // Only a literal true: anything else is no claim that the land stands closed.
    ...(row.standing === true ? { standing: true } : {}),
    ...(typeof row.issuer === 'string' && row.issuer.trim() !== ''
      ? { issuer: row.issuer.trim() }
      : {}),
    checked_at: textOrNull(row.checked_at),
    first_seen_at: textOrNull(row.first_seen_at),
    changed_at: textOrNull(row.changed_at),
    carried_since: textOrNull(row.carried_since),
  }
}

/**
 * Every club's notices (#1805), or null if there isn't a
 * usable file.
 *
 * Null is the ordinary state on a bucket the exporters still publish: no
 * exporter writes this file, so it 404s, and lib/useConditions.ts keeps
 * reading ATC's and NYNJTC's own files. Offline it is the copy this phone
 * kept (#447 — The closures baseline is unavailable in exactly the place a
 * hiker is: offline), if it kept one: the last file that arrived whole, up to
 * lib/conditionsCache.ts's ceiling, dated by its own `generated_at` like
 * every file here. A phone that never downloaded it, such as a first run
 * with no signal, holds none and reads null.
 */
export async function fetchPublishedNotices(
  signal?: AbortSignal,
  options?: PublishedReadOptions,
): Promise<PublishedConditions<OrgNotice> | null> {
  return (await readNotices(signal, options)).published
}

/** `fetchPublishedNotices`, with lib/publishedConditions.ts's `notServed`
 *  for notices.json itself (the states' file has no say in it). */
async function readNotices(
  signal?: AbortSignal,
  options?: PublishedReadOptions,
): Promise<PublishedRead<OrgNotice>> {
  const [read, states] = await Promise.all([
    readPublished<unknown>(PUBLISHED_NOTICES_KEY, 'notices', signal, options),
    fetchPublished<unknown>(PUBLISHED_NOTICE_STATES_KEY, 'states', signal, options),
  ])
  const { published } = read
  if (published === null) return { published: null, notServed: read.notServed }
  const items: OrgNotice[] = []
  for (const row of published.items) {
    const notice = validNotice(row)
    if (notice !== null) items.push(notice)
  }
  const areas = (states?.items ?? []).flatMap((row) => validStateArea(row) ?? [])
  return {
    published: { ...published, items: withStateAreas(items, areas) },
    notServed: false,
  }
}

/**
 * conditions/hazard_areas.json's notices, or null if there
 * isn't a usable file - read by the same row reader as notices.json, which
 * the pipeline writes the same rows for, and holding only rows that carry a
 * `hazard` this build knows: a row that does not is no area to draw.
 *
 * Null on a bucket without the file, which on a 404 or in a dead spot is the
 * copy this phone kept (#447 — The closures baseline is unavailable in
 * exactly the place a hiker is: offline) if it kept one, as every file here:
 * the caller reads null as "no answer", never as "no hazard area".
 *
 * Within MANIFEST_READ_TIMEOUT_MS, for NOTICES_DOWNLOAD_TIMEOUT_MS's reason:
 * a request that hangs holds the kept copy back. UA's file gzips to 235,202
 * bytes (level 6, measured 2026-10-09), which 20 s lets through above
 * 94 kbps.
 */
export async function fetchPublishedHazardAreas(
  options?: PublishedReadOptions,
): Promise<PublishedConditions<OrgNotice> | null> {
  const { signal, clear } = deadline(MANIFEST_READ_TIMEOUT_MS, options?.cancel)
  const published = await fetchPublished<unknown>(
    PUBLISHED_HAZARD_AREAS_KEY,
    'notices',
    signal,
    options,
  ).finally(clear)
  if (published === null) return null
  const items: OrgNotice[] = []
  for (const row of published.items) {
    const notice = validNotice(row)
    if (notice !== null && notice.hazard !== null) items.push(notice)
  }
  return { ...published, items }
}

/** Whether `value` is a [lon, lat] this map can draw: two finite numbers on
 *  the globe, a third (an elevation) allowed and ignored. */
function isLonLat(value: unknown): boolean {
  if (!Array.isArray(value) || value.length < 2) return false
  const [lon, lat] = value as unknown[]
  return (
    typeof lon === 'number' &&
    typeof lat === 'number' &&
    Math.abs(lon) <= 180 &&
    Math.abs(lat) <= 90
  )
}

/** A line of two or more drawable positions. */
function isLine(value: unknown): boolean {
  return Array.isArray(value) && value.length >= 2 && value.every(isLonLat)
}

/** A polygon's rings: an outline and its holes, each a closed ring of four
 *  or more drawable positions (RFC 7946 §3.1.6). */
function isPolygon(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((ring) => Array.isArray(ring) && ring.length >= 4 && ring.every(isLonLat))
  )
}

/** Every member of a Multi* geometry's coordinates passes `part`. */
function everyPart(coordinates: unknown, part: (value: unknown) => boolean): boolean {
  return Array.isArray(coordinates) && coordinates.length > 0 && coordinates.every(part)
}

/**
 * Whether a closure's geometry is the one its shape is drawn from, with every
 * coordinate drawable: a LineString or MultiLineString for a `line` (the
 * notice's own line) and an `area` (the trail stretches the pipeline cut
 * inside it), a Point or MultiPoint for a `point`, as pipeline/dbt's
 * pub_conditions_trail_closures writes one (the map crosses each of its
 * points), and a Polygon or MultiPolygon for a `shade` (the area itself). Checked whole here because every closure shares one GeoJSON
 * source on the map (map/clubClosureLayers.ts), and one row's unreadable
 * coordinates must not cost the others their marks.
 */
function drawable(shape: ClosureShape, geometry: NoticeGeometryValue): boolean {
  const { type, coordinates } = geometry
  if (shape === 'point') {
    if (type === 'Point') return isLonLat(coordinates)
    return type === 'MultiPoint' && everyPart(coordinates, isLonLat)
  }
  if (shape === 'shade') {
    if (type === 'Polygon') return isPolygon(coordinates)
    return type === 'MultiPolygon' && everyPart(coordinates, isPolygon)
  }
  if (type === 'LineString') return isLine(coordinates)
  return type === 'MultiLineString' && everyPart(coordinates, isLine)
}

const CLOSURE_SHAPES: ReadonlySet<string> = new Set(['line', 'area', 'point', 'shade'])

/**
 * One conditions/trail_closures.json row, or null for one the map cannot
 * draw as a closure. The row is a conditions/notices.json row read by
 * `validNotice`, so a field it repairs there is repaired the same way here;
 * then the map's own refusals, each a row the file's contract does not allow:
 *
 *  - no `shape`, or one that is not line, area, point or shade;
 *  - a place that is not a geometry, or not the one its shape is drawn from
 *    (`drawable`): an area row's polygon is refused, never crossed out along
 *    its edge, because its trails are what close, and a shade's line is
 *    refused, because a shade is the area itself;
 *  - `obstructs_trail` not true: a row that does not close the trail is no
 *    closure to draw, and a crossed-out trail that is open is the false
 *    alarm CLAUDE.md's "miss rather than cry wolf" rules out;
 *  - a `hazard`: the hazard areas are never drawn as closed
 *    (lib/hazardAreas.ts says why);
 *  - ATC's own rows, whose band map/atcUpdateLayers.ts already draws from
 *    ATC's own file: a second mark on the same stretch would open a second
 *    sheet.
 *
 * Whether it draws TODAY is not decided here: lib/noticeCurrency.ts's
 * `obstructsOn` holds a closure back until the day before its own start,
 * on the phone's own calendar (chrome/noticesPanel.tsx).
 */
export function validTrailClosure(value: unknown): TrailClosure | null {
  const notice = validNotice(value)
  if (notice === null) return null
  const shape = (value as Record<string, unknown>).shape
  if (typeof shape !== 'string' || !CLOSURE_SHAPES.has(shape)) return null
  const { place } = notice
  if (place.kind !== 'geometry' || !drawable(shape as ClosureShape, place.geometry)) {
    return null
  }
  if (!notice.obstructs_trail || notice.hazard !== null) return null
  if (notice.source_key === ATC_SOURCE_KEY) return null
  return { ...notice, place, shape: shape as ClosureShape }
}

/** The shapes an area closure is drawn as: its trails crossed out, or itself shaded. */
const AREA_SHAPES: ReadonlySet<unknown> = new Set(['area', 'shade'])

/**
 * conditions/trail_closures.json as it arrived, with the area closures it
 * could not draw this hour carried over from the copy this phone kept
 * (the maintainer's poll of 2026-10-15, "Now, in this
 * PR"). pipeline/dbt's pub_conditions_trail_closures lists in `uncut_areas`
 * every area closure standing this hour that its cut has no row for: all of
 * them in an hour with no trail lines to cut against (`areas_cut` false),
 * which on production is every hour until its lines are prepared. Without
 * this, a phone that refreshed in such an hour kept a file with no area in
 * it and drew none until it next connected.
 *
 * For each id listed, the area or shade row the kept copy holds for it is
 * added after the file's own rows, as it was, unless the file already holds
 * a row of that id. An id the kept copy has no area row for adds nothing:
 * there is no drawing to keep, and none is guessed. A closure lifted since
 * the kept copy is listed nowhere, so it is not carried and leaves the map
 * with the file that leaves it out, as on any hour. A file with no
 * `uncut_areas` (one written before it, or a cut hour with every area drawn)
 * is kept exactly as it arrived.
 *
 * What a carried row shows is the kept copy's: its trail stretches and its
 * words as of the hour they were cut, under the newer file's `generated_at`.
 */
export function keepUncutAreas(
  arrived: Record<string, unknown>,
  kept: Record<string, unknown> | null,
): Record<string, unknown> {
  const { closures, uncut_areas: uncut } = arrived
  if (kept === null || !Array.isArray(closures) || !Array.isArray(uncut)) return arrived
  if (!Array.isArray(kept.closures)) return arrived
  const listed = new Set(uncut.filter((id): id is string => typeof id === 'string'))
  const present = new Set(
    closures.map((row) => (row as Record<string, unknown> | null)?.notice_id),
  )
  const carried = kept.closures.filter((row: unknown) => {
    if (typeof row !== 'object' || row === null) return false
    const { notice_id: id, shape } = row as Record<string, unknown>
    return (
      typeof id === 'string' &&
      listed.has(id) &&
      !present.has(id) &&
      AREA_SHAPES.has(shape)
    )
  })
  if (carried.length === 0) return arrived
  return { ...arrived, closures: [...closures, ...carried] }
}

/**
 * conditions/trail_closures.json's closures (the maintainer's closure-map standard), or null if
 * there isn't a usable file. Every row the map cannot draw is refused one at
 * a time (`validTrailClosure`), never the file. An area closure the file
 * could not draw this hour is the one the kept copy drew (`keepUncutAreas`).
 *
 * Null on a bucket without the file, which on a 404 or in a dead spot is the
 * copy this phone kept (#447 — The closures baseline is unavailable in
 * exactly the place a hiker is: offline) if it kept one, as every file here:
 * the caller reads null as "no answer", never as "no closure".
 *
 * Within MANIFEST_READ_TIMEOUT_MS, as the hazard areas are. UA's first
 * published file, of 2026-10-14 18:15 UTC, is 3,165,161 bytes and 633,700 on
 * the wire (its latest.json); the 156 shaded areas add 32,244
 * gzipped at level 6 (Measured that evening on the areas' own outlines,
 * pipeline/dbt's pub_conditions_trail_closures says how), about 665,900 in
 * all, which 20 s lets through above about 266 kbps. Slower than that, a
 * phone shows the copy it kept. @unvalidated: whether 20 s is right for this
 * file, for MANIFEST_READ_TIMEOUT_MS's reason; what would settle it is
 * timings of this read at trailheads, which nothing records.
 */
export async function fetchPublishedTrailClosures(
  options?: PublishedReadOptions,
): Promise<PublishedConditions<TrailClosure> | null> {
  const { signal, clear } = deadline(MANIFEST_READ_TIMEOUT_MS, options?.cancel)
  const { published } = await readPublished<unknown>(
    PUBLISHED_TRAIL_CLOSURES_KEY,
    'closures',
    signal,
    options,
    keepUncutAreas,
  ).finally(clear)
  if (published === null) return null
  const items: TrailClosure[] = []
  for (const row of published.items) {
    const closure = validTrailClosure(row)
    if (closure !== null) items.push(closure)
  }
  return { ...published, items }
}

/**
 * Whether the bucket serves conditions/notices.json, asked with a HEAD
 * request, so no byte of the file is downloaded. False for a
 * 404, a dead spot or no bucket, which the caller reads as "not said", never
 * as "not served".
 *
 * A HEAD and not the manifest, though `latest.json` lists the file: this
 * build reads the pinned release's manifest (lib/dataRelease.ts's
 * RELEASE_MANIFEST_PATH), and that one lists no `conditions/` key, because
 * those files are rewritten in place outside every release folder (measured
 * 2026-10-05 on UA: 0 of releases/2026-10-03-2/manifest.json's 4,436
 * entries). Reading the root `latest.json` instead would cost 245,744 bytes
 * on the wire each time (measured the same day), against about 800 bytes of
 * headers for this, and the bucket answers HEAD with the same CORS headers
 * as GET (measured on data.ourhike.org from https://ourhike.org: 200 on
 * UA's file, 404 on production's, both with access-control-allow-origin).
 *
 * Within MANIFEST_READ_TIMEOUT_MS, for that constant's reason: a HEAD that
 * never answers is not said.
 */
export async function noticesListed(): Promise<boolean> {
  if (!DATA_CONFIGURED) return false
  const { signal, clear } = deadline(MANIFEST_READ_TIMEOUT_MS)
  try {
    return (await fetch(dataUrl(PUBLISHED_NOTICES_KEY), { method: 'HEAD', signal })).ok
  } catch {
    return false
  } finally {
    clear()
  }
}

/**
 * conditions/notices.json as a phone reads it: downloaded
 * only while `hikePlanned`, within NOTICES_DOWNLOAD_TIMEOUT_MS. With nothing
 * planned it is the copy this phone kept, read with no request
 * (lib/conditionsCache.ts keeps one only under its size ceiling), and
 * `listed` is the bucket's answer to a HEAD, asked only with signal. With a
 * hike planned, a file that arrives says it is listed too.
 *
 * `missing` is true only for a planned hike's read that ended with no copy
 * on this phone, for a reason a connection can change: no signal, so no
 * request (a first run, or a file over lib/conditionsCache.ts's ceiling
 * relaunched offline); a download that failed, answered an error other than
 * 404, brought bytes this build cannot read, or passed
 * NOTICES_DOWNLOAD_TIMEOUT_MS. chrome/noticesPanel.tsx says so to the hiker
 * (option A of the maintainer's poll of 2026-10-09). False on a 404 or with
 * no bucket configured: there is no file for a connection to bring, as on
 * the exporters' bucket, where the panel stays as it was. False with nothing
 * planned, which downloads nothing. And no answer at all until the read
 * settles: a download in flight is neither.
 *
 * conditions/hazard_areas.json is not read here. lib/useConditions.ts reads
 * it beside this, with `fetchPublishedHazardAreas`, on a promise of its own:
 * neither this download nor the HEAD may hold the hazard areas back.
 */
export async function readPublishedNotices(
  hikePlanned: boolean,
  options: PublishedReadOptions,
): Promise<{
  published: PublishedConditions<OrgNotice> | null
  listed: boolean
  missing: boolean
}> {
  if (hikePlanned) {
    const { signal, clear } = deadline(NOTICES_DOWNLOAD_TIMEOUT_MS, options.cancel)
    const { published, notServed } = await readNotices(signal, options).finally(clear)
    return {
      published,
      listed: published !== null,
      missing: published === null && !notServed,
    }
  }
  const [published, listed] = await Promise.all([
    fetchPublishedNotices(undefined, { online: false }),
    options.online === false ? false : noticesListed(),
  ])
  return { published, listed, missing: false }
}
