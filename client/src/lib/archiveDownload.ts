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
//
// A RESUME DOES NOT TRUST THE 206 IT IS GIVEN (#506).
//
// `If-Range` exists so the SERVER refuses a stale resume, and this sends it.
// The r2.dev endpoint ignores it - measured against the live bucket, a stale
// validator is answered 206 with the range served - so the 206 is no evidence
// that the object is still the one the held bytes came from. The ETag on that
// response is, and it is compared against the one those bytes were recorded
// under before any of the body is read.
//
// That comparison is deliberately not the same defence as the published hash,
// and covers what the hash cannot: the hash moves only when `publish.py`
// rewrites `latest.json`, so an object overwritten before that write, or any
// resume where the manifest is unreachable, leaves it nothing to compare.
//
// ROOM IS CHECKED BEFORE THE BODY IS READ, NOT AFTER THE LAST BYTE (#544).
//
// The completed bytes are stored in ONE `set()` at the end, and the Blob being
// accumulated before that is not charged against the origin's quota - so
// without a check, a phone that cannot hold the Fine tier accepts all 1.18 GB
// of it and only then refuses to store it. Measured in Chromium: 45 seconds of
// transfer, then a QuotaExceededError with an empty message, nothing kept and
// nothing resumable. `shortfall()` asks the browser the same question for the
// price of one set of response headers. See it for why this refuses where
// Downloads.tsx's identical warning does not.

