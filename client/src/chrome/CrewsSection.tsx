// Every crew this app lists, and the two shapes a hiker sees them in
// (#1440, D18-D22, frames 14g-14k).
//
// TWO SHAPES, ONE FILE, because they are two readings of one list and the
// handoff's rule for them is that they "cannot drift":
//
//   - `screen` - volunteer mode, where TODAY IS THE CREWS SCREEN: the crews
//     out today (the only urgent part), the List/Calendar switch, the window
//     filter, then the view.
//   - `walking` - the hiking modes, where the same crews arrive on a
//     different test and as TRAIL INFORMATION BEFORE THEY ARE AN INVITATION.
//     A crew rebuilding tread means tools out and a possible short hold-up,
//     which is the honest reason it belongs on a screen somebody opened to go
//     walking. The invitation rides along; it does not lead.
//
// WHY THIS IS NOT IN screens/Today.tsx, where it renders. Today is the first
// frame and is deliberately eager (screens/deferred.ts); this section pulls a
// calendar, a row component and six selection helpers behind it, and imported
// statically it put the launch budget 1,641 bytes over
// (features/LAUNCH_BUDGET.md §3, measured 2026-09-15). That is exactly what
// happened to chrome/FieldNoteSection.tsx in #1374's review, and the answer
// is the same one: declare it in `deferred.ts` and let Today render it
// through the loader.
//
// BOTH ABSENCES REPLACE EVERYTHING, and never hedge a list row by row - "a
// hedged invitation still reads as an invitation", and sending somebody to a
// trailhead for a workday cancelled on Thursday is this feature's own failure
// mode. In the calendar that means an empty grid.
//
// NOTHING HERE COUNTS ANYBODY. No score, no streak, no total - the guardrail
// four docs share, and the reason a calendar day stops adding dots at four.

import { useState } from 'react'
import type { HikerMode } from '../lib/hikerMode'
import { longDayLabel } from '../lib/planDisplay'
import { syncAgeLabel } from '../lib/syncAge'
import {
  WORKDAY_WINDOWS,
  opportunitiesUsable,
  sortWorkProjects,
  upcomingWorkProjects,
  workProjectDates,
  workdayAwayLine,
  type WorkProjectSummary,
  type WorkdayWindowId,
} from '../lib/workProjects'
import {
  crewOffWalkLine,
  crewWalkPositionLine,
  crewsAlongWalk,
  crewsOutToday,
  workdayCalendarMonth,
  type WalkSpan,
} from '../lib/crews'
import { WorkdayCalendar } from './WorkdayCalendar'
import { WorkdayRow } from './WorkdayRow'

export interface CrewsSectionProps {
  mode: HikerMode
  now: Date
  /** The published workdays, or null when no artifact has been read - which
   *  is a different claim from an empty list and is rendered differently. */
  opportunities: readonly WorkProjectSummary[] | null
  /** The bake's clock, for the age line and the 48-hour ceiling. */
  opportunitiesAsOf: Date | null
  /** The hiker's own trail mile, or null - which prints no distance rather
   *  than one measured from a position nobody has. */
  gpsMile: number | null
  /** The stretch being walked, in walking order, or null - see
   *  screens/Today.tsx's `todayWalk` for when it is null and why. */
  todayWalk: WalkSpan | null
  /** Open the Map tab with the workday layer on. Absent draws no door. */
  onSeeCrewsOnMap?: (() => void) | undefined
}

