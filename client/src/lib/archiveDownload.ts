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
// BYTES REACH THE DISK AS THEY ARRIVE, IN APPEND-ONLY SEGMENTS (#553).
//
// The claim above used to be true only of a transfer that FAILED. Nothing was
// written during a healthy one - `persistPartial` was called from two error
// paths and nowhere else - so the bytes lived in the renderer's blob store
// until the last one arrived. An app the OS kills throws no error, so no error
// path runs, and on Android a backgrounded tab holding a gigabyte is a prime
// candidate for the low-memory killer. The whole transfer was lost and the next
// launch started from zero, which is the most likely way for a 1.18 GB download
// to fail and the opposite of what WIREFRAMES.md `7a` promises.
//
// So the read loop checkpoints every SEGMENT_BYTES into a numbered record
// (lib/archiveStore.ts owns that layout), each byte written exactly once, and a
// kill costs at most the last unflushed segment. Nothing is accumulated in
// memory at all any more: what used to be a growing `new Blob([previous,
// chunk])` is now a byte count and a handful of pending chunks.
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
//
// ROOM IS CHECKED BEFORE THE BODY IS READ, NOT AFTER THE LAST BYTE (#544).
//
// A phone that cannot hold the Fine tier used to accept all 1.18 GB of it and
// only then refuse to store it, because the completed bytes went in as one
// `set()` at the end and the Blob accumulated before that was not charged
// against the origin's quota. Measured in Chromium: 45 seconds of transfer,
// then a QuotaExceededError with an empty message, nothing kept and nothing
// resumable. `shortfall()` asks the browser the same question for the price of
// one set of response headers. See it for why this refuses where Downloads.tsx's
// identical warning does not.
//
// Segmented storage does not retire that check, it sharpens it: the bytes are
// charged against the quota as they arrive now, so a phone with room for 800 MB
// of a 1.18 GB archive fails at 800 MB instead of at the end. Refusing up front
// is still the only answer that costs nobody their data allowance. What it does
// retire is the DOUBLE requirement a resume used to carry - see `shortfall`.

import { get, set, del } from 'idb-keyval'
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'
import { clearCompleted, estimateAvailableBytes, recordCompleted } from './storageHealth'
import { publishedHash } from './dataManifest'
import { formatBytes } from './formatBytes'
import { Sha256, type Sha256State } from './sha256'
import {
  deleteArchiveRecords,
  deleteGeneration,
  markComplete,
  readComplete,
  readSegmentRun,
  writeSegment,
  type ArchiveComplete,
} from './archiveStore'

/**
 * How much arrives before it is written down.
 *
 * The trade is bytes-at-risk against writes: a kill costs whatever has not
 * reached a segment yet, and every checkpoint is a record. 32 MiB is the step
 * #553 measured append-only storage at - 400 MB in 32 MB segments wrote 692 ms
 * against 3,287 ms for the rewrite-the-whole-blob approach, with `usage` landing
 * at 1x - and it puts a 1.18 GB Fine-tier archive in 36 records while risking
 * about eight seconds of a slow connection.
 */
const SEGMENT_BYTES = 32 * 1024 * 1024

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
  /**
   * Which generation (archiveStore.ts) these bytes are accumulating in.
   *
   * A resume has to write into the run its own bytes are already in, so this is
   * read back rather than recomputed: recomputing picks the generation the
   * COMPLETED archive is not in, which is the right answer when a transfer
   * starts and the wrong one once it is under way and something else has
   * completed since.
   */
  generation?: number
  /**
   * How many segment records the partial had been written as.
   *
   * Read back only by the delete path, and only as a floor: segments are probed
   * contiguously, which stops at the first gap, and a gap is reachable because a
   * segment write can fail on quota while earlier ones stand. Someone deleting a
   * map to free room must get every byte back, so the count that was claimed is
   * deleted through whatever answers (#554).
   */
  segments?: number
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
  /**
   * How much arrives before it is checkpointed to disk. Defaults to
   * SEGMENT_BYTES, which is what the app uses.
   *
   * It is here so that checkpointing can be EXERCISED rather than asserted
   * about: at 32 MiB, any test small enough to run in milliseconds flushes once
   * at the end and would pass whether the segment loop worked or not. The
   * storage probe wants the same knob for the opposite reason - to measure the
   * write pattern at sizes it can drive in a browser.
   *
   * Not a tuning dial for callers in the app. `SEGMENT_BYTES` is the measured
   * value and the reason it is that number is written there.
   */
  segmentBytes?: number
}

