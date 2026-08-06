import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// The published-hash lookup (#197). Everything here turns on one distinction:
// null means "no published answer", never "verified" - so the cases that
// matter most are the ones where the manifest is missing, stale or wrong,
// and the answer still has to be an honest null rather than a hash that
// happens to be lying around.
//
// config.ts reads VITE_DATA_BASE_URL once at module load and it is unset
// under test, so each case stubs the env and imports the module fresh -
// which is also the only way to cover "no bucket configured at all".

const BASE = 'https://cdn.example.org'

async function loadWithBase(base: string | undefined) {
  vi.resetModules()
  if (base === undefined) vi.stubEnv('VITE_DATA_BASE_URL', '')
  else vi.stubEnv('VITE_DATA_BASE_URL', base)
  return await import('./dataManifest')
}

function mockManifestResponse(body: unknown, { status = 200 } = {}) {
  return vi
    .spyOn(globalThis, 'fetch')
    .mockImplementation(
      async () =>
        new Response(typeof body === 'string' ? body : JSON.stringify(body), { status }),
    )
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

describe('artifactKeyFor', () => {
  it('reads the flat bucket key out of a download URL', async () => {
    const { artifactKeyFor } = await loadWithBase(BASE)
    expect(artifactKeyFor(`${BASE}/background.pmtiles`)).toBe('background.pmtiles')
  })

  it('keeps a nested key whole', async () => {
    // DATA_RELEASES.md's versioned layout addresses releases/<date>/<name>,
    // and the manifest names artifacts the same way. Taking only the last
    // segment would look up the wrong entry there.
    const { artifactKeyFor } = await loadWithBase(BASE)
    expect(artifactKeyFor(`${BASE}/releases/2026-08-07/background.pmtiles`)).toBe(
      'releases/2026-08-07/background.pmtiles',
    )
  })

  it('drops a query string', async () => {
    const { artifactKeyFor } = await loadWithBase(BASE)
    expect(artifactKeyFor(`${BASE}/background.pmtiles?v=2`)).toBe('background.pmtiles')
  })

  it('refuses a URL from outside the configured bucket', async () => {
    // A same-named file on another host is not this bucket's artifact, and
    // checking it against this bucket's hash would fail an honest download.
    const { artifactKeyFor } = await loadWithBase(BASE)
    expect(artifactKeyFor('https://elsewhere.example/background.pmtiles')).toBeNull()
    expect(artifactKeyFor(`${BASE}`)).toBeNull()
    expect(artifactKeyFor(`${BASE}/`)).toBeNull()
  })

  it('has no answer when no bucket is configured', async () => {
    const { artifactKeyFor } = await loadWithBase(undefined)
    expect(artifactKeyFor('https://cdn.example.org/background.pmtiles')).toBeNull()
  })
})

describe('publishedHash', () => {
  const HASH = 'A'.repeat(64)

  it('returns the manifest entry for the artifact, lowercased', async () => {
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({
      version: 'v1',
      artifacts: { 'background.pmtiles': { sha256: HASH } },
    })

    expect(await publishedHash(`${BASE}/background.pmtiles`)).toBe(HASH.toLowerCase())
    expect(globalThis.fetch).toHaveBeenCalledWith(`${BASE}/latest.json`, {
      signal: undefined,
    })
  })

  it('fetches the manifest again for every call', async () => {
    // Not cached on purpose: a republished archive must not leave the app
    // verifying against a hash the bucket has stopped serving, which would
    // make every retry discard its own bytes until the app restarted.
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({ artifacts: { 'background.pmtiles': { sha256: HASH } } })

    await publishedHash(`${BASE}/background.pmtiles`)
    await publishedHash(`${BASE}/background.pmtiles`)
    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
  })

  it('has no answer for an artifact the manifest does not list', async () => {
    // A release published before an artifact existed lists the others and
    // nothing else - which is "unverifiable", not "corrupt".
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({ artifacts: { 'trails.geojson': { sha256: HASH } } })

    expect(await publishedHash(`${BASE}/background.pmtiles`)).toBeNull()
  })

  it('has no answer when the manifest is absent, unreachable or malformed', async () => {
    const { publishedHash } = await loadWithBase(BASE)

    mockManifestResponse({}, { status: 404 })
    expect(await publishedHash(`${BASE}/background.pmtiles`)).toBeNull()

    mockManifestResponse('not json at all')
    expect(await publishedHash(`${BASE}/background.pmtiles`)).toBeNull()

    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    expect(await publishedHash(`${BASE}/background.pmtiles`)).toBeNull()

    mockManifestResponse({ artifacts: { 'background.pmtiles': { sha256: 42 } } })
    expect(await publishedHash(`${BASE}/background.pmtiles`)).toBeNull()

    mockManifestResponse({ artifacts: { 'background.pmtiles': { sha256: '' } } })
    expect(await publishedHash(`${BASE}/background.pmtiles`)).toBeNull()
  })

  it('lets a cancellation through instead of reporting no hash', async () => {
    // The hiker aborting the download has to stop the attempt, not silently
    // downgrade it to an unverified one that keeps running.
    const { publishedHash } = await loadWithBase(BASE)
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(
      new DOMException('Aborted', 'AbortError'),
    )

    await expect(publishedHash(`${BASE}/background.pmtiles`)).rejects.toThrow('Aborted')
  })

  it('passes the abort signal to the manifest fetch', async () => {
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({ artifacts: {} })
    const controller = new AbortController()

    await publishedHash(`${BASE}/background.pmtiles`, { signal: controller.signal })
    expect(globalThis.fetch).toHaveBeenCalledWith(`${BASE}/latest.json`, {
      signal: controller.signal,
    })
  })

  it('does not fetch a manifest when no bucket is configured', async () => {
    const { publishedHash } = await loadWithBase(undefined)
    const fetchSpy = mockManifestResponse({ artifacts: {} })

    expect(await publishedHash('https://cdn.example.org/background.pmtiles')).toBeNull()
    expect(fetchSpy).not.toHaveBeenCalled()
  })
})
