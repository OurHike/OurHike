// Volunteer work projects: the fourteen-day window, the honesty rule for a
// layer whose data EXPIRES, and the ordering a hiker actually wants
// (features/VOLUNTEERING.md Phase B, #760).
//
// Every other layer in this app is durable - a shelter is where it was last
// month. A workday nine days out is wrong the moment it is cancelled, and a
// downloaded map cannot know that. So opportunities are never baked into an
// offline package: they arrive only through conditions/work_projects.json
// (rewritten in place on every bake, so a cancellation clears within one),
// they render with their age visible, and past a staleness ceiling the app
// stops showing them as opportunities at all and says it is out of date -
// sending someone to a trailhead for a workday cancelled on Thursday is this
// feature's own failure mode, and an honest "I cannot tell you" beats a
// confident wrong answer (value #4).

import type { PublishedConditions } from './publishedConditions'

/** One row of conditions/work_projects.json, exactly as
 *  pipeline/export_work_projects.py bakes it from the reviewed file. */
export interface WorkProjectSummary {
  id: string
  club_name: string
  title: string
  description: string | null
  lat: number | null
  lon: number | null
  /** NOBO mile from Springer, when the reviewed row placed it on the axis. */
  mile: number | null
  /** "YYYY-MM-DD" - a date range covers a single day and a weekend;
   *  recurrence is deliberately unmodelled (VOLUNTEERING.md's open question). */
  starts_on: string
  ends_on: string
  status: 'upcoming' | 'completed' | 'cancelled'
  /** Null means "no cap stated", never zero. */
  capacity: number | null
  /** Phase B is read-only, so `contact` is the only mode the pipeline admits
   *  today - `in_app` arrives with #762's backend. */
  signup_mode: 'contact'
  signup_contact: string | null
}

/** The window the tab and the map filter to. VOLUNTEERING.md's own number:
 *  far enough out to plan a weekend around, near enough that the plans are
 *  real rather than aspirational. */
export const WORK_PROJECT_WINDOW_DAYS = 14

const DAY_MS = 24 * 60 * 60 * 1000

/**
 * How old the artifact may grow before the app stops calling its rows
 * opportunities. Past this the whole list is replaced by an out-of-date
 * notice - never rendered greyed or hedged row by row, because a hedged
 * invitation still reads as an invitation.
 *
 * @unvalidated - "about 48 hours" is the design doc's own phrase and nothing
 * establishes it (#760 tags it the same way). What would settle it is how
 * far ahead the partner clubs actually cancel, which is a question for them
 * rather than a measurement this repository can take.
 */
export const OPPORTUNITIES_STALE_MS = 48 * 60 * 60 * 1000

/**
 * Whether the artifact is still fresh enough to present as opportunities.
 *
 * Judged against the BAKE's clock (`generated_at`), not the fetch's: a
 * fresh fetch of a stale artifact is still stale - the bake stopping is
 * exactly the failure this ceiling exists to surface - and a stale fetch of
 * anything is covered by the same subtraction.
 */
export function opportunitiesUsable(generatedAt: Date, now: Date): boolean {
  return now.getTime() - generatedAt.getTime() <= OPPORTUNITIES_STALE_MS
}

/** "YYYY-MM-DD" as UTC midnight - the same reading publishedConditions.ts
 *  gives the drought week, so a date means one day everywhere. */
function utcDay(value: string): number {
  return new Date(value).getTime()
}

/**
 * The rows worth showing: upcoming, not yet over, and starting inside the
 * window. An event already running counts - a crew mid-weekend still takes
 * a walk-up pair of hands - which is why the near bound tests `ends_on`.
 */
export function upcomingWorkProjects(
  projects: readonly WorkProjectSummary[],
  now: Date,
): WorkProjectSummary[] {
  const today = now.getTime()
  const horizon = today + WORK_PROJECT_WINDOW_DAYS * DAY_MS

  return projects.filter((project) => {
    if (project.status !== 'upcoming') return false
    // ends_on is a whole day, so it ends at the following UTC midnight.
    if (utcDay(project.ends_on) + DAY_MS < today) return false
    return utcDay(project.starts_on) <= horizon
  })
}

/**
 * Nearest first when the hiker's own trail position is known - the doc's
 * "sorted by distance from the hiker" - and soonest first when it is not,
 * because with no fix the calendar is the only distance that means anything.
 * Rows the reviewed file could not place on the mile axis sort after the
 * placed ones rather than pretending to a distance nobody stated.
 */
export function sortWorkProjects(
  projects: readonly WorkProjectSummary[],
  gpsMile: number | null,
): WorkProjectSummary[] {
  const soonest = (a: WorkProjectSummary, b: WorkProjectSummary) =>
    utcDay(a.starts_on) - utcDay(b.starts_on) || a.id.localeCompare(b.id)

  if (gpsMile === null) return [...projects].sort(soonest)

  return [...projects].sort((a, b) => {
    if (a.mile === null && b.mile === null) return soonest(a, b)
    if (a.mile === null) return 1
    if (b.mile === null) return -1
    return Math.abs(a.mile - gpsMile) - Math.abs(b.mile - gpsMile) || soonest(a, b)
  })
}

/** "Sep 12" or "Sep 12–13", in UTC for publishedConditions.ts's reason: a
 *  hiker in Georgia and one in Maine read the same day off the same row. */
export function workProjectDates(project: WorkProjectSummary): string {
  const day = (value: string) =>
    new Date(value).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      timeZone: 'UTC',
    })
  if (project.starts_on === project.ends_on) return day(project.starts_on)
  return `${day(project.starts_on)}–${day(project.ends_on)}`
}

/** The published document's shape, for useConditions to hold. */
export type PublishedWorkProjects = PublishedConditions<WorkProjectSummary>
