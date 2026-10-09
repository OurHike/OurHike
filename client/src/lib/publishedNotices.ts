// conditions/notices.json, read and checked (#1805, decision 53 phase D).
//
// Its own module, imported by lib/useConditions.ts behind import(), for the
// launch budget's reason (lib/noticeSelection.ts's header has the numbers):
// the read waits for the first frame anyway, so its checking code need not
// be parsed before it. The fetch, the cache and the refusals are
// lib/publishedConditions.ts's `fetchPublished`, the same path every other
// conditions file takes.
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
// burned areas the map draws from it. `readPublishedNotices` reads this file
// on every call, planned or not, as every phone read notices.json before
// decision 77; its key is here for the reason the states' key is.

import {
  fetchPublished,
  PUBLISHED_NOTICES_KEY,
  type NoticeHazard,
  type NoticePlace,
  type NoticeStateArea,
  type OrgNotice,
  type PublishedConditions,
  type PublishedReadOptions,
} from './publishedConditions'
import type { NoticeGeometryValue } from './noticeGeometry'
import { DATA_CONFIGURED, dataUrl } from './config'

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
  const [published, states] = await Promise.all([
    fetchPublished<unknown>(PUBLISHED_NOTICES_KEY, 'notices', signal, options),
    fetchPublished<unknown>(PUBLISHED_NOTICE_STATES_KEY, 'states', signal, options),
  ])
  if (published === null) return null
  const items: OrgNotice[] = []
  for (const row of published.items) {
    const notice = validNotice(row)
    if (notice !== null) items.push(notice)
  }
  const areas = (states?.items ?? []).flatMap((row) => validStateArea(row) ?? [])
  return { ...published, items: withStateAreas(items, areas) }
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
 */
export async function fetchPublishedHazardAreas(
  options?: PublishedReadOptions,
): Promise<PublishedConditions<OrgNotice> | null> {
  const published = await fetchPublished<unknown>(
    PUBLISHED_HAZARD_AREAS_KEY,
    'notices',
    undefined,
    options,
  )
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
 */
export async function noticesListed(): Promise<boolean> {
  if (!DATA_CONFIGURED) return false
  try {
    return (await fetch(dataUrl(PUBLISHED_NOTICES_KEY), { method: 'HEAD' })).ok
  } catch {
    return false
  }
}

/**
 * conditions/notices.json as decision 77 has a phone read it: downloaded
 * only while `hikePlanned`. With nothing planned it is the copy this phone
 * kept, read with no request (lib/conditionsCache.ts keeps one only under
 * its size ceiling), and `listed` is the bucket's answer to a HEAD, asked
 * only with signal. With a hike planned, a file that arrives says it is
 * listed too.
 *
 * `hazards` is conditions/hazard_areas.json (decision 84), read on every
 * call whether or not a hike is planned, with signal as `options` says.
 */
export async function readPublishedNotices(
  hikePlanned: boolean,
  options: PublishedReadOptions,
): Promise<{
  published: PublishedConditions<OrgNotice> | null
  listed: boolean
  hazards: PublishedConditions<OrgNotice> | null
}> {
  const [published, listed, hazards] = await Promise.all([
    fetchPublishedNotices(undefined, hikePlanned ? options : { online: false }),
    hikePlanned || options.online === false ? false : noticesListed(),
    fetchPublishedHazardAreas(options),
  ])
  return { published, listed: listed || (hikePlanned && published !== null), hazards }
}
