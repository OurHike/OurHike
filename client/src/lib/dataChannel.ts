// Reading the pointer, `channels.json` (decision 44): what lib/dataRelease.ts
// decides a session's release FROM, read on launch and recorded for the next
// one. dataRelease.ts holds the synchronous half - the mirror read that fixes
// this session's release before the first URL is built - and this module the
// asynchronous half, which nothing needs until after launch.
//
// A MODULE OF ITS OWN, AND LOADED WITH import(), for the launch budget
// (features/LAUNCH_BUDGET.md §3, scripts/check-build-output.mjs): dataRelease
// is in the eager closure through config.ts, and the reader beside it was
// parsed before the first frame although lib/useTrailData.ts first calls it
// from an effect. Measured 2026-10-03 by that check, built with
// VITE_DATA_BASE_URL=https://data.example.org, two builds each: the eager
// closure went from 245,379-245,388 bytes compressed to 244,954-244,967,
// against the 245,760-byte budget, and this chunk is 898 bytes. (One tree's
// figure moves by about 10 bytes between builds, as the chunk hashes in it
// change.)

import { get, set } from 'idb-keyval'

import {
  asRecord,
  BASE_ENVIRONMENT,
  CHANNEL_RECORD_KEY,
  CHANNELS_KEY,
  type ChannelRecord,
  DATA_SCHEMA_VERSION,
  mirrorStore,
  readMirror,
  RELEASE_ID,
} from './dataRelease'

function writeMirror(record: ChannelRecord): void {
  try {
    mirrorStore()?.setItem(CHANNEL_RECORD_KEY, JSON.stringify(record))
  } catch {
    // A mirror that cannot be written costs the next launch the record's
    // release, which then reads the compiled fallback - the state
    // dataRelease.ts was in before the pointer existed - until the record
    // repairs it.
  }
}

/**
 * The record of the pointer entry this phone last verified, or null.
 *
 * Also the mirror's repair: a record the mirror does not match is written
 * back into it, for the next launch. A mirror with no record behind it is
 * left alone - the record is gone, and the next pointer read records again.
 */
export async function recallChannel(): Promise<ChannelRecord | null> {
  let record: ChannelRecord | null
  try {
    record = asRecord(await get(CHANNEL_RECORD_KEY))
  } catch {
    return readMirror()
  }
  if (record !== null) {
    const mirror = readMirror()
    if (mirror?.release !== record.release || mirror.at !== record.at) writeMirror(record)
  }
  return record
}

/**
 * How long one read of the pointer, or of the release manifest it names, may
 * take before it counts as unreachable.
 *
 * @unvalidated - lib/dataManifest.ts's MANIFEST_READ_TIMEOUT_MS, taken for the
 * same reason it gives: a fetch with no deadline HANGS on a captive portal at a
 * trailhead rather than failing. Twenty seconds is far longer than either read
 * has taken anywhere it was measured, and nobody has recorded what a real
 * trailhead connection does to them. Not imported, because that module imports
 * config.ts, which imports dataRelease.ts.
 */
export const CHANNEL_READ_TIMEOUT_MS = 20_000

/** What one pointer read did. Every outcome but `recorded` leaves the record
 *  as it was, which is the last good release or none. */
export type ChannelOutcome =
  /** No data base is configured, so there is no pointer to read. */
  | 'unconfigured'
  /** `channels.json` did not answer 200 in time: offline, a captive portal,
   *  a 404 before the first upload, or the request aborted. */
  | 'unreachable'
  /** It answered, but with no release id for this environment and schema
   *  version: not JSON, the wrong shape, or an entry that is not an id. */
  | 'malformed'
  /** The entry is the release already recorded. */
  | 'unchanged'
  /** The entry names a release whose manifest does not resolve here. */
  | 'unresolved'
  /** The entry resolved but IndexedDB would not keep it. */
  | 'unstorable'
  /** A new entry, verified and recorded: this phone's release from its next
   *  launch. */
  | 'recorded'

export interface ChannelAnswer {
  outcome: ChannelOutcome
  /** The release the record holds after this read, or null for none. */
  recorded: string | null
}

/**
 * The body at `url` as text, or null for an answer that is not 200-299; it
 * throws once CHANNEL_READ_TIMEOUT_MS passes or the caller aborts.
 *
 * THE BODY IS INSIDE THE DEADLINE, not only the headers. A server that sends
 * its headers and then stalls would otherwise outlive both the timeout and
 * the caller's abort, and the read would never settle. So the body read races
 * the same abort the request does, which also covers a fetch whose stream
 * does not honour the signal.
 */
