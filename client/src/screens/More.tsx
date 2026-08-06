// The "More" tab: the way to everything that is neither the map nor the
// download.
//
// Reporting is reached from here rather than from the map screen. WIREFRAMES.md
// §2 says of the map header "Nothing else lives here," and putting a report
// button on the map canvas instead is a design decision that has not been made
// - so it lives behind a tab that already exists rather than being invented
// into the most valuable strip of screen space.

import { Settings, type SettingsProps } from './Settings'

/** A report the server refused for good, reduced to what the screen shows. */
export interface StuckReport {
  id: string
  /** Already a full sentence, written for a hiker - see lib/api.ts. */
  reason: string
}

export interface MoreProps extends SettingsProps {
  onStartReport: () => void
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
  queuedReportCount,
  stuckReports = [],
  onRetryReport,
  onDiscardReport,
  ...settings
}: MoreProps) {
  return (
    <div className="more">
      <section className="settings__group">
        <h2 className="settings__heading">Contribute</h2>
        <button type="button" className="settings__action" onClick={onStartReport}>
          Report a problem
        </button>
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
                      onClick={() => onDiscardReport?.(report.id)}
                    >
                      Delete
                    </button>
                  </span>
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