export function CrewsSection({
  mode,
  now,
  opportunities,
  opportunitiesAsOf,
  gpsMile,
  todayWalk,
  onSeeCrewsOnMap,
}: CrewsSectionProps) {
  /**
   * THIS SECTION'S OWN STATE.
   *
   * Session state rather than a preference, for chrome/workdayPanel.tsx's
   * reason about the same three windows: which weekend a hiker is looking at
   * is not a setting.
   */
  const [crewView, setCrewView] = useState<'list' | 'calendar'>('list')
  const [crewWindow, setCrewWindow] = useState<WorkdayWindowId>('fortnight')
  const [crewDay, setCrewDay] = useState<string | null>(null)

  /**
   * THE ONE STALENESS GATE THE WHOLE SECTION READS (D19).
   *
   *   - `unchecked` - no artifact has been read. NOT the same claim as an
   *     empty one: "could not check" must never read as "no club has asked"
   *     (#249's rule).
   *   - `stale` - older than OPPORTUNITIES_STALE_MS.
   */
  const crewsUnchecked = opportunities === null
  const crewsStale =
    !crewsUnchecked &&
    (opportunitiesAsOf === null || !opportunitiesUsable(opportunitiesAsOf, now))
  /** Everything below reads this one list - the out-today block, the filtered
   *  list, the calendar and both hiking headings. */
  const crewsUsable: readonly WorkProjectSummary[] =
    opportunities !== null && !crewsStale ? opportunities : []

  /** Both absences, in the words every surface uses for them. */
  const crewsAbsence = crewsUnchecked ? (
    <p className="today__crews-note">
      The workday list needs signal to load, and hasn’t yet.
    </p>
  ) : crewsStale ? (
    <p className="today__crews-note" role="status">
      {`This list is out of date — last updated ${opportunitiesAsOf === null ? 'we cannot tell when' : syncAgeLabel(opportunitiesAsOf, now)}. A workday can be cancelled after a list this old was written, so check with the club before traveling to one.`}
    </p>
  ) : null

  const crewsAge =
    opportunitiesAsOf !== null && !crewsUnchecked && !crewsStale
      ? `Updated ${syncAgeLabel(opportunitiesAsOf, now)}.`
      : null

  /** The meta line every crew row carries, before whichever distance the
   *  surface measures: the club, then the dates. One home for the pair. */
  const crewMeta = (project: WorkProjectSummary) => [
    project.club_name,
    workProjectDates(project),
  ]

  const capacityPart = (project: WorkProjectSummary) =>
    project.capacity === null ? [] : [`room for ${project.capacity}`]

  /**
   * CREWS ON TODAY IN THE HIKING MODES (#1440, D18, frame 14k).
   *
   * TRAIL INFORMATION BEFORE IT IS AN INVITATION, which is the whole reason
   * this belongs on a screen somebody opened to go walking: a crew rebuilding
   * tread means tools out, a possible short hold-up, and somebody to say
   * hello to. The invitation rides along; it does not lead.
   *
   * Two headings rather than one list, because they answer different
   * questions and a hiker mid-walk is asking the first. And ONLY when there
   * are crews - no empty heading, because an absence announced every morning
   * is the app talking about itself.
   *
   * A crew the file never placed on the mile axis is in NEITHER: with no mile
   * there is no way to say it is on the route, and printing it under either
   * heading would claim a relationship nobody established. It keeps its place
   * in the volunteer list, which is the surface that can hold it honestly.
   */
  const walkingCrews = (() => {
    if (mode === 'volunteer' || todayWalk === null) return null
    // A DAY HIKE ASKS ABOUT TODAY; A LONG HIKE ASKS ABOUT THE MILES AHEAD.
    // The two are different questions and the section answers whichever the
    // mode is asking: a day hiker wants to know who they will meet on this
    // walk, and a thru-hiker three weeks out can time a crew they will reach
    // on Thursday. The span itself is the shell's - see `todayWalk`.
    const source =
      mode === 'day'
        ? crewsOutToday(crewsUsable, now)
        : upcomingWorkProjects(crewsUsable, now)
    const { onRoute, nearby } = crewsAlongWalk(source, todayWalk)
    if (onRoute.length === 0 && nearby.length === 0) return null

    /** "today" for a walk happening now; the dates for a crew days out. */
    const whenPart = (project: WorkProjectSummary) =>
      mode === 'day' ? 'today' : workProjectDates(project)

    return (
      <section className="today__crews" aria-label="Crews out today">
        {onRoute.length > 0 && (
          <>
            <div className="today__rule">
              <span className="today__rule-label">
                {mode === 'long'
                  ? 'Crews on the miles ahead'
                  : onRoute.length === 1
                    ? 'A crew on your walk today'
                    : 'Crews on your walk today'}
              </span>
            </div>
            <ul className="today__crew-list">
              {onRoute.map(({ project, mileOfWalk }) => (
                <WorkdayRow
                  key={project.id}
                  title={project.title}
                  meta={[
                    project.club_name,
                    whenPart(project),
                    crewWalkPositionLine(mileOfWalk),
                  ]}
                  // OUR sentence, kept apart from the club's own words below
                  // it - see WorkdayRow. It says what a hiker will meet
                  // before it says anything about joining.
                  lead={
                    mode === 'day'
                      ? 'You will pass them. Expect tools out and a possible short hold-up — and walk-up hands are welcome if you have an hour.'
                      : undefined
                  }
                  description={project.description}
                  contact={project.signup_contact}
                />
              ))}
            </ul>
          </>
        )}
        {nearby.length > 0 && (
          <>
            <div className="today__rule">
              <span className="today__rule-label">Nearby, not on your route</span>
            </div>
            <ul className="today__crew-list">
              {nearby.map(({ project, offRouteMi }) => (
                <WorkdayRow
                  key={project.id}
                  title={project.title}
                  meta={[
                    project.club_name,
                    whenPart(project),
                    crewOffWalkLine(offRouteMi),
                  ]}
                  description={project.description}
                  contact={project.signup_contact}
                />
              ))}
            </ul>
          </>
        )}
      </section>
    )
  })()

  /**
   * IN VOLUNTEER MODE, TODAY IS THE CREWS SCREEN (#1440, D22).
   *
   * One scrolling screen in this order: the crews out TODAY, which is the
   * only urgent part; then the switch; then the window filter; then the view.
   * Not behind a link, because this is the recruitment moment the whole
   * feature exists for and it happens on a screen the hiker already opens.
   *
   * What stays on the Volunteer page is the hiker's own half - the conditions
   * toggle, the places they passed, their hours, the private record. Today
   * answers "what is happening"; the page answers "what have I done, and what
   * can I hand back".
   *
   * THE KIND-OF-WORK CHIPS ARE ABSENT, and that is D20 rather than an
   * omission: `WorkProjectSummary` has no `work_type`, and until the field is
   * in the bake the row renders NOTHING - not greyed, and never inferred from
   * the title. Keyword-sniffing a club's own wording would file crews under
   * labels nobody chose and hide them behind a chip that looks authoritative.
   *
   * THE MAP IS A DOOR RATHER THAN THE THIRD VIEW frame 14i draws, and that is
   * the one place this falls short of the design. The canvas it would need is
   * the app's single MapLibre instance: map/MapView.tsx takes 86 props, and
   * a second instance on this screen is a memory cost nobody has measured on
   * a phone - the same gap this file already records for the day's route
   * thumbnail. So the map view is the Map tab, where the workday layer, the
   * in-view list and its "3 of 4" count already live, and the pins now carry
   * their dates. What would settle it is the map canvas being mountable in a
   * second, small viewport at once, which nothing in chrome/MapScreen.tsx
   * does today.
   */
  const crewsScreen = (() => {
    if (mode !== 'volunteer') return null

    const outToday = sortWorkProjects(crewsOutToday(crewsUsable, now), gpsMile)
    const windowed = sortWorkProjects(
      upcomingWorkProjects(crewsUsable, now, crewWindow),
      gpsMile,
    )
    const month = workdayCalendarMonth(crewsUsable, now)
    const dayCrews =
      crewDay === null
        ? []
        : (month.cells.find((cell) => cell.date === crewDay)?.crews ?? [])

    const awayPart = (project: WorkProjectSummary) =>
      project.mile === null || gpsMile === null
        ? []
        : [workdayAwayLine(Math.abs(project.mile - gpsMile))]

    return (
      <section className="today__crews" aria-label="Crews">
        {outToday.length > 0 && (
          <>
            <div className="today__rule">
              <span className="today__rule-label">Crews out today</span>
              {crewsAge !== null && <span className="today__rule-age">{crewsAge}</span>}
            </div>
            <ul className="today__crew-list">
              {outToday.map((project) => (
                <WorkdayRow
                  key={project.id}
                  title={project.title}
                  meta={[
                    ...crewMeta(project),
                    ...awayPart(project),
                    ...capacityPart(project),
                  ]}
                  description={project.description}
                  contact={project.signup_contact}
                />
              ))}
            </ul>
          </>
        )}

        <div className="today__rule">
          <span className="today__rule-label">Upcoming crews</span>
        </div>

        {/* THE SWITCH. Two views and a door, rather than three views, and the
            door says where it goes - a segment that navigated away would be a
            control lying about being a view. */}
        <div className="today__crew-views" role="group" aria-label="How to see the crews">
          {(['list', 'calendar'] as const).map((view) => (
            <button
              key={view}
              type="button"
              className={
                crewView === view
                  ? 'today__crew-view today__crew-view--on'
                  : 'today__crew-view'
              }
              aria-pressed={crewView === view}
              onClick={() => setCrewView(view)}
            >
              {view === 'list' ? 'List' : 'Calendar'}
            </button>
          ))}
        </div>

        {/* WHEN. `WORKDAY_WINDOWS` as they are - three windows rather than a
            date picker, because a crew is planned around a weekend or not at
            all. Filters narrow what is ALREADY in the artifact and never
            trigger a fetch: this layer needs signal, and a chip that quietly
            fails offline is a control that lies. */}
        <div className="today__crew-filters" role="group" aria-label="When">
          {WORKDAY_WINDOWS.map((option) => (
            <button
              key={option.id}
              type="button"
              className={
                crewWindow === option.id
                  ? 'today__crew-chip today__crew-chip--on'
                  : 'today__crew-chip'
              }
              aria-pressed={crewWindow === option.id}
              onClick={() => setCrewWindow(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>

        {crewsAbsence ??
          (crewView === 'list' ? (
            windowed.length === 0 ? (
              // WHICH CHIP EMPTIED IT, rather than the honest-absence copy -
              // which would let a hiker conclude no club has asked when what
              // happened is that they narrowed the window.
              <p className="today__crews-note">
                {crewWindow === 'month'
                  ? 'No workdays are posted here yet. Clubs add them as they schedule crews.'
                  : `Nothing in “${WORKDAY_WINDOWS.find((option) => option.id === crewWindow)?.label}”. There may be crews further out — try “Next 30 days”.`}
              </p>
            ) : (
              <>
                {crewsAge !== null && <p className="today__crews-age">{crewsAge}</p>}
                <ul className="today__crew-list">
                  {windowed.map((project) => (
                    <WorkdayRow
                      key={project.id}
                      title={project.title}
                      meta={[
                        ...crewMeta(project),
                        ...awayPart(project),
                        ...capacityPart(project),
                      ]}
                      description={project.description}
                      contact={project.signup_contact}
                    />
                  ))}
                </ul>
              </>
            )
          ) : (
            <>
              <WorkdayCalendar month={month} selected={crewDay} onSelect={setCrewDay} />
              {crewDay !== null && (
                <>
                  <div className="today__rule">
                    <span className="today__rule-label">{longDayLabel(crewDay)}</span>
                  </div>
                  {dayCrews.length === 0 ? (
                    <p className="today__crews-note">No crew posted for that day.</p>
                  ) : (
                    <ul className="today__crew-list">
                      {dayCrews.map((project) => (
                        <WorkdayRow
                          key={project.id}
                          title={project.title}
                          meta={[
                            project.club_name,
                            ...awayPart(project),
                            ...capacityPart(project),
                          ]}
                          description={project.description}
                          contact={project.signup_contact}
                        />
                      ))}
                    </ul>
                  )}
                </>
              )}
            </>
          ))}

        {onSeeCrewsOnMap !== undefined && (
          <button type="button" className="today__crew-map" onClick={onSeeCrewsOnMap}>
            See the crews on the map ›
          </button>
        )}
      </section>
    )
  })()

  return (
    <>
      {walkingCrews}
      {crewsScreen}
    </>
  )
}
