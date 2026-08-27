// The "More" tab: the way to everything that is neither the map nor the
// journal, back under its own name since #1054 put "Today" first and gave
// this screen's label back (chrome/tabs.ts records the reversal).
//
// Five destination rows over a storage card, instead of the four Tabs panels
// that lived here from features/MORE_TAB.md until #1054. What changed is the
// navigation, not the contents: every group Settings.tsx exports renders
// verbatim inside one of the sub-pages below, because that copy was argued
// for line by line and a redesign is not an argument against any of it. What
// the rows add is an answer BEFORE the tap - each carries a one-line summary
// of the state behind it, so "is location on" and "did my report send" are
// read from this screen rather than found behind it.
//
// The storage card leads because it answers this screen's most consequential
// question - is the map on this phone - where the old shape kept that answer
// behind the About tab's footer link. The card is a summary and a door; the
// download window is still the only surface that starts, resumes or deletes
// anything.
//
// Reporting is reached from here rather than from the map screen. WIREFRAMES.md
// §2 says of the map header "Nothing else lives here," and putting a report
// button on the map canvas instead is a design decision that has not been made
// - so it lives behind the "Volunteer & report" row, beside the volunteer
// surface those reports serve.

import { useState, type ReactNode } from 'react'
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
import { mapStyleLabel } from './MapStylePicker'
import { formatDay } from './DownloadCard'
import type { DownloadStatus } from './DownloadCard'
import { facingFullDownload } from '../lib/backgroundStatus'
import { formatBytes, formatBytesLive } from '../lib/formatBytes'
import {
  downloadFillPercent,
  downloadPercent,
  type DownloadActivity,
} from '../lib/downloadActivity'
import { unitSystemLabel } from '../lib/units'
import type { HikerMode } from '../lib/hikerMode'
import type { BuildInfo } from '../lib/buildInfo'

/** A report the server refused for good, reduced to what the screen shows. */
export interface StuckReport {
  id: string
  /** Already a full sentence, written for a hiker - see lib/api.ts. */
  reason: string
}

/**
 * Where within More the hiker is. Held by the shell rather than here, so the
 * Today column's volunteer card can land a hiker directly on 'volunteer'
 * (App.tsx) - a deep link this screen could not honour if the page were its
 * own useState.
 */
export type MorePage = 'home' | 'you' | 'map' | 'safety' | 'volunteer' | 'sources'

export interface MoreProps extends SettingsProps {
  page: MorePage
  onNavigate: (page: MorePage) => void
  onStartReport: () => void
  /**
   * The volunteer surface, rendered by the shell with the live props only it
   * holds (opportunities, hours, the GPS mile). A slot rather than a prop bag
   * because this screen has no business re-declaring Volunteer's interface -
   * it owns where the surface LIVES, which since #1054 is the foot of the
   * "Volunteer & report" page. Absent means the shell has nowhere to send it,
   * and the page simply ends after the contribute section.
   */
  volunteerScreen?: ReactNode
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
  /**
   * The hiking sheet - the map a hiker navigates by - as one combined status
   * (lib/backgroundStatus.ts), for the storage card. The USGS sheet is
   * deliberately not folded in: it is withdrawn (#855), and a card that
   * announced "stopped partway" about bytes nobody is offered any more would
   * be a summary of the wrong thing. Its own card, with its own Delete
   * button, is still in the download window for as long as its bytes are on
   * the phone.
   */
  hikingStatus: DownloadStatus
  /** What is arriving right now, if anything - the live figure outranks the
   *  resting status, exactly as it does on chrome/DownloadsLink.tsx, and via
   *  the same helpers so the two doors can never disagree about a percent. */
  downloadActivity?: DownloadActivity | null
  /** Opens the download window, from the storage card. Omitted, the card
   *  states what is on the phone and offers nothing - a surface that cannot
   *  open the window must not draw a button that promises to. */
  onOpenDownloads?: () => void
  /**
   * Opens the app-failure report (#848), from the row at the top of "Report a
   * bug". Omitted, no row is drawn - see ReportBug.tsx for why an unwired
   * build should draw nothing rather than a dead control.
   */
  onReportFailure?: () => void
  /** Which build this is (#378), for the sources page. Injectable for the
   *  same reason `now` is - see screens/AboutBuild.tsx. Omitted, the real one
   *  is shown. */
  build?: BuildInfo
  /** Who the map's data belongs to (#927). Defaults to none, which is what a
   *  phone with nothing downloaded holds and what a release built before
   *  pipeline/export_sources.py existed publishes - the section renders
   *  nothing for either. */
  stewards?: Stewards
}

