/**
 * One stretch, from the side of the person who looks after it.
 *
 * **AN ALERT FROM THE LAND MANAGER IS NOT THE VOLUNTEER'S TO CLOSE.** A park
 * order, an ATC notice and a county fire restriction are shown, read and
 * obeyed here, and nothing on this screen dismisses one. A maintainer who
 * could clear a park's closure off their own miles is a maintainer who can
 * put a hiker through a bridge that is out.
 *
 * **A CLOSURE NEEDS THREE OTHER VOLUNTEERS OR ONE SUPERVISOR, AND NEVER
 * WAITS ON US.** Closing a stretch turns people around, so it is the one act
 * on this screen a person cannot do alone - and the quorum is other people
 * who walked it, not our review queue. We are not a party to the decision,
 * which is why the screen says "nothing waits on us" rather than "pending
 * approval".
 *
 * **POINTS OF INTEREST AGE, AND THE AGE IS SHOWN RATHER THAN HIDDEN.** The
 * maintainer is the only person who passes them often enough to keep them
 * true, so "last checked Mar 2025" is the prompt. It never nags and never
 * scores: a tap confirms, and walking past without tapping costs nothing.
 *
 * **A THANK YOU NAMES A PLACE, NEVER A PERSON.** `TreadCard`'s own comment
 * makes the same point from the other end - nothing upstream carries a
 * hiker's name, so rule 4 is a shape rather than a setting.
 *
 * **NOTHING HERE IS DELETED.** Resolving an issue is a dated change the
 * supervisor sees, not a row disappearing. An issue that vanished when
 * somebody marked it done is an issue a hiker reported twice.
 */

import { useState } from 'react'
import { PageHeader } from '../components'

export type PoiAge = 'current' | 'needs a look'

export interface TreadPoi {
  readonly id: string
  readonly name: string
  readonly kind: string
  readonly note: string | null
  /** Who last stood at it and when, in the words the card prints. */
  readonly checked: string
  readonly age: PoiAge
}

export interface TreadAlert {
  readonly id: string
  readonly title: string
  readonly where: string
  readonly source: string
  readonly since: string
  readonly kind: string
  readonly detail: string
}

export interface TreadClosure {
  readonly id: string
  readonly title: string
  readonly where: string
  readonly requestedBy: string
  readonly standing: string
  readonly detail: string
  readonly live: boolean
}

export interface TreadIssue {
  readonly id: string
  readonly title: string
  readonly where: string
  readonly on: string
  readonly reportedBy: string
  readonly detail: string
  readonly open: boolean
}

export interface TreadHelpRequest {
  readonly id: string
  readonly title: string
  readonly where: string
  readonly posted: string
  readonly standing: string
}

export interface TreadThankYou {
  readonly id: string
  readonly words: string
  readonly on: string
}

export interface TreadQuestion {
  readonly id: string
  readonly words: string
  readonly on: string
}

export interface TreadRole {
  readonly id: string
  readonly label: string
}

export const TREAD_WINDOWS = ['30 days', '3 months', '1 year', 'All time'] as const
export type TreadWindow = (typeof TREAD_WINDOWS)[number]

export interface YourTreadProps {
  readonly sectionName: string
  readonly range: string
  readonly standing: string
  readonly roles: readonly TreadRole[]
  readonly roleId: string | null
  readonly period: TreadWindow
  readonly pois: readonly TreadPoi[]
  readonly alerts: readonly TreadAlert[]
  readonly closures: readonly TreadClosure[]
  readonly issues: readonly TreadIssue[]
  readonly helpRequests: readonly TreadHelpRequest[]
  readonly thanks: readonly TreadThankYou[]
  readonly questions: readonly TreadQuestion[]
  readonly hoursConfirmed: number
  readonly hoursClaimed: number
  readonly onRole: (roleId: string | null) => void
  readonly onPeriod: (period: TreadWindow) => void
  readonly onConfirmPoi: (poi: TreadPoi) => void
  readonly onEditPoi: (poi: TreadPoi) => void
  readonly onPoiGone: (poi: TreadPoi) => void
  readonly onAddPoi: () => void
  readonly onRequestClosure: () => void
  readonly onResolveIssue: (issue: TreadIssue) => void
  readonly onAskForHelp: (issue: TreadIssue | null) => void
  readonly onAnswer: (question: TreadQuestion, answer: string) => void
  readonly onReportThanks: (thanks: TreadThankYou) => void
}

