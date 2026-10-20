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

// THE PARSER AND THE FETCH ARE lib/challengeFeed.ts, loaded by import()
// once the launch is past its first frame - #1806 — main's eager JavaScript
// is 245,910 bytes against the 245,760 launch budget since the challenges
// merge, so every PR's preview build fails. What stays here is what the
// shell reads on every render: the shapes, and the questions asked of them.

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
