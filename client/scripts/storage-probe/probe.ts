// The page half of the storage probe: it drives the REAL download path
// (lib/archiveDownload.ts) against a real browser, and reports what came back.
//
// Nothing here re-implements the download. The whole point is that the code a
// hiker runs is the code being measured - the unit suite mocks `idb-keyval` and
// never sees a byte, so every question this file asks is one that suite
// structurally cannot answer (TESTING.md, "Storage has one layer").

import { clear, get, set } from 'idb-keyval'
import {
  deleteArchive,
  downloadArchive,
  readDownloadProgress,
} from '../../src/lib/archiveDownload'
import { readArchive, readComplete, segmentKeyFor } from '../../src/lib/archiveStore'
import { estimateAvailableBytes } from '../../src/lib/storageHealth'

declare global {
  interface Window {
    probe: (bytes: number) => Promise<Record<string, unknown>>
    reclaim: (bytes: number) => Promise<Record<string, unknown>>
    storeProbe: (bytes: number) => Promise<Record<string, unknown>>
    survey: (packageKey: string) => Promise<Record<string, unknown>>
    estimate: () => Promise<Record<string, unknown>>
  }
}

const KEY = 'ourhike:probe'

/** One shared filler block, reused for every Blob part: the Blob constructor
 *  copies what it is given, so building a gigabyte-sized Blob never needs a
 *  gigabyte-sized allocation. Not zeros - a compressible payload would let a
 *  layer underneath cheat on size. */
const PART = 4 * 1024 * 1024
const FILLER = new Uint8Array(PART)
for (let i = 0; i < PART; i += 512) FILLER[i] = i & 0xff
const filler = (bytes: number) => (bytes === PART ? FILLER : FILLER.subarray(0, bytes))

const report = (result: Record<string, unknown>) => {
  const line = JSON.stringify(result)
  document.querySelector('#log')!.textContent += `${line}\n`
  // The driver reads results off the console, so this is the wire format.
  console.log(line)
  return result
}

async function usage(): Promise<number> {
  return (await navigator.storage.estimate()).usage ?? -1
}

/** What storageHealth.ts's estimateAvailableBytes computes, and therefore what
 *  archiveDownload.ts's room check refuses on. */
async function available(): Promise<number> {
  const { quota, usage: used } = await navigator.storage.estimate()
  return quota === undefined || used === undefined ? -1 : quota - used
}

/**
 * A whole download of `bytes`, through the real module, timed.
 *
 * `elapsedMs` next to `error` is the number that matters: a failure that took
 * as long as the transfer is a failure that spent the hiker's data to find out.
 */
window.probe = async (bytes) => {
  await clear()
  const artifactKey = `probe_${bytes}.pmtiles`
  // Teaches the stub manifest this size before the download reads it.
  await fetch(`/data/latest.json?sizes=${bytes}`)

  const marks: { at: number; received: number }[] = []
  const started = performance.now()
  let error: string | null = null

  try {
    await downloadArchive(KEY, `/data/${artifactKey}`, {
      artifactKey,
      onProgress: ({ receivedBytes }) =>
        marks.push({ at: performance.now() - started, received: receivedBytes }),
    })
  } catch (thrown) {
    error = thrown instanceof Error ? `${thrown.name}: ${thrown.message}` : String(thrown)
  }

  const elapsed = performance.now() - started
  // Through the accessor, not the bare key: since #553 a finished archive is a
  // run of segment records named by a marker (src/lib/archiveStore.ts).
  const stored = await readArchive(KEY)

  /** Throughput over a slice of the transfer, in MB/s - the first quarter
   *  against the last is what would show a per-chunk cost that grows with what
   *  is already held. */
  const rate = (from: number, to: number) => {
    const window = marks.filter(
      (mark) => mark.received >= bytes * from && mark.received <= bytes * to,
    )
    if (window.length < 2) return null
    const first = window[0]
    const last = window[window.length - 1]
    const seconds = (last.at - first.at) / 1000
    return seconds === 0
      ? null
      : Math.round((last.received - first.received) / seconds / 1e5) / 10
  }

  return report({
    bytes,
    elapsedMs: Math.round(elapsed),
    storedBytes: stored?.size ?? null,
    partial: await readDownloadProgress(KEY),
    error,
    chunks: marks.length,
    firstQuarterMBps: rate(0, 0.25),
    lastQuarterMBps: rate(0.75, 1),
  })
}

/**
 * Storing one record of `bytes`, built the way the download builds it - one
 * Blob per chunk, each wrapping the last - with no network and no hashing, so
 * the store's own limits are separable from everything it shares a loop with.
 */
window.storeProbe = async (bytes) => {
  await clear()
  const before = await usage()

  let value: Blob = new Blob([])
  for (let at = 0; at < bytes; at += PART) {
    value = new Blob([value, filler(Math.min(PART, bytes - at))])
  }
  // Whether accumulating is charged against the quota at all, which is why a
  // download can run to completion and only then be refused.
  const afterBuild = await usage()

  let error: string | null = null
  let storedBytes: number | null = null
  try {
    await set('probe', value)
    storedBytes = ((await get('probe')) as Blob | undefined)?.size ?? null
  } catch (thrown) {
    error =
      thrown instanceof Error ? `${thrown.name}: "${thrown.message}"` : String(thrown)
  }

  return report({
    bytes,
    built: value.size,
    storedBytes,
    error,
    before,
    afterBuild,
    afterSet: await usage(),
  })
}

