// Settings (WIREFRAMES.md §10, features/MORE_TAB.md). Five groups over one
// canonical UserPreferences model, each its own component so More.tsx can
// spread them across its four tabs instead of rendering all of them in one
// scroll. AboutBuild.tsx, ReportBug.tsx and chrome/DownloadsLink.tsx hold no
// preference and write nothing (#378) - More.tsx composes them into its
// About tab directly rather than through here.
//
// Rows that are not built yet are shown with a "Later" tag and disabled,
// rather than hidden. That is WIREFRAMES.md's explicit instruction and it is
// the right call: a visible, dimmed row answers the question "can I do this
// at all?" honestly, where a missing one leaves someone hunting through every
// screen for it. Units was the standing example of that treatment and is now
// a live control (#619) - the tag is a holding position, not a destination,
// and what it holds is a promise that gets kept.

import { useState } from 'react'

import { syncAgeLabel } from '../lib/syncAge'
import { everythingIsSafe, type SyncStatus } from '../lib/syncStatus'
import type { DeletionReceipt } from '../lib/api'
import type { PaceProfile } from '../lib/pace'
import type {
  BackgroundSource,
  ReporterType,
  UserPreferences,
} from '../lib/userPreferences'
import { backgroundOverride } from '../lib/dataSaver'
import { offlineBackgroundAvailable } from '../lib/packages'
import { BackgroundPicker } from '../chrome/BackgroundPicker'
import { REPORTER_TYPES } from '../lib/contributionFlow'
import { MapDetailPicker } from './MapDetailPicker'
import { typeLabel } from '../chrome/legendLabels'
import { ModeSwitch } from '../chrome/ModeSwitch'
import type { HikerMode } from '../lib/hikerMode'
import { HIDEABLE_TYPES, hiddenTypesFrom, toggleType } from '../lib/waypointVisibility'
import { MapStylePicker } from './MapStylePicker'
import { ThemePicker } from './ThemePicker'
import { UnitPicker } from './UnitPicker'
import './settings.css'

/** The full prop bag every group below draws from - kept as one interface,
 *  rather than one per group, so `More.tsx`'s own props (`MoreProps extends
 *  SettingsProps`) and everything that constructs them did not need to
 *  change shape when this file split into five components. */
export interface SettingsProps {
  /** Null when signed out. */
  account: { email: string } | null
  onSignIn: () => void
  onSignOut: () => void
  preferences: UserPreferences
  onChange: (patch: Partial<UserPreferences>) => void
  /** The "today I'm…" mode, reflected under You - see YouSettingsProps. */
  mode?: HikerMode
  onChangeMode?: (mode: HikerMode) => void
  /**
   * The background, written through its own callback rather than `onChange`.
   *
   * Not because the preference is special - it is one field like any other -
   * but because CHOOSING it can mean more than storing it: picking the
   * downloaded corridor with nothing downloaded opens the download window
   * (App.tsx). The shell owns that rule, so the shell has to see the choice.
   *
   * Omitted, the background is written straight through `onChange` like every
   * other preference here, which is what a Settings rendered outside the shell
   * should do.
   */
  onChangeBackground?: (next: BackgroundSource) => void
  /**
   * What has reached the hiker's account, and whether this device is still
   * sending (#894).
   *
   * Optional as a pair, and absent means the section is not rendered at all
   * rather than rendered empty: a screen outside the shell has no sync to
   * describe, and a "Last sent: never synced" row on a surface that never
   * syncs would be a true sentence about nothing.
   */
  syncStatus?: SyncStatus
  syncEnabled?: boolean
  onToggleSync?: (enabled: boolean) => void
  /**
   * Taking the data back, and leaving (#895).
   *
   * Optional as a pair for the same reason the three above are, and with a
   * sharper edge: a surface that cannot actually run the deletion must not
   * draw a button that offers one. Absent means the section is not rendered.
   */
  onExportAccount?: () => Promise<void>
  onDeleteAccount?: () => Promise<DeletionReceipt>
  /**
   * Whether this device has just deleted its account, which keeps the panel
   * on screen after the sign-out that follows.
   *
   * Without it the receipt is unmountable by construction: deleting signs
   * the hiker out, `account` goes null, and the section that was about to
   * say what happened stops being rendered — so the one screen they are owed
   * disappears in the same tick it was earned.
   */
  accountDeleted?: boolean
  /**
   * The hiker's own pace (#880), and its setter.
   *
   * Its OWN pair rather than a `UserPreferences` field written through
   * `onChange`, for the reason PERSONALIZED_PACE.md §4 gives: a pace profile is
   * not a sync target even once an account exists, and `UserPreferences` IS a
   * whole-blob sync target. Same shape as `onChangeBackground` above, which
   * already sidesteps `onChange` for its own reasons.
   *
   * Optional, so a surface that does not offer the control still compiles.
   */
  pace?: PaceProfile
  onChangePace?: (next: PaceProfile) => void
  lastSyncedAt: Date | null
  /** See `DataSettingsProps` - optional, and omitted is the honest state
   *  today: a control with no handler draws "Later" rather than a button
   *  that does nothing (#657). */
  onSync?: () => void
  onExport?: (format: 'gpx' | 'geojson') => void
  /** Injectable so the sync-age wording is testable without a live clock. */
  now?: Date
  /**
   * Whether the phone is asking apps to go easy on data.
   *
   * Passed in rather than read here, so this screen and the map are answering
   * from one value. A row claiming the live sheet is on while the canvas draws
   * the archive is precisely the mismatch the override is supposed to prevent,
   * and two independent reads of the same API is how that happens.
   */
  dataSaver?: boolean
  /**
   * Whether a finished USGS raster archive is on this phone.
   *
   * Passed in for the same reason as `dataSaver`, and it feeds one decision:
   * with no archive, "downloaded only" has no download to draw and the map
   * falls back to the live sheet - see lib/dataSaver.ts.
   */
  archiveDownloaded?: boolean
}

