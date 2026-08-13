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
import { isBroadAdvisory } from './closureSpan'
import { formatDistance, type UnitSystem } from './units'

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
  /**
   * Whether a hiker is stopped from walking through, as the reviewer read it.
   *
   * NOT derivable from `category`, which is the thing this field replaced,
   * and ATC's live page on 2026-08-12 is why. The only notice they file as
   * `Closure` is a closed SHELTER - the trail past Limestone Spring is open -
   * while the one thing that genuinely stops a hiker, the Harpers Ferry
   * footbridge, is filed as `Detour`. A rule reading the category was wrong in
   * both directions at once: a barrier drawn across open trail for the
   * shelter, and the real obstruction included only by luck.
   *
   * So it is the reviewer's judgement, recorded per row, which is where
   * features/ATC_TRAIL_UPDATES.md puts every other judgement this data needs.
   */
  obstructs_trail: boolean
  /** ATC's `dateModified`, as an ISO string. The age a hiker cares about. */
  updated_at: string
  source_url: string
}

/** The categories ATC publishes, verbatim. Not mapped onto `ClosureReason`:
 *  that enum's labels would render an "Alert" as "Closed", which is a claim
 *  ATC did not make. */
export type AtcCategory =
  | 'Detour'
  | 'Alert'
  | 'Closure'
  | 'Parking'
  | 'Hiking Safety'
  /** Bear warnings and the like. Not among the five measured on 2026-08-09;
   *  ATC was using it for two live notices on 2026-08-12. */
  | 'Animal'

/**
 * Whether this update gets a band, rather than only a banner.
 *
 * A band's sentence is "do not walk down there, go around" - a barrier drawn
 * across the treadway. A bear warning, a closed car park and a closed shelter
 * are all real information and none of them says that, so none of them is
 * drawn as one. Getting this wrong is the same mistake `MAX_BAND_MILES` guards
 * against from the other direction: a barrier that turns out not to be a
 * barrier is what teaches a hiker that the barriers can be walked past.
 *
 * This reads the reviewer's answer rather than inferring one from ATC's
 * category - see `obstructs_trail` above for the live case that proved the
 * inference wrong.
 *
 * The undrawn ones are not dropped. They keep the banner, which needs only a
 * mile number, exactly as an over-long advisory does - so a hiker is still
 * told, in ATC's own words, that ATC has posted something about where they are
 * walking. features/ATC_TRAIL_UPDATES.md leaves "where the suppressed ones go"
 * an open question, and this is that answer for now rather than a new screen.
 */
