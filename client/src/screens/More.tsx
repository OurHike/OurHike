// The "More" tab: the way to everything that is neither the map nor the
// download. Labelled "Settings" on the tab bar (chrome/tabs.ts) since
// features/MORE_TAB.md - the file and the component keep the name "More"
// because nothing about what this screen IS changed, only its label and its
// internal navigation.
//
// Four sections under Tabs (screens/Tabs.tsx, already built for Onboarding
// and the download window) rather than one long scroll - features/MORE_TAB.md
// is the design this follows and carries the reasoning for each grouping.
// "You" is the default tab: it is what a hiker opens this screen for most
// often, and it is where "Your hike" and "Contribute" - this screen's own two
// sections, below - already lived before the split.
//
// Reporting is reached from here rather than from the map screen. WIREFRAMES.md
// §2 says of the map header "Nothing else lives here," and putting a report
// button on the map canvas instead is a design decision that has not been made
// - so it lives behind a tab that already exists rather than being invented
// into the most valuable strip of screen space.

import { useState } from 'react'
import { Tabs, type TabItem } from './Tabs'
import {
  YouSettings,
  AccountSyncSettings,
  AccountDataSettings,
  MapSettings,
  DisplaySettings,
  SafetyPrivacySettings,
  DataSettings,
  type SettingsProps,
} from './Settings'
import { PaceSettings } from './PaceSettings'
import { AboutBuild } from './AboutBuild'
import { SourcesSection } from '../chrome/SourcesSection'
import type { Stewards } from '../lib/stewards'
import { ReportBug } from './ReportBug'
import { DownloadsLink } from '../chrome/DownloadsLink'
import type { DownloadActivity } from '../lib/downloadActivity'
import type { BuildInfo } from '../lib/buildInfo'

/** A report the server refused for good, reduced to what the screen shows. */
export interface StuckReport {
  id: string
  /** Already a full sentence, written for a hiker - see lib/api.ts. */
  reason: string
}

export interface MoreProps extends SettingsProps {
  onStartReport: () => void
  /**
   * Opens the volunteer surface, which lost its tab with #1054 and gained
   * this door (chrome/tabs.ts records the decision). Optional like
   * `onOpenModeration`, and for the same shape of reason: absent means the
   * shell has nowhere to send it, and no row is drawn.
   */
  onOpenVolunteer?: () => void
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
  /** Whether ANY background sheet is on this phone, which words the download
   *  link in the About tab: choose a download, or change the one you have. */
  hasDownload?: boolean
  /** What is downloading right now, if anything - drawn on that same link
   *  (lib/downloadActivity.ts). */
  downloadActivity?: DownloadActivity | null
  /** Opens the download window, from the link in the About tab. Omitted, no
   *  link is drawn. */
  onOpenDownloads?: () => void
  /**
   * Opens the app-failure report (#848), from the row at the top of "Report a
   * bug". Omitted, no row is drawn - see ReportBug.tsx for why an unwired
   * build should draw nothing rather than a dead control.
   */
  onReportFailure?: () => void
  /** Which build this is (#378), for the About tab. Injectable for the same
   *  reason `now` is - see screens/AboutBuild.tsx. Omitted, the real one is
   *  shown. */
  build?: BuildInfo
  /** Who the map's data belongs to (#927). Defaults to none, which is what a
   *  phone with nothing downloaded holds and what a release built before
   *  pipeline/export_sources.py existed publishes - the section renders
   *  nothing for either. */
  stewards?: Stewards
}

const TABS: readonly TabItem[] = [
  { id: 'you', label: 'You' },
  { id: 'map-display', label: 'Map & Display' },
  { id: 'safety-privacy', label: 'Safety & Privacy' },
  { id: 'about', label: 'About' },
]
type MoreTabId = (typeof TABS)[number]['id']

