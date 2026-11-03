/**
 * The hiker's half: what you have done, and what you can give.
 *
 * **THIS PAGE OPENS ON THE SMALLEST POSSIBLE ACT, NOT A SIGN-UP FORM.** The
 * first thing on it is a question about a spring somebody walked past today.
 * A page that opened on "join our volunteer programme" would be answered by
 * the people who were already going to, and by nobody else.
 *
 * **ASKING IS OFF UNTIL SOMEBODY TURNS IT ON, AND TURNING IT OFF STOPS THE
 * ASKING, NOT THE RECORD.** A prompt a hiker did not ask for, arriving while
 * they are walking, is the failure mode this whole feature has to avoid - so
 * the default is silence and the switch is one tap, and what they already
 * filed stays theirs either way.
 *
 * **A CLAIMED HOUR COUNTS IMMEDIATELY, INCLUDING FOR A FEE EXEMPTION.** The
 * hiker claims, the organization confirms, and the claim is live in every
 * total until somebody disputes it. The state travels with the hour wherever
 * it is shown or exported, because an exemption resting on an hour whose
 * standing is not visible is an argument at a permit desk.
 *
 * **NOTHING HERE KEEPS SCORE.** There is no total across the tiles and no
 * comparison to another volunteer. The field-note count is absent rather than
 * estimated: the phone forgets a note once it sends, so we say so instead of
 * inventing a number - which is the `@unvalidated` habit applied to a figure
 * we could easily have faked.
 *
 * **SIGNING UP IS AN INTRODUCTION, NOT AN ENROLMENT.** Waivers, minimum ages
 * and tool training are the organization's to state; we show their answer and
 * never a tick of our own.
 */

import { PageHeader, WorkdaysWidget } from '../components'
import type { Workday } from '../orgApi'

export type HourState = 'claimed' | 'confirmed' | 'disputed'

export interface LoggedHour {
  readonly id: string
  readonly on: string
  readonly hours: number
  readonly what: string
  /** Why it stands where it does, in the words the row prints. */
  readonly standing: string
  readonly state: HourState
}

export interface PassedPlace {
  readonly id: string
  readonly name: string
  readonly kind: string
  readonly ask: string
}

export interface HandBackProps {
  readonly askingOn: boolean
  readonly passedToday: readonly PassedPlace[]
  readonly hours: readonly LoggedHour[]
  readonly hoursConfirmed: number
  readonly hoursClaimed: number
  readonly workdaysAttended: number
  readonly conditionsConfirmed: number
  readonly conditionsDetail: string
  readonly sectionsHeld: number
  readonly sectionsSince: string | null
  readonly crews: readonly Workday[]
  /** How old the crews file is, so "opportunities" can stop being claimed. */
  readonly crewsFetchedHoursAgo: number | null
  readonly summaryShown: boolean
  readonly onToggleAsking: (on: boolean) => void
  readonly onAnswerPlace: (place: PassedPlace) => void
  readonly onLogHours: () => void
  readonly onOpenRidgeRunner: () => void
  readonly onToggleSummary: () => void
  readonly onExport: () => void
  readonly onSeeOnMap: () => void
  readonly onSignUp: (workday: Workday) => void
}

/** How stale the crews list is allowed to get before we stop calling it one.
 *
 *  @unvalidated Two days is the wireframe's own number and nobody has checked
 *  it against how fast a club actually moves a workday. What would settle it
 *  is the observed lag between a change on a club's calendar and the mirror
 *  reading it, which the mirror could measure once it is running against real
 *  feeds. Until then it is a round number chosen to be shorter than a week.
 */
export const CREWS_STALE_AFTER_HOURS = 48

