// The sentences a long hike is described by (#1317).
//
// Split from the components for the reason `lib/todayText.ts` was: the pick
// sheet, the Plan band, the More row and the finish screen all say a hike's
// figures, and four hand-written versions of "412 mi walked · 1,786 mi to
// go" is how one of them quietly starts printing a percentage.
//
// FIGURES ARE `miles walked · miles to go`, ALWAYS, and nothing else. The
// design handoff's decision #6 and OurHikeValues.md #1 behind it: no
// percentages, no "behind", no "ahead of", no "on track", no streaks, no
// comparison with another hiker. `screens/Plan.test.tsx`'s standing guard
// enforces it on the Plan tab and #1317 extends that guard to every surface
// below.
//
// MILES NOT YET WALKED READ `0`, NEVER "unknown" (decision #7). A hike set
// up this morning has walked nothing, and "0 mi walked" is the true and
// useful thing to print; "unknown" would suggest the app had lost track of
// something rather than that nothing had happened yet.

import { hikeFigures, type Hike } from './hikes'
import type { StoredPoi } from './trailData'
import type { Trip } from './trips'
import { formatDistance, type UnitSystem } from './units'

/** `412 mi walked · 1,786 mi to go`. */
export function hikeFiguresLine(
  hike: Hike,
  trips: readonly Trip[],
  pois: readonly StoredPoi[],
  units: UnitSystem,
): string {
  const figures = hikeFigures(hike, trips, pois)
  return `${formatDistance(figures.walkedMi, units)} walked · ${formatDistance(
    figures.leftMi,
    units,
  )} to go`
}

/**
 * How long ago, in the coarse words a hiker uses about their own hike.
 *
 * Days up to a fortnight, then months, then years - and never a clock. The
 * figure answers "is this the hike I was on, or the one I left behind", and
 * "11 months ago" answers it where "334 days ago" only looks precise.
 *
 * Both dates are ISO calendar days (YYYY-MM-DD), compared as such rather
 * than as instants: "how many days ago" is a question about the hiker's
 * calendar, not about elapsed hours, so a pause at 23:00 and a read at 07:00
 * the next morning is one day rather than nine hours.
 */
export function agoLabel(from: string, today: string): string | null {
  const days = daysBetween(from, today)
  if (days === null || days < 0) return null
  if (days === 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 14) return `${days} days ago`
  const months = Math.round(days / 30.4)
  if (months < 12) return `${Math.max(1, months)} months ago`
  const years = Math.round(days / 365.25)
  return years <= 1 ? 'a year ago' : `${years} years ago`
}

/** Whole calendar days between two ISO dates, or null if either is not one. */
export function daysBetween(from: string, to: string): number | null {
  const a = Date.parse(`${from}T00:00:00Z`)
  const b = Date.parse(`${to}T00:00:00Z`)
  if (Number.isNaN(a) || Number.isNaN(b)) return null
  return Math.round((b - a) / 86_400_000)
}

/**
 * The meta line under a hike's name on the pick sheet.
 *
 * A paused hike says so instead of its figures, because that is the thing a
 * hiker choosing between hikes is actually distinguishing by - "the one I
 * stopped in August" - and its figures have not moved since.
 */
export function hikePickMeta(
  hike: Hike,
  trips: readonly Trip[],
  pois: readonly StoredPoi[],
  units: UnitSystem,
  today: string,
): string {
  if (hike.status === 'paused' && hike.pausedAtMile !== undefined) {
    const ago = hike.pausedOn === undefined ? null : agoLabel(hike.pausedOn, today)
    return [
      `paused at mi ${hike.pausedAtMile.toLocaleString('en-US', {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })}`,
      ago,
    ]
      .filter((part) => part !== null)
      .join(' · ')
  }

  const sections = hike.tripIds.length
  return [
    `${sections} ${sections === 1 ? 'section' : 'sections'}`,
    hikeFiguresLine(hike, trips, pois, units),
  ].join(' · ')
}

/** `mi 1,023.4 · 14 Mar`, or `mi 0.0 · no date` - a point's right-hand
 *  figure on the set-up list. A point with no date is normal, not
 *  incomplete, so it says so plainly rather than leaving a gap. */
export function pointMeta(mile: number, date: string | undefined): string {
  const miles = `mi ${mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}`
  return `${miles} · ${date === undefined ? 'no date' : shortDate(date)}`
}

/** `14 Mar` from an ISO calendar day, or the input when it is not one. */
export function shortDate(iso: string): string {
  const at = Date.parse(`${iso}T00:00:00Z`)
  if (Number.isNaN(at)) return iso
  return new Date(at).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  })
}