/**
 * The You row's word for each mode - a state ("on a long hike"), where
 * chrome/ModeSwitch.tsx's labels are choices ("Long hike"). Two records
 * because they are two sentences, but both are keyed by HikerMode, so a mode
 * added there without a phrase here is a type error rather than a blank row.
 */
const MODE_PHRASE: Record<HikerMode, string> = {
  day: 'day hiking',
  long: 'on a long hike',
  volunteer: 'volunteering',
}

/** Joined with the middle dots the prototype writes, first letter raised
 *  because the fragments themselves are mid-sentence words. */
function summaryLine(parts: ReadonlyArray<string | null>): string {
  const line = parts.filter((part): part is string => part !== null).join(' · ')
  return line.charAt(0).toUpperCase() + line.slice(1)
}

/**
 * The storage card's face for every state the sheet can be in. One derivation
 * rather than JSX branches, so a state this card has no sentence for is a
 * type error here and not a blank card on a phone.
 */
function storageFace(
  status: DownloadStatus,
  activity: DownloadActivity | null,
  detail: string,
): { title: string; size: string | null; fill: number | null; meta: string } {
  // A live transfer outranks the resting status, with DownloadsLink's own
  // precedence and figures: while the trail data is still coming there is no
  // percent to round, and the words alone carry it.
  if (activity !== null) {
    const title = `The whole trail, ${detail} detail`
    if (activity.kind === 'preparing') {
      return {
        title,
        size: null,
        fill: null,
        meta: 'Getting trail data — the map itself starts the moment it lands.',
      }
    }
    const percent = downloadPercent(activity.doneBytes, activity.totalBytes)
    return {
      title,
      size: `${percent}%`,
      fill: downloadFillPercent(activity.doneBytes, activity.totalBytes),
      // formatBytesLive for the moving figure - the static formatter's
      // decimal spins on every chunk, the "jumpy and crazy" text the
      // maintainer reported on first run's panel (2026-08-26), and this
      // line re-renders on the same ticks.
      meta:
        activity.kind === 'checking'
          ? 'Checking what is already on this phone — nothing is being fetched.'
          : `${formatBytesLive(activity.doneBytes)} of ${formatBytes(activity.totalBytes)} · picks up where it left off if you lose signal`,
    }
  }

  const title = `The whole trail, ${detail} detail`
  switch (status.state) {
    case 'downloaded':
      return {
        title,
        size: formatBytes(status.totalBytes),
        fill: 100,
        // "finished", not "refreshed": completedAt is when the transfer
        // ended, and nothing here re-fetches a finished sheet, so the
        // prototype's "refreshed 3 days ago" would claim an update run that
        // does not exist.
        meta: `Complete · finished ${formatDay(status.completedAt)}`,
      }
    case 'downloading':
      // Normally the live activity above carries this; kept so a status the
      // shell hands over without one still renders its own truth.
      return {
        title,
        size: `${downloadPercent(status.receivedBytes, status.totalBytes)}%`,
        fill: downloadFillPercent(status.receivedBytes, status.totalBytes),
        meta: `${formatBytesLive(status.receivedBytes)} of ${formatBytes(status.totalBytes)}`,
      }
    case 'checking':
      return {
        title,
        size: null,
        fill: null,
        meta: 'Checking what is already on this phone — nothing is being fetched.',
      }
    case 'failed':
      return {
        title,
        size: null,
        fill: downloadFillPercent(status.receivedBytes, status.totalBytes),
        // DownloadCard's sentence, literally true of a stopped transfer -
        // what arrived is kept, and the window's offer is to carry on.
        meta: `Stopped at ${formatBytes(status.receivedBytes)} of ${formatBytes(status.totalBytes)} — what arrived is kept.`,
      }
    case 'evicted':
      return {
        title,
        size: null,
        fill: null,
        meta:
          status.completedAt === null
            ? 'The phone removed this map to make space.'
            : `The phone removed the map you downloaded on ${formatDay(status.completedAt)} to make space.`,
      }
    case 'hash-mismatch':
      return {
        title,
        size: null,
        fill: null,
        meta: 'The last download didn’t match what was published, so none of it was kept.',
      }
    case 'not-downloaded':
      return {
        title: 'Nothing downloaded yet',
        size: null,
        fill: null,
        meta: 'The map works over signal for now. One download makes it yours everywhere.',
      }
  }
}

