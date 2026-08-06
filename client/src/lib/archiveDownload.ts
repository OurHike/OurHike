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
// Verified here, since #197: the completed bytes are checked against the
// SHA-256 publish.py records for that artifact in `latest.json`. This used to
// say it could not be done - SubtleCrypto has no streaming digest, and
// hashing a 1.18 GB archive through it means materialising the whole thing in
// memory, which is exactly what the Blob-append above avoids. The way out is
// that SHA-256 itself is a fold over 64-byte blocks: lib/sha256.ts hashes the
// chunks the read loop already sees, one at a time, and carries its own state
// across a resume. Nothing is ever held in memory that was not already.
//
// Why it matters more than the length check: `totalBytes` is DEFINED as
// heldBytes + declared, so a completed resume accumulates exactly that and
// the comparison can only catch a SHORT transfer. Bytes from two different
// builds spliced at the resume point produce a file of exactly the right
// length - a PMTiles archive whose directory disagrees with its tiles, which
// reports itself downloaded and renders a wrong map with no network to
// correct it (DATA_RELEASES.md consequence #1).
//
// A published hash is not always available - an older release, a field-test
// server, no bucket configured - and its absence downgrades the download to
// the checks that came before rather than failing it.
//
// A verified hash is also kept beside the archive (`readArchiveVersion`), so
// which build a phone holds is a question the app can now answer at all.

import { get, set, del } from 'idb-keyval'
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'
import { clearCompleted, recordCompleted } from './storageHealth'
import { publishedHash } from './dataManifest'
import { Sha256, type Sha256State } from './sha256'

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
export const versionKeyFor = (packageKey: string) => `${packageKey}:version`

/** The corridor package's record names, spelled out for the reader and for
 *  tests that assert against the real stored layout. */
export const ARCHIVE_PARTIAL_KEY = partialKeyFor(CORRIDOR_ARCHIVE_KEY)
export const ARCHIVE_PROGRESS_KEY = progressKeyFor(CORRIDOR_ARCHIVE_KEY)
export const ARCHIVE_SOURCE_KEY = sourceKeyFor(CORRIDOR_ARCHIVE_KEY)
export const ARCHIVE_VERSION_KEY = versionKeyFor(CORRIDOR_ARCHIVE_KEY)

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
  /**
   * The published SHA-256 these bytes are being accumulated toward, when the
   * manifest named one.
   *
   * This is the defence that does not depend on the bucket's CORS policy. The
   * `If-Range` check above is the better one when it works, but it works only
   * where `etag` is exposed to the page - and DATA_RELEASES.md's consequence
   * #1 is precisely the case where it is not. A published hash that has moved
   * since these bytes were held says the archive was republished, whatever
   * the response headers do or do not say, and the partial is dropped rather
   * than appended to.
   */
  sha256?: string
  /**
   * How far the hash of the held bytes had got. Carrying it means an app
   * restart at 900 MB costs no re-read; its absence, or a state that claims
   * more bytes than the partial holds (source is written before the blob, and
   * that write can fail), simply means hashing the held bytes again.
   */
  hash?: Sha256State
}

/** How far through re-reading the bytes already held this attempt has got. */
export interface CheckProgress {
  checkedBytes: number
  totalBytes: number
}

export interface DownloadOptions {
  /**
   * Which artifact this is, as `latest.json` names it - the flat bucket key
   * `publish.py` uploaded, e.g. `background_z13.pmtiles`.
   *
   * Required, and required for a reason. This used to be derived from the
   * URL's last segment, which worked only for as long as every artifact's URL
   * happened to read like its manifest key; the first one that did not would
   * have found no manifest entry, and "no published hash" means the download
   * proceeds UNVERIFIED. A silent downgrade of the check this module exists
   * for is not something a caller should be able to cause by omission, so the
   * catalog that knows a package's identity states it (lib/packages.ts) and
   * the type will not let it be forgotten.
   */
  artifactKey: string
  onProgress?: (progress: DownloadProgress) => void
  /**
   * Called while the bytes already on the phone are read back to catch their
   * hash up - a partial written before this file recorded hash state, or by
   * an attempt that found no published hash to check against.
   *
   * It exists because that work is invisible and slow in the same way a dead
   * connection is: several seconds of nothing for a gigabyte, on a phone,
   * before the transfer even starts. Someone resuming on one bar has no way
   * to tell a stalled network from a busy phone, and the two ask for
   * completely different responses - wait, or walk somewhere else. This is
   * what lets the screen say which is happening.
   */
  onChecking?: (progress: CheckProgress) => void
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

/**
 * The archive arrived whole and is not the archive that was published.
 *
 * Unlike a short transfer, nothing here is worth keeping: the bytes are of
 * the right length and the wrong content, so resuming onto them would only
 * rebuild the same wrong file. They are discarded and the hiker is told
 * plainly, which is the one honest option - a map that renders confidently
 * from spliced bytes is the failure this whole check exists to prevent.
 */
export class ArchiveHashMismatchError extends Error {
  /** The hashes, for a field report or a log - deliberately kept out of the
   *  sentence a hiker reads, which is not improved by hex. */
  readonly expected: string
  readonly actual: string