export class ArchiveSizeMismatchError extends Error {
  /** The raw counts, for a log or a field report - the sentence a hiker reads
   *  carries them through formatBytes, because "297483822 bytes" in an alert
   *  is a stack trace wearing a shirt. */
  readonly expectedBytes: number
  readonly actualBytes: number

  constructor(expected: number, actual: number) {
    super(
      `The download ended early — ${formatBytes(actual)} of the ` +
        `${formatBytes(expected)} map arrived. What arrived is kept, so picking it ` +
        `up again carries on from there.`,
    )
    this.name = 'ArchiveSizeMismatchError'
    this.expectedBytes = expected
    this.actualBytes = actual
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

/**
 * The phone has no room for this archive, said before a byte is spent finding
 * out (#544).
 *
 * The failure this replaces was the worst one in this module. The finished
 * bytes used to be stored in a single `set()` at the very END of the transfer,
 * and everything before that lived in the renderer's blob store, which is not
 * charged against the origin's quota - measured in Chromium: usage did not move
 * while a 1.18 GB Blob was being accumulated, and moved by the whole archive at
 * the moment it was stored. So a phone that cannot hold the Fine tier accepted
 * all 1.18 GB of it over the network, spent the hiker's entire allowance, and
 * then rejected the store with a `QuotaExceededError` whose `message` is the
 * empty string. Nothing was kept, nothing was resumable, the next attempt did
 * exactly the same thing, and the card had nothing to show but an empty alert.
 *
 * Segmented storage (#553) changes where that lands rather than removing the
 * need for the check: bytes are charged as they arrive now, so an unchecked
 * transfer would fail partway instead of at the end. Still 800 MB of somebody's
 * data to learn something one set of response headers answers for free.
 *
 * `navigator.storage.estimate()` answers this in a millisecond, and the app
 * already reads it - Downloads.tsx warns with it before the tap. This is the
 * same question asked at the one moment it can still save the data, against
 * the size the SERVER declares rather than the figure kept by hand in
 * downloadDetail.ts.
 *
 * Both counts ride along, because "not enough room" is only actionable next to
 * the two numbers it is a comparison of.
 */
export class ArchiveTooLargeError extends Error {
  readonly requiredBytes: number
  readonly availableBytes: number

  constructor(requiredBytes: number, availableBytes: number, heldBytes: number) {
    // Two sentences and a way out. The resumed case needs its own, because the
    // number is otherwise inexplicable: what it asks for is the room the REST of
    // the map needs, and someone refused over 200 MB on a map they can see is
    // half downloaded is owed a statement of which figure is which.
    super(
      (heldBytes > 0
        ? `There is not enough room on this phone to finish this map. The rest of it ` +
          `needs about ${formatBytes(requiredBytes)} free — the ` +
          `${formatBytes(heldBytes)} already downloaded is kept and counts toward the ` +
          `finished map — and about ${formatBytes(availableBytes)} is free for the app.`
        : `There is not enough room on this phone for this map. It needs about ` +
          `${formatBytes(requiredBytes)} and about ${formatBytes(availableBytes)} is ` +
          `free for the app.`) +
        ` Nothing was downloaded, so none of your data was spent. Freeing up space, ` +
        `or choosing a lighter detail level, makes room for it.`,
    )
    this.name = 'ArchiveTooLargeError'
    this.requiredBytes = requiredBytes
    this.availableBytes = availableBytes
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

/**
 * Whether a storage write failed because the browser has no room.
 *
 * Matched by name rather than by `instanceof DOMException`, for the reason
 * dataManifest.ts matches AbortError the same way: the name is the part the
 * platform specifies, and what a rejected IndexedDB request carries differs
 * between engines and test environments. The legacy numeric code is accepted
 * too - older WebKit throws a DOMException with code 22 and a name that is not
 * always spelled the same way.
 */
function isQuotaError(error: unknown): boolean {
  const { name, code } = (error ?? {}) as { name?: unknown; code?: unknown }
  return name === 'QuotaExceededError' || code === 22
}

/** The object's total length out of a `Content-Range`, or null where the header
 *  is absent or does not state one (`bytes 0-1/*`). */
function totalFromContentRange(header: string | null): number | null {
  const match = /\/\s*(\d+)\s*$/.exec(header ?? '')
  return match === null ? null : Number(match[1])
}

/**
 * The room this attempt still needs before it can succeed, against the room the
 * browser says it has - null where either is unanswerable.
 *
 * WHAT IS ASKED FOR IS THE REMAINDER, NOT THE ARCHIVE (#553).
 *
 * The held bytes used to be counted ON TOP of the archive, because the finished
 * bytes were stored under the package key before the partial was discarded, so
 * both existed at once and finishing a resume genuinely needed room for two
 * copies of what it was finishing. Segments retire that: the bytes already on
 * disk ARE part of the finished archive, completion is a marker rather than a
 * copy, and nothing is ever stored twice.
 *
 * So the requirement is what is not yet here. The held bytes are already inside
 * the browser's `usage` - and therefore already excluded from `available` - so
 * they are neither added nor subtracted; they simply are not asked for again.
 *
 * This is a real widening, not bookkeeping. A phone with 300 MB free and 980 MB
 * of a 1.18 GB archive already downloaded used to be refused a resume it could
 * comfortably finish, and told the reason was a second copy nothing would have
 * made.
 */
async function shortfall(
  remainingBytes: number,
): Promise<{ required: number; available: number } | null> {
  if (remainingBytes <= 0) return null
  const available = await estimateAvailableBytes()
  if (available === null) return null
  return remainingBytes > available ? { required: remainingBytes, available } : null
}

/**
 * The last act of a successful attempt: hold the bytes to the published hash,
 * store them, and record what they are.
 *
 * Shared by the ordinary path and by the one where the server reports that the
 * partial already covers the whole object (the 416 below), so that the rule
 * about what may be stored has exactly one home.
 */
async function finish(
  packageKey: string,
  artifactKey: string,
  stored: ArchiveComplete,
  expected: string | null,
  hash: Sha256 | null,
  signal?: AbortSignal,
): Promise<void> {
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
        // Nothing is kept: these bytes are the right length and the wrong file,
        // so a resume onto them would only rebuild the same wrong archive. What
        // is discarded is an unusable download, never a map anyone is
        // navigating by - the completed archive lives in the OTHER generation
        // (archiveStore.ts) and is left exactly where it was, so a hiker with a
        // working map who tried to update it still has it.
        await discardPartial(packageKey, stored.generation, stored.segments)
        throw new ArchiveHashMismatchError(expected, actual)
      }
    }
  }

  try {
    // The bytes are already on disk - this swings the marker onto them and
    // frees whatever they replace. No archive-sized write happens here, which
    // is the point: the old single `set()` needed room for a second copy of
    // the whole archive at the worst possible moment (#553).
    await markComplete(packageKey, stored)
  } catch (error) {
    // The quota answer, arriving at the only moment this module could not
    // avoid asking: the room check before the transfer is an ESTIMATE, and a
    // browser that rounds it generously, or another tab that filled the origin
    // meanwhile, lands here. Translated rather than rethrown, because what a
    // browser throws here carries no message at all - Chromium's
    // QuotaExceededError has an empty one, which the Downloads card rendered
    // as an empty alert (#544).
    //
    // Reachable but no longer expensive, and no longer a size problem worth
    // quoting figures at: what failed is a marker of a few bytes, and the
    // archive it names is intact underneath. `ArchiveTooLargeError` would have
    // to name a requirement, and every number available here is a lie - the
    // bytes are already stored, so "it needs 1.18 GB" is false and "it needs
    // 0 MB" is nonsense. What is true is that nothing was lost.
    if (isQuotaError(error)) {
      throw new Error(
        `The map finished downloading, but this phone would not record it as ` +
          `complete — it is out of room for even a small write. Nothing was lost: ` +
          `freeing up a little space and tapping again finishes from what is ` +
          `already here, with nothing left to download.`,
      )
    }
    throw error
  }

  // Which build is on this phone. Written after the marker, never before: a
  // version record for an archive that is not yet finished would be a claim
  // about bytes nobody can read. Cleared rather than left standing when the
  // archive could not be verified, because a stale hash beside unverified bytes
  // says something false with more confidence than saying nothing.
  if (verified !== null) await set(versionKeyFor(packageKey), verified)
  else await del(versionKeyFor(packageKey))
  // After the archive is really readable, and in a different storage mechanism
  // on purpose: this is what later distinguishes "the archive was evicted" from
  // "no archive was ever downloaded" (storageHealth.ts, #190).
  recordCompleted(packageKey)
  // The transfer's bookkeeping, not its bytes. The segments stay exactly where
  // they are - they ARE the archive now - so only the records describing an
  // in-flight download are cleared.
  await clearTransferRecords(packageKey)
}

export async function downloadArchive(
  packageKey: string,
  url: string,
  { artifactKey, onProgress, onChecking, signal, segmentBytes }: DownloadOptions,
): Promise<void> {
  const storedSource = (await get(sourceKeyFor(packageKey))) as PartialSource | undefined
  const completed = await readComplete(packageKey)

  // Which generation this attempt writes into (archiveStore.ts): the one the
  // finished archive is not in, so a re-download cannot damage the map the
  // hiker is navigating by. A resume stays in the generation its own bytes are
  // already in, whatever has completed since.
  const generation =
    storedSource?.generation ?? (completed === null ? 0 : 1 - completed.generation)

  const held = await readSegmentRun(packageKey, generation)
  const storedBlob = held.blob

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
  if (storedBlob !== undefined && !usable)
    await discardPartial(packageKey, generation, storedSource?.segments)

  // A partial written by a build before segments existed cannot be resumed onto:
  // its bytes are one record with no generation and no segment index, and the
  // ways to adopt them are all worse than restarting. Copying it into segment 0
  // needs room for a second copy of a partial that can be most of a gigabyte -
  // the exact failure #544 is about - and keeping it as a permanent base part
  // would mean a finished archive whose contents include a record named
  // ':partial' forever, to serve a case that exists only during this upgrade.
  //
  // So it is reclaimed rather than read. The cost is one interrupted transfer,
  // once, for a tester who was mid-download when the app updated. What #553 and
  // lib/packages.ts require to survive is a COMPLETED archive, and that does -
  // archiveStore.ts serves the legacy whole-archive record untouched.
  await del(partialKeyFor(packageKey))

  const heldBlob = usable ? storedBlob : undefined
  const heldBytes = heldBlob?.size ?? 0
  // Where the next segment goes. Segments are contiguous from 0, so the count
  // of held ones is the next index.
  let nextSegment = usable ? held.count : 0

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

  // 416 means the range asked for is not inside the object, and for a resume
  // there is exactly one innocent reading of that: the partial already holds
  // every byte there is, so `bytes=<size>-` starts one past the end.
  //
  // This was a permanent dead end (#544). A transfer that drops after the last
  // byte but before the stream closes - or that is aborted at the tail, or
  // whose body ran longer than the declared length - leaves a partial holding
  // the whole file. Every resume from then on asked for a range past the end,
  // got 416, fell into the generic failure below, and left the card offering
  // "Resume" over bytes that could never complete. On the Fine tier that is
  // 1.18 GB of correct map, on the phone, unreachable, with delete as the only
  // way forward.
  //
  // So the held bytes are finished from here rather than thrown away: the
  // server has just stated the object's length, and where that equals what is
  // held, the hash check below is what decides whether they are the right
  // bytes. Nothing is trusted that a completed transfer would not have been.
  if (response.status === 416 && heldBlob !== undefined) {
    const objectBytes = totalFromContentRange(response.headers.get('content-range'))
    if (objectBytes === heldBytes) {
      const expected = publishedSha256 ?? storedSource?.sha256 ?? null
      const hash =
        expected === null
          ? null
          : await resumeHash(heldBlob, storedSource?.hash, onChecking)
      onProgress?.({ receivedBytes: heldBytes, totalBytes: heldBytes })
      await finish(
        packageKey,
        artifactKey,
        { generation, segments: nextSegment, totalBytes: heldBytes },
        expected,
        hash,
        signal,
      )
      return
    }

    // The other readings are all "these bytes cannot be finished": the object
    // is shorter than the partial, or its length is unstated. Discarded, so the
    // next attempt starts clean instead of asking the same impossible question
    // forever - and said plainly, because a hiker who taps Resume is owed the
    // reason the button changed.
    await discardPartial(packageKey, generation, nextSegment)
    throw new Error(
      `The part of the map already on this phone no longer matches what the server ` +
        `has, so it was cleared. Anything already downloaded is untouched, and the ` +
        `next attempt starts a fresh copy.`,
    )
  }

  if (!response.ok) {
    // The message is what the download card shows, so it is written for the
    // hiker holding the phone, not the developer reading a log. The status
    // code rides along in parentheses because it is the one detail a field
    // report can carry that actually helps - but it does not lead.
    throw new Error(
      `The server could not send the map (it answered ${response.status}). ` +
        `Anything already on this phone is untouched, and trying again later is safe.`,
    )
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

  // Held segments this attempt is not resuming onto are in the way rather than
  // useful: the transfer restarts at index 0, and segments left past its end
  // would be read back as part of the archive and corrupt it. Reclaimed before
  // the first write, not after, since the write is what would overlap them.
  if (!resumed && held.count > 0) {
    await discardPartial(packageKey, generation, held.count)
    nextSegment = 0
  }

  const declared = Number(response.headers.get('content-length') ?? 0)
  const totalBytes = resumed ? heldBytes + declared : declared

  // ASKED HERE BECAUSE HERE IS WHERE IT IS STILL FREE (#544).
  //
  // The server has just declared how big this archive is, and no part of the
  // body has been read yet, so a phone that cannot hold it can be told so for
  // the price of one set of response headers instead of 1.18 GB of somebody's
  // data allowance. Measured in Chromium: a Fine-tier download on an origin
  // whose quota could not take it transferred all 1,184,700,000 bytes over 45
  // seconds and then failed the store, keeping nothing.
  //
  // Against the DECLARED length, which is the one that matters - the figure in
  // downloadDetail.ts is kept by hand and has drifted from the bucket before
  // (#505), and this comparison is exactly where being 15 MB optimistic strands
  // somebody who freed up just enough space.
  //
  // Downloads.tsx warns on this same estimate and deliberately does not refuse:
  // "a hiker at a trailhead deciding to try anyway is making an informed call."
  // That reasoning holds where it is - a warning costs nothing to ignore
  // because nothing has been spent yet. It stops holding once the transfer is
  // the thing being decided about, and the browser's own answer is the only one
  // available: no amount of trying makes a store succeed that the quota
  // forbids, so the choice on offer would be between an honest sentence and the
  // same sentence after a gigabyte. Refusing keeps the remedy in the message
  // rather than in a log.
  //
  // A browser with no estimate to give (`null`) refuses nothing, which is the
  // same posture every other best-effort answer in storageHealth.ts takes.
  //
  // What is asked for is the DECLARED remainder rather than the whole archive,
  // because that is what is not yet on disk: a resume's held segments are part
  // of the finished archive now, and `available` already excludes them. `declared`
  // says the same thing as `totalBytes - heldBytes` on a resume and is the honest
  // spelling of it - it is the number of bytes about to be written.
  const tooLarge = await shortfall(resumed ? declared : totalBytes)
  if (tooLarge !== null) {
    // Closed rather than left to garbage collection: the body is already on its
    // way, and an unread response holds the connection open and keeps the bytes
    // coming - which is the cost this whole check exists to avoid.
    void response.body?.cancel()
    throw new ArchiveTooLargeError(
      tooLarge.required,
      tooLarge.available,
      resumed ? heldBytes : 0,
    )
  }

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
    generation,
    segments: nextSegment,
  })