export function More({
  page,
  onNavigate,
  onStartReport,
  volunteerScreen,
  onOpenModeration,
  hikeSummary = null,
  onEditHike,
  queuedReportCount,
  stuckReports = [],
  onRetryReport,
  onDiscardReport,
  hikingStatus,
  downloadActivity = null,
  onOpenDownloads,
  onReportFailure,
  build,
  stewards = [],
  ...settings
}: MoreProps) {
  // Deleting a stuck report asks twice. "Try again" and "Delete" sit side by
  // side in the same style, and one of them destroys text someone wrote on a
  // ridge days ago with no way back - the note right below these buttons
  // promises "Nothing has been lost... until you delete it", and a promise
  // like that should not hinge on which of two identical buttons a cold
  // thumb landed on. Keyed by report id so confirming one never arms another.
  const [confirmingDiscard, setConfirmingDiscard] = useState<string | null>(null)

  // The contribute section, whole: the queue counts live here rather than on
  // the home screen so role="status" and role="alert" announce beside the
  // controls that answer them - the home row carries the same facts as plain
  // words instead.
  const contribute = (
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
            Nothing has been lost. What you wrote is still on this phone until you delete
            it.
          </p>
        </div>
      )}
    </section>
  )

  if (page !== 'home') {
    let panel: ReactNode
    if (page === 'you') {
      panel = (
        <>
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
          <YouSettings
            account={settings.account}
            onSignIn={settings.onSignIn}
            onSignOut={settings.onSignOut}
            preferences={settings.preferences}
            onChange={settings.onChange}
            mode={settings.mode}
            onChangeMode={settings.onChangeMode}
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
          {/* Below the sync panel and last in the page, which is the order
              #895 asks for - export first, delete second, both from one
              screen - and the order that puts the irreversible control
              furthest from the thumb that opened the page. Signed-in only:
              there is no account to take back or delete without one, and the
              device's own half is reachable through this button anyway once
              there is. */}
          {(settings.account !== null || settings.accountDeleted === true) &&
            settings.onExportAccount !== undefined &&
            settings.onDeleteAccount !== undefined && (
              <AccountDataSettings
                onExport={settings.onExportAccount}
                onDelete={settings.onDeleteAccount}
              />
            )}
        </>
      )
    } else if (page === 'map') {
      panel = (
        <>
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
          {/* Directly under the unit picker, which is the setting it reads
              with: a pace is a speed, so its own labels follow imperial or
              metric. */}
          {settings.pace !== undefined && settings.onChangePace !== undefined && (
            <PaceSettings
              pace={settings.pace}
              units={settings.preferences.unit_system}
              onChange={settings.onChangePace}
            />
          )}
        </>
      )
    } else if (page === 'safety') {
      panel = (
        <SafetyPrivacySettings
          preferences={settings.preferences}
          onChange={settings.onChange}
        />
      )
    } else if (page === 'volunteer') {
      panel = (
        <>
          {contribute}
          {/* The volunteer surface itself, below the reporting it exists
              beside - unchanged by #1054, which moved only its doors
              (chrome/tabs.ts). */}
          {volunteerScreen}
        </>
      )
    } else {
      panel = (
        <>
          <DataSettings
            lastSyncedAt={settings.lastSyncedAt}
            onSync={settings.onSync}
            onExport={settings.onExport}
            now={settings.now}
          />
          {/* Directly after "Your data" and before the build, which is the
              order a hiker reads in: what is on this phone, then whose it
              is, then which build is showing it. */}
          <SourcesSection stewards={stewards} />
          <AboutBuild build={build} />
          {/* Immediately after it, because the build is what a bug report
              has to name and these links carry it (#626). The same `build`
              reaches both, so the section that displays it and the links
              that send it can never disagree about which one this is. */}
          <ReportBug build={build} onReportFailure={onReportFailure} />
        </>
      )
    }

    return (
      <div className="more">
        <div className="more__pagebar">
          {/* Named for where it goes, not what it does: five pages share this
              one way home, and "More" is the same word the tab bar taught. */}
          <button type="button" className="more__back" onClick={() => onNavigate('home')}>
            <span aria-hidden="true">‹ </span>More
          </button>
        </div>
        <div className="settings">{panel}</div>
      </div>
    )
  }

  // ---- Home: the storage card, five rows, and the thank-you line. ----

  const face = storageFace(
    hikingStatus,
    downloadActivity,
    settings.preferences.hiking_detail_level,
  )

  const youSummary = summaryLine([
    settings.preferences.trail_name,
    settings.mode !== undefined ? MODE_PHRASE[settings.mode] : null,
    settings.account === null ? 'not signed in' : 'signed in',
  ])

  const mapSummary = summaryLine([
    mapStyleLabel(settings.preferences.map_style),
    unitSystemLabel(settings.preferences.unit_system),
  ])

  // The location switch is this page's one live control, so its state is the
  // summary. The trailing clause keeps the promise Settings.tsx's own note
  // makes - used on the device, sent only inside a report you file - rather
  // than the prototype's "nothing leaves this phone", which is false the
  // moment sync is on.
  const safetySummary = settings.preferences.location_permission_requested
    ? 'Location on · sent only with your reports'
    : 'Location off · the map still works everywhere'

  // Stuck outranks queued, the precedence #243 established - and only stuck
  // wears the danger coat below. "Waiting to send" is the ordinary state of
  // an offline-first outbox, not a fault, which is the same reasoning
  // .settings__pending gives for staying grey. The prototype paints the
  // waiting count in alert orange; that would cry wolf on every ridge.
  const stuckCount = stuckReports.length
  const volunteerSummary =
    stuckCount > 0
      ? stuckCount === 1
        ? '1 report could not be sent'
        : `${stuckCount} reports could not be sent`
      : queuedReportCount > 0
        ? queuedReportCount === 1
          ? '1 report waiting to send'
          : `${queuedReportCount} reports waiting to send`
        : // Deliberately not the "Report a problem" button's own label: the
          // row's accessible name contains this line, and a summary that
          // quotes a control verbatim makes every query for that control
          // ambiguous - for a screen reader saying "which one" as much as
          // for a test.
          'Report problems, or lend a hand'

  const destinations: ReadonlyArray<{
    page: Exclude<MorePage, 'home'>
    title: string
    sub: string
    alert?: boolean
  }> = [
    { page: 'you', title: 'You', sub: youSummary },
    { page: 'map', title: 'The map', sub: mapSummary },
    { page: 'safety', title: 'Safety & privacy', sub: safetySummary },
    {
      page: 'volunteer',
      title: 'Volunteer & report',
      sub: volunteerSummary,
      alert: stuckCount > 0,
    },
    {
      page: 'sources',
      title: 'Where this map comes from',
      sub: 'The sources, their terms, and this build',
    },
  ]

  return (
    <div className="more">
      <header className="more__header">
        <h1 className="more__title">More</h1>
        <p className="more__tagline">Your phone, your data, and how this map got here.</p>
      </header>
      <div className="more__home">
        <section className="more__storage">
          <div className="more__storage-head">
            <span className="more__storage-eyebrow">On this phone</span>
            {face.size !== null && (
              <span className="more__storage-size">{face.size}</span>
            )}
          </div>
          <h2 className="more__storage-title">{face.title}</h2>
          {face.fill !== null && (
            // Presentational for the same reason DownloadsLink's bar is: the
            // figure is in the card's own text, which is what gets announced.
            <div className="more__storage-bar" aria-hidden="true">
              <div className="more__storage-fill" style={{ width: `${face.fill}%` }} />
            </div>
          )}
          <p className="more__storage-meta">{face.meta}</p>
          {onOpenDownloads !== undefined && (
            <div className="more__storage-actions">
              {/* One door where the prototype draws two pills, Refresh and
                  Change size - both of which could only have opened this same
                  window, and Refresh promised a re-fetch this build does not
                  have. The labels are DownloadsLink's own argued-for pair:
                  which one depends on whether the next tap starts from zero
                  (lib/backgroundStatus.ts). */}
              <button type="button" className="more__pill" onClick={onOpenDownloads}>
                {facingFullDownload(hikingStatus)
                  ? 'Choose what to download'
                  : "Change what's downloaded"}
              </button>
            </div>
          )}
        </section>
        {destinations.map((destination) => (
          <button
            key={destination.page}
            type="button"
            className={
              destination.alert === true ? 'more__row more__row--alert' : 'more__row'
            }
            onClick={() => onNavigate(destination.page)}
          >
            <span className="more__row-text">
              <span className="more__row-title">{destination.title}</span>
              <span className="more__row-sub">{destination.sub}</span>
            </span>
            <span className="more__row-chevron" aria-hidden="true">
              ›
            </span>
          </button>
        ))}
        {/* The last word on the screen that holds the volunteer door. A
            statement, not a score - nothing here counts anything (see
            features/HIKE_PLANNING.md's anti-gamification guardrail). */}
        <p className="more__footer">
          Volunteers keep this trail open. Thank you for carrying a map that says so.
        </p>
      </div>
    </div>
  )
}
