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
 * The day windows the map's workday list offers (#1373, frame 14d): the
 * tab's own fortnight, the coming weekend, and a month. Three rather than a
 * date picker, because a crew is planned around a weekend or not at all,
 * and the fortnight is VOLUNTEERING.md's number kept as the default.
 */
export const WORKDAY_WINDOWS = [
  { id: 'fortnight', label: 'Next 14 days' },
  { id: 'weekend', label: 'This weekend' },
  { id: 'month', label: 'Next 30 days' },
] as const

export type WorkdayWindowId = (typeof WORKDAY_WINDOWS)[number]['id']

/**
 * What a window covers, as UTC-midnight millis: `from` inclusive, `to`
 * exclusive. "This weekend" is the coming Saturday and Sunday - today's, when
 * today is one of them - so on a Sunday it still names the weekend under
 * way rather than the next one. The calendar is read in UTC because the
 * rows' dates are UTC days (`starts_on`), and a window read in local time
 * would drift a day either side of them at the edges.
 */
export function workdayWindowSpan(
  id: WorkdayWindowId,
  now: Date,
): { from: number; to: number } {
  if (id === 'weekend') {
    const weekday = now.getUTCDay()
    // Sunday is the weekend's second day, so its Saturday was yesterday.
    const untilSaturday = weekday === 0 ? -1 : 6 - weekday
    const saturday = Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth(),
      now.getUTCDate() + untilSaturday,
    )
    return { from: saturday, to: saturday + 2 * DAY_MS }
  }
  const days = id === 'month' ? 30 : WORK_PROJECT_WINDOW_DAYS
  return { from: now.getTime(), to: now.getTime() + days * DAY_MS }
}

/**
 * The rows worth showing: upcoming, not yet over, and starting inside the
 * window. An event already running counts - a crew mid-weekend still takes
 * a walk-up pair of hands - which is why the near bound tests `ends_on`.
 */
export function upcomingWorkProjects(
  projects: readonly WorkProjectSummary[],
  now: Date,
  window: WorkdayWindowId = 'fortnight',
): WorkProjectSummary[] {
  const today = now.getTime()
  const span = workdayWindowSpan(window, now)

  return projects.filter((project) => {
    if (project.status !== 'upcoming') return false
    // ends_on is a whole day, so it ends at the following UTC midnight. A
    // workday that is over is over in every window, the weekend's included.
    const over = utcDay(project.ends_on) + DAY_MS
    if (over <= today || over <= span.from) return false
    return utcDay(project.starts_on) < span.to
  })
}

/**
 * One workday as a list prints it (#1373, frame 14d) - the map's "Workdays
 * in view" and, being the same row, whatever else lists them. The distance
 * is trail miles between the hiker's mile and the row's, or null where
 * either is missing; a straight line would be a different number wearing
 * the same word.
 */
export interface WorkdayRow {
  id: string
  title: string
  club: string
  /** `workProjectDates`' own wording. */
  dates: string
  /** Trail miles from the hiker, or null. */
  awayMi: number | null
  /** Null means "no cap stated", never zero. */
  capacity: number | null
  /** The club's own channel, or null. */
  contact: string | null
  lat: number
  lon: number
}

