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
  artifacts?: Record<string, { sha256?: unknown } | undefined>
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
