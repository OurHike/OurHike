// Whether the data on this phone is still the data that is published, and what
// to say about the difference (#919).
//
// Until this existed, a phone that had completed one download never fetched
// another. `useTrailData`'s `fetchOnce` asked `haveTrailData()` - "are there
// trail lines, and was the last download finished" - and returned. It never
// asked WHICH release, and nothing stored could have answered: the six data
// keys held bytes and a completion flag, no version, no hashes, no date.
//
// The cost was measured rather than imagined. #749's water gate shipped, the
// bucket served the corrected layer, and every device that already had data
// went on drawing 1,535 ungated OSM water points - drinking fountains in
// Manhattan, in the water style, at up to 29.9 mi from the trail. The pipeline
// was fixed, the publish was green, and the hiker still had the old answer.
//
// WHAT THIS MODULE DECIDES, AND WHAT IT DELIBERATELY DOES NOT
//
// It decides whether an update exists, what it changed, and what it costs. It
// never applies one. **The maintainer's decision (2026-08-21) is that nothing
// is replaced without the hiker being asked**, so the severity below shapes
// what the prompt says and never whether it appears. A future change that
// applied `routine` updates silently would need that decision revisited, not
// just this file edited.
//
// Three more of that day's decisions are built in here rather than argued
// again: the check runs on launch when online, alongside the `conditions/*`
// refresh that already works this way (useConditions.ts); the archives are out
// of scope, because 2.89 GB is not something to re-fetch on a description; and
// this is built against `latest.json` as it stands, leaving RELEASING.md §10's
// `DATA_RELEASE` pin to decide later which manifest is read.
//
// WHY THE PUBLISHER GRADES THE CHANGE AND NOT THIS FILE
//
// A phone holds one side of the diff. Working out that a water point was
// deleted would mean keeping the previous release beside the current one -
// twice the storage, on the device least able to spare it, to answer a
// question `publish.py` already had both sides of. So `data_change.py` grades
// it at publish time and `latest.json` carries the verdict.
//
// The verdict describes exactly ONE hop, and `previousVersion` is what makes
// that checkable rather than a caveat nobody can act on: a phone further back
// than one release is reading a description of somebody else's transition, and
// `availableRefresh` refuses to repeat it.

import { get, set } from 'idb-keyval'

import {
  CONSEQUENTIAL,
  ROUTINE,
  type ArtifactChange,
  type PublishedSnapshot,
} from './dataManifest'

/** Where the record of what this phone downloaded lives. Beside the data it
 *  describes (`trailData.ts`'s keys), under the same `ourhike:` prefix. */
export const RELEASE_KEY = 'ourhike:trail-data-release'

/**
 * How large an update has to be before a hiker is warned about spending it on
 * mobile data.
 *
 * Derived rather than picked, from the artifact sizes measured against the
 * live bucket on 2026-08-21 (bytes on the wire, gzipped, which is what
 * `transfer_bytes` carries):
 *
 *     one poi_*.geojson        ~0.10 MB
 *     all eight poi_*.geojson   0.67 MB
 *     + trails.geojson          4.81 MB
 *     the whole set             5.78 MB
 *
 * One megabyte is the gap in that list. Below it are the POI corrections -
 * a water point removed, a shelter renamed - which is the common case and the
 * one a warning would only nag about. Above it the trail lines or the
 * elevation profile have changed, and the update is a real fraction of a
 * metered allowance. So this separates the two kinds of release that actually
 * occur rather than naming a round number.
 */
export const LARGE_UPDATE_BYTES = 1_000_000

/** What this phone downloaded, written when a download completes. */
export interface StoredRelease {
  /** The manifest version the artifacts came from, or null for a download that
   *  completed while the manifest was unreadable - which is a real state
   *  (`publishedSnapshot` never throws) and reads as "cannot compare". */
  version: string | null
  /** The published hash of each artifact this phone actually fetched. */
  hashes: Record<string, string>
  /** When it completed, epoch ms. Recorded so a prompt can say how old the
   *  data is rather than only that it is not the newest. */
  at: number
}

/** A connection good enough to spend megabytes on without asking twice.
 *
 *  `unknown` is its own answer and not a synonym for either. The Network
 *  Information API is not available on every browser this app runs in - Safari
 *  has none of it - so claiming "you are on mobile data" would be inventing a
 *  fact, and claiming wifi would be spending somebody's allowance on a guess. */
export type ConnectionKind = 'wifi' | 'cellular' | 'unknown'

interface NetworkInformation {
  type?: string
  saveData?: boolean
}

/**
 * What can honestly be said about this connection.
 *
 * `saveData` outranks the type: a hiker who has asked their browser to
 * conserve data has said what they want, and that is a stronger signal than
 * any guess about the radio.
 */
export function connectionKind(
  connection: NetworkInformation | undefined = (
    navigator as Navigator & { connection?: NetworkInformation }
  ).connection,
): ConnectionKind {
  if (connection === undefined) return 'unknown'
  if (connection.saveData === true) return 'cellular'
  if (connection.type === 'wifi' || connection.type === 'ethernet') return 'wifi'
  if (connection.type === 'cellular') return 'cellular'
  return 'unknown'
}