async function textWithin(
  url: string,
  signal: AbortSignal | undefined,
  init: RequestInit = {},
): Promise<string | null> {
  // An abort that landed before this read began, as fetch itself treats one.
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
  const controller = new AbortController()
  const abort = () => controller.abort()
  const deadline = setTimeout(abort, CHANNEL_READ_TIMEOUT_MS)
  signal?.addEventListener('abort', abort, { once: true })
  const abandoned = new Promise<never>((_, reject) => {
    controller.signal.addEventListener(
      'abort',
      () => reject(new DOMException('Aborted', 'AbortError')),
      { once: true },
    )
  })
  try {
    const response = await Promise.race([
      fetch(url, { ...init, signal: controller.signal }),
      abandoned,
    ])
    if (!response.ok) return null
    return await Promise.race([response.text(), abandoned])
  } finally {
    clearTimeout(deadline)
    signal?.removeEventListener('abort', abort)
  }
}

/** The release id `channels.json`'s text names for this build, or null. */
function entryIn(text: string): string | null {
  let document: unknown
  try {
    document = JSON.parse(text)
  } catch {
    return null
  }
  if (typeof document !== 'object' || document === null) return null
  const channel = (document as Record<string, unknown>)[BASE_ENVIRONMENT]
  if (typeof channel !== 'object' || channel === null) return null
  const entry = (channel as Record<string, unknown>)[DATA_SCHEMA_VERSION]
  return typeof entry === 'string' && RELEASE_ID.test(entry) ? entry : null
}

/** Whether `release` resolves at `base`: its manifest answers 200 and reads as
 *  the manifest of that release (an `artifacts` object, and its own `release`
 *  field naming it where it carries one, as publish.py's staged ones do). */
async function resolves(
  base: string,
  release: string,
  signal?: AbortSignal,
): Promise<boolean> {
  try {
    const text = await textWithin(`${base}/releases/${release}/manifest.json`, signal)
    if (text === null) return false
    const manifest: unknown = JSON.parse(text)
    if (typeof manifest !== 'object' || manifest === null) return false
    const { artifacts, release: named } = manifest as Record<string, unknown>
    if (typeof artifacts !== 'object' || artifacts === null || Array.isArray(artifacts))
      return false
    return named === undefined || named === release
  } catch {
    return false
  }
}

/**
 * Read `channels.json` at `base` and record the release it names for this
 * build's environment and schema version, once that release resolves.
 *
 * On launch when online, beside #919's update check (lib/useTrailData.ts).
 * What it records is this phone's release from its NEXT launch: see
 * dataRelease.ts's SESSION_RELEASE for why never this one.
 *
 * A PHONE NEVER ENDS WITH NO DATA BECAUSE OF THIS. Missing, malformed or
 * unreachable, a pointer changes nothing: the record keeps the last release
 * this phone verified, and with no record the compiled fallback stands. An
 * entry naming a release whose manifest does not resolve is never recorded.
 * Never rejects; a caller may drop the promise.
 */
export async function readDataChannel(
  base: string,
  { signal }: { signal?: AbortSignal } = {},
): Promise<ChannelAnswer> {
  if (base === '') return { outcome: 'unconfigured', recorded: null }
  let recorded: ChannelRecord | null = null
  try {
    recorded = await recallChannel()
  } catch {
    recorded = null
  }
  const kept = (outcome: ChannelOutcome): ChannelAnswer => ({
    outcome,
    recorded: recorded?.release ?? null,
  })

  let text: string | null
  try {
    // no-store: the pointer is what says which release is current, and a
    // cached copy is the one answer it must not give (publish.py serves it
    // no-cache, as it serves latest.json).
    text = await textWithin(`${base}/${CHANNELS_KEY}`, signal, { cache: 'no-store' })
  } catch {
    return kept('unreachable')
  }
  if (text === null) return kept('unreachable')

  const entry = entryIn(text)
  if (entry === null) return kept('malformed')
  if (entry === recorded?.release) return kept('unchanged')
  if (!(await resolves(base, entry, signal))) return kept('unresolved')

  const record: ChannelRecord = {
    release: entry,
    schema: DATA_SCHEMA_VERSION,
    environment: BASE_ENVIRONMENT,
    at: Date.now(),
  }
  try {
    await set(CHANNEL_RECORD_KEY, record)
  } catch {
    // The mirror only follows the record, so a record that was not written
    // leaves the mirror alone too and the two cannot disagree that way round.
    return kept('unstorable')
  }
  writeMirror(record)
  return { outcome: 'recorded', recorded: entry }
}
