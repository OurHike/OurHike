import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// The published closures baseline (#435). Everything here turns on the same
// distinction lib/dataManifest.test.ts records: `null` means "no usable
// baseline", never "no closures" - the two are opposite answers and the whole
// point of this path is that a hiker can tell them apart.
//
// config.ts reads VITE_DATA_BASE_URL once at module load and it is unset under
// test, so each case imports the module fresh against a stubbed env - which is
// also the only way to cover "no bucket configured at all".

const BASE = 'https://cdn.example.org'

async function loadWithBase(base: string | undefined) {
  vi.resetModules()
  vi.stubEnv('VITE_DATA_BASE_URL', base ?? '')
  return await import('./publishedConditions')
}

function mockResponse(body: unknown, { status = 200 } = {}) {
  return vi
    .spyOn(globalThis, 'fetch')
    .mockImplementation(
      async () =>
        new Response(typeof body === 'string' ? body : JSON.stringify(body), { status }),
    )
}

const A_DOCUMENT = {
  generated_at: '2026-08-08T06:00:00Z',
  closures: [{ id: 'c1', start_mile_marker: 10, end_mile_marker: 11 }],
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

describe('fetchPublishedClosures', () => {
  it('reads the artifact from the configured bucket', async () => {
    const fetchSpy = mockResponse(A_DOCUMENT)
    const { fetchPublishedClosures, PUBLISHED_CLOSURES_KEY } = await loadWithBase(BASE)

    const published = await fetchPublishedClosures()

    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/${PUBLISHED_CLOSURES_KEY}`,
      expect.anything(),
    )
    expect(published?.closures).toHaveLength(1)
    expect(published?.generatedAt.toISOString()).toBe('2026-08-08T06:00:00.000Z')
  })

  it('asks for nothing when no bucket was configured at build time', async () => {
    const fetchSpy = mockResponse(A_DOCUMENT)
    const { fetchPublishedClosures } = await loadWithBase(undefined)

    expect(await fetchPublishedClosures()).toBeNull()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('returns null rather than throwing when the bucket is unreachable', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('offline'))
    const { fetchPublishedClosures } = await loadWithBase(BASE)

    await expect(fetchPublishedClosures()).resolves.toBeNull()
  })

  it('returns null on a 404, which is what a release built before this artifact looks like', async () => {
    mockResponse('', { status: 404 })
    const { fetchPublishedClosures } = await loadWithBase(BASE)

    expect(await fetchPublishedClosures()).toBeNull()
  })

  it('returns null on a document that is not JSON', async () => {
    mockResponse('<!doctype html>')
    const { fetchPublishedClosures } = await loadWithBase(BASE)

    expect(await fetchPublishedClosures()).toBeNull()
  })

  it('refuses a document with no generated_at, rather than defaulting one', async () => {
    // The strict case, and the only one. That timestamp is what becomes
    // "as of <date>" - without it the app would show day-old closures with no
    // sign of their age, which is the failure this path exists to remove.
    mockResponse({ closures: [] })
    const { fetchPublishedClosures } = await loadWithBase(BASE)

    expect(await fetchPublishedClosures()).toBeNull()
  })

  it('refuses a document whose generated_at is not a date', async () => {
    mockResponse({ generated_at: 'whenever', closures: [] })
    const { fetchPublishedClosures } = await loadWithBase(BASE)

    expect(await fetchPublishedClosures()).toBeNull()
  })

  it('refuses a document whose closures are not a list', async () => {
    mockResponse({ generated_at: '2026-08-08T06:00:00Z', closures: 'none' })
    const { fetchPublishedClosures } = await loadWithBase(BASE)

    expect(await fetchPublishedClosures()).toBeNull()
  })

  it('accepts an empty list, which is a real answer and not a failure', async () => {
    // The state of the bucket the day this shipped: the bake ran, read zero
    // verified closures, and published exactly that. Treating it as a failure
    // would fall back to "unavailable" and tell a hiker we could not ask,
    // when in fact we asked and the trail is open.
    mockResponse({ generated_at: '2026-08-08T06:00:00Z', closures: [] })
    const { fetchPublishedClosures } = await loadWithBase(BASE)

    const published = await fetchPublishedClosures()

    expect(published).not.toBeNull()
    expect(published?.closures).toEqual([])
  })
})
