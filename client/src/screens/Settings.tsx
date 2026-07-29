// Settings (WIREFRAMES.md §10). Five groups over one canonical
// UserPreferences model.
//
// The account row (Phase E5) states plainly that signing out keeps
// everything. The map, the outbox and the preferences are local first, and an
// account only syncs them (IDENTITY_AND_PRIVACY.md) - but nobody knows that
// from the outside, and someone who suspects signing out might discard a
// queued report simply will not sign out. Saying it is what makes the option
// usable.
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
import { REPORTER_TYPES } from '../lib/contributionFlow'
import type { ReportDraft } from '../lib/outbox'
import './settings.css'

export interface SettingsProps {
  /** Null when signed out. */
  account: { email: string } | null
  reporterType: ReportDraft['reporter_type']
  onSignIn: () => void
  onSignOut: () => void
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
  account,
  reporterType,
  onSignIn,
  onSignOut,
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
            {`${preferences.trail_name ?? 'Not set'} · ${
              account === null ? 'on this device' : 'Linked'
            }`}
          </span>
        </p>

        <p className="settings__row">
          <span className="settings__label">Reports signed as</span>
          <span className="settings__value">
            {REPORTER_TYPES.find((r) => r.id === reporterType)?.label ?? reporterType}
          </span>
        </p>

        {REPORTER_TYPES.find((r) => r.id === reporterType)?.clubGranted && (
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
