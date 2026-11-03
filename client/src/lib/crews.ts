// Crews measured against a hiker - today, and against the stretch they are
// walking (#1440, D18, D21, frames 14g-14k).
//
// WHY THIS IS NOT IN lib/workProjects.ts, which holds everything else about
// the workday layer. That module is imported by screens/Today.tsx for the
// volunteer card's one line, so it lands in the EAGER chunk; these helpers
// are reached only by the deferred crews section, and living beside the rest
// dragged all of them across that boundary regardless of who used them
// (measured 2026-09-15 against features/LAUNCH_BUDGET.md §3).
//
// The split is a real seam rather than a budget dodge. `workProjects.ts`
// answers "what has been published, and may it still be believed" - the
// window, the staleness ceiling, the wording of a date and a distance.
// This file answers "where is a crew relative to THIS hiker, today" - which
// is a question about a walk, and one the map layer and the Volunteer page
// never ask.
//
// One thing is shared deliberately rather than duplicated: the UTC day
// reading (`utcDayOf`). A date means one day everywhere, and two readings of
// `starts_on` is how a Saturday crew comes to show on Friday for half the
// trail.

import {
  DAY_IN_MS,
  utcDayOf,
  WORK_PROJECT_WINDOW_DAYS,
  type WorkProjectSummary,
} from './workProjects'

/**
 * A crew running TODAY - the only urgent part of the whole layer (#1440,
 * D18, frame 14g).
 *
 * **"TODAY" IS THE HIKER'S CALENDAR DAY, NOT UTC'S** (#1447 review). The two
 * halves of the comparison are deliberately read differently, and the split is
 * the whole of what makes it right:
 *
 *   - `starts_on`/`ends_on` are CALENDAR DATES a club published, with no time
 *     and no zone. `utcDayOf` reads them at UTC midnight, the same spelling
 *     `upcomingWorkProjects` uses, so a date still means one day everywhere.
 *   - `now` is a MOMENT, and which calendar day it falls on is a question only
 *     the hiker's own clock can answer. It is read with the local getters and
 *     then expressed in that same UTC-midnight space, so what is compared is
 *     two calendar dates and nothing else.
 *
 * This used to read `now` in UTC too, justified as "a hiker in Georgia and one
 * in Maine read the same row the same way". That argument is about rendering a
 * date and this function is not rendering one - it is answering "is a crew out
 * RIGHT NOW", which is local by construction. The A.T. spans one timezone, so
 * the consistency it bought was worth nothing, while the cost was real: from
 * about 8pm every evening, Eastern being four or five hours behind UTC, a crew
 * starting TOMORROW read as out today. That is the cry-wolf direction on a
 * surface the hiking modes present as trail information.
 *
 * A multi-day crew counts on every day it covers, which is the same `ends_on`
 * test the list keeps - a crew mid-weekend is still out on the Sunday.
 */
export function crewsOutToday(
  projects: readonly WorkProjectSummary[],
  now: Date,
): WorkProjectSummary[] {
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())
  return projects.filter(
    (project) =>
      project.status === 'upcoming' &&
      utcDayOf(project.starts_on) <= today &&
      utcDayOf(project.ends_on) >= today,
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
  // WHICH MONTH, and whose today, both read off the local clock for
  // `crewsOutToday`'s reason above. In UTC these were wrong for the same four
  // or five hours every evening, and visibly so: at 8pm on the 31st the grid
  // opened on the NEXT month, and the day a hiker was still living was already
  // greyed as `past`. The cells themselves stay in UTC-midnight space, because
  // a cell IS a calendar date and that is how `utcDayOf` spells one.
  const year = month.getFullYear()
  const monthIndex = month.getMonth()
  const first = new Date(Date.UTC(year, monthIndex, 1))
  const days = new Date(Date.UTC(year, monthIndex + 1, 0)).getUTCDate()

  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())
  const horizon = today + WORK_PROJECT_WINDOW_DAYS * DAY_IN_MS

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
          utcDayOf(project.starts_on) <= at &&
          utcDayOf(project.ends_on) >= at,
      ),
    })
  }

  return { first, blanks, cells }
}