  constructor(expected: string, actual: string) {
    super(
      `The map that arrived is not the one the server published, so it was ` +
        `not saved. Any map already on this phone is untouched. Try the ` +
        `download again.`,
    )
    this.name = 'ArchiveHashMismatchError'
    this.expected = expected
    this.actual = actual
  }
}

/** How much of a held partial is read at a time when its hash has to be
 *  recomputed. Big enough that a gigabyte is not ten thousand reads, small
 *  enough that it is never one gigabyte-sized ArrayBuffer. */
const HASH_READ_BYTES = 4 * 1024 * 1024

/** Brings `hash` up to the end of `blob`, reading in windows, reporting as it
 *  goes so a phone doing seconds of local work does not look like a dead
 *  connection. Reports nothing when there is nothing to catch up on. */
async function hashBlobFrom(
  hash: Sha256,
  blob: Blob,
  from: number,
  onChecking?: (progress: CheckProgress) => void,
): Promise<void> {
  if (from >= blob.size) return

  onChecking?.({ checkedBytes: from, totalBytes: blob.size })
  for (let at = from; at < blob.size; at += HASH_READ_BYTES) {
    const window = blob.slice(at, Math.min(at + HASH_READ_BYTES, blob.size))
    hash.update(new Uint8Array(await window.arrayBuffer()))
    onChecking?.({ checkedBytes: hash.bytesHashed, totalBytes: blob.size })
  }
}

/**
 * The hash accumulator for an attempt: caught up over whatever bytes are
 * already held, from a persisted state where there is a usable one.
 *
 * A state claiming more bytes than the partial holds is not usable - it can
 * only mean the source record outlived a failed blob write - and re-hashing
 * from zero is always correct, because the partial is append-only, so any
 * shorter state is a prefix of what is there now.
 */
async function resumeHash(
  held: Blob | undefined,
  state: Sha256State | undefined,
  onChecking?: (progress: CheckProgress) => void,
): Promise<Sha256> {
  if (held === undefined) return new Sha256()
  const hash =
    state !== undefined && state.byteLength <= held.size
      ? Sha256.fromState(state)
      : new Sha256()
  await hashBlobFrom(hash, held, hash.bytesHashed, onChecking)
  return hash
}

export async function downloadArchive(
  packageKey: string,
  url: string,
  { artifactKey, onProgress, onChecking, signal }: DownloadOptions,
): Promise<void> {
  const storedBlob = (await get(partialKeyFor(packageKey))) as Blob | undefined
  const storedSource = (await get(sourceKeyFor(packageKey))) as PartialSource | undefined

  // What the bucket currently says this artifact hashes to. Fetched per
  // attempt rather than cached, so a republish moves the expectation instead
  // of leaving every retry checking against bytes that are no longer served
  // (dataManifest.ts). Null where there is no published answer at all.
  //
  // **Unfinished, and needed for v1 (#192/#223).** Deriving the artifact name
  // from the URL is a stopgap taken because #192's multi-package store was
  // being written at the same time as this, and an explicit argument would
  // have put the two changes in the same files. Once the package catalog is
  // the place a package's identity lives, the expected hash belongs there and
  // should be passed in - a package that knows its own key should not have
  // that key re-guessed from a string. This is not optional polish: leaving
  // it means the one artifact whose URL does not read like its manifest key
  // silently downloads unverified, which is the failure mode this whole file
  // now exists to prevent.
  const publishedSha256 = await publishedHash(artifactKey, { signal })

  // Only resume onto bytes we can prove came from this same URL. An
  // unidentified partial - a different detail level, or one written by a build
  // before this record existed - is discarded rather than appended to.
  //
  // And onto bytes from this same BUILD: a partial held against a hash the
  // bucket has since replaced is from the previous release, and appending the
  // remainder of the new one to it is exactly the splice this cannot detect
  // afterwards by length. Caught here, before a byte is requested, rather
  // than left to the final digest - the difference is a wasted download.
  const republished =
    publishedSha256 !== null &&
    storedSource?.sha256 !== undefined &&
    storedSource.sha256 !== publishedSha256
  const usable = storedBlob !== undefined && storedSource?.url === url && !republished
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
  const etag =
    responseEtag !== undefined && !responseEtag.startsWith('W/')
      ? responseEtag
      : resumed
        ? storedSource?.etag
        : undefined

  // The expectation these bytes will be held to. A stored one applies only to
  // the bytes it was recorded against, so it carries forward on a resume and
  // is dropped when the server ignored the range and started the file again.
  const expected = publishedSha256 ?? (resumed ? (storedSource?.sha256 ?? null) : null)

  // Hashing is skipped outright when there is nothing to check against -
  // there is no point spending a phone's CPU, or re-reading a held partial,
  // to compute a digest no one will compare.
  const hash =
    expected === null
      ? null
      : await resumeHash(resumed ? heldBlob : undefined, storedSource?.hash, onChecking)

  const sourceRecord = (): PartialSource => ({
    url,
    etag,
    sha256: expected ?? undefined,
    hash: hash?.toState(),
  })

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
      hash?.update(value)
      receivedBytes = accumulated.size
      onProgress?.({ receivedBytes, totalBytes })
    }
  } catch (error) {
    // Everything received so far is kept. The next attempt picks up here
    // rather than starting again.
    await persistPartial(packageKey, accumulated, totalBytes, sourceRecord())
    throw error
  }

  if (totalBytes > 0 && accumulated.size !== totalBytes) {
    // Truncation: a short PMTiles archive opens fine and then returns nothing
    // for tiles past the cut, which looks like missing map rather than a
    // failed download. Keep the bytes so a resume can finish the job.
    await persistPartial(packageKey, accumulated, totalBytes, sourceRecord())
    throw new ArchiveSizeMismatchError(totalBytes, accumulated.size)
  }

  // What these bytes were finally verified as, which is not always what the
  // attempt set out to match - see the republish case below.
  let verified = expected

  if (expected !== null && hash !== null) {
    const actual = hash.digest()
    if (actual !== expected) {
      // Before throwing anything away: a mismatch has an innocent cause. The
      // bucket can be republished between the manifest read at the start of
      // this attempt and the last byte arriving, in which case what arrived
      // is a WHOLE, correct, newer archive that simply is not the build we
      // asked about. Discarding a gigabyte of good map over that would be a
      // real loss on a trailhead connection, so the manifest gets one more
      // read, and bytes that match what the bucket publishes NOW are kept.
      //
      // This does not soften the splice defence: a spliced file matches no
      // published hash at all, so it still ends up in the branch below.
      const republished = await publishedHash(artifactKey, { signal })
      if (republished !== null && republished === actual) {
        verified = actual
      } else {
        // Nothing is stored and nothing is kept: these bytes are the right
        // length and the wrong file, so a resume onto them would only rebuild
        // the same wrong archive. What is discarded is an unusable download,
        // never a map anyone is navigating by - any previously-completed
        // archive under the package key is left exactly where it was, so a
        // hiker with a working map who tried to update it still has it.
        await discardPartial(packageKey)
        throw new ArchiveHashMismatchError(expected, actual)
      }
    }
  }

  await set(packageKey, accumulated)
  // Which build is on this phone. Written after the blob, never before: a
  // version record for bytes that failed to store would be a claim about an
  // archive nobody has. Cleared rather than left standing when the archive
  // could not be verified, because a stale hash beside unverified bytes says
  // something false with more confidence than saying nothing.
  if (verified !== null) await set(versionKeyFor(packageKey), verified)
  else await del(versionKeyFor(packageKey))
  // After the blob is really stored, and in a different storage mechanism on
  // purpose: this is what later distinguishes "the archive was evicted" from
  // "no archive was ever downloaded" (storageHealth.ts, #190).
  recordCompleted(packageKey)
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

