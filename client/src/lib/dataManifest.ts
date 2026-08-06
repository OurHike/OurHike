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
// **Not cached.** One small JSON fetch per download attempt, which is a
// rounding error beside the hundreds of megabytes that follow. A cached
// manifest would be worse than useless: an archive republished mid-session
// would leave every subsequent attempt verifying against a hash the bucket
// no longer serves, and each attempt would discard its own bytes and retry
// forever. Fetching per attempt means the expectation is always the one the
// bucket is currently publishing.
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

/**
 * The artifact key `url` addresses, or null when it addresses something
 * outside the published bucket.
 *
 * Keys are flat at the bucket root (config.ts, DATA_RELEASES.md §Migration),
 * so the key is the last path segment - but only for URLs actually under the
 * configured base. A viewer pointed at a one-off file, or a build with no
 * bucket configured at all, has no manifest entry to look up, and guessing
 * from the filename alone would invite a same-named file elsewhere to be
 * checked against this bucket's hash.
 */
export function artifactKeyFor(url: string): string | null {
  if (DATA_BASE_URL === '') return null
  const prefix = `${DATA_BASE_URL}/`
  if (!url.startsWith(prefix)) return null
  const key = url.slice(prefix.length)
  // A nested key is still one key - `releases/2026-08-07/background.pmtiles`
  // is what DATA_RELEASES.md's versioned layout will address - so the whole
  // remainder is the name, not just its last segment. A query string is not
  // part of it.
  return key === '' ? null : key.split(/[?#]/)[0]
}

/**
 * The published SHA-256 for `url`, or null when there is no published answer:
 * no bucket configured, no manifest, no entry for this artifact, or a
 * manifest that could not be fetched or parsed.
 *
 * Null means "unverifiable", never "verified". Callers must treat it as the
 * absence of a check rather than as a passing one.
 */
export async function publishedHash(
  url: string,
  { signal }: { signal?: AbortSignal } = {},
): Promise<string | null> {
  const key = artifactKeyFor(url)
  if (key === null) return null

  let manifest: DataManifest
  try {
    const response = await fetch(dataUrl(MANIFEST_KEY), { signal })
    if (!response.ok) return null
    manifest = (await response.json()) as DataManifest
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
    return null
  }

  const entry = manifest?.artifacts?.[key]
  const hash = entry?.sha256
  // Lowercased because hashlib writes lowercase hex and so does sha256.ts,
  // but a hand-edited manifest is a plausible field-test artifact and a
  // case difference is not a corrupted archive.
  return typeof hash === 'string' && hash !== '' ? hash.toLowerCase() : null
}
