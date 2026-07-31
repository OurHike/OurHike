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

export const ARCHIVE_PARTIAL_KEY = 'ourhike:corridor-archive:partial'
export const ARCHIVE_PROGRESS_KEY = 'ourhike:corridor-archive:progress'

export interface DownloadProgress {
  receivedBytes: number
  totalBytes: number
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
  url: string,
  { onProgress, signal }: DownloadOptions = {},
): Promise<void> {
  const heldBlob = (await get(ARCHIVE_PARTIAL_KEY)) as Blob | undefined
  const heldBytes = heldBlob?.size ?? 0

  const response = await fetch(url, {
    signal,
    headers: heldBytes > 0 ? { Range: `bytes=${heldBytes}-` } : undefined,
  })

  if (!response.ok) {
    throw new Error(`Archive download failed: ${response.status} ${response.statusText}`)
  }

  // A 206 means the server honoured the range and is sending the remainder.
  // A 200 in reply to a Range request means it ignored it and is sending the
  // WHOLE file - appending that to what we hold would produce a corrupt
  // archive of exactly the expected length, which passes every size check and
  // then renders a broken map. Start clean instead.
  const resumed = heldBytes > 0 && response.status === 206
  let accumulated: Blob = resumed && heldBlob ? heldBlob : new Blob([])

  const declared = Number(response.headers.get('content-length') ?? 0)
  const totalBytes = resumed ? heldBytes + declared : declared

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
    await persistPartial(accumulated, totalBytes)
    throw error
  }

  if (totalBytes > 0 && accumulated.size !== totalBytes) {
    // Truncation: a short PMTiles archive opens fine and then returns nothing
    // for tiles past the cut, which looks like missing map rather than a
    // failed download. Keep the bytes so a resume can finish the job.
    await persistPartial(accumulated, totalBytes)
    throw new ArchiveSizeMismatchError(totalBytes, accumulated.size)
  }

  await set(CORRIDOR_ARCHIVE_KEY, accumulated)
  await del(ARCHIVE_PARTIAL_KEY)
  await del(ARCHIVE_PROGRESS_KEY)
}

async function persistPartial(blob: Blob, totalBytes: number): Promise<void> {
  await set(ARCHIVE_PARTIAL_KEY, blob)
  await set(ARCHIVE_PROGRESS_KEY, { receivedBytes: blob.size, totalBytes })
}

/** What Downloads.tsx shows on load, before anything is tapped. */
export async function readDownloadProgress(): Promise<DownloadProgress | null> {
  return ((await get(ARCHIVE_PROGRESS_KEY)) as DownloadProgress | undefined) ?? null
}

/** Reclaims the space, partial bytes included - someone deleting a 1.18 GB
 *  map to free room would not expect a stalled attempt to keep holding
 *  several hundred megabytes of it. */
export async function deleteArchive(): Promise<void> {
  await del(CORRIDOR_ARCHIVE_KEY)
  await del(ARCHIVE_PARTIAL_KEY)
  await del(ARCHIVE_PROGRESS_KEY)
}