import { get, set, del } from 'idb-keyval'
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'
import { clearCompleted, estimateAvailableBytes, recordCompleted } from './storageHealth'
import { publishedHash } from './dataManifest'
import { formatBytes } from './formatBytes'
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
  /**
   * The strong validator these bytes were served under.
   *
   * Read back on every resume and compared against the ETag the `206` states,
   * because the bucket will not make that comparison itself (#506). Absent
   * where the bucket exposes no ETag, or states only a weak one; the url check
   * and the published hash still apply.
   */
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
 * bytes are stored in a single `set()` at the very END of the transfer, and
 * everything before that lives in the renderer's blob store, which is not
 * charged against the origin's quota - measured in Chromium: usage does not
 * move while a 1.18 GB Blob is being accumulated, and moves by the whole
 * archive at the moment it is stored. So a phone that cannot hold the Fine
 * tier accepts all 1.18 GB of it over the network, spends the hiker's entire
 * allowance, and then rejects the store with a `QuotaExceededError` whose
 * `message` is the empty string. Nothing is kept, nothing is resumable, the
 * next attempt does exactly the same thing, and the card had nothing to show
 * but an empty alert.
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
    // number is otherwise inexplicable: finishing a resume needs room for the
    // whole archive WHILE the partial is still held, since the partial is only
    // released once the finished bytes are safely stored.
    super(
      (heldBytes > 0
        ? `There is not enough room on this phone to finish this map. It needs about ` +
          `${formatBytes(requiredBytes)} free — the finished map plus the ` +
          `${formatBytes(heldBytes)} already here, which is only released once the ` +
          `finished copy is stored — and about ${formatBytes(availableBytes)} is free ` +
          `for the app.`
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

/**
 * The held bytes cannot be finished, and have been discarded.
 *
 * Two different discoveries end here: the server reporting an object shorter
 * than the partial (the 416 below), and the server serving a range of an
 * object that is no longer the one those bytes came from (the ETag check
 * below). They are one event to the hiker — what was held is gone, the map
 * they already have is not, and tapping again starts a fresh copy — so they
 * get one sentence rather than two that can drift apart.
 */
function stalePartialError(): Error {
  return new Error(
    `The part of the map already on this phone no longer matches what the server ` +
      `has, so it was cleared. Anything already downloaded is untouched, and the ` +
      `next attempt starts a fresh copy.`,
  )
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
 * The room this attempt needs before it can succeed, against the room the
 * browser says it has - null where either is unanswerable.
 *
 * `held` is counted ON TOP of the archive, and that is not defensive
 * arithmetic: the finished bytes are stored under the package key BEFORE the
 * partial is discarded, so both records exist at once, and a resume of a large
 * archive genuinely needs room for two copies of what it is finishing. The
 * held bytes are already inside the browser's `usage`, so they have to be added
 * to the requirement rather than subtracted from it.
 */
async function shortfall(
  archiveBytes: number,
  heldBytes: number,
): Promise<{ required: number; available: number } | null> {
  if (archiveBytes <= 0) return null
  const available = await estimateAvailableBytes()
  if (available === null) return null
  const required = archiveBytes + heldBytes
  return required > available ? { required, available } : null
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
  archive: Blob,
  expected: string | null,
  hash: Sha256 | null,
  heldBytes: number,
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

  try {
    await set(packageKey, archive)
  } catch (error) {
    // The quota answer, arriving at the only moment this module could not
    // avoid asking: the room check before the transfer is an ESTIMATE, and a
    // browser that rounds it generously, or another tab that filled the origin
    // meanwhile, lands here. Translated rather than rethrown, because what a
    // browser throws here carries no message at all - Chromium's
    // QuotaExceededError has an empty one, which the Downloads card rendered
    // as an empty alert (#544).
    if (isQuotaError(error)) {
      throw new ArchiveTooLargeError(
        archive.size + heldBytes,
        (await estimateAvailableBytes()) ?? 0,
        heldBytes,
      )
    }
    throw error
  }

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
    // If-Range asks the server itself to arbitrate: the range is honoured only
    // while the object still matches, and a republished archive comes back 200
    // with the whole body instead. The 206 check below already treats that as
    // "start clean", so the correct behaviour is code that already exists.
    //
    // Still sent although the current bucket ignores it (#506), for two
    // reasons: it costs one header, and it is the BETTER mechanism where it
    // works - the server refuses the splice before spending a byte on it, and
    // a move to a custom domain may well restore that. Where it is ignored,
    // the ETag comparison below catches the same case from the response.
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
      await finish(packageKey, artifactKey, heldBlob, expected, hash, heldBytes, signal)
      return
    }

    // The other readings are all "these bytes cannot be finished": the object
    // is shorter than the partial, or its length is unstated. Discarded, so the
    // next attempt starts clean instead of asking the same impossible question
    // forever - and said plainly, because a hiker who taps Resume is owed the
    // reason the button changed.
    await discardPartial(packageKey)
    throw stalePartialError()
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

  // What the server says this object is NOW. A weak ETag is dropped, for the
  // reason RFC 9110 §13.1.5 will not let one validate a range either: it
  // promises semantic equivalence, not the byte-for-byte identity an append
  // depends on.
  const responseEtag = response.headers.get('etag') ?? undefined
  const strongEtag =
    responseEtag !== undefined && !responseEtag.startsWith('W/')
      ? responseEtag
      : undefined

  // THE ARBITRATION THE BUCKET DECLINES TO MAKE (#506).
  //
  // The `If-Range` sent above asks the SERVER to refuse a stale resume, and a
  // conforming one answers 200 with the whole body - which the 206 test above
  // already treats as "start clean". The r2.dev endpoint does not: measured
  // 2026-08-12, a stale ETag, a wrong-but-valid-shaped one and a long-past
  // HTTP-date are all answered 206 with the range served, on a 70-byte JSON
  // object and on the 532 MB archive alike. So a 206 is NOT evidence that the
  // object is still the one these bytes came from, and every line below here
  // used to assume it was.
  //
  // The ETag still is that evidence. R2 states the object's current one on the
  // 206 - the same value its HEAD gives, multipart archives included - and
  // `.github/expected-origins.yml` requires `etag` to stay readable by a
  // browser, which `check_deployment.py` re-asserts daily against every origin.
  // So the comparison is made here instead, before a byte of the body is read.
  //
  // This is the second defence #506 asks for, and it is the one the published
  // hash structurally cannot be. That hash moves only when `publish.py`
  // rewrites `latest.json`, so an object overwritten before that write - or any
  // resume where the manifest is unreachable, which is every field-test server
  // and every older release - leaves the hash check with nothing to compare
  // against. The ETag moves with the OBJECT, so it is right in precisely the
  // window the manifest is wrong.
  //
  // Nothing here is salvageable, unlike the 200 case: what is on the wire is a
  // range of a DIFFERENT object, so there is no prefix worth keeping and no
  // whole file to fall back to. The partial goes and the next attempt starts
  // clean - the same disposal, and deliberately the same sentence, as the 416.
  if (
    resumed &&
    storedSource?.etag !== undefined &&
    strongEtag !== undefined &&
    strongEtag !== storedSource.etag
  ) {
    // Closed rather than left to garbage collection, for the reason the quota
    // check below closes it: an unread response keeps the bytes coming, and
    // these are bytes that can only ever be thrown away.
    void response.body?.cancel()
    await discardPartial(packageKey)
    throw stalePartialError()
  }

  let accumulated: Blob = resumed ? heldBlob : new Blob([])

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
  // `heldBytes`, not `resumed ? heldBytes : 0`: what occupies the quota is the
  // partial RECORD, which is on disk whenever those bytes were usable - whether
  // or not this attempt resumed onto them. A server that ignored the range is
  // rebuilding the archive from zero with the old partial still sitting there.
  const tooLarge = await shortfall(totalBytes, heldBytes)
  if (tooLarge !== null) {
    // Closed rather than left to garbage collection: the body is already on its
    // way, and an unread response holds the connection open and keeps the bytes
    // coming - which is the cost this whole check exists to avoid.
    void response.body?.cancel()
    throw new ArchiveTooLargeError(tooLarge.required, tooLarge.available, heldBytes)
  }

  // Taken from the response actually being read, so a partial is always
  // labelled with the version it came from. Where the response states no strong
  // ETag, a resume keeps the one already recorded - those bytes are unchanged,
  // and the check above has just established that nothing contradicts it.
  const etag = strongEtag ?? (resumed ? storedSource?.etag : undefined)

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
  if (reader === undefined)
    throw new Error(
      'The connection opened but no map data arrived. Trying again is safe — ' +
        'anything already on this phone is untouched.',
    )

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
    await keepPartial(packageKey, accumulated, totalBytes, sourceRecord())
    throw error
  }

  if (totalBytes > 0 && accumulated.size !== totalBytes) {
    // Truncation: a short PMTiles archive opens fine and then returns nothing
    // for tiles past the cut, which looks like missing map rather than a
    // failed download. Keep the bytes so a resume can finish the job.
    await keepPartial(packageKey, accumulated, totalBytes, sourceRecord())
    throw new ArchiveSizeMismatchError(totalBytes, accumulated.size)
  }

  await finish(packageKey, artifactKey, accumulated, expected, hash, heldBytes, signal)
}

/**
 * `persistPartial`, for the two callers that are already carrying a failure.
 *
 * Keeping the bytes is a best effort by nature - the failure being reported is
 * often quota, and quota is exactly what stops a partial being written. What
 * must not happen is the write's own error replacing the one being reported: a
 * dropped connection surfaced as an empty-message QuotaExceededError tells the
 * hiker nothing about either problem, and the news here is the transfer.
 */
async function keepPartial(
  packageKey: string,
  blob: Blob,
  totalBytes: number,
  source: PartialSource,
): Promise<void> {
  try {
    await persistPartial(packageKey, blob, totalBytes, source)
  } catch {
    // Nothing to add - see the docstring. The next attempt discards a partial
    // it cannot identify, so a half-written one costs the resume, never
    // correctness.
  }
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
