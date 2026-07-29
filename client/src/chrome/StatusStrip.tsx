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
}

export function StatusStrip({ time, online, hasGpsFix, lastSyncedAt }: StatusStripProps) {
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
      </span>

      <span className="status-strip__sync">{syncAgeLabel(lastSyncedAt, time)}</span>
    </div>
  )
}
