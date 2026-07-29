// Settings (WIREFRAMES.md §10). Five groups over one canonical
// UserPreferences model.
//
// The account row is absent - it needs the backend and is Phase E5.
//
// Rows that are not built yet are shown with a "Later" tag and disabled,
// rather than hidden. That is WIREFRAMES.md's explicit instruction and it is
// the right call: a visible, dimmed "Units (Later)" answers the question
// "can I switch to metric?" honestly, where a missing row leaves someone
// hunting through every screen for it.
//
// The locked callout about closures and serious warnings is the visible half
// of an invariant whose real enforcement is in lib/userPreferences.ts - there
// is no key for hiding them, so there is no control that could be built. What
// this callout does is tell someone who went looking that the absence is
// deliberate.

import { syncAgeLabel } from '../lib/syncAge'
import type { UserPreferences } from '../lib/userPreferences'
import './settings.css'

export interface SettingsProps {
  preferences: UserPreferences
  onChange: (patch: Partial<UserPreferences>) => void
  lastSyncedAt: Date | null
  onSync: () => void
  onExport: (format: 'gpx' | 'geojson') => void
  /** Injectable so the sync-age wording is testable without a live clock. */
  now?: Date
}

function LaterTag() {
  return <span className="settings__later">Later</span>
}

export function Settings({
  preferences,
  onChange,
  lastSyncedAt,
  onSync,
  onExport,
  now = new Date(),
}: SettingsProps) {
  return (
    <main className="settings">
      <section className="settings__group">
        <h2 className="settings__heading">You</h2>
        <p className="settings__row">
          <span className="settings__label">Trail name</span>
          <span className="settings__value">
            {preferences.trail_name ?? 'Not set · on this device'}
          </span>
        </p>
      </section>

      <section className="settings__group">
        <h2 className="settings__heading">The map</h2>
        <p className="settings__row">
          <span className="settings__label">Background</span>
          <span className="settings__value">USGS topo, downloaded</span>
        </p>
        <p className="settings__note">The only background that works with no signal.</p>
        <label className="settings__row settings__row--later">
          <span className="settings__label">Roads &amp; walkability</span>
          <LaterTag />
          <input type="checkbox" name="show_roads" disabled checked={false} readOnly />
        </label>
      </section>

      <section className="settings__group">
        <h2 className="settings__heading">Display</h2>
        <p className="settings__row">
          <span className="settings__label">Theme</span>
          <span className="settings__value">Auto</span>
        </p>
        <label className="settings__row settings__row--later">
          <span className="settings__label">Units</span>
          <LaterTag />
          <input type="checkbox" name="unit_system" disabled checked={false} readOnly />
        </label>
        <p className="settings__note">Mile markers stay in miles either way.</p>
      </section>

      <section className="settings__group">
        <h2 className="settings__heading">Safety &amp; privacy</h2>
        <label className="settings__row">
          <span className="settings__label">Wrong-way alert</span>
          <input
            type="checkbox"
            name="wrong_way_alert_enabled"
            checked={preferences.wrong_way_alert_enabled}
            onChange={(event) =>
              onChange({ wrong_way_alert_enabled: event.target.checked })
            }
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
          Map data: USGS US Topo, ATC GIS, © OpenStreetMap contributors, USGS 3DEP.
        </p>
      </section>
    </main>
  )
}
