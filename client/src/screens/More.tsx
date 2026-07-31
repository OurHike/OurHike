// The "More" tab: the way to everything that is neither the map nor the
// download.
//
// Reporting is reached from here rather than from the map screen. WIREFRAMES.md
// §2 says of the map header "Nothing else lives here," and putting a report
// button on the map canvas instead is a design decision that has not been made
// - so it lives behind a tab that already exists rather than being invented
// into the most valuable strip of screen space.

import { Settings, type SettingsProps } from './Settings'

export interface MoreProps extends SettingsProps {
  onStartReport: () => void
  queuedReportCount: number
}

export function More({ onStartReport, queuedReportCount, ...settings }: MoreProps) {
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
      </section>

      <Settings {...settings} />
    </div>
  )
}
