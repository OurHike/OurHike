// How many distinct days this phone has used OurHike in the current calendar
// year - the count the support ask waits on (#1876: "on a hiker's 5th
// distinct day of use in a year", maintainer, 2026-10-23).
//
// ON THIS PHONE AND NOWHERE ELSE. features/EVENTING.md §1's first rule is
// that no identifier leaves the device, and a per-hiker day count sent to a
// server is exactly the "stable identifier + when" pair #252 removed from
// the report feed. Nothing here is sent anywhere; the only reader is the ask
// on this same phone. A hiker who uses two phones is counted twice, once on
// each, and that is the price of not knowing who they are.
//
// WHAT A DAY IS borrows EVENTING.md §2's definition of active: "a foreground
// session with at least one hiker interaction". The shell calls
// `recordActiveDay` from the first pointer or key event of a page load, so a
// background sync, a service-worker wake or a phone that opened the app in a
// pocket counts for nothing. A day is the hiker's LOCAL calendar date,
// because "five days out" means five of their days, not five UTC ones.
//
// CALENDAR YEAR, NOT ROLLING. The ask is "once a year" and the count resets
// on January 1 local time. Reasoned rather than measured: a rolling window
// would need the dates themselves kept, and five dates in a row is a sketch
// of somebody's season; a count and the last date is all this needs.

/** Stored as JSON: `{ year, days, last }`. Private to this file except for
 *  the literal the stored-shapes ledger records at the next release. */
export const ACTIVE_DAYS_KEY = 'ourhike:active-days'

interface ActiveDays {
  /** The calendar year `days` counts within. */
  year: number
  /** Distinct local dates seen in `year`. */
  days: number
  /** The last date counted, `YYYY-MM-DD` local, so a second launch that day
   *  adds nothing. */
  last: string
}

/** `YYYY-MM-DD` in the phone's own time zone. */
export function localDate(now: Date): string {
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function read(): ActiveDays | null {
  try {
    const raw = localStorage.getItem(ACTIVE_DAYS_KEY)
    if (raw === null) return null
    const parsed: unknown = JSON.parse(raw)
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      typeof (parsed as ActiveDays).year === 'number' &&
      typeof (parsed as ActiveDays).days === 'number' &&
      typeof (parsed as ActiveDays).last === 'string'
    ) {
      return parsed as ActiveDays
    }
    return null
  } catch {
    // Unreadable reads as never counted. The cost is the ask arriving a few
    // days late, never early.
    return null
  }
}

/** Days counted so far in `now`'s calendar year. Zero in a new year until
 *  the first interaction of it. */
export function activeDaysThisYear(now: Date): number {
  const stored = read()
  return stored !== null && stored.year === now.getFullYear() ? stored.days : 0
}

/**
 * Count `now`'s date if it has not been counted, and return the year's total.
 *
 * Idempotent within a day. A clock set backwards does not count a day twice:
 * a date at or before `last` in the same year adds nothing, which can only
 * ever make the ask later.
 */
export function recordActiveDay(now: Date): number {
  const today = localDate(now)
  const year = now.getFullYear()
  const stored = read()

  let next: ActiveDays
  if (stored === null || stored.year !== year) {
    next = { year, days: 1, last: today }
  } else if (today <= stored.last) {
    return stored.days
  } else {
    next = { year, days: stored.days + 1, last: today }
  }

  try {
    localStorage.setItem(ACTIVE_DAYS_KEY, JSON.stringify(next))
  } catch {
    // Storage refused: today counts for this page load only. The ask then
    // waits for a phone that can remember, rather than asking every launch.
    return stored?.year === year ? stored.days : 0
  }
  return next.days
}