export function More({
  onStartReport,
  onOpenVolunteer,
  onOpenModeration,
  hikeSummary = null,
  onEditHike,
  queuedReportCount,
  stuckReports = [],
  onRetryReport,
  onDiscardReport,
  hasDownload = false,
  downloadActivity = null,
  onOpenDownloads,
  onReportFailure,
  build,
  stewards = [],
  ...settings
}: MoreProps) {
  const [activeTab, setActiveTab] = useState<MoreTabId>('you')

  // Deleting a stuck report asks twice. "Try again" and "Delete" sit side by
  // side in the same style, and one of them destroys text someone wrote on a
  // ridge days ago with no way back - the note right below these buttons
  // promises "Nothing has been lost... until you delete it", and a promise
  // like that should not hinge on which of two identical buttons a cold
  // thumb landed on. Keyed by report id so confirming one never arms another.
  const [confirmingDiscard, setConfirmingDiscard] = useState<string | null>(null)

  let panel
  if (activeTab === 'you') {
    panel = (
      <div className="settings">
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
          {/* The volunteer surface's door while the tab is gone (#1054) -
              scaffolding until this screen's five-destination shape gives
              volunteering a destination row of its own. */}
          {onOpenVolunteer !== undefined && (
            <button type="button" className="settings__action" onClick={onOpenVolunteer}>
              Volunteer
            </button>
          )}
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
        <YouSettings
          account={settings.account}
          onSignIn={settings.onSignIn}
          onSignOut={settings.onSignOut}
          preferences={settings.preferences}
          onChange={settings.onChange}
        />
        {/* Under the account it depends on, and above nothing (#894). Only
            when signed in and only when the shell actually has a sync to
            describe - see AccountSyncSettings' header for why it is here
            rather than beside "Your data", whose "Last synced" is a
            different clock entirely. */}
        {settings.account !== null &&
          settings.syncStatus !== undefined &&
          settings.onToggleSync !== undefined && (
            <AccountSyncSettings
              status={settings.syncStatus}
              enabled={settings.syncEnabled ?? true}
              onToggle={settings.onToggleSync}
              now={settings.now}
            />
          )}
        {/* Below the sync panel and last in the tab, which is the order #895
            asks for - export first, delete second, both from one screen -
            and the order that puts the irreversible control furthest from
            the thumb that opened the tab. Signed-in only: there is no
            account to take back or delete without one, and the device's own
            half is reachable through this button anyway once there is. */}
        {(settings.account !== null || settings.accountDeleted === true) &&
          settings.onExportAccount !== undefined &&
          settings.onDeleteAccount !== undefined && (
            <AccountDataSettings
              onExport={settings.onExportAccount}
              onDelete={settings.onDeleteAccount}
            />
          )}
      </div>
    )
  } else if (activeTab === 'map-display') {
    panel = (
      <div className="settings">
        <MapSettings
          preferences={settings.preferences}
          onChange={settings.onChange}
          onChangeBackground={settings.onChangeBackground}
          dataSaver={settings.dataSaver}
          archiveDownloaded={settings.archiveDownloaded}
        />
        <DisplaySettings
          preferences={settings.preferences}
          onChange={settings.onChange}
        />
        {/* Directly under the unit picker, which is the setting it reads with:
            a pace is a speed, so its own labels follow imperial or metric. */}
        {settings.pace !== undefined && settings.onChangePace !== undefined && (
          <PaceSettings
            pace={settings.pace}
            units={settings.preferences.unit_system}
            onChange={settings.onChangePace}
          />
        )}
      </div>
    )
  } else if (activeTab === 'safety-privacy') {
    panel = (
      <div className="settings">
        <SafetyPrivacySettings
          preferences={settings.preferences}
          onChange={settings.onChange}
        />
      </div>
    )
  } else {
    panel = (
      <div className="settings">
        <DataSettings
          lastSyncedAt={settings.lastSyncedAt}
          onSync={settings.onSync}
          onExport={settings.onExport}
          now={settings.now}
        />

        {/* Directly after "Your data" and before the build, which is the
            order frame `1h` draws and the order a hiker reads in: what is on
            this phone, then whose it is, then which build is showing it. */}
        <SourcesSection stewards={stewards} />

        {/* Below the group above, and above the download link rather than
            below it - see screens/AboutBuild.tsx for the rest of why. */}
        <AboutBuild build={build} />

        {/* Immediately after it, because the build is what a bug report has
            to name and these links carry it (#626). The same `build` reaches
            both, so the section that displays it and the links that send it
            can never disagree about which one this is. */}
        <ReportBug build={build} onReportFailure={onReportFailure} />

        {/* Last: the only way to the download, and still a once-a-season
            errand, so it gets the foot of the tab rather than the top. */}
        {onOpenDownloads !== undefined && (
          <DownloadsLink
            onOpen={onOpenDownloads}
            hasDownload={hasDownload}
            downloadActivity={downloadActivity}
          />
        )}
      </div>
    )
  }

  return (
    <div className="more">
      <Tabs
        label="Settings sections"
        tabs={TABS}
        activeId={activeTab}
        onSelect={(id) => setActiveTab(id as MoreTabId)}
        idPrefix="more"
      >
        {panel}
      </Tabs>
    </div>
  )
}
