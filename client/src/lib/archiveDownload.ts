// Downloads a PMTiles archive into IndexedDB, resumably.
//
// This is what sits behind the Downloads screen's buttons, and it is more
// than a `fetch` for one reason: WIREFRAMES.md `7a` promises a failed
// transfer RESUMES rather than restarts. Re-pulling 300 MB from zero because
// a connection dropped at 90% is precisely the failure someone on trailhead
// wifi cannot afford, and it is the failure that promise exists to prevent.
//
// Partial bytes live under their own key, separate from the completed
// archive. That separation is what lets a failed attempt leave both the
// work-in-progress AND any previously-working archive intact - someone with a
// good map on their phone who taps download and loses signal should still
// have their good map.
//
// Blobs are appended rather than buffered: `new Blob([previous, chunk])`
// references its parts rather than copying them, so a 300 MB archive is never
// held in memory as one contiguous allocation.
//
// NOT verified here: a content hash. publish.py records a SHA-256 per
// artifact, and checking it would catch corruption that a length check
// cannot - but SubtleCrypto has no streaming digest, so hashing a 1.18 GB
// archive means materialising the whole thing in memory, which is exactly
// what the Blob-append approach above avoids. Length is checked instead,
// which catches truncation (the common failure). Real hash verification
// wants an incremental implementation and is worth doing separately.

import { get, set, del } from 'idb-keyval'
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'

/**
 * Every function here takes the PACKAGE key - the IndexedDB key the finished
 * archive lives under (lib/packages.ts) - and derives the download records
 * from it. One suffix scheme for every package is what keeps "does package X
 * have a resumable partial" answerable without a registry of record names,
 * and it is exactly the layout the original single-archive store used, so
 * the corridor package's records keep their historical names.
 */
export const partialKeyFor = (packageKey: string) => `${packageKey}:partial`
export const progressKeyFor = (packageKey: string) => `${packageKey}:progress`
export const sourceKeyFor = (packageKey: string) => `${packageKey}:source`

/** The corridor package's record names, spelled out for the reader and for
 *  tests that assert against the real stored layout. */
export const ARCHIVE_PARTIAL_KEY = partialKeyFor(CORRIDOR_ARCHIVE_KEY)
export const ARCHIVE_PROGRESS_KEY = progressKeyFor(CORRIDOR_ARCHIVE_KEY)
export const ARCHIVE_SOURCE_KEY = sourceKeyFor(CORRIDOR_ARCHIVE_KEY)

export interface DownloadProgress {
  receivedBytes: number
  totalBytes: number
}

/**
 * What the held partial bytes actually came from.
 *
 * Without this a resume asks for "the rest of the file" with no statement of
 * which file, and gets whatever is at that URL now. Two ways that ends badly:
 * the archive is republished between attempts, or the hiker picks a different
 * detail level - and either way the result is bytes from two different
 * archives concatenated into one.
 *
 * The size check cannot catch that, and not by oversight: totalBytes is
 * DEFINED as heldBytes + declared, and a completed resume accumulates exactly
 * heldBytes + declared. Both sides of that comparison are the same expression,
 * so it can only ever catch a SHORT transfer. A spliced one always passes,
 * producing a PMTiles file whose directory and tile offsets disagree - a map
 * that reports itself downloaded and renders wrong past the seam, with no
 * network to correct it.
 */
interface PartialSource {
  url: string
  /** Absent when the bucket does not expose ETag; the url check still applies. */
  etag?: string
}

export interface DownloadOptions {
  onProgress?: (progress: DownloadProgress) => void
  signal?: AbortSignal
}

export class ArchiveSizeMismatchError extends Error {
  constructor(expected: number, actual: number) {
    super(
      `Downloaded archive is ${actual} bytes but the server said ${expected}. ` +
        `Keeping what arrived so it can be resumed.`,
    )
    this.name = 'ArchiveSizeMismatchError'
  }
}