  // Bytes that have arrived but are not yet in a segment record. This is the
  // only thing held in memory now, and SEGMENT_BYTES bounds it - what used to
  // be a Blob growing to the size of the whole archive.
  let pending: BlobPart[] = []
  let pendingBytes = 0
  // On disk, in segments. What a resume would find, and therefore what the
  // progress record must say - not `receivedBytes`, which counts bytes the
  // renderer is still holding and an OS kill would take with it.
  let flushedBytes = resumed ? heldBytes : 0
  let receivedBytes = flushedBytes
  onProgress?.({ receivedBytes, totalBytes })

  /**
   * Writes the pending bytes as the next segment, and records the transfer's
   * position.
   *
   * The order is the same invariant `persistPartial` has always kept, for the
   * same reason: identity first, so the dangerous combination (bytes on disk,
   * nothing saying what they are) is never reachable. Here it also carries the
   * hash state, which at this instant covers exactly the bytes about to be
   * written - every arrived chunk has been folded in, and pending is all of
   * them since the last flush. A segment write that fails after it leaves a
   * source claiming more bytes than are held, which `resumeHash` already treats
   * as "hash the held bytes again".
   */
  const flush = async (): Promise<void> => {
    if (pendingBytes === 0) return
    const segment = new Blob(pending)
    // Cleared before the awaits, so a failure cannot write the same bytes twice
    // if the caller flushes again on its way out.
    pending = []
    pendingBytes = 0

    try {
      await set(sourceKeyFor(packageKey), sourceRecord())
      await writeSegment(packageKey, generation, nextSegment, segment)
    } catch (error) {
      // The quota answer, now arriving mid-transfer rather than after the last
      // byte. Translated for the same reason it always was - what a browser
      // throws here carries no message at all (#544) - and with the numbers the
      // sentence needs: what is left to write, and what is already safe.
      if (isQuotaError(error)) {
        throw new ArchiveTooLargeError(
          Math.max(totalBytes - flushedBytes, segment.size),
          (await estimateAvailableBytes()) ?? 0,
          flushedBytes,
        )
      }
      throw error
    }
    nextSegment += 1
    flushedBytes += segment.size
    await set(progressKeyFor(packageKey), { receivedBytes: flushedBytes, totalBytes })
  }

