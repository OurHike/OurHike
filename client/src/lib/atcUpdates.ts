// The ATC's own trail updates, as the ATC's word rather than as OurHike's.
//
// features/ATC_TRAIL_UPDATES.md is the design and #461 is the issue. The
// short version: the ATC publishes closures, detours and hazards at
// appalachiantrail.org/trail-updates, writes their locations in NOBO miles
// from Springer - which is what `start_mile_marker`/`end_mile_marker` already
// are - and none of it used to reach a hiker using OurHike.
//
// THE GEOMETRY NEEDED NO NEW CODE, AND THE PROVENANCE NEEDED ALL OF IT.
// `trailSlice` already turns a mile range into coordinates and `closureBands`
// already turns those into a source, so this module adapts an update into the
// shared `Closure` shape and hands it to them unchanged. What it deliberately
// does NOT do is let the adaptation reach the screen: an ATC notice, a
// verified hiker report and an unverified one are three different kinds of
// claim, and rendering them identically is the failure OurHikeValues.md #4
// exists to prevent. OurHike did not verify this. The ATC published it. Those
// are different statements, and laundering the second into the first would
// also misrepresent the ATC.
//
// So the adapter below is for GEOMETRY ONLY, and `reason_type` on its result
// is never rendered - the sheet and the banner read `AtcUpdate` directly and
// say ATC's own category in ATC's own words.
//
// WHAT IS NOT HERE. There is no live tier and there never will be: a hiker
// report has a backend endpoint behind it, and an ATC notice has ATC's
// website. `lib/publishedConditions.ts` reads the one published artifact, and
// its absence is rendered as no ATC layer rather than as a clear trail.

import type { Closure, HikeDirection } from './closureBanner'

/** One notice, exactly as `pipeline/export_atc_updates.py` publishes it.
 *
 *  Facts and a link, and no body text - that paragraph is ATC's writing, and
 *  `pipeline/sources.json`'s `licence` field on `atc_trail_updates` records
 *  why this stops where it does. The link is therefore load-bearing rather
 *  than a nicety: it is the whole of the detail a hiker can read. */
export interface AtcUpdate {
  /** ATC's own slug. Stable, and the only id there is - these rows never
   *  reach the closures table, so nothing ever mints a UUID for one. */
  atc_id: string
  title: string
  category: AtcCategory
  states: string[]
  start_mile_marker: number
  end_mile_marker: number
  /** ATC's `dateModified`, as an ISO string. The age a hiker cares about. */
  updated_at: string
  source_url: string
}

/** The categories ATC publishes, verbatim. Not mapped onto `ClosureReason`:
 *  that enum's labels would render an "Alert" as "Closed", which is a claim
 *  ATC did not make. */
export type AtcCategory = 'Detour' | 'Alert' | 'Closure' | 'Parking' | 'Hiking Safety'

/**
 * The categories that mean the trail itself is obstructed.
 *
 * Only these get a band. A band's sentence is "do not walk down there, go
 * around" - it is a barrier drawn across the treadway - and an Alert about
 * bear activity or a notice about a closed car park does not say that. Drawing
 * one for those would be the same mistake `MAX_BAND_MILES` guards against from
 * the other direction: a barrier that turns out not to be a barrier is what
 * teaches a hiker that the barriers can be walked past.
 *
 * The suppressed ones are not dropped. They keep the banner, which needs only
 * a mile number, exactly as an over-long advisory does - so a hiker is still
 * told, in ATC's own words, that ATC has posted something about where they are
 * walking. features/ATC_TRAIL_UPDATES.md leaves "where the suppressed ones go"
 * an open question, and this is that answer for now rather than a new screen.
 */
const OBSTRUCTING_CATEGORIES: ReadonlySet<AtcCategory> = new Set<AtcCategory>([
  'Closure',
  'Detour',
])

export function obstructsTheTrail(update: AtcUpdate): boolean {
  return OBSTRUCTING_CATEGORIES.has(update.category)
}

/** How a band's id says which update it is, and that it is ATC's.
 *
 *  Prefixed rather than bare so it can never collide with a closure's UUID in
 *  a shared id space, and so a tap that produces one of these is recognisably
 *  an ATC tap rather than an ambiguous string. */
export const ATC_BAND_ID_PREFIX = 'atc:'

export function atcBandId(update: AtcUpdate): string {
  return `${ATC_BAND_ID_PREFIX}${update.atc_id}`
}

export function atcUpdateForBandId(
  updates: readonly AtcUpdate[],
  bandId: string,
): AtcUpdate | null {
  return updates.find((update) => atcBandId(update) === bandId) ?? null
}

