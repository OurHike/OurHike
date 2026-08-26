// What the bucket says the bytes behind a key should hash to (#197).
//
// `pipeline/publish.py` writes `latest.json` at the bucket root on every
// publish: a version and, per flat artifact key, the SHA-256 of exactly the
// bytes it uploaded. Until now nothing on the client read it - the archive
// download checked length alone, and its own comment recorded why that check
// "can only ever catch a SHORT transfer. A spliced one always passes."
// This module is the other half of closing that: the expectation a completed
// download can be held to.
//
// Two deliberate non-behaviours:
//
// **Not cached BETWEEN attempts.** One small JSON fetch per download attempt,
// which is a rounding error beside the hundreds of megabytes that follow. A
// manifest cached across attempts would be worse than useless: an archive
// republished mid-session would leave every subsequent attempt verifying
// against a hash the bucket no longer serves, and each attempt would discard
// its own bytes and retry forever. Fetching per attempt means the expectation
// is always the one the bucket is currently publishing.
//
// That sentence described the intent and not the code, and the gap was worth
// a round trip per artifact. `publishedHash()` fetches the manifest, and it is
// called once per artifact from lib/trailData.ts's readChecked() - so the
// launch fetch of eleven artifacts pulled `latest.json` ELEVEN times, measured
// on a first run at 23512, 25343, 25670, 26071, 26375, 26576, 27524, 28302,
// 28916, 29285 and 34725 ms (#717). The bytes are trivial; the round trips sat
// on the critical path between one artifact and the next.
//
// `publishedHashes()` below is the shape the comment always described: fetch
// once, hand back a lookup, let one attempt use it for every artifact in that
// attempt. `publishedHash()` remains for callers holding a single artifact -
// lib/archiveDownload.ts, where the second read is deliberately a FRESH one
// (it is checking whether the archive was republished mid-download) and
// sharing a snapshot would defeat the check.
//
// **Never fatal.** An unreachable, malformed or older manifest - one written
// before an artifact existed, or a field-test server that has none at all -
// yields "no published hash", and the caller falls back to exactly the
// checks it ran before this existed. A download that would have succeeded
// yesterday must not start failing because a metadata file moved; the
// verification is a gate on corruption, not a second thing to be offline
// from.

import { DATA_BASE_URL, dataUrl } from './config'

/** publish.py's MANIFEST_KEY. */
export const MANIFEST_KEY = 'latest.json'

interface DataManifest {
  version?: string
  previous_version?: unknown
  artifacts?: Record<string, ArtifactEntry | undefined>
}

interface ArtifactEntry {
  sha256?: unknown
  size_bytes?: unknown
  change?: unknown
}

/**
 * How one artifact changed, as `pipeline/lib/data_change.py` graded it (#919).
 *
 * Deliberately not re-derived here: the phone holds one side of the diff and
 * would have to keep the other to work this out, which is twice the storage to
 * answer a question the publisher already had both sides of.
 */
export interface ArtifactChange {
  severity: 'routine' | 'consequential'
  added: number
  removed: number
  moved: number
  edited: number
}

/** The publisher's two grades, spelled as `data_change.py` spells them. */
export const ROUTINE = 'routine'
export const CONSEQUENTIAL = 'consequential'

/**
 * One read of `latest.json`, as everything a caller can learn from it.
 *
 * `publishedHashes` is this minus the parts only #919's refresh needs, and is
 * kept because eight callers want exactly that and nothing more.
 */
export interface PublishedSnapshot {
  /** The published version, or null where nothing could be read. */
  version: string | null
  /**
   * The version every `change` below is relative to.
   *
   * A release describes exactly one hop. A phone further back than that is
   * looking at a description of somebody else's transition, and this is what
   * lets it know rather than being told a caveat it cannot check - see
   * `dataRefresh.ts`, which refuses to describe a change when this does not
   * match what the phone stored.
   */
  previousVersion: string | null
  lookup: PublishedHashLookup
  /** Every artifact's published hash, by key. */
  hashes: Record<string, string>
  /** Every artifact's published size in bytes, where the manifest carries one.
   *  It does not for entries published before #505/#556, so a caller adding
   *  these up is adding up what it knows and must say so. */
  sizes: Record<string, number>
  /** Every artifact's change grade, where this release describes one. */
  changes: Record<string, ArtifactChange>
}

/** What a manifest snapshot answers: the published hash for a key, or null
 *  where the manifest names none and the caller should fall back to the checks
 *  it ran before #197 existed. */
export type PublishedHashLookup = (artifactKey: string) => string | null

/** Nothing is published, as far as anything can tell - the answer for a build
 *  with no bucket, and for a manifest that could not be read. */
const NOTHING_PUBLISHED: PublishedHashLookup = () => null

