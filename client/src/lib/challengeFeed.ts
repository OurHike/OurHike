// Reading `challenges.json` into the shapes lib/challenges.ts declares: the
// validation, the kept copy and the fetch (#1780, features/CHALLENGES.md).
//
// A MODULE OF ITS OWN SO IT IS NOT EAGER. lib/useChallenges.ts loads it with
// import() from the effects that read the list, which run only once the
// launch is past its first frame (#1302). Before #1806 — main's eager
// JavaScript is 245,910 bytes against the 245,760 launch budget since the
// challenges merge, so every PR's preview build fails — this code sat in
// lib/challenges.ts and rode the shell's static imports in front of the
// first frame, where nothing calls it. Do not re-export it from
// lib/challenges.ts: a re-export is a static import, and would put it back.
//
// lib/challenges.ts's header says how the list reaches the phone and why one
// bad row never costs the list; that is this file's behaviour, written there
// beside the shapes it describes.

import type {
  Challenge,
  ChallengeItem,
  ChallengeMatch,
  ChallengePlace,
  ChallengeSection,
  MatchKind,
  RewardKind,
} from './challenges'
import { CHALLENGES_KEY, DATA_CONFIGURED, dataUrl } from './config'
import { recallPublished, rememberPublished } from './conditionsCache'

const MATCH_KINDS: readonly MatchKind[] = [
  'place',
  'places_all',
  'poi_type',
  'elevation_min_ft',
  'section_walked',
  'workday',
  'self_report',
]
const REWARD_KINDS: readonly RewardKind[] = ['patch', 'postcard', 'sticker', 'drawing']
const DATE = /^\d{4}-\d{2}-\d{2}$/

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null
}

