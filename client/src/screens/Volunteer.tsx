// The Volunteer tab (features/VOLUNTEERING.md, #759) - the screen that
// bridges hiking a trail and maintaining one, which is the reason this
// project exists rather than a feature it happens to want.
//
// The tab is called Volunteer against a real objection - it names a kind of
// person, and someone who does not think they are one may never open it.
// The doc's answer is that the objection is about THE FIRST SCREEN, not the
// word: a tab that opens on a sign-up form earns it, and a tab that opens on
// "the spring you passed at lunch could use a word" does not, because that
// is a thing a person does before they would ever call themselves a
// volunteer. So this screen leads with the smallest possible act and never
// opens on a form.
//
// WHAT THIS SCREEN MUST NEVER DO, from four docs' shared guardrail: no
// counts of contributions, no streaks, no leaderboard, no "you haven't
// volunteered lately", no comparison to anyone. And nothing here is a
// notification or ever becomes one - HIKER_SAFETY.md's wrong-way alert stays
// the only push this app sends.

import type { UnitSystem } from '../lib/units'
import {
  opportunitiesUsable,
  sortWorkProjects,
  upcomingWorkProjects,
  workProjectDates,
  type WorkProjectSummary,
} from '../lib/workProjects'
import { syncAgeLabel } from '../lib/syncAge'
import './volunteer.css'

export interface PassedPlace {
  id: string
  name: string
  type: string
  mile: number
}

export interface VolunteerProps {
  /** The #759 opt-in, read from UserPreferences. */
  contributeConditions: boolean
  onToggleContribute: (next: boolean) => void
  /**
   * Today's walked-past places, oldest mile first (lib/passedToday.ts) -
   * only rendered for a hiker who opted in, because the list is the "asked
   * more thoroughly" surface consent makes legitimate.
   */
  passedToday: readonly PassedPlace[]
  /** Open a place's card on the map - the same card a pin tap opens, where
   *  the one-tap ask lives. The list is a shortcut to it, not a second form. */
  onOpenPlace: (id: string) => void
  units: UnitSystem
  /**
   * The published workdays (#760), or null when no artifact has been read -
   * which is a different claim from an empty list, and rendered differently:
   * "could not check" is never allowed to look like "no club has asked".
   */
  opportunities: readonly WorkProjectSummary[] | null
  /** The bake's clock, for the age line and the 48-hour ceiling. */
  opportunitiesAsOf: Date | null
  /** The hiker's own trail mile, for nearest-first ordering; null sorts by
   *  date instead - with no fix, the calendar is the only honest distance. */
  gpsMile: number | null
  now: Date
  /** Below the contribution section: the opportunities list (#760), hours
   *  (#761) - the tab's later residents, composed by the shell so this
   *  screen does not accumulate their plumbing. */
  children?: React.ReactNode
}

function mileLabel(mile: number, units: UnitSystem): string {
  // The trail's own unit is the mile whichever display unit is chosen for
  // distances; mile markers are signage, not measurement (lib/units.ts's
  // own stance for the header readout).
  void units
  return `mi ${mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}`
}

