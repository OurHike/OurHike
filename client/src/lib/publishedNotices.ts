// conditions/notices.json, read and checked (#1805, decision 53 phase D).
//
// Its own module, imported by lib/useConditions.ts behind import(), for the
// launch budget's reason (lib/noticeSelection.ts's header has the numbers):
// the read waits for the first frame anyway, so its checking code need not
// be parsed before it. The fetch, the cache and the refusals are
// lib/publishedConditions.ts's `fetchPublished`, the same path every other
// conditions file takes (its `readPublished`, which also says whether an
// empty answer means the bucket serves no such file).
//
// ONLY ONCE A HIKE IS PLANNED (decision 77, the maintainer's poll of
// 2026-10-05): the file was 24,966,662 bytes, 6,203,870 gzipped, on soak run
// 536, and every phone fetched it on each conditions refresh.
// `readPublishedNotices` downloads it only for a phone with a hike planned;
// any other phone asks the bucket whether it serves the file, and no more.
//
// AND THE STATES' SHAPES BESIDE IT (decision 76): conditions/notice_states.json,
// read here in the same breath and attached to each state-wide notice as its
// `state_areas`, so lib/plannedNotices.ts can ask whether a planned route is
// in one of its states. Here, behind the same import(), rather than one more
// file the conditions hook asks for: the hook is on the first frame's path,
// and this adds no launch byte. Its key is here too, for the same reason;
// pipeline/tests/test_published_key_contract.py reads this file for it.
//
// AND THE HAZARD AREAS AT LAUNCH, WHATEVER IS PLANNED (decision 84, the
// maintainer's poll of 2026-10-05, Q5: "Their own small file, read at
// launch"): conditions/hazard_areas.json, the rows of notices.json that carry
// decision 67's `hazard`, written by pipeline/dbt's
// pub_conditions_hazard_areas. Decision 77 left a phone with nothing planned
// without notices.json, and so without the hunting areas, shooting sites and
// burned areas the map draws from it. `fetchPublishedHazardAreas` reads this
// file, and lib/useConditions.ts calls it on every read, planned or not, as
// every phone read notices.json before decision 77, on a promise of its own
// so that nothing about notices.json holds it back; its key is here for the
// reason the states' key is.

import {
  fetchPublished,
  PUBLISHED_NOTICES_KEY,
  readPublished,
  type NoticeHazard,
  type NoticeMatchedPage,
  type NoticePlace,
  type NoticeStateArea,
  type OrgNotice,
  type PublishedConditions,
  type PublishedRead,
  type PublishedReadOptions,
} from './publishedConditions'
import type { NoticeGeometryValue } from './noticeGeometry'
import { DATA_CONFIGURED, dataUrl } from './config'
import { MANIFEST_READ_TIMEOUT_MS } from './dataManifest'

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
function deadline(ms: number): { signal: AbortSignal; clear: () => void } {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), ms)
  return { signal: controller.signal, clear: () => clearTimeout(timer) }
}

/** The shapes of the states a state-wide notice names (decision 76): written
 *  by pipeline/dbt's pub_conditions_notice_states, on the dbt path only, so
 *  a bucket without it serves a 404 and no state-wide notice shows - as
 *  decision 68 left them. */
export const PUBLISHED_NOTICE_STATES_KEY = 'conditions/notice_states.json'

/** Decision 67's hazard notices in a file of their own (decision 84): on the
 *  dbt path only, so a bucket without it (production until the cutover)
 *  serves a 404, and the map draws the areas from notices.json where that
 *  file has reached this phone, as it did before this file existed. */
export const PUBLISHED_HAZARD_AREAS_KEY = 'conditions/hazard_areas.json'

const HAZARDS: ReadonlySet<string> = new Set(['hunting', 'shooting', 'burned_area'])

const STATE_CODE = /^[A-Z]{2}$/

function textOrNull(value: unknown): string | null {
  return typeof value === 'string' && value !== '' ? value : null
}

/**
 * Category values that stand for no category, compared whole after trimming
 * and ignoring case, never as a part of a longer value.
 *
 * Decision 78 shows a notice's category under its title, so a source's blank
 * spelled as a word read as a category it chose. Reviewed against soak run
 * 536's file on 2026-10-05: Midpen's preserve-access layer sends "None" (2
 * rows) and Santa Clara County Parks' closed areas send "na" (4 rows). "n/a"
 * and "null" are in no row there, and are listed as the same blank spelled
 * the other usual ways. NOT "unknown": it is one of USFS's recreation-site
 * `openstatus` values, the Forest Service's own status for a site, as
 * "unreachable" and "not cleared" are, and decision 78 shows it as sent.
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
    return {
      kind: 'org_terms',
      terms: place.terms.filter((term): term is string => typeof term === 'string'),
    }
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

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/

/**
 * Decision 128's `matched_page`, or nothing: the page's link as an absolute
 * http or https URL (pageUrlOrNull's rule, so a sentence never links to
 * OurHike itself), and its day where it reads as an ISO day. A link that
 * fails leaves the row without it, so the row reads as any other notice
 * rather than claiming a page it cannot open.
 */
function validMatchedPage(value: unknown): { matched_page?: NoticeMatchedPage } {
  if (typeof value !== 'object' || value === null) return {}
  const page = value as Record<string, unknown>
  const url = pageUrlOrNull(page.url)
  if (url === null) return {}
  const day =
    typeof page.updated_on === 'string' && ISO_DAY.test(page.updated_on)
      ? page.updated_on
      : null
  return { matched_page: { url, updated_on: day } }
}

/** Decision 76's `states`: the two-letter codes a row carries, or nothing -
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
    checked_at: textOrNull(row.checked_at),
    first_seen_at: textOrNull(row.first_seen_at),
    changed_at: textOrNull(row.changed_at),
    carried_since: textOrNull(row.carried_since),
    ...validMatchedPage(row.matched_page),
  }
}

/**
 * Every club's notices (#1805, decision 53 phase D), or null if there isn't a
 * usable file.
 *
 * Null is the ordinary state on a bucket the exporters still publish: no
 * exporter writes this file, so it 404s, and lib/useConditions.ts keeps
 * reading ATC's and NYNJTC's own files. Offline it is the copy this phone
 * kept (#447), if it kept one: the last file that arrived whole, up to
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
 * conditions/hazard_areas.json's notices (decision 84), or null if there
 * isn't a usable file - read by the same row reader as notices.json, which
 * the pipeline writes the same rows for, and holding only rows that carry a
 * `hazard` this build knows: a row that does not is no area to draw.
 *
 * Null on a bucket without the file, which on a 404 or in a dead spot is the
 * copy this phone kept (#447) if it kept one, as every file here: the caller
 * reads null as "no answer", never as "no hazard area".
 *
 * Within MANIFEST_READ_TIMEOUT_MS, for NOTICES_DOWNLOAD_TIMEOUT_MS's reason:
 * a request that hangs holds the kept copy back. UA's file gzips to 235,202
 * bytes (level 6, measured 2026-10-09), which 20 s lets through above
 * 94 kbps.
 */
export async function fetchPublishedHazardAreas(
  options?: PublishedReadOptions,
): Promise<PublishedConditions<OrgNotice> | null> {
  const { signal, clear } = deadline(MANIFEST_READ_TIMEOUT_MS)
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

/**
 * Whether the bucket serves conditions/notices.json, asked with a HEAD
 * request, so no byte of the file is downloaded (decision 77). False for a
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
 * conditions/notices.json as decision 77 has a phone read it: downloaded
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
    const { signal, clear } = deadline(NOTICES_DOWNLOAD_TIMEOUT_MS)
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
