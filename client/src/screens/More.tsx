// The "More" tab: the way to everything that is neither the map nor the
// download.
//
// Reporting is reached from here rather than from the map screen. WIREFRAMES.md
// §2 says of the map header "Nothing else lives here," and putting a report
// button on the map canvas instead is a design decision that has not been made
// - so it lives behind a tab that already exists rather than being invented
// into the most valuable strip of screen space.

import { useState } from 'react'
import { Settings, type SettingsProps } from './Settings'

/** A report the server refused for good, reduced to what the screen shows. */
export interface StuckReport {
  id: string
  /** Already a full sentence, written for a hiker - see lib/api.ts. */
  reason: string
}

export interface MoreProps extends SettingsProps {
  onStartReport: () => void
  /**
   * Opens the moderation queue, and present ONLY for a moderator (#235).
   *
   * An optional callback rather than an `isModerator` flag, deliberately:
   * this screen has no business knowing what a role is, and the difference
   * between "may moderate" and "has somewhere to go" is a distinction it
   * would only get wrong. Absent means no entry is rendered at all.
   */
  onOpenModeration?: () => void
  /**
   * The hike in one line (lib/plannedHike.ts), or null for a hiker who has
   * not set one - which is a first-class state, not an incomplete setup. The
   * row invites rather than nags, because every part of this app works
   * without a hike.
   */
  hikeSummary?: string | null
  onEditHike?: () => void
  /** Waiting for signal. Excludes anything in `stuckReports`. */
  queuedReportCount: number
  /**
   * Refused permanently. Separate from the count above because they are
   * different facts: one resolves itself when the signal returns, the other
   * never will, and rolling them together is what let a phone with a wrong
   * clock claim "waiting to send" indefinitely (#243).
   */
  stuckReports?: StuckReport[]
  onRetryReport?: (id: string) => void
  onDiscardReport?: (id: string) => void
}

export function More({
  onStartReport,
  onOpenModeration,
  hikeSummary = null,
  onEditHike,
  queuedReportCount,
  stuckReports = [],
  onRetryReport,
  onDiscardReport,
  ...settings
}: MoreProps) {
  // Deleting a stuck report asks twice. "Try again" and "Delete" sit side by
  // side in the same style, and one of them destroys text someone wrote on a
  // ridge days ago with no way back - the note right below these buttons
  // promises "Nothing has been lost... until you delete it", and a promise
  // like that should not hinge on which of two identical buttons a cold
  // thumb landed on. Keyed by report id so confirming one never arms another.
  const [confirmingDiscard, setConfirmingDiscard] = useState<string | null>(null)

  return (
    <div className="more">
      {onEditHike !== undefined && (
        <section className="settings__group">
          <h2 className="settings__heading">Your hike</h2>
          <button type="button" className="settings__action" onClick={onEditHike}>
            {hikeSummary ?? 'Say where you are walking'}
          </button>
          <p className="settings__note">
            {hikeSummary === null
              ? 'Optional. It lets the map say what is ahead of you instead of waiting until you have walked far enough for it to work out which way you are going.'
              : 'Change or clear this at any time.'}
          </p>
        </section>
      )}
      <section className="settings__group">
        <h2 className="settings__heading">Contribute</h2>
        <button type="button" className="settings__action" onClick={onStartReport}>
          Report a problem
        </button>
        {onOpenModeration !== undefined && (
          <button type="button" className="settings__action" onClick={onOpenModeration}>
            Moderation queue
          </button>
        )}
        {queuedReportCount > 0 && (
          <p className="settings__note" role="status">
            {queuedReportCount === 1
              ? '1 report waiting to send.'
              : `${queuedReportCount} reports waiting to send.`}
          </p>
        )}
        {stuckReports.length > 0 && (
          // role="alert", not "status": this is the one thing on this screen
          // that will not resolve itself, and it appears after someone has
          // already walked away believing the report was on its way.
          <div className="more__stuck" role="alert">
            <p className="more__stuck-heading">
              {stuckReports.length === 1
                ? '1 report could not be sent.'
                : `${stuckReports.length} reports could not be sent.`}
            </p>
            <ul className="more__stuck-list">
              {stuckReports.map((report) => (
                <li key={report.id} className="more__stuck-item">
                  <span className="more__stuck-reason">{report.reason}</span>
                  {confirmingDiscard === report.id ? (
                    <span className="more__stuck-actions">
                      <span className="more__stuck-confirm">
                        Delete what you wrote? There is no way back.
                      </span>
                      <button
                        type="button"
                        className="settings__action"
                        onClick={() => setConfirmingDiscard(null)}
                      >
                        Keep it
                      </button>
                      <button
                        type="button"
                        className="settings__action"
                        onClick={() => {
                          setConfirmingDiscard(null)
                          onDiscardReport?.(report.id)
                        }}
                      >
                        Yes, delete it
                      </button>
                    </span>
                  ) : (
                    <span className="more__stuck-actions">
                      <button
                        type="button"
                        className="settings__action"
                        onClick={() => onRetryReport?.(report.id)}
                      >
                        Try again
                      </button>
                      <button
                        type="button"
                        className="settings__action"
                        onClick={() => setConfirmingDiscard(report.id)}
                      >
                        Delete
                      </button>
                    </span>
                  )}
                </li>
              ))}
            </ul>
            {/* Said out loud, because the alternative reading - that the app
                threw the report away - is the one that stops someone
                reporting anything again. */}
            <p className="settings__note">
              Nothing has been lost. What you wrote is still on this phone until you
              delete it.
            </p>
          </div>
        )}
      </section>

      <Settings {...settings} />
    </div>
  )
}