  /** Everything on disk and labelled, pending bytes included. */
  const persist = async (): Promise<void> => {
    await flush()
    // Written even with nothing pending: the next attempt reads these to decide
    // whether the held segments are usable at all, and a transfer that failed
    // before its first checkpoint has none of them yet.
    await set(sourceKeyFor(packageKey), sourceRecord())
    await set(progressKeyFor(packageKey), { receivedBytes: flushedBytes, totalBytes })
  }

  const reader = response.body?.getReader()
  if (reader === undefined)
    throw new Error(
      'The connection opened but no map data arrived. Trying again is safe — ' +
        'anything already on this phone is untouched.',
    )

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break

      // Taken in BEFORE the abort is acted on. These bytes really arrived, and
      // an abort that lands while they are in hand is no reason to make the next
      // attempt fetch them again - the catch below writes them down. Checking
      // first dropped the chunk that had just been read, which is what made
      // "keeps what arrived when interrupted" hold for an EMPTY partial.
      pending.push(value)
      pendingBytes += value.byteLength
      hash?.update(value)
      receivedBytes += value.byteLength
      onProgress?.({ receivedBytes, totalBytes })

      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')

      // The checkpoint. Everything before it is durable, so a kill here costs
      // this segment rather than the transfer.
      if (pendingBytes >= (segmentBytes ?? SEGMENT_BYTES)) await flush()
    }
    await flush()
  } catch (error) {
    // Everything received so far is kept, including the bytes that had not
    // reached a segment yet - this is a live failure with a live renderer, so
    // there is still a chance to write them.
    await keepQuietly(persist)
    throw error
  }

  if (totalBytes > 0 && receivedBytes !== totalBytes) {
    // Truncation: a short PMTiles archive opens fine and then returns nothing
    // for tiles past the cut, which looks like missing map rather than a
    // failed download. The bytes are already kept, so a resume finishes the job.
    await keepQuietly(persist)
    throw new ArchiveSizeMismatchError(totalBytes, receivedBytes)
  }

  await finish(
    packageKey,
    artifactKey,
    { generation, segments: nextSegment, totalBytes: receivedBytes },
    expected,
    hash,
    signal,
  )
}