export function HandBack({
  askingOn,
  passedToday,
  hours,
  hoursConfirmed,
  hoursClaimed,
  workdaysAttended,
  conditionsConfirmed,
  conditionsDetail,
  sectionsHeld,
  sectionsSince,
  crews,
  crewsFetchedHoursAgo,
  summaryShown,
  onToggleAsking,
  onAnswerPlace,
  onLogHours,
  onOpenRidgeRunner,
  onToggleSummary,
  onExport,
  onSeeOnMap,
  onSignUp,
}: HandBackProps) {
  const stale =
    crewsFetchedHoursAgo !== null && crewsFetchedHoursAgo > CREWS_STALE_AFTER_HOURS

  return (
    <>
      <PageHeader
        eyebrow="Volunteer · the hiker's half"
        title="What you can hand back"
        sub={
          <>
            This page opens on the smallest possible act, not a sign-up form. Crews and
            calendars live on Today; this is your own half — what you have done, and what
            you can give.
          </>
        }
        glyph={
          <>
            <path d="M12 20s-7-4.4-7-9.2A4 4 0 0 1 12 8a4 4 0 0 1 7 2.8C19 15.6 12 20 12 20z" />
          </>
        }
      />

      <section className="org-card org-panel">
        <div className="org-panel__head">
          <h2>Help keep the map true</h2>
          <span className="org-pill" data-tone={askingOn ? 'done' : 'quiet'}>
            {askingOn ? 'on' : 'off by default'}
          </span>
        </div>
        <p className="org-panel__note">
          <strong>Ask me about the places I pass.</strong> Water first, then shelters and
          campsites, then everything else. A photo is offered, never required. Off unless
          you turn it on — and turning it off stops the asking, not your record.
        </p>
        <div className="org-inline">
          <button
            type="button"
            className={askingOn ? 'org-btn org-btn--ghost' : 'org-btn'}
            onClick={() => onToggleAsking(!askingOn)}
          >
            {askingOn ? 'Stop asking me' : 'Ask me about places I pass'}
          </button>
        </div>
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Places you passed today</h2>
        </div>
        <p className="org-panel__note">
          A shortcut for logging from memory at camp. It does not keep score and it will
          never tell you what you skipped.
        </p>
        {passedToday.length === 0 ? (
          <div className="org-empty">
            <h3>Nothing to ask you about</h3>
            <p>
              Either you have not moved past a mapped place today, or the asking is off.
              Both are fine and neither is a gap in your record.
            </p>
          </div>
        ) : (
          <div className="org-stack">
            {passedToday.map((place) => (
              <div className="org-card" key={place.id}>
                <div className="org-inline">
                  <span className="org-table__name">{place.name}</span>
                  <span className="org-mono">{place.kind}</span>
                  <button
                    type="button"
                    className="org-btn org-btn--ghost org-btn--small"
                    style={{ marginLeft: 'auto' }}
                    onClick={() => onAnswerPlace(place)}
                  >
                    {place.ask}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Your hours</h2>
          <span className="org-panel__count">claimed · confirmed · disputed</span>
        </div>
        <p className="org-panel__note">
          You claim them, the organization confirms them. A claim counts everywhere
          immediately — the fee exemption included — until an organization disputes it,
          and the state travels with every hour wherever it is shown or exported.
        </p>
        {hours.length === 0 ? (
          <div className="org-empty">
            <h3>Nothing logged yet</h3>
            <p>
              Hours are yours to claim rather than ours to award. Log the first one
              whenever you have done something; nobody has to approve it before it counts.
            </p>
          </div>
        ) : (
          <div className="org-card org-card--flush">
            <table className="org-table">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Hrs</th>
                  <th scope="col">What</th>
                  <th scope="col">State</th>
                </tr>
              </thead>
              <tbody>
                {hours.map((hour) => (
                  <tr key={hour.id}>
                    <td className="org-mono">{hour.on}</td>
                    <td className="org-table__num">{hour.hours.toFixed(1)}</td>
                    <td>
                      <span className="org-table__name">{hour.what}</span>
                      <div className="org-mono">{hour.standing}</div>
                    </td>
                    <td>
                      <span
                        className="org-pill"
                        data-tone={
                          hour.state === 'confirmed'
                            ? 'done'
                            : hour.state === 'claimed'
                              ? 'waiting'
                              : 'stopped'
                        }
                      >
                        {hour.state}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="org-inline">
          <button type="button" className="org-btn" onClick={onLogHours}>
            + Log hours
          </button>
        </div>
      </section>

      <section className="org-card org-panel">
        <div className="org-panel__head">
          <h2>Ridge Runner At-Large</h2>
          <span className="org-panel__count">seven days, maximum</span>
        </div>
        <p className="org-panel__note">
          Working while you walk — pick a window and what you will watch for, and the app
          puts those tasks at the front for that week.
        </p>
        <div className="org-inline">
          <button
            type="button"
            className="org-btn org-btn--ghost"
            onClick={onOpenRidgeRunner}
          >
            Open Ridge Runner
          </button>
        </div>
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>What you've put back</h2>
          <button type="button" className="org-link" onClick={onToggleSummary}>
            {summaryShown ? 'Hide the summary' : 'Show the summary'}
          </button>
        </div>
        {summaryShown ? (
          <>
            <span className="org-eyebrow">Kept for you, seen by no one</span>
            <div className="org-grid org-grid--three">
              <div className="org-tile">
                <span className="org-tile__label">Hours logged</span>
                <span className="org-tile__value">
                  {(hoursConfirmed + hoursClaimed).toFixed(1)}
                </span>
                <span className="org-tile__meta">
                  {hoursConfirmed.toFixed(1)} confirmed · {hoursClaimed.toFixed(1)}{' '}
                  claimed
                </span>
              </div>
              <div className="org-tile">
                <span className="org-tile__label">Workdays attended</span>
                <span className="org-tile__value">{workdaysAttended}</span>
                <span className="org-tile__meta">confirmed by your organization</span>
              </div>
              <div className="org-tile">
                <span className="org-tile__label">Conditions confirmed</span>
                <span className="org-tile__value">{conditionsConfirmed}</span>
                <span className="org-tile__meta">{conditionsDetail}</span>
              </div>
              <div className="org-tile">
                <span className="org-tile__label">
                  {sectionsHeld === 1
                    ? 'Section you look after'
                    : 'Sections you look after'}
                </span>
                <span className="org-tile__value">{sectionsHeld}</span>
                {sectionsSince ? (
                  <span className="org-tile__meta">since {sectionsSince}</span>
                ) : null}
              </div>
            </div>
            <p className="org-mono">
              No total across these, and nothing here compares you to anybody. We do not
              keep a count of the field notes you filed — the phone forgets them once they
              send, so we would rather say that than invent a number.
            </p>
            <div className="org-inline">
              <button
                type="button"
                className="org-btn org-btn--ghost org-btn--small"
                onClick={onExport}
              >
                Export CSV
              </button>
              <button
                type="button"
                className="org-btn org-btn--ghost org-btn--small"
                onClick={onSeeOnMap}
              >
                See it on a map
              </button>
            </div>
          </>
        ) : (
          <p className="org-mono">
            Hidden because you asked. It is kept either way and shown to nobody else.
          </p>
        )}
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Crews near you</h2>
          <span className="org-panel__count">next 14 days</span>
        </div>
        <p className="org-panel__note">
          The full list lives on Today.{' '}
          {crewsFetchedHoursAgo === null
            ? 'Nothing fetched yet, so this is empty rather than current.'
            : `Read from a file fetched ${crewsFetchedHoursAgo} ${crewsFetchedHoursAgo === 1 ? 'hour' : 'hours'} ago.`}
        </p>
        {stale ? (
          <div className="org-callout" data-tone="warn">
            <span>
              <strong>This list is out of date.</strong> Past about two days we stop
              calling these opportunities and say so instead — a workday that moved on an
              organization's own calendar is a drive to the wrong trailhead.
            </span>
          </div>
        ) : null}
        <WorkdaysWidget
          workdays={crews}
          onSignUp={onSignUp}
          emptyNote="No crews within the window near you. That is the honest answer rather than a widened search."
        />
        <div className="org-callout" data-tone="info">
          <span>
            <strong>Signing up is an introduction, not an enrolment.</strong> Waivers,
            minimum ages and tool training are the organization's to state — we show you
            their answer, never a tick of our own. The organization confirms; we never
            mark you confirmed ourselves.
          </span>
        </div>
      </section>
    </>
  )
}