export function YourTread({
  sectionName,
  range,
  standing,
  roles,
  roleId,
  period,
  pois,
  alerts,
  closures,
  issues,
  helpRequests,
  thanks,
  questions,
  hoursConfirmed,
  hoursClaimed,
  onRole,
  onPeriod,
  onConfirmPoi,
  onEditPoi,
  onPoiGone,
  onAddPoi,
  onRequestClosure,
  onResolveIssue,
  onAskForHelp,
  onAnswer,
  onReportThanks,
}: YourTreadProps) {
  const [poiQuery, setPoiQuery] = useState('')
  const [answers, setAnswers] = useState<Record<string, string>>({})

  const stale = pois.filter((poi) => poi.age === 'needs a look').length
  const openIssues = issues.filter((issue) => issue.open)
  const shownPois = pois.filter((poi) => {
    const needle = poiQuery.trim().toLowerCase()
    if (!needle) return true
    return [poi.name, poi.kind, poi.note ?? ''].join(' ').toLowerCase().includes(needle)
  })

  return (
    <>
      <PageHeader
        eyebrow={`Your section · ${range}`}
        title={sectionName}
        sub={
          <>
            {standing}
            <br />
            Every boot that walks it walks on your work.
          </>
        }
        glyph={
          <>
            <path d="M3 17.5 9 7l4 6.5L16 9l5 8.5z" />
          </>
        }
      />

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Role</h2>
        </div>
        <div className="org-chips">
          <button
            type="button"
            className="org-chip"
            aria-pressed={roleId === null}
            onClick={() => onRole(null)}
          >
            All my roles
          </button>
          {roles.map((role) => (
            <button
              key={role.id}
              type="button"
              className="org-chip"
              aria-pressed={roleId === role.id}
              onClick={() => onRole(role.id)}
            >
              {role.label}
            </button>
          ))}
        </div>
        <div className="org-panel__head">
          <h2>Showing</h2>
        </div>
        <div className="org-chips">
          {TREAD_WINDOWS.map((entry) => (
            <button
              key={entry}
              type="button"
              className="org-chip"
              aria-pressed={period === entry}
              onClick={() => onPeriod(entry)}
            >
              {entry}
            </button>
          ))}
        </div>
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Points of interest</h2>
          <span className="org-panel__count">{pois.length} on your miles</span>
        </div>
        <p className="org-panel__note">
          Water, shelters, privies, viewpoints, parking. You are the only person who
          passes these often enough to keep them true.
          {stale > 0 ? (
            <>
              {' '}
              <strong>
                {stale} of these {stale === 1 ? 'was' : 'were'} last checked more than a
                year ago.
              </strong>{' '}
              If you walk past, a tap keeps {stale === 1 ? 'it' : 'them'} honest.
            </>
          ) : null}
        </p>
        <label className="org-field">
          <span className="org-field__label">Search your points of interest</span>
          <input
            className="org-input"
            value={poiQuery}
            placeholder="Name, type, note…"
            onChange={(event) => setPoiQuery(event.target.value)}
          />
        </label>
        {shownPois.length === 0 ? (
          <div className="org-empty">
            <h3>
              {pois.length === 0
                ? 'Nothing mapped on your miles yet'
                : 'Nothing matches that'}
            </h3>
            <p>
              {pois.length === 0
                ? 'A stretch with no water, no shelter and no parking on it is unusual but not wrong. Add the first one when you walk past it.'
                : 'The search reads a name, a type and the note. Nothing here carries that word.'}
            </p>
          </div>
        ) : (
          <div className="org-stack">
            {shownPois.map((poi) => (
              <div className="org-card" key={poi.id}>
                <div className="org-inline">
                  <span className="org-table__name">{poi.name}</span>
                  <span className="org-mono">{poi.kind}</span>
                  <span
                    className="org-pill"
                    data-tone={poi.age === 'current' ? 'done' : 'waiting'}
                    style={{ marginLeft: 'auto' }}
                  >
                    {poi.age}
                  </span>
                </div>
                <p className="org-mono">{poi.checked}</p>
                {poi.note ? <p className="org-panel__note">{poi.note}</p> : null}
                <div className="org-inline">
                  <button
                    type="button"
                    className="org-btn org-btn--small"
                    onClick={() => onConfirmPoi(poi)}
                  >
                    Still true
                  </button>
                  <button
                    type="button"
                    className="org-btn org-btn--ghost org-btn--small"
                    onClick={() => onEditPoi(poi)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="org-link"
                    onClick={() => onPoiGone(poi)}
                  >
                    gone
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="org-inline">
          <button
            type="button"
            className="org-btn org-btn--ghost org-btn--small"
            onClick={onAddPoi}
          >
            + Add a point of interest
          </button>
        </div>
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Alerts on your miles</h2>
          <span className="org-panel__count">from the park, the ATC and the county</span>
        </div>
        <p className="org-panel__note">
          These come from whoever manages the land, so they are not yours to close. Read
          them before you go out, and before you send anybody else.
        </p>
        {alerts.length === 0 ? (
          <div className="org-empty">
            <h3>Nothing from a land manager right now</h3>
            <p>
              That is what we have been told, not a guarantee the trail is clear. An alert
              nobody published does not reach this page.
            </p>
          </div>
        ) : (
          <div className="org-stack">
            {alerts.map((alert) => (
              <div className="org-callout" data-tone="stop" key={alert.id}>
                <span>
                  <strong>{alert.title}</strong> · {alert.where} · {alert.source} · since{' '}
                  {alert.since} · {alert.kind}
                  <br />
                  {alert.detail}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Close a stretch</h2>
          <span className="org-panel__count">3 volunteers, or 1 supervisor</span>
        </div>
        <p className="org-panel__note">
          You can ask for your own miles to be closed to hikers. Because a closure turns
          people around, it needs <strong>three other volunteers who have seen it</strong>{' '}
          or <strong>one supervisor</strong> before it reaches the map. Nothing waits on
          us.
        </p>
        {closures.length === 0 ? (
          <p className="org-mono">Nothing asked for and nothing standing.</p>
        ) : (
          <div className="org-stack">
            {closures.map((closure) => (
              <div className="org-card" key={closure.id}>
                <div className="org-inline">
                  <span className="org-table__name">{closure.title}</span>
                  <span className="org-mono">{closure.where}</span>
                  <span
                    className="org-pill"
                    data-tone={closure.live ? 'stopped' : 'waiting'}
                    style={{ marginLeft: 'auto' }}
                  >
                    {closure.live ? 'showing to hikers' : closure.standing}
                  </span>
                </div>
                <p className="org-mono">requested by {closure.requestedBy}</p>
                <p className="org-panel__note">{closure.detail}</p>
              </div>
            ))}
          </div>
        )}
        <div className="org-inline">
          <button type="button" className="org-btn" onClick={onRequestClosure}>
            Request a closure
          </button>
        </div>
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Reported issues</h2>
          <span className="org-panel__count">{openIssues.length} still open</span>
        </div>
        <p className="org-panel__note">
          Close one when you have been out and dealt with it. Your supervisor sees the
          change; nothing is deleted.
        </p>
        {issues.length === 0 ? (
          <div className="org-empty">
            <h3>Nothing reported on your miles</h3>
            <p>
              Which means nobody has told us, not that nothing is wrong. Most of what a
              hiker walks past never gets reported at all.
            </p>
          </div>
        ) : (
          <div className="org-stack">
            {issues.map((issue) => (
              <div className="org-card" key={issue.id}>
                <div className="org-inline">
                  <span className="org-table__name">{issue.title}</span>
                  <span className="org-mono">
                    {issue.where} · {issue.on} · {issue.reportedBy}
                  </span>
                  <span
                    className="org-pill"
                    data-tone={issue.open ? 'waiting' : 'done'}
                    style={{ marginLeft: 'auto' }}
                  >
                    {issue.open ? 'open' : 'resolved'}
                  </span>
                </div>
                <p className="org-panel__note">{issue.detail}</p>
                {issue.open ? (
                  <div className="org-inline">
                    <button
                      type="button"
                      className="org-btn org-btn--small"
                      onClick={() => onResolveIssue(issue)}
                    >
                      Mark resolved
                    </button>
                    <button
                      type="button"
                      className="org-btn org-btn--ghost org-btn--small"
                      onClick={() => onAskForHelp(issue)}
                    >
                      Ask for help
                    </button>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Ask other volunteers for help</h2>
          <span className="org-panel__count">
            {helpRequests.length} open{' '}
            {helpRequests.length === 1 ? 'request' : 'requests'}
          </span>
        </div>
        <p className="org-panel__note">
          Some jobs are not a one-person job. Post what you need and it reaches the crews
          working near you, plus your supervisor.
        </p>
        <div className="org-stack">
          {helpRequests.map((request) => (
            <div className="org-card" key={request.id}>
              <div className="org-inline">
                <span className="org-table__name">{request.title}</span>
                <span className="org-mono">{request.where}</span>
                <span className="org-mono" style={{ marginLeft: 'auto' }}>
                  posted {request.posted}
                </span>
              </div>
              <p className="org-mono">{request.standing}</p>
            </div>
          ))}
        </div>
        <div className="org-inline">
          <button
            type="button"
            className="org-btn org-btn--ghost org-btn--small"
            onClick={() => onAskForHelp(null)}
          >
            Request help
          </button>
        </div>
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Thank yous</h2>
          <span className="org-panel__count">{period}</span>
        </div>
        <p className="org-panel__note">From hikers who walked your miles.</p>
        {thanks.length === 0 ? (
          <div className="org-empty">
            <h3>None in this window</h3>
            <p>
              Most people who are glad of a cleared blowdown never say so. An empty list
              is not a verdict on the work.
            </p>
          </div>
        ) : (
          <div className="org-stack">
            {thanks.map((entry) => (
              <div className="org-callout" data-tone="good" key={entry.id}>
                <span>
                  “{entry.words}” · A hiker · {entry.on}{' '}
                  <button
                    type="button"
                    className="org-link"
                    onClick={() => onReportThanks(entry)}
                  >
                    report
                  </button>
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Questions worth answering</h2>
        </div>
        <p className="org-panel__note">
          You know this ground better than anyone. A sentence from you goes on the map for
          every hiker who asks the same thing.
        </p>
        {questions.length === 0 ? (
          <p className="org-mono">Nothing waiting on you.</p>
        ) : (
          <div className="org-stack">
            {questions.map((question) => (
              <div className="org-card" key={question.id}>
                <p className="org-table__name">“{question.words}”</p>
                <p className="org-mono">A hiker · {question.on}</p>
                <label className="org-field">
                  <span className="org-field__label">Answer in a sentence</span>
                  <input
                    className="org-input"
                    value={answers[question.id] ?? ''}
                    onChange={(event) =>
                      setAnswers({ ...answers, [question.id]: event.target.value })
                    }
                  />
                </label>
                <div className="org-inline">
                  <button
                    type="button"
                    className="org-btn org-btn--small"
                    disabled={!(answers[question.id] ?? '').trim()}
                    onClick={() => {
                      onAnswer(question, (answers[question.id] ?? '').trim())
                      setAnswers({ ...answers, [question.id]: '' })
                    }}
                  >
                    Put it on the map
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>This section</h2>
          <span className="org-panel__count">{period}</span>
        </div>
        <div className="org-grid org-grid--three">
          <div className="org-tile">
            <span className="org-tile__label">Thank yous</span>
            <span className="org-tile__value">{thanks.length}</span>
          </div>
          <div className="org-tile">
            <span className="org-tile__label">Issues reported</span>
            <span className="org-tile__value">{issues.length}</span>
          </div>
          <div className="org-tile">
            <span className="org-tile__label">Still open</span>
            <span className="org-tile__value">{openIssues.length}</span>
          </div>
          <div className="org-tile">
            <span className="org-tile__label">Your hours</span>
            <span className="org-tile__value">{hoursConfirmed + hoursClaimed}</span>
            <span className="org-tile__meta">
              {hoursConfirmed} confirmed · {hoursClaimed} claimed
            </span>
          </div>
        </div>
        <p className="org-mono">
          No total across these, and nothing here compares you to anybody.
        </p>
      </section>
    </>
  )
}
