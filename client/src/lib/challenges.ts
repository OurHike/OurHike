// Clubs' challenges, as read from the artifact pipeline/export_challenges.py
// publishes (#1780, features/CHALLENGES.md).
//
// WHAT A CHALLENGE IS. A list of places on one organization's trails, a date
// window, an optional finish line and an optional reward. A hiker opts in,
// walks, and tags the places at camp. This module is the artifact's shape and
// the questions a screen asks of it; lib/challengeProgress.ts is what the
// hiker has done about one.
//
// HOW IT REACHES THE PHONE, AND WHY NOT THE TRAIL BUNDLE. The kept copy goes
// through lib/conditionsCache.ts, the path lib/suggestedHikesData.ts already
// rides: fetched from the release when there is signal, validated on the way
// in AND on the way back out, and never fatal. Riding lib/trailData.ts's
// all-or-nothing download would make a 38,914-byte list (5,328 gzipped -
// measured 2026-09-30, the ATC draft resolved against release 2026-09-24-2
// and serialised as the exporter writes it) a reason a trail download could
// fail, which it must not be.
//
// JUNK COSTS THE RECORD, NEVER THE LIST - the stance lib/highlights.ts and
// lib/suggestedHikesData.ts take. One unreadable challenge is dropped and the
// rest are shown; one unreadable item is dropped and its challenge is kept,
// unless the challenge's finish line can then no longer be reached, which is
// the promise-nobody-can-keep case the exporter also refuses.
//
// A DRAFT IS SHOWN, LABELLED. The maintainer's choice by poll, 2026-09-30:
// a challenge whose publisher has not confirmed it publishes everywhere, and
// every surface that names it says so - `draftLabel` is that sentence.

import { CHALLENGES_KEY, DATA_CONFIGURED, dataUrl } from './config'
import { recallPublished, rememberPublished } from './conditionsCache'

export type MatchKind =
  | 'place'
  | 'places_all'
  | 'poi_type'
  | 'elevation_min_ft'
  | 'section_walked'
  | 'workday'
  | 'self_report'

/** One published POI, copied into the challenge at export time - its own
 *  mile, coordinate and name, so nothing else need be loaded to use it. */
export interface ChallengePlace {
  poi: string
  name: string
  poiType: string
  mile: number
  lat: number
  lon: number
}

export type ChallengeMatch =
  | {
      kind: 'place' | 'places_all'
      radiusM: number
      /** Reaching it means leaving the trail - a town, a visitor centre. A
       *  day's walked miles say nothing about one, so it is tagged by hand. */
      offTrail: boolean
      places: ChallengePlace[]
    }
  | {
      kind: 'poi_type'
      type: string
      radiusM: number
      /** Its waypoints are places a hiker walks into (a town): never offered
       *  at camp from a mile interval, only tagged by hand. */
      offTrail: boolean
    }
  | { kind: 'elevation_min_ft'; valueFt: number }
  | {
      kind: 'section_walked'
      trail: string
      fromMile: number
      toMile: number
      fromName: string
      toName: string
      minFraction: number
    }
  | { kind: 'workday'; org: string | null; trail: string }
  | { kind: 'self_report' }

export interface ChallengeItem {
  id: string
  section: string
  /** Null for a mystery item that is still sealed, or that never had one. */
  title: string | null
  /** Base64 of a sealed title - a spoiler guard, not a secret. */
  sealedTitle: string | null
  note: string | null
  noteBy: string | null
  photo: string | null
  match: ChallengeMatch
  mystery: { number: number; revealOn: string | null } | null
}

export interface ChallengeSection {
  id: string
  title: string
  /** The filter pill's word - "Anywhere", "Learn". */
  short: string
}

export type RewardKind = 'patch' | 'postcard' | 'sticker' | 'drawing'

export interface Challenge {
  id: string
  org: string
  /** "Appalachian Trail Conservancy" */
  orgName: string
  /** "ATC" */
  orgShort: string
  /** "appalachiantrail.org" - the publisher's web domain (publishers.json),
   *  which an entry carries and the server makes a club prove. Null on a
   *  document from before it was published: such a challenge takes no
   *  entries from this phone. */
  orgDomain: string | null
  trail: string
  name: string
  status: 'draft' | 'published'
  summary: string | null
  /** YYYY-MM-DD, either end may be absent: "any time", "no end". */
  window: { opens: string | null; closes: string | null }
  /** Null: a record, with no finish line. */
  finish: { count: number; label: string | null } | null
  /** Null for most challenges - a finish needs no reward. */
  reward: { kind: RewardKind; rulesUrl: string | null; art: string | null } | null
  /** Whether the club collects entries through OurHike. False: the finish
   *  screen sends the hiker to the club's own rules rather than asking for a
   *  name and address the server would refuse. */
  takesEntries: boolean
  photo: string | null
  sections: ChallengeSection[]
  items: ChallengeItem[]
  reviewed: string
}