/**
 * Persistence for the two callers that are already carrying a failure.
 *
 * Keeping the bytes is a best effort by nature - the failure being reported is
 * often quota, and quota is exactly what stops a partial being written. What
 * must not happen is the write's own error replacing the one being reported: a
 * dropped connection surfaced as an empty-message QuotaExceededError tells the
 * hiker nothing about either problem, and the news here is the transfer.
 */
async function keepQuietly(persist: () => Promise<void>): Promise<void> {
  try {
    await persist()
  } catch {
    // Nothing to add - see the docstring. The next attempt discards a partial
    // it cannot identify, so a half-written one costs the resume, never
    // correctness.
  }
}

/**
 * Clears the records that describe an in-flight transfer, leaving any bytes
 * alone.
 *
 * What `finish` uses, because the segments are the finished archive by then and
 * deleting them would delete the download. Every caller that means "throw the
 * bytes away too" says so through `discardPartial`.
 */
async function clearTransferRecords(packageKey: string): Promise<void> {
  await del(progressKeyFor(packageKey))
  await del(sourceKeyFor(packageKey))
}

/**
 * Throws away an unfinished transfer: its segments and its bookkeeping.
 *
 * `segments` is the count the source record claimed, passed through to
 * archiveStore.ts so a gap left by a failed write cannot strand later segments
 * on the phone (#554). The completed archive in the other generation is never
 * touched - that is what generations are for.
 */