function finite(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function day(value: unknown): string | null {
  return typeof value === 'string' && DATE.test(value) ? value : null
}

function parsePlace(value: unknown): ChallengePlace | null {
  if (!isRecord(value)) return null
  const poi = text(value.poi)
  const mile = finite(value.mile)
  const lat = finite(value.lat)
  const lon = finite(value.lon)
  if (poi === null || mile === null || lat === null || lon === null) return null
  return {
    poi,
    name: text(value.name) ?? poi,
    poiType: text(value.poi_type) ?? '',
    mile,
    lat,
    lon,
  }
}

function parseMatch(value: unknown): ChallengeMatch | null {
  if (!isRecord(value)) return null
  const kind = value.kind as MatchKind
  if (!MATCH_KINDS.includes(kind)) return null
  switch (kind) {
    case 'place':
    case 'places_all': {
      const raw = Array.isArray(value.places) ? value.places : []
      const places = raw.map(parsePlace)
      // All or nothing, the exporter's rule: a Triple Crown with one peak
      // unreadable is a different item, not a smaller one.
      if (places.length === 0 || places.some((place) => place === null)) return null
      if (kind === 'places_all' && places.length < 2) return null
      return {
        kind,
        radiusM: finite(value.radius_m) ?? 0,
        offTrail: value.off_trail === true,
        places: places as ChallengePlace[],
      }
    }
    case 'poi_type': {
      const type = text(value.type)
      return type === null
        ? null
        : {
            kind,
            type,
            radiusM: finite(value.radius_m) ?? 0,
            offTrail: value.off_trail === true,
          }
    }
    case 'elevation_min_ft': {
      const valueFt = finite(value.value)
      return valueFt === null || valueFt <= 0 ? null : { kind, valueFt }
    }
    case 'section_walked': {
      const fromMile = finite(value.from_mile)
      const toMile = finite(value.to_mile)
      const minFraction = finite(value.min_fraction)
      const trail = text(value.trail)
      if (fromMile === null || toMile === null || trail === null) return null
      if (minFraction === null || minFraction <= 0 || minFraction > 1) return null
      return {
        kind,
        trail,
        fromMile: Math.min(fromMile, toMile),
        toMile: Math.max(fromMile, toMile),
        fromName: text(value.from_name) ?? '',
        toName: text(value.to_name) ?? '',
        minFraction,
      }
    }
    case 'workday': {
      const trail = text(value.trail)
      return trail === null ? null : { kind, org: text(value.org), trail }
    }
    case 'self_report':
      return { kind }
  }
}

function parseItem(
  value: unknown,
  sectionIds: ReadonlySet<string>,
): ChallengeItem | null {
  if (!isRecord(value)) return null
  const id = text(value.id)
  const section = text(value.section)
  if (id === null || section === null || !sectionIds.has(section)) return null
  const match = parseMatch(value.match)
  if (match === null) return null
  let mystery: ChallengeItem['mystery'] = null
  if (isRecord(value.mystery)) {
    const number = finite(value.mystery.number)
    if (number === null || number < 1) return null
    mystery = { number, revealOn: day(value.mystery.reveal_on) }
  }
  const title = text(value.title)
  const sealedTitle = text(value.sealed_title)
  // An item with nothing to call it is only legitimate as a mystery.
  if (title === null && mystery === null) return null
  return {
    id,
    section,
    title,
    sealedTitle,
    note: text(value.note),
    noteBy: text(value.note_by),
    photo: httpsOnly(value.photo),
    match,
    mystery,
  }
}

function parseChallenge(value: unknown): Challenge | null {
  if (!isRecord(value)) return null
  const id = text(value.id)
  const org = text(value.org)
  const trail = text(value.trail)
  const name = text(value.name)
  if (id === null || org === null || trail === null || name === null) return null
  const status =
    value.status === 'published' ? 'published' : value.status === 'draft' ? 'draft' : null
  if (status === null) return null

  const sections: ChallengeSection[] = []
  for (const raw of Array.isArray(value.sections) ? value.sections : []) {
    if (!isRecord(raw)) continue
    const sectionId = text(raw.id)
    const title = text(raw.title)
    if (sectionId === null || title === null) continue
    sections.push({ id: sectionId, title, short: text(raw.short) ?? title })
  }
  const sectionIds = new Set(sections.map((section) => section.id))

  const seen = new Set<string>()
  const items: ChallengeItem[] = []
  for (const raw of Array.isArray(value.items) ? value.items : []) {
    const item = parseItem(raw, sectionIds)
    // A second row with the same id would take the first one's tags.
    if (item === null || seen.has(item.id)) continue
    seen.add(item.id)
    items.push(item)
  }
  if (items.length === 0) return null

  const window = isRecord(value.window) ? value.window : {}
  let finish: Challenge['finish'] = null
  if (isRecord(value.finish)) {
    const count = finite(value.finish.count)
    if (count === null || count < 1 || count > items.length) return null
    finish = { count, label: text(value.finish.label) }
  }
  let reward: Challenge['reward'] = null
  if (isRecord(value.reward)) {
    const kind = value.reward.kind as RewardKind
    const rulesUrl = text(value.reward.rules_url)
    if (REWARD_KINDS.includes(kind) && finish !== null) {
      reward = {
        kind,
        rulesUrl: rulesUrl !== null && rulesUrl.startsWith('https://') ? rulesUrl : null,
        art: httpsOnly(value.reward.art),
      }
    }
  }

  return {
    id,
    org,
    orgName: text(value.org_name) ?? org,
    orgShort: text(value.org_short) ?? org.toUpperCase(),
    orgDomain: text(value.org_domain),
    trail,
    name,
    status,
    summary: text(value.summary),
    window: { opens: day(window.opens), closes: day(window.closes) },
    finish,
    reward,
    takesEntries:
      value.takes_entries === true && reward !== null && status === 'published',
    photo: httpsOnly(value.photo),
    sections,
    items,
    reviewed: text(value.reviewed) ?? '',
  }
}

/** An https URL or nothing. A club's photo is a request from the hiker's
 *  phone to whoever hosts it; the pipeline refuses anything else, and this
 *  holds the line for a document that did not come through it. */
function httpsOnly(value: unknown): string | null {
  const url = text(value)
  return url !== null && url.startsWith('https://') ? url : null
}

/**
 * Parses `challenges.json`. Never throws, and never loses the whole list over
 * one bad row.
 */
export function parseChallenges(raw: unknown): Challenge[] {
  const list = isRecord(raw) ? raw.challenges : raw
  if (!Array.isArray(list)) return []
  const seen = new Set<string>()
  const out: Challenge[] = []
  for (const entry of list) {
    const challenge = parseChallenge(entry)
    if (challenge === null || seen.has(challenge.id)) continue
    seen.add(challenge.id)
    out.push(challenge)
  }
  return out
}

/** The last document that reached this phone, validated again, or null. */
export async function recallChallenges(): Promise<Challenge[] | null> {
  const cached = await recallPublished(CHALLENGES_KEY)
  return cached === null ? null : parseChallenges(cached.document)
}

/**
 * Ask the release, keep what it says, hand back the challenges - or null
 * when nothing usable came back, in which case the caller keeps what it had.
 *
 * A 404 is the ordinary answer for every release built before
 * export_challenges.py existed, and it must not clear the kept copy: a
 * release that stopped carrying the artifact is not evidence a club withdrew
 * its list.
 */
export async function fetchChallenges(signal?: AbortSignal): Promise<Challenge[] | null> {
  if (!DATA_CONFIGURED) return null
  try {
    const response = await fetch(dataUrl(CHALLENGES_KEY), { signal })
    if (!response.ok) return null
    const document: unknown = await response.json()
    // A document with no list at all - `{}`, or a release whose exporter
    // broke - parses to nothing, and keeping it would replace a good copy
    // and take every joined challenge off every screen (review, 2026-09-30).
    if (!isRecord(document) || !Array.isArray(document.challenges)) return null
    const challenges = parseChallenges(document)
    // Kept raw, so the same validation runs on the way back out; and only
    // once it has parsed, so a broken document never replaces a good one.
    await rememberPublished(CHALLENGES_KEY, document)
    return challenges
  } catch {
    return null
  }
}