/**
 * When the space a deleted archive occupied comes back (#554).
 *
 * The app's own recommended remedy is "delete the Standard sheet, then download
 * the Fine one" - DownloadCard's locked detail picker says so, and #544's
 * refusal message says "freeing up space... makes room for it". If the quota is
 * not reclaimed by the time the next transfer's room check runs, the app refuses
 * a download the phone genuinely has room for, having just told the hiker to do
 * the thing that would make room. On a trailhead connection that is a wasted
 * trip.
 *
 * Three questions, and they want different fixes (#554):
 *
 *   1. WHEN does usage drop - a flush, a transaction boundary, a timer, the next
 *      page load? Polled below, with the elapsed time on every sample.
 *   2. Is `estimate()` LAGGING, or are the bytes genuinely still held? The store
 *      is read back empty first, so any usage still reported after that is the
 *      ACCOUNTING rather than the data - which makes the room check the thing
 *      that should stop refusing, not the delete the thing that should try
 *      harder.
 *   3. Can `deleteArchive` force reclamation at all?
 *
 * Deletes through `deleteArchive`, not `clear()`, because the app path is the
 * subject - and since #553 that path removes a run of segment records plus a
 * marker rather than one blob, which is a different shape to reclaim.
 */
window.reclaim = async (bytes) => {
  await clear()
  const idle = await usage()

  // Stored as the segments a real download leaves behind, at the real segment
  // size, so the reclamation is measured against the shape the app produces.
  const SEGMENT = 32 * 1024 * 1024
  let segments = 0
  for (let at = 0; at < bytes; at += SEGMENT) {
    const size = Math.min(SEGMENT, bytes - at)
    const parts: Uint8Array[] = []
    for (let filled = 0; filled < size; filled += PART) {
      parts.push(filler(Math.min(PART, size - filled)))
    }
    await set(segmentKeyFor(KEY, 0, segments), new Blob(parts))
    segments += 1
  }
  await set(`${KEY}:complete`, { generation: 0, segments, totalBytes: bytes })
  const afterStore = await usage()

  const started = performance.now()
  await deleteArchive(KEY)
  const deleteMs = Math.round(performance.now() - started)

  // Question 2, answered before any polling: the store really is empty. If usage
  // still counts the bytes after this, it is the accounting that is behind.
  const stillReadable = (await readArchive(KEY)) !== undefined
  const marker = await readComplete(KEY)

  // Question 1. Sampled rather than waited on, so the ANSWER is the curve and
  // not a single number that happens to have been taken after it settled.
  const samples: { atMs: number; usage: number }[] = []
  const settled = idle + Math.max(0, bytes * 0.05)
  let reclaimedAtMs: number | null = null
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const now = await usage()
    samples.push({ atMs: Math.round(performance.now() - started), usage: now })
    if (now <= settled) {
      reclaimedAtMs = samples[samples.length - 1].atMs
      break
    }
    await new Promise((resolve) => setTimeout(resolve, 250))
  }

  return report({
    bytes,
    segments,
    idle,
    afterStore,
    deleteMs,
    // Both must be false/null for the usage figures below to be about
    // accounting rather than about data still on disk.
    stillReadable,
    markerLeft: marker !== null,
    reclaimedAtMs,
    finalUsage: samples[samples.length - 1]?.usage ?? null,
    // The browser's own arithmetic, which is what the app refused on before
    // #554: quota - usage, still counting the deleted bytes.
    browserSaysFree: await available(),
    // What the app computes NOW - estimateAvailableBytes credits a release the
    // accounting has not returned, so this is the number `shortfall` refuses on
    // and the one that decides whether the printed remedy works.
    appSaysFree: await estimateAvailableBytes(),
    samples: samples.filter(
      (_, index) => index % 4 === 0 || index === samples.length - 1,
    ),
  })
}

/** Every record the download path writes for one package, as it stands right
 *  now - runnable from a second page while a transfer is in flight, which is
 *  how "nothing is checkpointed" is observed rather than assumed. */
window.survey = async (packageKey) => {
  const out: Record<string, unknown> = {}
  const show = (value: unknown) =>
    value instanceof Blob
      ? `Blob(${value.size})`
      : value === undefined
        ? null
        : JSON.stringify(value).slice(0, 100)

  for (const suffix of [
    '',
    ':partial',
    ':progress',
    ':source',
    ':version',
    ':complete',
  ]) {
    out[`${packageKey}${suffix}`] = show(await get(`${packageKey}${suffix}`))
  }

  // The segments themselves, which are where the bytes are during a transfer
  // and after one (#553). Reported per generation and per record rather than as
  // a total, because "which of these is on disk right now" is the question this
  // probe exists to answer - the original run of it showed every record null
  // eight seconds into an eleven-second download.
  for (const generation of [0, 1]) {
    const present: string[] = []
    for (let index = 0; ; index += 1) {
      const value = await get(segmentKeyFor(packageKey, generation, index))
      if (!(value instanceof Blob)) break
      present.push(`${index}:${value.size}`)
    }
    out[`${packageKey}:g${generation}`] = present.length === 0 ? null : present.join(' ')
  }

  out.archiveBytes = (await readArchive(packageKey))?.size ?? null
  out.complete = await readComplete(packageKey)
  out.usage = await usage()
  out.completedMarker = localStorage.getItem(`${packageKey}:completed`)
  return report(out)
}

window.estimate = async () => {
  const { quota, usage: used } = await navigator.storage.estimate()
  return report({ quota, usage: used, persisted: await navigator.storage.persisted() })
}