export async function downloadArchive(
  packageKey: string,
  url: string,
  { onProgress, signal }: DownloadOptions = {},
): Promise<void> {
  const storedBlob = (await get(partialKeyFor(packageKey))) as Blob | undefined
  const storedSource = (await get(sourceKeyFor(packageKey))) as PartialSource | undefined

  // Only resume onto bytes we can prove came from this same URL. An
  // unidentified partial - a different detail level, or one written by a build
  // before this record existed - is discarded rather than appended to.
  const usable = storedBlob !== undefined && storedSource?.url === url
  if (storedBlob !== undefined && !usable) await discardPartial(packageKey)

  const heldBlob = usable ? storedBlob : undefined
  const heldBytes = heldBlob?.size ?? 0

  const headers: Record<string, string> = {}
  if (heldBytes > 0) {
    headers.Range = `bytes=${heldBytes}-`
    // If-Range makes the server itself arbitrate: the range is honoured only
    // while the object still matches, and a republished archive comes back 200
    // with the whole body instead. The 206 check below already treats that as
    // "start clean", so the correct behaviour is code that already exists.
    if (storedSource?.etag !== undefined) headers['If-Range'] = storedSource.etag
  }

  const response = await fetch(url, {
    signal,
    headers: heldBytes > 0 ? headers : undefined,
  })

  if (!response.ok) {
    throw new Error(`Archive download failed: ${response.status} ${response.statusText}`)
  }

  // A 206 means the server honoured the range and is sending the remainder.
  // A 200 in reply to a Range request means it ignored it and is sending the
  // WHOLE file - appending that to what we hold would produce a corrupt
  // archive of exactly the expected length, which passes every size check and
  // then renders a broken map. Start clean instead.
  // Tested against the blob rather than against heldBytes, which says the same
  // thing here - heldBytes IS heldBlob's size, and a 206 can only arrive in
  // reply to the Range header above, which is only sent when that size is
  // non-zero. Phrasing it this way lets the type narrowing flow into the line
  // below, instead of needing a second `&& heldBlob` there that no input could
  // ever make false.
  const resumed = heldBlob !== undefined && response.status === 206
  let accumulated: Blob = resumed ? heldBlob : new Blob([])

  const declared = Number(response.headers.get('content-length') ?? 0)
  const totalBytes = resumed ? heldBytes + declared : declared

  // Taken from the response actually being read, so a partial is always
  // labelled with the version it came from. A weak ETag is dropped: it only
  // promises semantic equivalence, which is not the byte-for-byte identity a
  // range append depends on.
  const responseEtag = response.headers.get('etag') ?? undefined
  const source: PartialSource = {
    url,
    etag:
      responseEtag !== undefined && !responseEtag.startsWith('W/')
        ? responseEtag
        : resumed
          ? storedSource?.etag
          : undefined,
  }

  let receivedBytes = accumulated.size
  onProgress?.({ receivedBytes, totalBytes })

  const reader = response.body?.getReader()
  if (reader === undefined) throw new Error('Archive download failed: no response body')

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')

      accumulated = new Blob([accumulated, value])
      receivedBytes = accumulated.size
      onProgress?.({ receivedBytes, totalBytes })
    }
  } catch (error) {
    // Everything received so far is kept. The next attempt picks up here
    // rather than starting again.
    await persistPartial(packageKey, accumulated, totalBytes, source)
    throw error
  }

  if (totalBytes > 0 && accumulated.size !== totalBytes) {
    // Truncation: a short PMTiles archive opens fine and then returns nothing
    // for tiles past the cut, which looks like missing map rather than a
    // failed download. Keep the bytes so a resume can finish the job.
    await persistPartial(packageKey, accumulated, totalBytes, source)
    throw new ArchiveSizeMismatchError(totalBytes, accumulated.size)
  }

  await set(packageKey, accumulated)
  await discardPartial(packageKey)
}

async function persistPartial(
  packageKey: string,
  blob: Blob,
  totalBytes: number,
  source: PartialSource,
): Promise<void> {
  // Source first. Every later write can fail - quota is exactly the situation
  // that produces a partial - and a partial with no source record is discarded
  // on the next attempt rather than resumed onto blindly. Writing the identity
  // last would leave the dangerous combination (bytes, no identity) reachable.
  await set(sourceKeyFor(packageKey), source)
  await set(partialKeyFor(packageKey), blob)
  await set(progressKeyFor(packageKey), { receivedBytes: blob.size, totalBytes })
}

async function discardPartial(packageKey: string): Promise<void> {
  await del(partialKeyFor(packageKey))
  await del(progressKeyFor(packageKey))
  await del(sourceKeyFor(packageKey))
}

/** What Downloads.tsx shows on load, before anything is tapped. */
export async function readDownloadProgress(
  packageKey: string,
): Promise<DownloadProgress | null> {
  return ((await get(progressKeyFor(packageKey))) as DownloadProgress | undefined) ?? null
}

/** Reclaims one package's space, partial bytes included - someone deleting a
 *  1.18 GB map to free room would not expect a stalled attempt to keep
 *  holding several hundred megabytes of it. Other packages' archives and
 *  partials are untouched by construction: every record touched here derives
 *  from this one key. */
export async function deleteArchive(packageKey: string): Promise<void> {
  await del(packageKey)
  await discardPartial(packageKey)
}