/**
 * Which published build the archive under `packageKey` actually is - its
 * verified SHA-256 - or null where the archive was stored without a hash to
 * check it against.
 *
 * This is the record `DATA_RELEASES.md` consequence #2 says does not exist:
 * "a completed archive is stored with no hash, no ETag and no version, so a
 * republish is invisible to a device that already downloaded". It exists now.
 * Nothing in the app reads it yet - a staleness signal ("your map is from an
 * older release") is that issue's work, not this one's - but the fact is
 * recorded at the only moment it is knowable for free, which is the moment
 * the digest was compared.
 *
 * It describes the archive under the key and is cleared with it. An archive
 * evicted by the browser can leave this behind; callers answer "what is on
 * this phone" from the blob first, as they already must.
 */
export async function readArchiveVersion(packageKey: string): Promise<string | null> {
  return ((await get(versionKeyFor(packageKey))) as string | undefined) ?? null
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
  // The marker goes with the archive the hiker asked to remove - an absent
  // blob with a live marker would otherwise read as an eviction, and "the
  // phone removed your map" about a deletion they performed is exactly the
  // kind of false statement the marker exists to prevent.
  clearCompleted(packageKey)
  // The version record describes bytes that are now gone, so it goes with
  // them - otherwise the next unverifiable download under this key would
  // inherit a build number belonging to an archive nobody has any more.
  await del(versionKeyFor(packageKey))
  await discardPartial(packageKey)
}
