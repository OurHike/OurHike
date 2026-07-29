// How old the on-device data is, in words (WIREFRAMES.md §1's status strip).
//
// Distinct from lib/staleness.ts, which grades how long ago a HUMAN last
// confirmed a POI. This is the much simpler question of when the app last
// talked to the server, and it never returns an empty string: "never synced"
// is a real answer a fresh install has to be able to give, and a blank would
// read as "synced just fine" to anyone glancing at the strip.

const MINUTE_MS = 60 * 1000
const HOUR_MS = 60 * MINUTE_MS
const DAY_MS = 24 * HOUR_MS

export function syncAgeLabel(lastSyncedAt: Date | null, now: Date): string {
  if (lastSyncedAt === null) return 'never synced'

  const elapsed = now.getTime() - lastSyncedAt.getTime()

  if (elapsed < MINUTE_MS) return 'just now'
  if (elapsed < HOUR_MS) return `${Math.floor(elapsed / MINUTE_MS)}m ago`
  if (elapsed < DAY_MS) return `${Math.floor(elapsed / HOUR_MS)}h ago`
  return `${Math.floor(elapsed / DAY_MS)}d ago`
}