async function discardPartial(
  packageKey: string,
  generation: number,
  segments = 0,
): Promise<void> {
  await deleteGeneration(packageKey, generation, segments)
  // The pre-segment record. Nothing writes it any more; a build that did may
  // have left one behind.
  await del(partialKeyFor(packageKey))
  await clearTransferRecords(packageKey)
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
  // Every generation's segments, the completion marker, and any legacy
  // whole-archive record. The source record's segment count is passed in as a
  // floor so a gap left by a failed write cannot strand later segments on a
  // phone whose owner is deleting a map precisely to free the space (#554).
  const source = (await get(sourceKeyFor(packageKey))) as PartialSource | undefined
  await deleteArchiveRecords(packageKey, source?.segments ?? 0)
  // The marker goes with the archive the hiker asked to remove - an absent
  // blob with a live marker would otherwise read as an eviction, and "the
  // phone removed your map" about a deletion they performed is exactly the
  // kind of false statement the marker exists to prevent.
  clearCompleted(packageKey)
  // The version record describes bytes that are now gone, so it goes with
  // them - otherwise the next unverifiable download under this key would
  // inherit a build number belonging to an archive nobody has any more.
  await del(versionKeyFor(packageKey))
  // The bookkeeping. `deleteArchiveRecords` above already took every byte in
  // both generations, so this is the pre-segment record and the progress/source
  // pair rather than anything the hiker was storing.
  await del(partialKeyFor(packageKey))
  await clearTransferRecords(packageKey)
}