/** An update that is published and not on this phone. */
export interface AvailableRefresh {
  /** The published version being offered. Carried so a "not now" can be
   *  remembered against THIS release and not against every later one. */
  version: string
  /** The artifacts whose published hash differs from what was stored. */
  keys: string[]
  /**
   * `consequential` where something a hiker had was removed or moved, OR where
   * this could not be described at all. The unreadable case takes the louder
   * grade for the reason `data_change.py` gives: an honest unknown outranks a
   * confident answer, and the confident answer here would be "nothing much".
   */
  severity: typeof ROUTINE | typeof CONSEQUENTIAL
  /**
   * Whether the counts below describe THIS phone's hop.
   *
   * False when the manifest's `previous_version` is not the version this phone
   * holds - it is more than one release behind, so the published description
   * covers a transition it is not making. The counts are then all zero and the
   * severity is `consequential`, because what changed across the gap is
   * genuinely unknown.
   */
  described: boolean
  added: number
  removed: number
  moved: number
  edited: number
  /** What accepting this will transfer, or null where the manifest publishes
   *  no size for one of the changed artifacts. Null means "cannot say", and a
   *  caller must not render it as zero. */
  bytes: number | null
}

const EMPTY_COUNTS = { added: 0, removed: 0, moved: 0, edited: 0 }

function rollUp(changes: ArtifactChange[]): {
  severity: typeof ROUTINE | typeof CONSEQUENTIAL
} & typeof EMPTY_COUNTS {
  const total = {
    severity: ROUTINE as typeof ROUTINE | typeof CONSEQUENTIAL,
    ...EMPTY_COUNTS,
  }
  for (const change of changes) {
    total.added += change.added
    total.removed += change.removed
    total.moved += change.moved
    total.edited += change.edited
    if (change.severity === CONSEQUENTIAL) total.severity = CONSEQUENTIAL
  }
  return total
}

/**
 * The update waiting for this phone, or null if it is current.
 *
 * Compares only the artifacts this phone actually stored. An artifact it has
 * never held is not an update to what it has - it is a layer this build does
 * not read, and treating a new published key as a pending change would prompt
 * every hiker about data their app has no code to draw.
 */
export function availableRefresh(
  stored: StoredRelease | null,
  snapshot: PublishedSnapshot,
): AvailableRefresh | null {
  // Nothing downloaded yet, or a manifest that could not be read. The first
  // case is downloadTrailData's job; the second is not a claim about anything.
  if (stored === null || snapshot.version === null) return null
  // A phone that stored no version cannot be placed against the published one.
  // Offering it an update would be guessing, and the counts would be a fiction.
  if (stored.version === null) return null
  if (stored.version === snapshot.version) return null

  const keys = Object.keys(stored.hashes)
    .filter((key) => {
      const published = snapshot.hashes[key]
      return published !== undefined && published !== stored.hashes[key]
    })
    .sort()
  // The version moved but nothing this phone holds did - a release that only
  // touched the archives, or an artifact this build does not read. Nothing to
  // offer, and offering it anyway would spend 5.78 MB to change nothing.
  if (keys.length === 0) return null

  const described =
    snapshot.previousVersion !== null && snapshot.previousVersion === stored.version
  const changes = described ? keys.map((key) => snapshot.changes[key]) : []
  // A changed artifact the release did not describe is a change nobody graded.
  const complete = described && changes.every((change) => change !== undefined)
  const rolled = complete
    ? rollUp(changes as ArtifactChange[])
    : { severity: CONSEQUENTIAL as typeof CONSEQUENTIAL, ...EMPTY_COUNTS }

  const sizes = keys.map((key) => snapshot.sizes[key])
  const bytes = sizes.every((size) => size !== undefined)
    ? (sizes as number[]).reduce((total, size) => total + size, 0)
    : null

  return { version: snapshot.version, keys, described: complete, ...rolled, bytes }
}

/** Whether to caution the hiker about what this costs before they accept it.
 *
 *  Not on wifi, and big enough to matter - the maintainer's decision
 *  (2026-08-21). An unknown size is treated as large: it is the only direction
 *  that cannot quietly spend somebody's allowance. */
export function warnsAboutData(
  refresh: AvailableRefresh,
  connection: ConnectionKind = connectionKind(),
): boolean {
  if (connection === 'wifi') return false
  return refresh.bytes === null || refresh.bytes >= LARGE_UPDATE_BYTES
}

export async function rememberRelease(release: StoredRelease): Promise<void> {
  await set(RELEASE_KEY, release)
}

/**
 * What this phone last downloaded, or null.
 *
 * Validated rather than cast, on `conditionsCache`'s principle that a stored
 * document is no more trustworthy than a fetched one and less recently
 * checked. A record written by an older build - or a half-written one - reads
 * as null, which is the same as never having downloaded and offers no update
 * rather than a wrong one.
 */
export async function recallRelease(): Promise<StoredRelease | null> {
  const raw = await get(RELEASE_KEY)
  if (typeof raw !== 'object' || raw === null) return null
  const record = raw as Record<string, unknown>
  const { version, hashes, at } = record
  if (version !== null && typeof version !== 'string') return null
  if (typeof hashes !== 'object' || hashes === null) return null
  if (typeof at !== 'number' || !Number.isFinite(at)) return null
  const entries = Object.entries(hashes as Record<string, unknown>)
  if (!entries.every(([, value]) => typeof value === 'string')) return null
  return { version, hashes: Object.fromEntries(entries) as Record<string, string>, at }
}

/** Where a "not now" is remembered.
 *
 *  Keyed by the version declined, so it silences THAT release and nothing
 *  after it - the same shape as the notice watermarks (lib/notices.ts)
 *  and for the same reason: a prompt that returns every launch after being
 *  answered is a nag, and a prompt silenced forever is a fix nobody is offered
 *  twice. */
export const DISMISSED_KEY = 'ourhike:trail-data-update-dismissed'

export async function dismissRelease(version: string): Promise<void> {
  await set(DISMISSED_KEY, version)
}

export async function dismissedRelease(): Promise<string | null> {
  const raw = await get(DISMISSED_KEY)
  return typeof raw === 'string' && raw !== '' ? raw : null
}
