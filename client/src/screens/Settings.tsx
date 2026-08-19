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

import { syncAgeLabel } from '../lib/syncAge'
import type {
  BackgroundSource,
  ReporterType,
  UserPreferences,
} from '../lib/userPreferences'
import { backgroundOverride } from '../lib/dataSaver'
import { BackgroundPicker } from '../chrome/BackgroundPicker'
import { REPORTER_TYPES } from '../lib/contributionFlow'
import { MapDetailPicker } from './MapDetailPicker'
import { typeLabel } from '../chrome/legendLabels'
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
  lastSyncedAt: Date | null
  onSync: () => void
  onExport: (format: 'gpx' | 'geojson') => void
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
}: YouSettingsProps) {
  return (
    <section className="settings__group">
      <h2 className="settings__heading">You</h2>

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
        <legend className="settings__label">Waypoints shown</legend>
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

      <p className="settings__locked" role="note">
        Closures and serious warnings are always shown. There is no switch, here or
        anywhere.
      </p>
    </section>
  )
}

// --- Your data ---------------------------------------------------------------

export interface DataSettingsProps {
  lastSyncedAt: Date | null
  onSync: () => void
  onExport: (format: 'gpx' | 'geojson') => void
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
      <button type="button" className="settings__action" onClick={onSync}>
        Sync
      </button>
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
