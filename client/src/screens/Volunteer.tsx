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
  children,
}: VolunteerProps) {
  return (
    <div className="volunteer" data-testid="volunteer-screen">
      <h1 className="volunteer__title">Volunteer</h1>
      <p className="volunteer__intro">
        The people who cut this tread are volunteers. Everything here is a way
        to hand something back — starting with the smallest one there is.
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
          A one-tap answer on a waypoint’s card — flowing or dry, fine or full —
          is the single most useful thing a hiker can hand the next one. With
          this on, the card offers a longer note too, and today’s water and
          shelters gather below so you can answer from camp.
        </p>
        <p className="volunteer__note">
          Never a notification, and never a score. OurHike only asks when
          you’re already looking.
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

      {children}
    </div>
  )
}