function LaterTag() {
  return <span className="settings__later">Later</span>
}

// --- You ---------------------------------------------------------------

export interface YouSettingsProps {
  account: SettingsProps['account']
  onSignIn: () => void
  onSignOut: () => void
  preferences: UserPreferences
  onChange: (patch: Partial<UserPreferences>) => void
  /**
   * The "today I'm…" mode and its setter (#1054, lib/hikerMode.ts).
   *
   * Reflected here so the state is discoverable from the place people look
   * for preferences, but it is NOT a UserPreferences key and must not become
   * one - the blob syncs at a schema with extra="forbid", and a mode is a
   * statement about today on this phone (the module's header has the whole
   * argument). Optional so a caller without the state renders no row rather
   * than a dead control.
   */
  mode?: HikerMode
  onChangeMode?: (mode: HikerMode) => void
}

// The account row (Phase E5) states plainly that signing out keeps
// everything. The map, the outbox and the preferences are local first, and an
// account only syncs them (IDENTITY_AND_PRIVACY.md) - but nobody knows that
// from the outside, and someone who suspects signing out might discard a
// queued report simply will not sign out. Saying it is what makes the option
// usable.
export function YouSettings({
  account,
  onSignIn,
  onSignOut,
  preferences,
  onChange,
  mode,
  onChangeMode,
}: YouSettingsProps) {
  return (
    <section className="settings__group">
      <h2 className="settings__heading">You</h2>

      {/* The same state the Today header's switch writes - one control in
          two homes, never two states (chrome/ModeSwitch.tsx renders all
          three segments always, and why is its comment to keep). */}
      {mode !== undefined && onChangeMode !== undefined && (
        <div className="settings__row settings__row--mode">
          <span className="settings__label">Today I&rsquo;m</span>
          <ModeSwitch mode={mode} onChange={onChangeMode} variant="paper" />
        </div>
      )}

      <p className="settings__row">
        <span className="settings__label">Trail name</span>
        <span className="settings__value">
          {`${preferences.trail_name ?? 'Not set'} · ${
            account === null ? 'on this device' : 'Linked'
          }`}
        </span>
      </p>

      {/* Editable here, not only at first contribution (#233). Someone who
          skipped the screen, or who started section-hiking after a day hike,
          had no way to correct what every one of their reports says about
          them - and this is the one attribution that survives the anonymity
          window, so it is the one a maintainer reads. */}
      <label className="settings__row">
        <span className="settings__label">Reports signed as</span>
        <select
          className="settings__value"
          name="reporter_type"
          value={preferences.reporter_type ?? ''}
          onChange={(event) =>
            onChange({
              reporter_type:
                event.target.value === '' ? null : (event.target.value as ReporterType),
            })
          }
        >
          {/* Present only while it is the truth: an app that keeps offering
              "Not set" after an answer invites someone to un-say something
              every report still has to carry. */}
          {preferences.reporter_type === null && <option value="">Not set</option>}
          {/* A value this build has no label for still has to be shown, not
              silently swallowed: the set can grow server-side ahead of the
              app, and a select with no matching option renders as its first
              one - which would quietly re-sign every future report as a
              thru-hiker. Shown by its raw id, which is at least true. */}
          {preferences.reporter_type !== null &&
            !REPORTER_TYPES.some((r) => r.id === preferences.reporter_type) && (
              <option value={preferences.reporter_type}>
                {preferences.reporter_type}
              </option>
            )}
          {REPORTER_TYPES.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      {REPORTER_TYPES.find((r) => r.id === preferences.reporter_type)?.clubGranted && (
        <p className="settings__note">Unverified until a club confirms it.</p>
      )}

      {account === null ? (
        <button type="button" className="settings__action" onClick={onSignIn}>
          Sign in
        </button>
      ) : (
        <>
          <p className="settings__row">
            <span className="settings__label">Account</span>
            <span className="settings__value">{account.email}</span>
          </p>
          <button type="button" className="settings__action" onClick={onSignOut}>
            Sign out
          </button>
          <p className="settings__note">
            Signing out stays on this phone — your downloaded map, anything waiting in
            your outbox, and these settings are all kept.
          </p>
        </>
      )}

      <p className="settings__note">Reading the map never needs an account.</p>
    </section>
  )
}

// --- What has reached the account ---------------------------------------
//
// #894, features/ACCOUNT_SYNC.md phase D. One question, answered plainly:
// *if I drop this phone tomorrow, what have I lost?*
//
// WHY IT IS HERE AND NOT BESIDE "Your data"
//
// That section's "Last synced" is the PUBLISHED CONDITIONS bucket, which
// every hiker gets whether or not they have an account. This is the account
// exchange. Two rows called "Last synced" in one app already risks being
// read as one number; putting them in the same panel would guarantee it, and
// a hiker whose conditions refreshed an hour ago and whose trips have not
// been sent since Tuesday would read the reassuring one.
//
// So it sits under the account it depends on, next to the button that turns
// it off and the button that signs out - which is also where somebody asking
// "what happens to my things" is already looking.
//
// NEVER A PROGRESS BAR. features/HIKE_PLANNING.md's anti-gamification
// guardrail applies here too: this reports machinery, never the hiker. There
// is no percentage, no bar, and nothing that could be read as a score.

export interface AccountSyncSettingsProps {
  status: SyncStatus
  enabled: boolean
  onToggle: (enabled: boolean) => void
  /** Injectable so the age wording is testable without a live clock, like
   *  `DataSettings`' own. */
  now?: Date
}

export function AccountSyncSettings({
  status,
  enabled,
  onToggle,
  now = new Date(),
}: AccountSyncSettingsProps) {
  const safe = everythingIsSafe(status)

  return (
    <section className="settings__group">
      <h2 className="settings__heading">What your account has</h2>

      <p className="settings__row">
        <span className="settings__label">Last sent</span>
        {/* A real timestamp rather than a spinner, per the issue. A device
            whose own clock is wrong renders a wrong age here - the stamp is
            the server's - and `syncAgeLabel` reads anything in the future as
            "just now", which is the least wrong thing to say about a
            disagreement this app cannot detect. */}
        <span className="settings__value">{syncAgeLabel(status.lastSyncedAt, now)}</span>
      </p>

      {!enabled && (
        <p className="settings__note">
          Syncing is off on this phone, so nothing below is being sent. Everything is
          still here.
        </p>
      )}

      {safe ? (
        <p className="settings__note">
          Everything on this phone has reached your account.
        </p>
      ) : (
        <>
          {/* Named, never counted. "3 items pending" tells a hiker nothing
              they can act on; a trip they recognise tells them whether to
              worry. */}
          {status.neverSent.length > 0 && (
            <>
              <p className="settings__note">
                On this phone only — if you lost it today, these would go with it:
              </p>
              <ul className="settings__pending">
                {status.neverSent.map((name) => (
                  <li key={name}>{name}</li>
                ))}
              </ul>
            </>
          )}

          {status.unsentEdits.length > 0 && (
            <>
              {/* A different sentence from the one above, deliberately: your
                  account HAS these, in an older form. Adding the two lists
                  together would lose the distinction that decides whether
                  losing the phone costs a trip or costs an afternoon. */}
              <p className="settings__note">
                Your account has an older copy of these — the newest changes are still on
                this phone:
              </p>
              <ul className="settings__pending">
                {status.unsentEdits.map((name) => (
                  <li key={name}>{name}</li>
                ))}
              </ul>
            </>
          )}

          {status.hikeUnsent && (
            <p className="settings__note">The hike you are on has not been sent yet.</p>
          )}
          {status.preferencesUnsent && (
            <p className="settings__note">Your settings have not been sent yet.</p>
          )}
        </>
      )}

      {/* Photos, said as what is true rather than as a setting. The issue
          asks for "what is off" so a hiker reads it as a state they chose -
          but nobody chose this, because photo sync is not built (phase C,
          #893). Calling it "off" would tell them they had made a decision
          they have never been offered. */}
      <p className="settings__note">
        Photos stay on this phone. Syncing them is not built yet.
      </p>

      <button
        type="button"
        className="settings__action"
        onClick={() => onToggle(!enabled)}
      >
        {enabled ? 'Stop syncing on this phone' : 'Start syncing on this phone'}
      </button>
      {/* The copy the issue is most explicit about, and the reason this
          paragraph exists at all: stopping must never read as deleting.
          Someone who suspects the button might discard their trips will not
          press it, and someone who presses it expecting a delete has been
          misled - both are failures of this sentence rather than of the
          button. Deleting is phase E and a different button in a different
          place. */}
      <p className="settings__note">
        Stopping keeps every trip and setting on this phone and on your account. It only
        stops sending. It does not delete anything, anywhere.
      </p>
    </section>
  )
}

// --- Taking it all back, or being rid of us (#895) ------------------------

/** What deletion leaves behind, in the same words the backend's receipt uses.
 *
 *  Written here rather than derived from a count the server has not been
 *  asked for yet, because the whole point is that a hiker reads this BEFORE
 *  the button. The receipt afterwards names the real rows; this names the
 *  rule. If the two ever disagree the receipt is right and this is the bug,
 *  which is why `app/schemas/profile.py` keys `kept` by these same phrases. */
const WHAT_STAYS: readonly string[] = [
  'Closures and condition reports you filed — other hikers are routing around them.',
  'Trail notes you posted, and notes you flagged for a moderator.',
  'Volunteer hours a club has already confirmed.',
]

export interface AccountDataSettingsProps {
  /** Builds the archive and hands it to the browser. Resolves when the file
   *  has been offered; rejects only if the device half could not be read. */
  onExport: () => Promise<void>
  onDelete: () => Promise<DeletionReceipt>
}

type Stage =
  | { name: 'idle' }
  | { name: 'confirming' }
  | { name: 'working' }
  | { name: 'done'; receipt: DeletionReceipt }
  | { name: 'failed'; message: string }

/**
 * Export first, delete second, and both from the same screen — which is the
 * issue's phrasing and its reasoning: a hiker taking their data back should
 * not have to choose between having it and being rid of us.
 *
 * WHY THE PLAIN STATEMENTS ARE ABOVE THE CONFIRM AND NOT IN A POLICY
 *
 * Two things about this deletion are genuinely surprising, and both are
 * things a hiker would be entitled to be angry about learning afterwards:
 * the contributions other people rely on do not go, and a photograph they
 * shared keeps their trail name on it because that is the condition the
 * CC BY-SA licence was granted under (#577) and no deletion can walk a
 * licence back. #895 asks for those to be said "plainly before the button is
 * pressed, not in a policy nobody reads", so they are rendered in the confirm
 * step itself, where the only way past them is through.
 *
 * THE TWO-STEP IS NOT A DARK PATTERN AND IS NOT A `confirm()`
 *
 * There is no undo. The first press reveals what will happen; the second is
 * the act. A native `window.confirm` was the shorter version and cannot
 * carry the paragraphs above, which are the entire reason this screen is
 * more than a button.
 */
export function AccountDataSettings({ onExport, onDelete }: AccountDataSettingsProps) {
  const [stage, setStage] = useState<Stage>({ name: 'idle' })
  const [exporting, setExporting] = useState(false)
  const [exportFailed, setExportFailed] = useState(false)

  // Caught rather than left to reject. `buildAccountArchive` already
  // swallows the ordinary reasons the ACCOUNT half is missing and writes a
  // sentence into the file instead - what reaches here is the device half
  // failing, which is unreadable local storage, and a hiker whose own phone
  // could not be read has to be told rather than watched to press a button
  // that silently does nothing. Letting it reject would be quieter than a
  // log while reading like the error was taken seriously.
  const takeMyData = async () => {
    setExporting(true)
    setExportFailed(false)
    try {
      await onExport()
    } catch {
      setExportFailed(true)
    } finally {
      setExporting(false)
    }
  }

  const reallyDelete = async () => {
    setStage({ name: 'working' })
    try {
      setStage({ name: 'done', receipt: await onDelete() })
    } catch {
      // Deliberately one sentence and deliberately not the error's own text:
      // what a hiker needs here is that nothing happened and they can try
      // again, and an HTTP status in the middle of that sentence buries it.
      setStage({
        name: 'failed',
        message: 'Your account was not deleted — nothing was changed. Try again.',
      })
    }
  }

  if (stage.name === 'done') {
    const kept = Object.entries(stage.receipt.kept)
    return (
      <section className="settings__group">
        <h2 className="settings__heading">Your account is gone</h2>
        <p className="settings__note">
          Your trips, your planned hike and your settings have been deleted from our
          server, and you have been signed out.
        </p>
        {kept.length > 0 && (
          <>
            <p className="settings__note">What stayed, as promised:</p>
            <ul className="settings__pending">
              {kept.map(([what, count]) => (
                <li key={what}>
                  {count} {what}
                </li>
              ))}
            </ul>
          </>
        )}
        <p className="settings__note">
          What is on this phone is still on this phone. Delete the app to be rid of that
          too.
        </p>
      </section>
    )
  }

  return (
    <section className="settings__group">
      <h2 className="settings__heading">Taking your data, or leaving</h2>

      <button
        type="button"
        className="settings__action"
        onClick={() => void takeMyData()}
        disabled={exporting}
      >
        {exporting ? 'Building your file…' : 'Download everything of yours'}
      </button>
      <p className="settings__note">
        One file: what is on this phone, and what your account holds, kept apart so you
        can see which is which. The photographs themselves are not in it.
      </p>
      {exportFailed && (
        <p className="settings__note">
          This phone&rsquo;s own storage could not be read, so no file was made. Nothing
          was lost — try again.
        </p>
      )}

      {stage.name === 'idle' && (
        <button
          type="button"
          className="settings__action"
          onClick={() => setStage({ name: 'confirming' })}
        >
          Delete my account
        </button>
      )}

      {(stage.name === 'confirming' || stage.name === 'failed') && (
        <div className="settings__locked">
          <p className="settings__note">
            This cannot be undone. Download your file first if you have not.
          </p>
          <p className="settings__note">
            <strong>What goes:</strong> your trips, your planned hike, your settings, any
            trail section you maintain, and volunteer hours nobody has confirmed yet.
          </p>
          <p className="settings__note">
            <strong>What stays, without your name on it:</strong>
          </p>
          <ul className="settings__pending">
            {WHAT_STAYS.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="settings__note">
            <strong>Photos you shared keep your trail name.</strong> You shared them under
            a licence that requires the credit, and other people are using them on those
            terms. Deleting your account cannot take that back.
          </p>
          <p className="settings__note">
            What is on this phone stays on this phone. Delete the app to be rid of that
            too.
          </p>
          {stage.name === 'failed' && <p className="settings__note">{stage.message}</p>}
          <button
            type="button"
            className="settings__action"
            onClick={() => void reallyDelete()}
          >
            Yes, delete my account
          </button>
          <button
            type="button"
            className="settings__action"
            onClick={() => setStage({ name: 'idle' })}
          >
            Keep my account
          </button>
        </div>
      )}

      {stage.name === 'working' && <p className="settings__note">Deleting…</p>}
    </section>
  )
}

// --- The map -------------------------------------------------------------

export interface MapSettingsProps {
  preferences: UserPreferences
  onChange: (patch: Partial<UserPreferences>) => void
  onChangeBackground?: (next: BackgroundSource) => void
  dataSaver?: boolean
  archiveDownloaded?: boolean
}

export function MapSettings({
  preferences,
  onChange,
  onChangeBackground,
  dataSaver = false,
  archiveDownloaded = false,
}: MapSettingsProps) {
  return (
    <section className="settings__group">
      <h2 className="settings__heading">The map</h2>
      {/* The same control the legend shows, from one component. This used
          to be a select with its own copy, which meant two places writing
          one preference and disagreeing about what it looked like. */}
      <BackgroundPicker
        value={preferences.background_source}
        onChange={
          onChangeBackground ?? ((background_source) => onChange({ background_source }))
        }
        override={backgroundOverride(
          preferences.background_source,
          dataSaver,
          archiveDownloaded,
        )}
        // Whether that control has anything to offer at all (#855). Off the
        // catalog, from the same function the map's copy of this picker
        // reads, so the two cannot disagree about whether a background
        // exists - which is the whole reason both are one component.
        offlineBackgroundAvailable={offlineBackgroundAvailable(archiveDownloaded)}
        idPrefix="settings"
      />

      <MapStylePicker
        value={preferences.map_style}
        onChange={(map_style) => onChange({ map_style })}
      />

      {/* night_hike's sub-mode, and only while night_hike is chosen: a
          toggle that does nothing under Field would be a live-looking
          control with no effect, which is the same dishonesty the Later
          rows exist to avoid - see MapStylePicker's header for why it is
          not a third style segment. */}
      {preferences.map_style === 'night_hike' && (
        <>
          <label className="settings__row">
            <span className="settings__label">Red light</span>
            <input
              type="checkbox"
              name="red_light_enabled"
              checked={preferences.red_light_enabled}
              onChange={(event) => onChange({ red_light_enabled: event.target.checked })}
            />
          </label>
          <p className="settings__note">
            Re-inks the night sheet in red, the light night vision keeps. Every trail
            draws in the same red — blaze colours return when you switch it off.
          </p>
        </>
      )}

      <MapDetailPicker
        value={preferences.layer_detail_level}
        onChange={(layer_detail_level) => onChange({ layer_detail_level })}
      />

      {/* The full category list. It used to be the ONLY one - WIREFRAMES.md §2
          said "Full 10-category list lives in Settings, not here", because the
          legend showed what was in the viewport and a category with nothing in
          view had no row to tap. That is the second of the three consequences
          #530 lists, and #723 is it being reported from a phone: at z14 the
          legend was routinely offering two of the eight switches.

          The legend carries all of them now (chrome/Legend.tsx), and this list
          stays rather than being retired to it. Two homes for one control is
          not a duplicate here - it is the same HIDEABLE_TYPES behind both, and
          the two are read at different moments. Somebody setting the app up
          before a hike works down this screen; somebody looking at a crowded
          map wants the switch without leaving the map.

          The safety layers are absent rather than listed-and-disabled, which is
          how HIKER_SAFETY.md and MAP_OPTIONS.md §4 say to keep that rule:
          lib/waypointVisibility.ts's HIDEABLE_TYPES excludes them, so there is
          nothing here to build an affordance from. */}
      <fieldset className="settings__waypoints">
        <legend className="settings__label">Default Waypoints shown</legend>
        {HIDEABLE_TYPES.map((type) => {
          const shown = !hiddenTypesFrom(preferences.waypoint_types_shown).has(type)
          return (
            <label key={type} className="settings__row">
              <span className="settings__label">{typeLabel(type)}</span>
              <input
                type="checkbox"
                name={`waypoint-${type}`}
                checked={shown}
                onChange={() =>
                  onChange({
                    waypoint_types_shown: toggleType(
                      preferences.waypoint_types_shown,
                      type,
                    ),
                  })
                }
              />
            </label>
          )
        })}
        <p className="settings__note">
          Hiding a category hands its space on the map to the ones left, so the crowded
          zooms draw more of what you did keep.
        </p>
      </fieldset>

      <label className="settings__row settings__row--later">
        <span className="settings__label">Roads &amp; walkability</span>
        <LaterTag />
        <input type="checkbox" name="show_roads" disabled checked={false} readOnly />
      </label>
    </section>
  )
}

// --- Display ---------------------------------------------------------------

export interface DisplaySettingsProps {
  preferences: UserPreferences
  onChange: (patch: Partial<UserPreferences>) => void
}

export function DisplaySettings({ preferences, onChange }: DisplaySettingsProps) {
  return (
    <section className="settings__group">
      <h2 className="settings__heading">Display</h2>
      <ThemePicker value={preferences.theme} onChange={(theme) => onChange({ theme })} />

      {/* Was a disabled checkbox under a "Later" tag, with the mile-marker
          note beside it - the honest shape for a row that had a preference
          key, a backend column and nothing reading either. The note moved
          into the picker's own description, where it is read by whoever is
          actually choosing rather than by everyone scrolling past. */}
      <UnitPicker
        value={preferences.unit_system}
        onChange={(unit_system) => onChange({ unit_system })}
      />
    </section>
  )
}

// --- Safety & privacy --------------------------------------------------------

export interface SafetyPrivacySettingsProps {
  preferences: UserPreferences
  onChange: (patch: Partial<UserPreferences>) => void
}

// The locked callout about closures and serious warnings is the visible half
// of an invariant whose real enforcement is in lib/userPreferences.ts - there
// is no key for hiding them, so there is no control that could be built. What
// this callout does is tell someone who went looking that the absence is
// deliberate.
export function SafetyPrivacySettings({
  preferences,
  onChange,
}: SafetyPrivacySettingsProps) {
  return (
    <section className="settings__group">
      <h2 className="settings__heading">Safety &amp; privacy</h2>

      {/* The row #312 exists for, and the only live control in this
          section. `location_permission_requested` was written in exactly
          one place - onboarding's completion handler - and the location
          step there is skippable, correctly. So a hiker who tapped "Not
          now" had disabled GPS in this app for the life of the install,
          with the header telling them it was still "Looking for GPS…" and
          nothing anywhere offering a way back.

          A real switch rather than a Later tag, because unlike the two
          below it governs machinery that is already wired: the watch in
          lib/useGeolocation.ts and the map's own locate control, which is
          attached only while this is on (map/mapChrome.ts).

          Turning it on does not grant browser permission - it starts the
          watch, which asks. If the browser has already been told no, the
          header says "Location blocked" rather than pretending, which is
          the honest end of what this switch can do. */}
      <label className="settings__row">
        <span className="settings__label">Use my location</span>
        <input
          type="checkbox"
          name="location_permission_requested"
          checked={preferences.location_permission_requested}
          onChange={(event) =>
            onChange({ location_permission_requested: event.target.checked })
          }
        />
      </label>
      <p className="settings__note">
        Draws where you are on the map and reads your mile. The fix is used on the device
        and sent nowhere unless you file a report. Off, the map still works everywhere; it
        just cannot say where you are on it.
      </p>

      {/* The detection exists (lib/wrongWay.ts) and nothing runs it yet -
          no monitor is wired, no cue is mounted, no push ever fires. Until
          that changes, a live-looking switch here is the most dangerous
          control in the app: a hiker who checks that it is on believes an
          alarm is armed, and there is no alarm. "Later" is the same honest
          treatment the other unbuilt rows get, and the preference key stays
          (default on, lib/userPreferences.ts) so the day the monitor is
          wired, every phone already has it enabled. */}
      <label className="settings__row settings__row--later">
        <span className="settings__label">Wrong-way alert</span>
        <LaterTag />
        <input
          type="checkbox"
          name="wrong_way_alert_enabled"
          disabled
          checked={false}
          readOnly
        />
      </label>
      <label className="settings__row settings__row--later">
        <span className="settings__label">Hide my name on reports for…</span>
        <LaterTag />
        <input
          type="checkbox"
          name="anonymity_window_days"
          disabled
          checked={false}
          readOnly
        />
      </label>

      {/* WHAT THIS NOTICE PROMISES, AND WHY THE WORDING CHANGED (#1047).
          It read "Closures and serious warnings are always shown. There is no
          switch, here or anywhere." The second sentence was true until the
          legend gained an Alerts switch, and a settings screen that goes on
          denying a control a hiker can see is worse than one that says
          nothing.

          What is promised now is what this screen can actually keep: nothing
          about the alert layers is a setting, nothing about them is saved, and
          the map opens with them on. That is a stronger claim than it sounds -
          it is the whole reason chrome/alertLayerPanel.ts holds the flag in a
          `useState` rather than in the object this screen edits. */}
      <p className="settings__locked" role="note">
        Closures and serious warnings are not a setting. The legend can take them off the
        map while you are looking at it — never for longer, and never on your other
        phones. The map opens with them shown, and tells you what is ahead either way.
      </p>
    </section>
  )
}

// --- Your data ---------------------------------------------------------------

export interface DataSettingsProps {
  lastSyncedAt: Date | null
  /**
   * Refresh the published conditions, when there is something to call.
   *
   * OPTIONAL, and omitted is the honest state today (#657). These three
   * buttons were bound to `App.tsx`'s `notYet = () => undefined`: live-
   * looking controls that did nothing, in the same file that already has a
   * standard for the opposite - `LaterTag` beside a disabled input, which is
   * what "Roads & walkability" wears two sections up.
   *
   * A control that looks usable and is not costs more than a missing one. It
   * is pressed, nothing happens, and the hiker learns that this app's buttons
   * sometimes lie - on the screen where the other buttons are export and
   * sign-out.
   */
  onSync?: () => void
  onExport?: (format: 'gpx' | 'geojson') => void
  /** Injectable so the sync-age wording is testable without a live clock. */
  now?: Date
}

export function DataSettings({
  lastSyncedAt,
  onSync,
  onExport,
  now = new Date(),
}: DataSettingsProps) {
  return (
    <section className="settings__group">
      <h2 className="settings__heading">Your data</h2>
      <p className="settings__row">
        <span className="settings__label">Last synced</span>
        <span className="settings__value">{syncAgeLabel(lastSyncedAt, now)}</span>
      </p>
      {onSync === undefined ? (
        <p className="settings__row settings__row--later">
          <span className="settings__label">Refresh now</span>
          <LaterTag />
        </p>
      ) : (
        <button type="button" className="settings__action" onClick={onSync}>
          Sync
        </button>
      )}
      {onExport === undefined ? (
        <p className="settings__row settings__row--later">
          <span className="settings__label">Export GPX or GeoJSON</span>
          <LaterTag />
        </p>
      ) : (
        <div className="settings__exports">
          <button
            type="button"
            className="settings__action"
            onClick={() => onExport('gpx')}
          >
            Export GPX
          </button>
          <button
            type="button"
            className="settings__action"
            onClick={() => onExport('geojson')}
          >
            Export GeoJSON
          </button>
        </div>
      )}
      <p className="settings__note">
        Map data: USGS US Topo, ATC GIS, © OpenStreetMap contributors, OpenFreeMap ©
        OpenMapTiles, USGS 3DEP via AWS Terrain Tiles.
      </p>
      {/* NDMC's credit, in their own words and unabridged (#720).
          droughtmonitor.unl.edu/About/Permission.aspx asks for this exact
          sentence naming all four partners, so it is quoted rather than
          summarised into the line above - a shortened version of a credit
          somebody specified word for word is not the credit they asked for.
          It sits here whether or not the layer is switched on: the terms
          attach to shipping the data, not to drawing it. */}
      <p className="settings__note">
        The U.S. Drought Monitor is jointly produced by the National Drought Mitigation
        Center at the University of Nebraska-Lincoln, the United States Department of
        Agriculture, the National Oceanic and Atmospheric Administration and the National
        Aeronautics and Space Administration. Map courtesy of NDMC.
      </p>
    </section>
  )
}
