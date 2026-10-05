// conditions/notices.json, read and checked (#1805, decision 53 phase D).
//
// Its own module, imported by lib/useConditions.ts behind import(), for the
// launch budget's reason (lib/noticeSelection.ts's header has the numbers):
// the read waits for the first frame anyway, so its checking code need not
// be parsed before it. The fetch, the cache and the refusals are
// lib/publishedConditions.ts's `fetchPublished`, the same path every other
// conditions file takes.
//
// AND THE STATES' SHAPES BESIDE IT (decision 76): conditions/notice_states.json,
// read here in the same breath and attached to each state-wide notice as its
// `state_areas`, so lib/plannedNotices.ts can ask whether a planned route is
// in one of its states. Here, behind the same import(), rather than one more
// file the conditions hook asks for: the hook is on the first frame's path,
// and this adds no launch byte. Its key is here too, for the same reason;
// pipeline/tests/test_published_key_contract.py reads this file for it.

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

/** The shapes of the states a state-wide notice names (decision 76): written
 *  by pipeline/dbt's pub_conditions_notice_states, on the dbt path only, so
 *  a bucket without it serves a 404 and no state-wide notice shows - as
 *  decision 68 left them. */
export const PUBLISHED_NOTICE_STATES_KEY = 'conditions/notice_states.json'

const HAZARDS: ReadonlySet<string> = new Set(['hunting', 'shooting', 'burned_area'])

const STATE_CODE = /^[A-Z]{2}$/

function textOrNull(value: unknown): string | null {
  return typeof value === 'string' && value !== '' ? value : null
}

/** A place this build can read, or `unplaced` - a notice nobody can place is
 *  still one a hiker is told about (ORG_NOTICES.md §3). */
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
    category: textOrNull(row.category),
    locality: typeof row.locality === 'string' ? row.locality : '',
    place: validPlace(row.place),
    obstructs_trail: row.obstructs_trail === true,
    updated_at: textOrNull(row.updated_at),
    source_url: textOrNull(row.source_url),
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
 * kept (#447), dated by its own `generated_at`, like every file here.
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
