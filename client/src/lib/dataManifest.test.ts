import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// The published-hash lookup (#197). Everything here turns on one distinction:
// null means "no published answer", never "verified" - so the cases that
// matter most are the ones where the manifest is missing, stale or wrong,
// and the answer still has to be an honest null rather than a hash that
// happens to be lying around.
//
// The artifact key is passed in by the caller (lib/packages.ts owns which
// artifact a package is) rather than parsed back out of a URL here - see
// DownloadOptions.artifactKey for why that stopped being this module's job.
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

describe('publishedHash', () => {
  const HASH = 'A'.repeat(64)

  it('returns the manifest entry for the artifact, lowercased', async () => {
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({
      version: 'v1',
      artifacts: { 'background.pmtiles': { sha256: HASH } },
    })

    expect(await publishedHash('background.pmtiles')).toBe(HASH.toLowerCase())
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

    await publishedHash('background.pmtiles')
    await publishedHash('background.pmtiles')
    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
  })

  it('reads a nested key exactly as given', async () => {
    // DATA_RELEASES.md's versioned layout will address
    // releases/<date>/<name>, and the manifest names artifacts the same way.
    // Nothing here splits or normalises the key: the catalog's string is the
    // manifest's string.
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({
      artifacts: { 'releases/2026-08-07/background.pmtiles': { sha256: HASH } },
    })

    expect(await publishedHash('releases/2026-08-07/background.pmtiles')).toBe(
      HASH.toLowerCase(),
    )
  })

  it('has no answer for an artifact the manifest does not list', async () => {
    // A release published before an artifact existed lists the others and
    // nothing else - which is "unverifiable", not "corrupt".
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({ artifacts: { 'trails.geojson': { sha256: HASH } } })

    expect(await publishedHash('background.pmtiles')).toBeNull()
  })

  it('has no answer when the manifest is absent, unreachable or malformed', async () => {
    const { publishedHash } = await loadWithBase(BASE)

    mockManifestResponse({}, { status: 404 })
    expect(await publishedHash('background.pmtiles')).toBeNull()

    mockManifestResponse('not json at all')
    expect(await publishedHash('background.pmtiles')).toBeNull()

    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    expect(await publishedHash('background.pmtiles')).toBeNull()

    mockManifestResponse({ artifacts: { 'background.pmtiles': { sha256: 42 } } })
    expect(await publishedHash('background.pmtiles')).toBeNull()

    mockManifestResponse({ artifacts: { 'background.pmtiles': { sha256: '' } } })
    expect(await publishedHash('background.pmtiles')).toBeNull()
  })

  it('lets a cancellation through instead of reporting no hash', async () => {
    // The hiker aborting the download has to stop the attempt, not silently
    // downgrade it to an unverified one that keeps running.
    const { publishedHash } = await loadWithBase(BASE)
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(
      new DOMException('Aborted', 'AbortError'),
    )

    await expect(publishedHash('background.pmtiles')).rejects.toThrow('Aborted')
  })

  it('passes the abort signal to the manifest fetch', async () => {
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({ artifacts: {} })
    const controller = new AbortController()

    await publishedHash('background.pmtiles', { signal: controller.signal })
    expect(globalThis.fetch).toHaveBeenCalledWith(`${BASE}/latest.json`, {
      signal: controller.signal,
    })
  })

  it('does not fetch a manifest when no bucket is configured', async () => {
    const { publishedHash } = await loadWithBase(undefined)
    const fetchSpy = mockManifestResponse({ artifacts: {} })

    expect(await publishedHash('background.pmtiles')).toBeNull()
    expect(fetchSpy).not.toHaveBeenCalled()
  })
})
