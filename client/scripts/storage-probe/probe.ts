// The page half of the storage probe: it drives the REAL download path
// (lib/archiveDownload.ts) against a real browser, and reports what came back.
//
// Nothing here re-implements the download. The whole point is that the code a
// hiker runs is the code being measured - the unit suite mocks `idb-keyval` and
// never sees a byte, so every question this file asks is one that suite
// structurally cannot answer (TESTING.md, "Storage has one layer").

import { clear, get, set } from 'idb-keyval'
import { downloadArchive, readDownloadProgress } from '../../src/lib/archiveDownload'
import { readArchive, readComplete, segmentKeyFor } from '../../src/lib/archiveStore'

declare global {
  interface Window {
    probe: (bytes: number) => Promise<Record<string, unknown>>
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