export function obstructsTheTrail(update: AtcUpdate): boolean {
  return update.obstructs_trail
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

/**
 * Whether ATC named a place rather than a stretch.
 *
 * Most of what they publish is a place: of the seven placeable updates live on
 * 2026-08-12, five were a single mile marker - a shelter, a footbridge, two
 * bear warnings, a flooded section. Only Hurricane Helene was a real range,
 * and it is over the band ceiling. So this is the common case, not the edge
 * one, and it is why the map draws points at all (lib/atcUpdateStyle.ts).
 */
export function isPointNotice(update: AtcUpdate): boolean {
  return update.start_mile_marker === update.end_mile_marker
}

/**
 * The updates drawn as a band along the trail, in the shared shape.
 *
 * Ranges only. A point goes to `atcPointNotices` instead, because `trailSlice`
 * would widen it to the two vertices that bracket it and draw a few dozen feet
 * of line - which is not a small band, it is an invisible one.
 */
export function atcBandCandidates(updates: readonly AtcUpdate[]): Closure[] {
  return updates
    .filter((update) => obstructsTheTrail(update) && !isPointNotice(update))
    .map(atcUpdateAsClosure)
}

/**
 * The updates drawn as a dot at a single mile.
 *
 * Unlike the bands, this is NOT limited to the ones that obstruct the trail.
 * A dot makes no claim about passability - it says "the ATC has posted
 * something here" - so a bear warning at mile 195.8 and a closed shelter at
 * mile 1,503.6 both belong on the map, and neither is the barrier a band
 * would have made them. That difference is the whole reason the two
 * geometries are decided separately rather than by one filter.
 */
export function atcPointNotices(updates: readonly AtcUpdate[]): AtcUpdate[] {
  return updates.filter(isPointNotice)
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
 *
 * How far ahead it is reads in the hiker's units, like every distance in the
 * app; ATC's mile range does not, for the reason lib/units.ts gives. The two
 * sit in one sentence because they are two different facts - how far you walk
 * before you are in it, and where on the trail "it" is.
 */
export function atcUpdateBanner(
  update: AtcUpdate,
  currentMile: number,
  direction: HikeDirection | undefined,
  units: UnitSystem = 'imperial',
): string | null {
  const { start_mile_marker: start, end_mile_marker: end } = update
  const range = start === end ? `mi ${mile(start)}` : `mi ${mile(start)} – ${mile(end)}`
  const inside = currentMile >= start && currentMile <= end

  if (inside) {
    // "here" is false when "inside" spans a fifth of the trail (#485). ATC's
    // Helene advisory runs NOBO 239.4 to 637.8, so a hiker read `Alert here` for
    // 398 miles of walking - and their own text says the damage is patchy. The
    // extent replaces the position claim, in whole miles because a span this size
    // does not need tenths. ATC's category and headline are still theirs
    // verbatim; only OurHike's word for WHERE they are changes.
    const where = isBroadAtcAdvisory(update)
      ? `along ${formatDistance(Math.abs(end - start), units, 'whole')} of trail`
      : 'here'

    return `ATC · ${update.category} ${where} · ${update.title} · ${range}`
  }

  if (direction === undefined) return null

  const nearEdge = direction === 'NOBO' ? start : end
  const distanceAhead =
    direction === 'NOBO' ? nearEdge - currentMile : currentMile - nearEdge
  if (distanceAhead < 0) return null

  return `ATC · ${update.category} ${formatDistance(distanceAhead, units)} ahead · ${update.title} · ${range}`
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

/** An update and how far ahead of the hiker it is. */
export interface RankedAtcUpdate {
  update: AtcUpdate
  distance: number
}

/** The nearest ATC update matching `wanted`, and its distance - or null. */
function nearestWhere(
  updates: readonly AtcUpdate[],
  currentMile: number,
  direction: HikeDirection | undefined,
  wanted: (update: AtcUpdate) => boolean,
): RankedAtcUpdate | null {
  let best: RankedAtcUpdate | null = null

  for (const update of updates) {
    if (!wanted(update)) continue
    const distance = atcUpdateDistanceAhead(update, currentMile, direction)
    if (distance === null) continue
    if (best === null || distance < best.distance) best = { update, distance }
  }

  return best
}

/**
 * Whether ATC named a region rather than a stretch of trail.
 *
 * Read through the shared `Closure` shape on purpose, so this is the SAME
 * ceiling `closureBands` applies rather than a second number that could drift
 * from it - the point `atcUpdateAsClosure` above is written for. Of the seven
 * placeable updates live on 2026-08-12, exactly one answered true: Helene.
 */
export function isBroadAtcAdvisory(update: AtcUpdate): boolean {
  return isBroadAdvisory(atcUpdateAsClosure(update))
}

/**
 * The two updates that matter right now, one per line of the header.
 *
 * The mirror of `closureLanes` in lib/closureBanner.ts, and it exists for the
 * same reason (#485): an update the hiker is inside scores 0 and would win the
 * urgent line outright, which is right for a footbridge and wrong for a
 * 398-mile advisory. The reasoning is written once, over there.
 *
 * Two lanes here as well rather than only on the closure side, because since
 * #461 the ATC path is the one the Helene advisory actually travels - it arrives
 * as an `AtcUpdate`, never as a `Closure`. Fixing only `closureBanner.ts` would
 * have left the exact case #485 reports still broken.
 */
export function atcUpdateLanes(
  updates: readonly AtcUpdate[],
  currentMile: number,
  direction: HikeDirection | undefined,
): { specific: RankedAtcUpdate | null; broad: RankedAtcUpdate | null } {
  return {
    specific: nearestWhere(
      updates,
      currentMile,
      direction,
      (update) => !isBroadAtcAdvisory(update),
    ),
    broad: nearestWhere(updates, currentMile, direction, isBroadAtcAdvisory),
  }
}
