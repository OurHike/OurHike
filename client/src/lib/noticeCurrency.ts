// Whether a notice still reads as current on this phone, and the one line a
// hiker reads under it when it does not (#1805; pipeline/ELT.md, "Status,
// water and expiry rules", rules 2 and 4).
//
// THE PIPELINE DECIDES THE DAY, THE PHONE DECIDES TODAY. conditions/notices.json
// carries `current_until` on every notice: the last day it reads as current
// (its own end date, else the long end of a duration its title states from
// its own start, else its edit date plus 90 days), or null where it gives no
// date that bounds it. pipeline/dbt/macros/notice_current_until.sql is the
// rule's one home, and dbt_project.yml's `notice_freshness_limit_days` the
// 90 days' - none of that is restated here. This module only compares that
// day with the phone's own calendar, so a phone offline for a week greys a
// notice on the day its date passes, which no build-time answer could do.
//
// FRAME A (the maintainer's poll of 2026-10-10): a notice that no longer reads
// as current STAYS where it is, greyed, with one line under it. Two of the
// lines are the maintainer's, word for word, from the frame:
//
//   "Last reported <Month D, YYYY>. It may no longer apply."
//   "Its source gives no date. It may no longer apply."
//
// and three are proposals for the cases the frame did not draw, in the same
// shape: an end date that has passed, a duration that ran out, and a source
// that gives a start date and nothing else (a burned area dated by its fire).
//
// A FILE WITH NO VERDICT READS AS IT ALWAYS DID. A notice whose row has no
// `current_until` key at all - a copy of notices.json kept from before the
// field existed, or a row of conditions/atc_updates.json or nynjtc_alerts.json,
// whose shapes decision 51 keeps as they are - is current here. Greying every
// notice of an older file would be a display outrunning its source just as
// surely as calling a stale one current; the file simply makes no claim.
//
// A LEAF MODULE, with no import but the notice's type, for the launch budget's
// reason (lib/noticeSelection.ts's header): lib/plannedNotices.ts and
// lib/hazardAreas.ts import it, so it travels in the chunk those two already
// share, and the sheets that import it add no chunk of their own.

import type { TrailNotice } from './notices'

/** An ISO day such as "2026-10-01", and only a real one: V8 rolls "2026-04-31"
 *  over to May 1, so the parsed day must name the same day back. */
export function isIsoDay(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const at = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(at.getTime()) && at.toISOString().slice(0, 10) === value
}

/**
 * "October 1, 2026" from a notice's `starts_on`, `ends_on` or `current_until`,
 * an ISO day, read as the calendar day it names - the same words
 * lib/atcNoticeText.ts's `longDate` gives a stamp, so a sheet that prints both
 * prints one date style, never "2026-10-01" beside "October 5, 2026".
 * Anything that is not an ISO day is shown as the source wrote it, never as
 * "Invalid Date": publishedNotices.ts reads the dates as plain text. So is
 * a day no calendar has, such as "2026-04-31" (`isIsoDay`).
 *
 * Here rather than beside `longDate` because the panel, the area's card and
 * lib/noticeSelection.ts already import this chunk, and an import of
 * atcNoticeText.ts from here would tie lib/noticeSelection.ts's chunk to the
 * sheets' (that module's header gives the launch budget's reason). It lived
 * in lib/hazardAreas.ts until this module, which re-exports it.
 */
export function longDay(day: string): string {
  if (!isIsoDay(day)) return day
  return new Date(`${day}T00:00:00Z`).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  })
}

/** The calendar day an ISO stamp falls on in UTC, as lib/atcNoticeText.ts's
 *  `longDate` prints it, or null for a stamp this build cannot read. */
function stampDay(stamp: string | null): string | null {
  if (stamp === null) return null
  const at = new Date(stamp)
  return Number.isNaN(at.getTime()) ? null : at.toISOString().slice(0, 10)
}

/**
 * Whether a notice reads as current on `today`, the phone's own calendar day
 * (lib/passedToday.ts's `localDay`).
 *
 * Current through `current_until` itself and greyed the day after, so a
 * closure reads as current all through its last day: shown a day too long
 * rather than greyed a day early, the side a hiker in front of a closed trail
 * is safer on (Reasoned). The day is compared in the phone's own zone, where
 * the source's end date is a day in the source's zone: for a hiker in the
 * zone of the trail they are reading about, the two are the same day.
 */
export function isCurrentOn(notice: TrailNotice, today: string): boolean {
  const until = notice.current_until
  if (until === undefined) return true
  return until !== null && isIsoDay(until) && today <= until
}

/** What a notice that no longer reads as current says about itself. */
export interface NotCurrent {
  /** The line printed under it, a whole sentence or two. */
  line: string
  /** True when the line already carries the notice's own edit date ("Last
   *  reported ..."), so the row's "— updated <date>" would only repeat it:
   *  frame A drops it there. */
  saysUpdated: boolean
}

/** The maintainer's two lines (frame A), word for word, and the three
 *  proposed beside them. Exported so a test can quote them. */
export const NOT_CURRENT_LINES = {
  lastReported: (day: string) => `Last reported ${day}. It may no longer apply.`,
  noDate: 'Its source gives no date. It may no longer apply.',
  ended: (day: string) => `Its source said it would end ${day}. It may no longer apply.`,
  ranOut: (day: string) =>
    `The time its source gave ran out on ${day}. It may no longer apply.`,
  startOnly: 'Its source gives no end or update date. It may no longer apply.',
} as const

/**
 * Null while the notice reads as current on `today` (or its file carries no
 * verdict), and otherwise the line it is shown with, greyed.
 *
 * Which line follows from which of the pipeline's steps set `current_until`,
 * read off the row rather than published: an end date wins first, so a row
 * with one is "Its source said it would end ...". With no end date, a row
 * with an edit stamp says when it was last reported, as frame A's middle row
 * does for a stated duration that ran out (that row's title carries the
 * duration itself). A row with neither ran out on its stated duration, the
 * only step left that gives a day. A null day is no date at all, or only a
 * start, which bounds nothing.
 */
export function notCurrent(notice: TrailNotice, today: string): NotCurrent | null {
  if (isCurrentOn(notice, today)) return null
  const until = notice.current_until ?? null
  if (until === null || !isIsoDay(until)) {
    return {
      line:
        typeof notice.starts_on === 'string' && notice.starts_on !== ''
          ? NOT_CURRENT_LINES.startOnly
          : NOT_CURRENT_LINES.noDate,
      saysUpdated: false,
    }
  }
  if (typeof notice.ends_on === 'string' && notice.ends_on !== '') {
    return { line: NOT_CURRENT_LINES.ended(longDay(notice.ends_on)), saysUpdated: false }
  }
  const edited = stampDay(notice.updated_at)
  if (edited !== null) {
    return { line: NOT_CURRENT_LINES.lastReported(longDay(edited)), saysUpdated: true }
  }
  return { line: NOT_CURRENT_LINES.ranOut(longDay(until)), saysUpdated: false }
}
