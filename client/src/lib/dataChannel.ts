// Reading the pointer, `channels.json`: what lib/dataRelease.ts
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
//
// The gone-release check (manifestAnswers404 and forget, below) went in here for
// the same reason. Measured 2026-10-15 the same way: the eager closure was
// 244,748-244,759 bytes over three builds before it and 244,745-244,755 over
// four after, inside that drift, and this chunk went from 898 bytes to 1,035.

import { del, get, set } from 'idb-keyval'

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
 *  as it stood when the pointer was read: the last good release, or none -
 *  none, too, when the answer's `forgotten` names a release the gone-release
 *  check deleted first. */
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
  /** The release this read forgot: the record named it and its
   *  own manifest answered 404, so the mirror was removed and the record
   *  deleted - or, where IndexedDB refused the delete, left for the next
   *  launch's check to forget again (forget says how). Absent when nothing
   *  was forgotten. `recorded` is null after a forgetting either way, because
   *  the pointer is then read as on a phone with no record. */
  forgotten?: string
}

/**
 * Fetch `url` and return `read(response)`, both under one deadline: it throws
 * once CHANNEL_READ_TIMEOUT_MS passes or the caller aborts.
 *
 * THE BODY IS INSIDE THE DEADLINE, not only the headers. A server that sends
 * its headers and then stalls would otherwise outlive both the timeout and
 * the caller's abort, and the read would never settle. So `read` races the
 * same abort the request does, which also covers a fetch whose stream does
 * not honour the signal.
 */
async function within<T>(
  url: string,
  signal: AbortSignal | undefined,
  init: RequestInit,
  read: (response: Response) => Promise<T>,
): Promise<T> {
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
    return await Promise.race([read(response), abandoned])
  } finally {
    clearTimeout(deadline)
    signal?.removeEventListener('abort', abort)
  }
}

/** The body at `url` as text, or null for an answer that is not 200-299,
 *  under {@link within}'s deadline. */
function textWithin(
  url: string,
  signal: AbortSignal | undefined,
  init: RequestInit = {},
): Promise<string | null> {
  return within(url, signal, init, async (response) =>
    response.ok ? response.text() : null,
  )
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
 * Whether `release`'s own manifest at `base` answers exactly 404: the one
 * answer that makes readDataChannel forget a recorded release.
 *
 * Every other result is false: a 200, a 5xx or any other status, no answer,
 * the deadline passing, the caller aborting. Each of those is also what a
 * good release looks like from a phone on one bar of signal, and forgetting
 * on any of them would send that phone back to the compiled DATA_RELEASE,
 * which can be older than the release it recorded. Over HTTPS a captive
 * portal cannot present the data host's certificate, so a portal arrives
 * here as no answer, not as a 404.
 *
 * A HEAD, because the status is the whole question and the manifest is not
 * small. Measured 2026-10-15 with curl sending `Origin: https://ourhike.org`:
 * UA's releases/2026-10-10-2/manifest.json is 851,076 bytes, 213,769 on the
 * wire as brotli, which a GET would spend on every launch that holds a
 * record; the bucket answers a HEAD for it 200, and for UA's gone 2026-09-24-2
 * 404, each with Access-Control-Allow-Origin, so a browser can read either
 * status (.github/expected-origins.yml allows HEAD beside GET). Nothing in the
 * app answers it first: the service worker vite.config.ts generates routes
 * only precached same-origin GETs and navigations (read from the built
 * dist/sw.js the same day).
 *
 * `no-store`, because that manifest carries no Cache-Control (measured the
 * same day), so a browser may keep a 200 for it on heuristic freshness after
 * the folder has gone (Reasoned, from RFC 9111 §4.2.2).
 */
async function manifestAnswers404(
  base: string,
  release: string,
  signal?: AbortSignal,
): Promise<boolean> {
  try {
    const status = await within(
      `${base}/releases/${release}/manifest.json`,
      signal,
      { method: 'HEAD', cache: 'no-store' },
      async (response) => response.status,
    )
    return status === 404
  } catch {
    return false
  }
}

/**
 * Delete the record and its mirror, so that the next launch
 * reads the compiled DATA_RELEASE and then reads `channels.json` again.
 *
 * The mirror goes first, and whether or not IndexedDB deletes the record,
 * because the mirror is what the next launch's SESSION_RELEASE is read from
 * (lib/dataRelease.ts). A record IndexedDB will not delete is read again by
 * the next launch's recallChannel, which writes the mirror back from it, and
 * that launch's own check forgets it again if it hears the 404 again: only a
 * launch that hears no answer leaves the mirror for the one after it.
 */
async function forget(): Promise<void> {
  try {
    mirrorStore()?.removeItem(CHANNEL_RECORD_KEY)
  } catch {
    // The next launch reads the mirror as it stands, and its check asks again.
  }
  try {
    await del(CHANNEL_RECORD_KEY)
  } catch {
    // Left for the next launch's check, as above.
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
 *
 * FIRST, A RECORDED RELEASE WHOSE FOLDER IS GONE IS FORGOTTEN
 * (#1833 — A phone that recorded a data release keeps reading it after the
 * folder is gone, and no app update moves it off). Before the pointer is
 * read, and whatever it says, a phone with a record asks for that release's
 * own manifest; exactly 404 deletes the record and its mirror
 * (manifestAnswers404 says why nothing else counts). This session keeps the
 * release it started on. The next launch reads the compiled DATA_RELEASE and
 * then the pointer, as a phone with no record does, and a pointer naming the
 * same gone release is `unresolved` like any other. The check does not wait
 * on the pointer because a bucket move like the one of 2026-10-02,
 * which copied nothing, takes `channels.json` with the folder, and then the
 * pointer can never move the phone. Before this nothing deleted the record,
 * so a recorded release outranked every DATA_RELEASE an app update shipped.
 * The promise above still holds: a release whose own manifest answers 404 is
 * already one the phone cannot download from. Silent, by the maintainer's
 * choice: nothing for the hiker to tap.
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

  let forgotten: string | undefined
  if (recorded !== null && (await manifestAnswers404(base, recorded.release, signal))) {
    forgotten = recorded.release
    recorded = null
    await forget()
  }
  const answer = (outcome: ChannelOutcome, release: string | null): ChannelAnswer =>
    forgotten === undefined
      ? { outcome, recorded: release }
      : { outcome, recorded: release, forgotten }
  const kept = (outcome: ChannelOutcome): ChannelAnswer =>
    answer(outcome, recorded?.release ?? null)

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
  return answer('recorded', entry)
}
