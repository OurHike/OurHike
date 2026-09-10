// Your reports (#1373, frame 9d) - what this phone has reported: the ones
// still waiting for signal, and the ones that went, with what a moderator
// has done about them.
//
// TWO SHELVES, TWO SOURCES, AND THE SCREEN SAYS WHICH IS WHICH. "Waiting to
// send" is the outbox - the only copy of what somebody wrote down, and the
// row stays until it goes (the design's own line). "Sent from this phone" is
// lib/sentReports.ts's ledger: the phone's memory of its own sends, because
// nothing in `GET /reports` says which rows are the hiker's (#252 withholds
// the reporter id from everyone). The status beside a sent row is the live
// list's, joined by id, and is ABSENT rather than guessed when the list has
// not been read or does not hold the row (D14). "Sent 4 Sep" is a fact about
// this phone; "Confirmed" is a fact about the server, and they are never
// blended.
//
// THE FOUR WORDS ARE THE REPOSITORY'S, NOT THE FRAME'S. The frame writes
// "Verified" and "In review" - the moderator's vocabulary. lib/reportStatus.ts
// is the one place the two vocabularies meet, and a reporter reads Waiting /
// Confirmed / Fixed / Not confirmed (WIREFRAMES.md's load-bearing values), so
// "Not confirmed" carries no penalty and this screen prints no "rejected".
//
// NO COUNT THAT READS AS A SCORE. The shelf titles carry a count because a
// list says how long it is; nothing here totals across time, ranks, or
// compares (D12).

import { REPORTER_TYPES } from '../lib/contributionFlow'
import { agoLabel } from '../lib/hikeText'
import type { ReportDraft } from '../lib/outbox'
import type { ReportStateWord } from '../lib/reportStatus'
import { categoryLabel, type ReportTypeId } from '../reporting/categories'
import './plan.css'
import './settings.css'

export interface WaitingReportRow {
  id: string
  type: ReportTypeId
  /** The place, as the phone can name it: the waypoint's name, a retired
   *  place's last name, "mi 1,347.2", or "the trail". */
  place: string
  /** ISO timestamp - the moment of the tap. */
  authoredAt: string
}

export interface SentReportRow {
  id: string
  type: ReportTypeId
  place: string
  authoredAt: string
  sentAt: string
  /** The live list's word for it, or null where the list has not been
   *  read or does not carry this id. */
  state: ReportStateWord | null
}

export interface YourReportsProps {
  waiting: readonly WaitingReportRow[]
  sent: readonly SentReportRow[]
  /** Whether the live list has been read this session. Decides which of two
   *  honest sentences explains a missing status. */
  statusesRead: boolean
  /** The phone's own signing - a preference, never something the server
   *  says - or null with no trail name set. */
  signedAs: { trailName: string; reporterType: ReportDraft['reporter_type'] } | null
  /** YYYY-MM-DD, the phone's local day, for "written yesterday". */
  today: string
}

function whenLabel(verb: string, iso: string, today: string): string {
  const ago = agoLabel(iso.slice(0, 10), today)
  return ago === null ? verb : `${verb} ${ago}`
}

function reporterLabel(type: ReportDraft['reporter_type']): string {
  const found = REPORTER_TYPES.find((option) => option.id === type)
  return (found?.label ?? type).toLowerCase()
}

export function YourReports({
  waiting,
  sent,
  statusesRead,
  signedAs,
  today,
}: YourReportsProps) {
  const unread = sent.some((row) => row.state === null)
  return (
    <section className="settings__group" aria-label="Your reports">
      <h2 className="settings__heading">Your reports</h2>

      {waiting.length > 0 && (
        <section className="plan-home__section" aria-label="Waiting to send">
          <span className="plan-home__title">Waiting to send · {waiting.length}</span>
          {waiting.map((row) => (
            <div key={row.id} className="plan-home__row plan-home__row--figures">
              <span className="plan-home__row-name">
                {categoryLabel(row.type)} at {row.place}
              </span>
              <span className="plan-home__meta">
                {whenLabel('written', row.authoredAt, today)}
              </span>
            </div>
          ))}
          {/* The design's own sentence, and the one thing a hiker needs to
              know about an offline-first outbox: it is not a fault and it
              is not theirs to fix. */}
          <p className="settings__note">
            It goes the moment this phone has signal — nothing to do.
          </p>
        </section>
      )}

      {sent.length > 0 && (
        <section className="plan-home__section" aria-label="Sent from this phone">
          <span className="plan-home__title">Sent from this phone · {sent.length}</span>
          {sent.map((row) => (
            <div key={row.id} className="plan-home__row plan-home__row--figures">
              <span className="plan-home__row-name">
                {categoryLabel(row.type)} at {row.place}
              </span>
              <span className="plan-home__meta">
                {[whenLabel('sent', row.sentAt, today), row.state]
                  .filter((part) => part !== null)
                  .join(' · ')}
              </span>
            </div>
          ))}
          {/* Which of two absences this is, said rather than left as a gap
              (D13): a status this phone has not read, or a status the list
              it read does not hold. */}
          {!statusesRead ? (
            <p className="settings__note">
              Statuses need signal — they are read with the map’s conditions, and this
              phone has not read them yet.
            </p>
          ) : (
            unread && (
              <p className="settings__note">
                Some of these carry no status: the list this phone read does not hold them
                — sent under a different account, or read before they went.
              </p>
            )
          )}
        </section>
      )}

      {waiting.length === 0 && sent.length === 0 && (
        <p className="settings__note">
          Nothing reported from this phone yet. A report starts from a waypoint’s card, a
          long press on the map, or the door above.
        </p>
      )}

      {/* A fact about a LOCAL preference (the trail name never leaves the
          phone on a report) and a true sentence about the wire: the reporter
          is an account id the public never sees (#252). */}
      {signedAs !== null && (
        <p className="settings__note">
          Reported as {signedAs.trailName}, {reporterLabel(signedAs.reporterType)}. Your
          email is never on a report.
        </p>
      )}
    </section>
  )
}
