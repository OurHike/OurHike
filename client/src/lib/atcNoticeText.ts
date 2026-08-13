// The words an ATC notice is rendered with, in one place.
//
// Extracted when a second surface needed them (chrome/AtcNoticeList.tsx). Two
// components formatting the same mile marker to different precision, or
// disagreeing about what an unreadable date should say, is exactly the kind of
// drift a safety surface cannot afford - a hiker comparing the banner, the
// sheet and the list must be reading one claim, not three renderings of it.
//
// Deliberately here rather than in lib/atcUpdates.ts. That module is about
// what an update IS - which ones get a band, how far ahead one is, how a band
// id is formed. This one is about how it READS, and the two change for
// different reasons.

import type { AtcUpdate } from './atcUpdates'

/** A date as a hiker reads it, in UTC.
 *
 *  UTC rather than local, because ATC's `dateModified` is a publication stamp
 *  and rendering it in the phone's zone would move it a day for anyone west of
 *  Greenwich - a notice "updated 31 July" becoming "updated 30 July" is a
 *  smaller lie than most and still one nobody asked for. */
export function longDate(value: Date): string {
  return value.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  })
}

/** One mile marker, to tenths - the precision ATC publishes at. */
export function mile(value: number): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

/** An update's extent, as `mi 1,026.7` or `mi 476.6 – 485.8`.
 *
 *  A point notice says one number rather than the same number twice. Most of
 *  what ATC publishes is a point (`isPointNotice`), so this is the common
 *  branch and not the tidy-up. */
export function mileRange(update: AtcUpdate): string {
  const { start_mile_marker: start, end_mile_marker: end } = update
  return start === end ? `mi ${mile(start)}` : `mi ${mile(start)} – ${mile(end)}`
}

/**
 * The date ATC last edited a notice, or null if it is unreadable.
 *
 * Null rather than a fallback. "Updated —" invites the reader to supply their
 * own guess, and an invented date on a safety notice is worse than an absent
 * one: the whole point of showing it is that the hiker can judge how old the
 * claim is.
 */
export function atcUpdatedAt(update: AtcUpdate): Date | null {
  const parsed = new Date(update.updated_at)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

/**
 * Whether a URL may be rendered as a link.
 *
 * `pipeline/lib/atc_updates.py` refuses a non-`http(s)` URL on the way in as
 * well, so this is the second line rather than the only one; a check that only
 * exists at the far end is one a future second producer walks straight past.
 *
 * Note for anyone extending this: chrome/ClosureSheet.tsx renders a
 * moderator-supplied `reroute_url` with NO such check. That is a real gap and
 * it is not this module's to close quietly - it wants its own issue, because
 * the fix is a decision about what a sheet does with a URL it refuses, not a
 * one-line import.
 */
export function isSafeLink(url: string): boolean {
  try {
    const scheme = new URL(url, window.location.href).protocol
    return scheme === 'http:' || scheme === 'https:'
  } catch {
    return false
  }
}