/**
 * An update in the shared `Closure` shape, for the geometry path only.
 *
 * `closureBands` needs an id, two mile markers and a status, and gives back
 * coordinates; reusing it means an ATC update inherits `trailSlice`'s
 * centerline placement and `isBroadAdvisory`'s length ceiling without either
 * being reimplemented, which is what #461 means by "the geometry path needs no
 * new code".
 *
 * `reason_type: 'other'` is a placeholder that must never be rendered. Its
 * label is "Closed", and applying that to an ATC Detour would put a word in
 * their mouth. Everything a hiker reads about an ATC update comes off
 * `AtcUpdate` itself - see `atcUpdateBanner` below and chrome/AtcUpdateSheet.
 *
 * `status: 'closed'` for the same narrow reason: `closureBands` drops
 * anything marked `open` because drawing a barrier across a reopened trail is
 * a false statement. A reopened ATC notice never reaches this function - the
 * reviewed file holds current notices and a person decides what "Reopened"
 * means (features/ATC_TRAIL_UPDATES.md) - so this is the honest constant
 * rather than a field with nothing behind it.
 */
export function atcUpdateAsClosure(update: AtcUpdate): Closure {
  return {
    id: atcBandId(update),
    reason_type: 'other',
    note: null,
    status: 'closed',
    start_mile_marker: update.start_mile_marker,
    end_mile_marker: update.end_mile_marker,
  }
}

/** The updates that may be drawn as bands, in the shared shape. */
export function atcBandCandidates(updates: readonly AtcUpdate[]): Closure[] {
  return updates.filter(obstructsTheTrail).map(atcUpdateAsClosure)
}

function mile(value: number): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

/**
 * One line for the header, in ATC's voice.
 *
 * Deliberately not `closureBanner`'s sentence. That one opens "Trail closed",
 * which is OurHike asserting a closure; this one names the ATC first and then
 * quotes their category and their headline, so the hiker reads a claim with
 * an owner on it. The mile range is theirs too, to tenths, because that is the
 * precision they publish at.
 *
 * `null` for an update behind the hiker, and for one whose direction cannot
 * be established while they stand outside it - both rules come straight from
 * lib/closureBanner.ts and are deliberately not re-derived here: warning half
 * of all hikers about something behind them is how a warning surface teaches
 * people to ignore it.
 */
export function atcUpdateBanner(
  update: AtcUpdate,
  currentMile: number,
  direction: HikeDirection | undefined,
): string | null {
  const { start_mile_marker: start, end_mile_marker: end } = update
  const range = start === end ? `mi ${mile(start)}` : `mi ${mile(start)} – ${mile(end)}`
  const inside = currentMile >= start && currentMile <= end

  if (inside) {
    return `ATC · ${update.category} here · ${update.title} · ${range}`
  }

  if (direction === undefined) return null

  const nearEdge = direction === 'NOBO' ? start : end
  const distanceAhead =
    direction === 'NOBO' ? nearEdge - currentMile : currentMile - nearEdge
  if (distanceAhead < 0) return null

  return `ATC · ${update.category} ${mile(distanceAhead)} mi ahead · ${update.title} · ${range}`
}

/**
 * How far ahead an update is, or null if it is behind or unplaceable.
 *
 * The same rule as lib/closureBanner.ts's, and it is exported because App.tsx
 * has one banner line and two sources competing for it. Comparing distances
 * is what lets the nearer warning win, which is the rule that module already
 * applies among closures - "the closure two hundred miles north is not the one
 * that changes what they do next".
 */
export function atcUpdateDistanceAhead(
  update: AtcUpdate,
  currentMile: number,
  direction: HikeDirection | undefined,
): number | null {
  const { start_mile_marker: start, end_mile_marker: end } = update
  if (currentMile >= start && currentMile <= end) return 0
  if (direction === undefined) return null

  const nearEdge = direction === 'NOBO' ? start : end
  const ahead = direction === 'NOBO' ? nearEdge - currentMile : currentMile - nearEdge
  return ahead < 0 ? null : ahead
}

/** The nearest ATC update ahead, and its distance - or null if none is. */
export function nearestAtcUpdate(
  updates: readonly AtcUpdate[],
  currentMile: number,
  direction: HikeDirection | undefined,
): { update: AtcUpdate; distance: number } | null {
  let best: { update: AtcUpdate; distance: number } | null = null

  for (const update of updates) {
    const distance = atcUpdateDistanceAhead(update, currentMile, direction)
    if (distance === null) continue
    if (best === null || distance < best.distance) best = { update, distance }
  }

  return best
}