export function workdayRow(
  project: WorkProjectSummary,
  gpsMile: number | null,
): WorkdayRow | null {
  if (project.lat === null || project.lon === null) return null
  return {
    id: project.id,
    title: project.title,
    club: project.club_name,
    dates: workProjectDates(project),
    awayMi:
      project.mile === null || gpsMile === null ? null : Math.abs(project.mile - gpsMile),
    capacity: project.capacity,
    contact: project.signup_contact,
    lat: project.lat,
    lon: project.lon,
  }
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

/**
 * "8.4 trail mi away": the distance from the hiker's own mile to the
 * workday's, as the Volunteer tab, the pin's sheet and the map's In view
 * list all print it - one string, so the three cannot drift.
 *
 * Trail miles rather than lib/units.ts: this is a difference of two mile
 * markers on the pipeline's axis, which the repo prints as markers
 * (lib/planDisplay.ts's rule), not a measured length a hiker would want in
 * kilometres. Whether a metric hiker is served by that is an open question
 * the three surfaces inherited together (#1374 review).
 */
export function workdayAwayLine(awayMi: number): string {
  return `${awayMi.toLocaleString('en-US', { maximumFractionDigits: 1 })} trail mi away`
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

/**
 * A crew running TODAY - the only urgent part of the whole layer (#1440,
 * D18, frame 14g).
 *
 * "Today" is the row's own UTC day span, matching `upcomingWorkProjects`'
 * reading of `starts_on`/`ends_on` rather than a second one: a date means one
 * day everywhere, and a hiker in Georgia and one in Maine read the same row
 * the same way. A multi-day crew counts on every day it covers, which is the
 * same `ends_on` test the list keeps - a crew mid-weekend is still out on the
 * Sunday.
 */
export function crewsOutToday(
  projects: readonly WorkProjectSummary[],
  now: Date,
): WorkProjectSummary[] {
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())
  return projects.filter(
    (project) =>
      project.status === 'upcoming' &&
      utcDay(project.starts_on) <= today &&
      utcDay(project.ends_on) >= today,
  )
}

/**
 * The stretch a hiker is walking, in walking order (#1440, D18).
 *
 * `start` is where they set off and `end` is where they stop, so `start > end`
 * is a southbound walk and not a mistake. The pair is what makes "mile 4.1 of
 * your walk" computable at all - a mile marker alone cannot say how far into
 * somebody's day a crew is.
 */
export interface WalkSpan {
  start: number
  end: number
}

/**
 * How far off a walk a crew's mile falls: zero when it is on the walk, and
 * the distance to the nearer end when it is not.
 *
 * Null for a crew the reviewed file never placed on the mile axis. That is
 * the honest answer and it has a consequence the callers keep: such a crew
 * appears in NEITHER hiking heading, because with no mile there is no way to
 * say it is on the route, and printing it under either would claim a
 * relationship nobody established. It keeps its place in the full list, which
 * is the only surface that can hold it honestly.
 */
export function crewOffWalkMiles(
  project: WorkProjectSummary,
  walk: WalkSpan,
): number | null {
  if (project.mile === null) return null
  const low = Math.min(walk.start, walk.end)
  const high = Math.max(walk.start, walk.end)
  if (project.mile < low) return low - project.mile
  if (project.mile > high) return project.mile - high
  return 0
}

/**
 * How far into today's walk a crew is - the number that answers "will I meet
 * them" (#1440, frame 14k).
 *
 * Measured from where the hiker SET OFF, not from a mile marker, because a
 * mile marker is a position on the trail and "mile 4.1 of your walk" is a
 * position in somebody's day. Null for a crew that is not on the walk at all.
 */
export function crewMileOfWalk(
  project: WorkProjectSummary,
  walk: WalkSpan,
): number | null {
  if (crewOffWalkMiles(project, walk) !== 0) return null
  return Math.abs((project.mile as number) - walk.start)
}

/**
 * How far off the route a crew may be and still be worth naming as nearby.
 *
 * @unvalidated. Ten trail miles is about half a day at the app's own standard
 * pace (lib/pace.ts's `STANDARD_FLAT_PACE_MPH`, ~3.1 mph), so a crew inside it
 * is somewhere a hiker could reach on the day they are looking at - which is
 * the only sense in which "nearby" means anything on a footpath. That is a
 * reason for the order of magnitude and not a measurement of the number.
 *
 * What would settle it is how far a hiker will actually walk out of their way
 * to join a crew, which nobody has asked and which plausibly differs by the
 * kind of hiker: a thru-hiker on a schedule and somebody out for the weekend
 * are not answering the same question.
 *
 * Erring large is the safer direction here and worth saying why: the cost of
 * too wide is a row a hiker scrolls past, and the cost of too narrow is a
 * crew eight miles away that the app never mentioned.
 */
export const NEARBY_CREW_MILES = 10

/**
 * Today's crews, split the two ways a walking hiker asks about them (#1440,
 * frame 14k): the ones on the walk, soonest along it first, and the ones
 * near it but not on it, nearest first.
 *
 * A crew with no mile is in neither - see `crewOffWalkMiles`.
 */
export function crewsAlongWalk(
  projects: readonly WorkProjectSummary[],
  walk: WalkSpan,
): {
  onRoute: { project: WorkProjectSummary; mileOfWalk: number }[]
  nearby: { project: WorkProjectSummary; offRouteMi: number }[]
} {
  const onRoute: { project: WorkProjectSummary; mileOfWalk: number }[] = []
  const nearby: { project: WorkProjectSummary; offRouteMi: number }[] = []

  for (const project of projects) {
    const off = crewOffWalkMiles(project, walk)
    if (off === null) continue
    if (off === 0) {
      onRoute.push({ project, mileOfWalk: crewMileOfWalk(project, walk) as number })
    } else if (off <= NEARBY_CREW_MILES) {
      nearby.push({ project, offRouteMi: off })
    }
  }

  onRoute.sort(
    (a, b) => a.mileOfWalk - b.mileOfWalk || a.project.id.localeCompare(b.project.id),
  )
  nearby.sort(
    (a, b) => a.offRouteMi - b.offRouteMi || a.project.id.localeCompare(b.project.id),
  )
  return { onRoute, nearby }
}

/** "mile 4.1 of your walk" - the position `crewMileOfWalk` computes, said the
 *  way frame 14k writes it. A distance along a walk rather than a marker on
 *  the trail, so it is not spelled "mi 4.1" the way lib/planDisplay.ts spells
 *  a marker. */
export function crewWalkPositionLine(mileOfWalk: number): string {
  return `mile ${mileOfWalk.toLocaleString('en-US', { maximumFractionDigits: 1 })} of your walk`
}

/** "3.2 trail mi off your walk" - `workdayAwayLine`'s sibling for a crew
 *  measured against a ROUTE rather than against the hiker's own position. Two
 *  strings because they are two claims; one formatter each, so neither can be
 *  re-rounded by a surface. */
export function crewOffWalkLine(offRouteMi: number): string {
  return `${offRouteMi.toLocaleString('en-US', { maximumFractionDigits: 1 })} trail mi off your walk`
}

/** The most dots a day carries before it stops counting (#1440, D21).
 *
 *  A dot is not a count. Two dots means two crews and three means three, and
 *  past this it stops adding them rather than turning a day into a score -
 *  the same rule that keeps every other surface in this app free of one
 *  (OurHikeValues.md #1). Four because a fifth dot is the point at which a
 *  reader stops counting and starts seeing "a lot", which is a comparison. */
export const MAX_DAY_DOTS = 4

/**
 * One cell of the crews calendar.
 *
 * `state` is the honesty of the grid, and it has three values rather than two
 * because a month shows days the published file was never asked about:
 *
 *   - `past` - already gone. The past is over, not unknown.
 *   - `open` - inside the published window, so an empty cell really does mean
 *     no club has posted a crew.
 *   - `beyond` - past today + `WORK_PROJECT_WINDOW_DAYS`. An empty cell out
 *     here would read as "no crew that day" when the truth is "nobody has
 *     said", which is why it is drawn as hatching rather than left blank.
 */
export interface WorkdayCalendarCell {
  /** "YYYY-MM-DD", UTC, matching the rows' own dates. */
  date: string
  dayOfMonth: number
  state: 'past' | 'open' | 'beyond'
  weekend: boolean
  /** The crews covering this day, in the file's order. */
  crews: WorkProjectSummary[]
}

export interface WorkdayCalendarMonth {
  /** The first of the month, for the heading. */
  first: Date
  /** How many empty cells before the 1st, on a Monday-first grid. */
  blanks: number
  cells: WorkdayCalendarCell[]
}

/**
 * A month of crews, with the published window's edge drawn on it (#1440,
 * D21, frame 14j).
 *
 * UTC throughout, for `workProjectDates`' reason: the rows' dates are UTC
 * days, so a hiker in Georgia and one in Maine read the same cell the same
 * way. A local-time grid would put a Saturday crew on Friday for half the
 * trail.
 *
 * A MULTI-DAY CREW DOTS EVERY DAY IT COVERS, matching the list's `ends_on`
 * test: a crew mid-weekend still shows on the Sunday, and a hiker scanning
 * the grid for "is anyone out while I am there" gets the same answer the list
 * gives.
 */
export function workdayCalendarMonth(
  projects: readonly WorkProjectSummary[],
  now: Date,
  /** Which month, as any date inside it. Defaults to the one `now` is in. */
  month: Date = now,
): WorkdayCalendarMonth {
  const year = month.getUTCFullYear()
  const monthIndex = month.getUTCMonth()
  const first = new Date(Date.UTC(year, monthIndex, 1))
  const days = new Date(Date.UTC(year, monthIndex + 1, 0)).getUTCDate()

  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())
  const horizon = today + WORK_PROJECT_WINDOW_DAYS * DAY_MS

  // Monday-first: getUTCDay() is Sunday-first, so Sunday's six columns of
  // lead-in are the one value that does not simply shift by one.
  const weekday = first.getUTCDay()
  const blanks = weekday === 0 ? 6 : weekday - 1

  const cells: WorkdayCalendarCell[] = []
  for (let dayOfMonth = 1; dayOfMonth <= days; dayOfMonth += 1) {
    const at = Date.UTC(year, monthIndex, dayOfMonth)
    const dow = new Date(at).getUTCDay()
    cells.push({
      date: new Date(at).toISOString().slice(0, 10),
      dayOfMonth,
      state: at < today ? 'past' : at > horizon ? 'beyond' : 'open',
      weekend: dow === 0 || dow === 6,
      crews: projects.filter(
        (project) =>
          project.status === 'upcoming' &&
          utcDay(project.starts_on) <= at &&
          utcDay(project.ends_on) >= at,
      ),
    })
  }

  return { first, blanks, cells }
}