function lookupInto(manifest: DataManifest): PublishedHashLookup {
  return (artifactKey) => {
    if (artifactKey === '') return null
    const hash = manifest?.artifacts?.[artifactKey]?.sha256
    // Lowercased because hashlib writes lowercase hex and so does sha256.ts,
    // but a hand-edited manifest is a plausible field-test artifact and a
    // case difference is not a corrupted archive.
    return typeof hash === 'string' && hash !== '' ? hash.toLowerCase() : null
  }
}

/** Nothing readable - the snapshot equivalent of NOTHING_PUBLISHED. */
const NOTHING_READABLE: PublishedSnapshot = {
  version: null,
  previousVersion: null,
  lookup: NOTHING_PUBLISHED,
  hashes: {},
  sizes: {},
  changes: {},
}

const isCount = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0

/**
 * One artifact's `change` block, or null where the manifest has none or it is
 * not the shape `data_change.py` writes.
 *
 * Validated field by field rather than cast, for the reason `conditionsCache`
 * gives about a stored document: a published document is no more trustworthy
 * than a fetched one, and a malformed grade rendered into a prompt would be
 * this app telling a hiker something nobody computed. An unreadable block is
 * dropped, and `dataRefresh` treats a missing grade as one it cannot describe -
 * never as `routine`.
 */
function changeIn(entry: ArtifactEntry | undefined): ArtifactChange | null {
  const raw = entry?.change
  if (typeof raw !== 'object' || raw === null) return null
  const record = raw as Record<string, unknown>
  const severity = record.severity
  if (severity !== ROUTINE && severity !== CONSEQUENTIAL) return null
  const counts = (['added', 'removed', 'moved', 'edited'] as const).map(
    (field) => record[field],
  )
  if (!counts.every(isCount)) return null
  const [added, removed, moved, edited] = counts as number[]
  return { severity, added, removed, moved, edited }
}

function snapshotInto(manifest: DataManifest): PublishedSnapshot {
  const hashes: Record<string, string> = {}
  const sizes: Record<string, number> = {}
  const changes: Record<string, ArtifactChange> = {}
  const lookup = lookupInto(manifest)

  for (const [key, entry] of Object.entries(manifest?.artifacts ?? {})) {
    const hash = lookup(key)
    if (hash !== null) hashes[key] = hash
    if (isCount(entry?.size_bytes)) sizes[key] = entry.size_bytes
    const change = changeIn(entry)
    if (change !== null) changes[key] = change
  }

  const version = manifest?.version
  const previous = manifest?.previous_version
  return {
    version: typeof version === 'string' && version !== '' ? version : null,
    previousVersion: typeof previous === 'string' && previous !== '' ? previous : null,
    lookup,
    hashes,
    sizes,
    changes,
  }
}

/**
 * The whole of one `latest.json` read.
 *
 * Never fatal, on exactly the terms {@link publishedHashes} is not: anything
 * that cannot be read becomes a snapshot that knows nothing, and a caller that
 * knows nothing offers no update rather than a wrong one.
 */
export async function publishedSnapshot({
  signal,
}: { signal?: AbortSignal } = {}): Promise<PublishedSnapshot> {
  if (DATA_BASE_URL === '') return NOTHING_READABLE

  try {
    const response = await fetch(dataUrl(MANIFEST_KEY), { signal })
    if (!response.ok) return NOTHING_READABLE
    return snapshotInto((await response.json()) as DataManifest)
  } catch (error) {
    if ((error as { name?: string } | null)?.name === 'AbortError') throw error
    return NOTHING_READABLE
  }
}

/**
 * One read of the manifest, as a lookup every artifact in this attempt shares.
 *
 * Never fatal, exactly like {@link publishedHash}: an unreachable, malformed
 * or older manifest yields a lookup that answers null for everything, which is
 * the same downgrade a single unreadable fetch already produced.
 */
export async function publishedHashes({
  signal,
}: { signal?: AbortSignal } = {}): Promise<PublishedHashLookup> {
  // Nothing to fetch, and nothing that could answer: a build with no bucket
  // configured has no manifest to read.
  if (DATA_BASE_URL === '') return NOTHING_PUBLISHED

  try {
    const response = await fetch(dataUrl(MANIFEST_KEY), { signal })
    if (!response.ok) return NOTHING_PUBLISHED
    return lookupInto((await response.json()) as DataManifest)
  } catch (error) {
    // An abort is the hiker cancelling the download, not a missing manifest,
    // and swallowing it here would let the attempt continue past its own
    // cancellation. Everything else - offline, CORS, 404, malformed JSON -
    // is simply "no published hash".
    // Matched by name rather than by `instanceof DOMException`: what a fetch
    // rejects with on abort differs between browsers and test environments
    // (jsdom's DOMException does not even extend Error), and the name is the
    // part the platform actually specifies.
    if ((error as { name?: string } | null)?.name === 'AbortError') throw error
    return NOTHING_PUBLISHED
  }
}

export async function publishedHash(
  artifactKey: string,
  { signal }: { signal?: AbortSignal } = {},
): Promise<string | null> {
  if (artifactKey === '') return null
  return (await publishedHashes({ signal }))(artifactKey)
}
