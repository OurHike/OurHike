// The words a challenge surface prints (#1780): a row's second line, a
// place's mile, a date, the moment a tag was made, and the sealed line of a
// mystery item. Sentences in a lib/*Text.ts module, the repository's habit
// (lib/todayText.ts, lib/hikeText.ts), so chrome/ChallengeParts.tsx holds
// components only and every screen spells these one way.

import {
  isPlaceItem,
  isSelfReport,
  itemTitle,
  type Challenge,
  type ChallengeItem,
} from './challenges'

/** A mile marker, grouped with one decimal - the rendering lib/clubDetail.ts,
 *  PoiCard and the position line give a mile, so every surface shows one
 *  number. A position label, not a distance: `mi` before the figure, which is
 *  the one thing lib/units.ts says does not convert. */
export function mileLabel(mile: number): string {
  return `mi ${mile.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`
}

/** A trail's name for a sentence. Only the A.T. has a spelling the app
 *  prints elsewhere; any other trail id is shown as it is published. */
export function trailLabel(trail: string): string {
  return trail === 'AT' ? 'A.T.' : trail
}

/**
 * What a row says under an item's title: where it is, or how it is done.
 * Never what the hiker has not done.
 */
export function itemMeta(item: ChallengeItem): string {
  const match = item.match
  switch (match.kind) {
    case 'place':
      // Off the trail is the one place a hiker's walked miles cannot see,
      // so the row says so; the Tag it pill beside it is how it is done.
      return match.offTrail
        ? `${match.places[0].name} · off the trail`
        : match.places[0].name
    case 'places_all':
      return match.places.map((place) => place.name).join(' · ')
    case 'poi_type':
      return `any ${match.type === 'viewpoint' ? 'vista' : match.type === 'resupply' ? 'A.T. community' : match.type}`
    case 'elevation_min_ft':
      return 'from the elevation profile'
    case 'section_walked':
      return `${match.fromName} to ${match.toName}, walked`
    case 'workday':
      return 'a workday you log in Volunteer'
    case 'self_report':
      return 'at home'
  }
}

/** The trailing figure: a place's mile, or nothing. */
export function itemTrailing(item: ChallengeItem): string | undefined {
  if (isPlaceItem(item)) return mileLabel(item.match.places[0].mile)
  if (item.match.kind === 'section_walked') return mileLabel(item.match.fromMile)
  return undefined
}

/** Whether a hiker may tag this item by a tap: an at-home item, a named
 *  place (the hand tag for GPS gaps and for places off the trail), or "any
 *  shelter" - which the camp card offers only on the day it was passed, so
 *  without a tap here a "Not tonight" would lose it for good. The kinds that
 *  tag themselves - a section, a height, a workday - never take a tap, which
 *  is design principle 1 holding. */
export function handTaggable(item: ChallengeItem): boolean {
  return isSelfReport(item) || isPlaceItem(item) || item.match.kind === 'poi_type'
}

/** The title as it reads today, or the sealed line. */
export function titleOrSealed(
  item: ChallengeItem,
  challenge: Challenge,
  today: string,
): string {
  const title = itemTitle(item, today)
  if (title !== null) return title
  if (item.mystery?.revealOn != null)
    return `Sealed until ${formatDay(item.mystery.revealOn)}`
  return `Sealed · announced by the ${challenge.orgShort}`
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

/** "Jul 14" from "2027-07-14" or an ISO instant. */
export function formatDay(value: string): string {
  // A tag's `at` is an ISO instant in UTC; its first ten characters are the
  // UTC date, which is tomorrow for a tag made after 8 pm in New York. Read
  // an instant on the hiker's own clock, and a bare YYYY-MM-DD as written.
  if (value.length > 10) {
    const at = new Date(value)
    if (!Number.isNaN(at.getTime())) return `${MONTHS[at.getMonth()]} ${at.getDate()}`
  }
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  if (!year || !month || !day) return value
  return `${MONTHS[month - 1]} ${day}`
}

/** "Jul 14 · 6:12 am" in the hiker's own clock - the moment line. The
 *  handoff draws temperature and sky too; the phone keeps no weather against
 *  a tag, so those are omitted rather than guessed. */
export function formatMoment(iso: string): string {
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return formatDay(iso)
  const hours = at.getHours()
  const minutes = String(at.getMinutes()).padStart(2, '0')
  const clock = `${hours % 12 === 0 ? 12 : hours % 12}:${minutes} ${hours < 12 ? 'am' : 'pm'}`
  return `${MONTHS[at.getMonth()]} ${at.getDate()} · ${clock}`
}
