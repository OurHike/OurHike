// The strip where the map admits what it doesn't know (WIREFRAMES.md §1).
//
// Time, connectivity, GPS fix, and how old the data is. Being offline or
// losing the fix is a normal condition on trail, not an error - but it has to
// be SAID, because the failure mode this strip exists to prevent is a stale
// position rendered exactly like a live one. Silence would read as "this is
// where you are" when the honest answer is "this is where you last were."

import { syncAgeLabel } from '../lib/syncAge'

export interface StatusStripProps {
  time: Date
  online: boolean
  hasGpsFix: boolean
  /** When the on-device data last synced; null if it never has. */
  lastSyncedAt: Date | null
  /**
   * The live background's tiles reported an error and never drew - see
   * map/liveSourceHealth.ts.
   *
   * Distinct from `online`, and that distinction is the point: navigator.onLine
   * is documented as optimistic (lib/useOnline.ts), so a captive portal, a
   * filtered network or an outage at the tile host all look like a working
   * connection while the map draws nothing at all.
   */
  liveBackgroundUnavailable?: boolean
  /**
   * Data Saver is overriding the chosen background - see lib/dataSaver.ts.
   *
   * That module's rule is that the app "is allowed to override a preference,
   * and is not allowed to do it silently," and until now the only screen that
   * said so was Settings. On a phone with nothing downloaded the override is
   * the whole map: the live sheet is subtracted and the archive underneath is
   * empty, so the hiker gets blank paper and no reason for it.
   */
  backgroundOverridden?: boolean
}

export function StatusStrip({
  time,
  online,
  hasGpsFix,
  lastSyncedAt,
  liveBackgroundUnavailable = false,
  backgroundOverridden = false,
}: StatusStripProps) {
  return (
    <div className="status-strip">
      <span className="status-strip__time">
        {time.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
      </span>

      {/* Polite, not assertive: losing signal mid-walk is expected, and should
          never interrupt whatever the hiker is already reading. */}
      <span className="status-strip__conditions" role="status">
        {!online && <span className="status-strip__flag">Offline</span>}
        {!hasGpsFix && <span className="status-strip__flag">No GPS fix</span>}
        {/* Suppressed while offline: "Offline" already accounts for the paper,
            and two flags for one condition is noise on a strip this narrow.
            What it catches is the case "Offline" cannot - a connection the
            phone believes in and the tile host does not answer. */}
        {online && liveBackgroundUnavailable && (
          <span className="status-strip__flag">No live map</span>
        )}
        {backgroundOverridden && (
          <span className="status-strip__flag">Data Saver: downloaded map only</span>
        )}
      </span>

      <span className="status-strip__sync">{syncAgeLabel(lastSyncedAt, time)}</span>
    </div>
  )
}