export function Volunteer({
  contributeConditions,
  onToggleContribute,
  passedToday,
  onOpenPlace,
  units,
  opportunities,
  opportunitiesAsOf,
  gpsMile,
  now,
  children,
}: VolunteerProps) {
  const upcoming =
    opportunities === null
      ? []
      : sortWorkProjects(upcomingWorkProjects(opportunities, now), gpsMile)
  // Out of date replaces the LIST, never hedges it row by row: a hedged
  // invitation still reads as an invitation, and sending someone to a
  // trailhead for a workday cancelled on Thursday is this feature's own
  // failure mode (#760, value #4).
  const opportunitiesStale =
    opportunitiesAsOf !== null && !opportunitiesUsable(opportunitiesAsOf, now)

  return (
    <div className="volunteer" data-testid="volunteer-screen">
      <h1 className="volunteer__title">Volunteer</h1>
      <p className="volunteer__intro">
        The people who cut this tread are volunteers. Everything here is a way to hand
        something back — starting with the smallest one there is.
      </p>

      <section className="volunteer__section" aria-labelledby="volunteer-contribute">
        <h2 id="volunteer-contribute" className="volunteer__heading">
          Trail conditions
        </h2>
        <label className="volunteer__toggle">
          <input
            type="checkbox"
            name="contribute_conditions"
            checked={contributeConditions}
            onChange={(event) => onToggleContribute(event.target.checked)}
          />
          <span className="volunteer__toggle-label">
            Ask me about conditions as I pass things
          </span>
        </label>
        <p className="volunteer__note">
          A one-tap answer on a waypoint’s card — flowing or dry, fine or full — is the
          single most useful thing a hiker can hand the next one. With this on, the card
          offers a longer note too, and today’s water and shelters gather below so you can
          answer from camp.
        </p>
        <p className="volunteer__note">
          Never a notification, and never a score. OurHike only asks when you’re already
          looking.
        </p>
      </section>

      {contributeConditions && passedToday.length > 0 && (
        <section className="volunteer__section" aria-labelledby="volunteer-passed">
          <h2 id="volunteer-passed" className="volunteer__heading">
            Places you passed today
          </h2>
          {/* A shortcut for logging from memory at camp - NOT a scoreboard of
              the day's omissions. The rule that keeps it honest
              (DATA_NUDGES.md): it never counts, and it never mentions what
              was skipped. So: no "3 of 7 answered", no ticks, no dimming of
              the ones walked past. Names and miles, tap to open the card. */}
          <ul className="volunteer__passed">
            {passedToday.map((place) => (
              <li key={place.id}>
                <button
                  type="button"
                  className="volunteer__place"
                  onClick={() => onOpenPlace(place.id)}
                >
                  <span className="volunteer__place-name">{place.name}</span>
                  <span className="volunteer__place-mile">
                    {mileLabel(place.mile, units)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="volunteer__section" aria-labelledby="volunteer-workdays">
        <h2 id="volunteer-workdays" className="volunteer__heading">
          Workdays in the next two weeks
        </h2>

        {opportunities === null ? (
          // Null is "we could not check", and it must not read as "no club
          // has asked" - the two draw the same empty list and mean opposite
          // things about the trail's people (#249's rule, applied here).
          <p className="volunteer__note">
            The workday list needs signal to load, and hasn’t yet.
          </p>
        ) : opportunitiesStale ? (
          <p className="volunteer__note" role="status">
            {`This list is out of date — last updated ${syncAgeLabel(opportunitiesAsOf, now)}. A workday can be cancelled after a list this old was written, so check with the club before traveling to one.`}
          </p>
        ) : upcoming.length === 0 ? (
          <p className="volunteer__note">
            No workdays are posted here yet. Clubs add them as they schedule crews.
          </p>
        ) : (
          <>
            {opportunitiesAsOf !== null && (
              <p className="volunteer__age">
                {`Updated ${syncAgeLabel(opportunitiesAsOf, now)}.`}
              </p>
            )}
            <ul className="volunteer__workdays">
              {upcoming.map((project) => (
                <li key={project.id} className="volunteer__workday">
                  <p className="volunteer__workday-title">{project.title}</p>
                  <p className="volunteer__workday-meta">
                    {project.club_name}
                    <span aria-hidden="true"> · </span>
                    {workProjectDates(project)}
                    {project.mile !== null && gpsMile !== null && (
                      <>
                        <span aria-hidden="true"> · </span>
                        {`${Math.abs(project.mile - gpsMile).toLocaleString('en-US', {
                          maximumFractionDigits: 1,
                        })} trail mi away`}
                      </>
                    )}
                    {project.capacity !== null && (
                      <>
                        <span aria-hidden="true"> · </span>
                        {`room for ${project.capacity}`}
                      </>
                    )}
                  </p>
                  {project.description !== null && (
                    <p className="volunteer__workday-description">
                      {project.description}
                    </p>
                  )}
                  {/* An introduction, not an enrolment (VOLUNTEERING.md):
                      the link is the club's own channel, and the app never
                      renders a roster claim of its own invention. */}
                  {project.signup_contact !== null && (
                    <a
                      className="volunteer__workday-contact"
                      href={project.signup_contact}
                    >
                      Ask the crew about joining
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      {children}
    </div>
  )
}