export const NO_CHALLENGES: readonly Challenge[] = []

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

/** Decodes a sealed title. Null when the bytes are not base64 of UTF-8. */
export function unseal(sealed: string): string | null {
  try {
    const binary = atob(sealed)
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0))
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    return null
  }
}

/**
 * What an item is called today, or null while it is sealed.
 *
 * A mystery item's title stays unreadable until the hiker's own calendar
 * reaches `revealOn`, with no network: the title arrived with the data
 * refresh, base64'd, and this is the only place it is decoded. `today` is
 * the hiker's local YYYY-MM-DD (lib/passedToday.localDay).
 */
export function itemTitle(item: ChallengeItem, today: string): string | null {
  if (item.title !== null) return item.title
  if (item.sealedTitle === null || item.mystery?.revealOn == null) return null
  if (today < item.mystery.revealOn) return null
  return unseal(item.sealedTitle)
}

/** A mystery item still waiting on its date (or on its club). */
export function isSealed(item: ChallengeItem, today: string): boolean {
  return item.mystery !== null && itemTitle(item, today) === null
}

/** An item whose match names one or more fixed places. */
export type PlaceItem = ChallengeItem & {
  match: Extract<ChallengeMatch, { places: ChallengePlace[] }>
}

/** The kinds that name fixed places - the only ones a pin can be drawn for. */
export function isPlaceItem(item: ChallengeItem): item is PlaceItem {
  return item.match.kind === 'place' || item.match.kind === 'places_all'
}

/** Whether a hiker can tag this item by a tap alone - the named exception to
 *  "days, not clicks", the PDF's at-home lines. */
export function isSelfReport(item: ChallengeItem): boolean {
  return item.match.kind === 'self_report'
}

/** Whether today falls inside the challenge's window. An open end is open. */
export function isOpen(challenge: Challenge, today: string): boolean {
  const { opens, closes } = challenge.window
  if (opens !== null && today < opens) return false
  if (closes !== null && today > closes) return false
  return true
}

/** The sentence every surface naming a draft carries - the maintainer's
 *  condition for publishing one at all (poll, 2026-09-30). */
export function draftLabel(challenge: Challenge): string | null {
  return challenge.status === 'draft'
    ? `Draft · not yet confirmed by the ${challenge.orgShort}`
    : null
}

const MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]

/** "Sep 1" from "2027-09-01" - a date, never a count of days left, which
 *  would be the lack-state VOLUNTEERING.md §5 rule 2 forbids. */
export function shortDate(isoDay: string): string {
  const [, month, dayOfMonth] = isoDay.split('-').map(Number)
  return `${MONTHS[month - 1] ?? ''} ${dayOfMonth}`
}

/** The mono window line: "until Sep 1", "May 15 – Sep 1", "no end date". */
export function windowLine(challenge: Challenge): string {
  const { opens, closes } = challenge.window
  if (opens !== null && closes !== null)
    return `${shortDate(opens)} – ${shortDate(closes)}`
  if (closes !== null) return `until ${shortDate(closes)}`
  if (opens !== null) return `from ${shortDate(opens)}`
  return 'no end date'
}

/**
 * The window as it stands today, for a line that has room for one phrase:
 * "opens May 15" before it opens, "closed Sep 1" after, otherwise what is
 * left of it. A list that opens next May no longer reads "until Sep 1".
 */
export function windowNow(challenge: Challenge, today: string): string {
  const { opens, closes } = challenge.window
  if (opens !== null && today < opens) return `opens ${shortDate(opens)}`
  if (closes !== null && today > closes) return `closed ${shortDate(closes)}`
  return closes !== null ? `until ${shortDate(closes)}` : 'no end date'
}

/** One item's places, in trail order - empty for anything but a place kind. */
export function itemPlaces(item: ChallengeItem): readonly ChallengePlace[] {
  return isPlaceItem(item) ? item.match.places : []
}

/** Every item in this challenge that names the given published POI. */
export function itemsAtPoi(challenge: Challenge, poiId: string): ChallengeItem[] {
  return challenge.items.filter((item) =>
    itemPlaces(item).some((place) => place.poi === poiId),
  )
}
