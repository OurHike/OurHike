// The other organizations' trail lines: stricter than the sketch it is
// modelled on, and since #1082 a cache of the last verified fetch.
//
// The strictness (#950): lib/trailOverview.ts draws unverifiable bytes,
// because what rides on the sketch is three seconds of a line drawn only
// below the pin seam. Nothing about that argument survives the move to these
// lines - they are drawn at every zoom, sit under the hiker's dot, and at a
// junction they are the map - so no published hash means nothing FRESH drawn.
// The tests that pin that flip are the reason this file exists rather than a
// second copy of trailOverview.test.ts.
//
// The cache (#1082): the last verified copy is kept whole in IndexedDB,
// served with or without signal, and replaced only when the manifest names a
// hash it does not carry - so the ordinary launch asks a ~KB question
// instead of re-fetching a 7.3 MB artifact. What these tests hold that
// stance to: a stored copy is one that PASSED the hash check on the day it
// was fetched, so serving it beats serving nothing, and no test here ever
// lets unverified fresh bytes into the store or onto the map.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
}))

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
}))

const { get, set } = await import('idb-keyval')
const { loadNearbyTrails, NEARBY_TRAILS_STORE_KEY } = await import('./nearbyTrailData')
const { NEARBY_TRAILS_KEY } = await import('./config')

// One OPRHP line, carrying exactly the properties
// pipeline/export_nearby_trails.py publishes.
const NETWORK = JSON.stringify({
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: {
        id: 'oprhp_trails:1',
        source: 'oprhp_trails',
        name: 'Ramapo-Dunderberg',
        blaze_color: 'Red',
        trail_status: 'open',
      },
      geometry: { type: 'LineString', coordinates: [[-74.1, 41.25]] },
    },
  ],
})

/** The sha256 of NETWORK as the manifest would publish it - computed rather
 *  than pasted, so this file cannot drift from the bytes it serves. */
async function networkHash(): Promise<string> {
  const digest = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(NETWORK) as unknown as BufferSource,
  )
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

function serve({
  network,
  manifest,
}: {
  network?: Partial<Response> | 'missing'
  manifest?: unknown
}) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (String(url).includes('latest.json')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(manifest ?? { artifacts: {} }),
        } as unknown as Response)
      }
      if (network === 'missing') {
        return Promise.resolve({ ok: false, status: 404 } as unknown as Response)
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/geo+json' }),
        arrayBuffer: () => Promise.resolve(new TextEncoder().encode(NETWORK).buffer),
        ...network,
      } as unknown as Response)
    }),
  )
}

/** What a launch that verified NETWORK on an earlier day left behind. */
async function aStoredCopy(hash?: string): Promise<void> {
  vi.mocked(get).mockResolvedValue({
    bytes: new Blob([NETWORK], { type: 'application/geo+json' }),
    hash: hash ?? (await networkHash()),
  })
}

/** Every artifact URL the module actually asked the network for. */
function fetchedUrls(): string[] {
  return vi.mocked(fetch).mock.calls.map(([url]) => String(url))
}

beforeEach(() => {
  // The module-factory mocks outlive restoreAllMocks, history included - a
  // `set` this test asserts never happened must not be one an earlier test
  // performed.
  vi.mocked(get).mockReset()
  vi.mocked(set).mockReset()
  vi.mocked(get).mockResolvedValue(undefined)
  vi.mocked(set).mockResolvedValue(undefined)
  vi.stubGlobal('URL', {
    ...URL,
    createObjectURL: vi.fn(() => 'blob:nearby'),
    revokeObjectURL: vi.fn(),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('the nearby-trail network, online with nothing stored', () => {
  it('hands back a URL for bytes that match what was published, and stores them', async () => {
    serve({
      manifest: { artifacts: { [NEARBY_TRAILS_KEY]: { sha256: await networkHash() } } },
    })

    await expect(loadNearbyTrails(true)).resolves.toEqual({
      url: 'blob:nearby',
      hash: await networkHash(),
      revalidated: true,
    })
    // The half that makes the next launch cheap and the next dead spot lit:
    // the verified bytes and the hash they matched, under the store's key.
    expect(vi.mocked(set)).toHaveBeenCalledWith(
      NEARBY_TRAILS_STORE_KEY,
      expect.objectContaining({ hash: await networkHash() }),
    )
  })

  it('draws nothing when the bytes are not what was published - and stores nothing', async () => {
    // A corrupted trail line is a trail drawn where the trail is not, and a
    // hiker at a junction cannot tell which organization drew the line they
    // are looking at. Somebody else's trail gets the same check ours does -
    // and a store holding unverified bytes would serve them for launches.
    serve({ manifest: { artifacts: { [NEARBY_TRAILS_KEY]: { sha256: 'nope' } } } })

    await expect(loadNearbyTrails(true)).resolves.toBeNull()
    expect(vi.mocked(set)).not.toHaveBeenCalled()
  })

  it('draws nothing when the manifest names no hash for it', async () => {
    // THE DEPARTURE FROM lib/trailOverview.ts, and the reason this file is
    // not a copy of its tests. There, unverifiable bytes are drawn, because
    // the sketch is worth three seconds and is never read for a position.
    // These lines are read for a position, so unverifiable means undrawn.
    serve({ manifest: { artifacts: {} } })

    await expect(loadNearbyTrails(true)).resolves.toBeNull()
  })

  it('says nothing when the bucket holds no network', async () => {
    // A 404 stays an ordinary answer: a release predating the artifact, or a
    // bucket a publish has not reached. Quiet, like the day it was the only
    // answer.
    serve({
      network: 'missing',
      manifest: { artifacts: { [NEARBY_TRAILS_KEY]: { sha256: 'ahead' } } },
    })

    await expect(loadNearbyTrails(true)).resolves.toBeNull()
  })

  it('says nothing when the fetch fails outright', async () => {
    // No signal after all, a refused origin. Nobody asked for these lines -
    // the chosen trail is drawn either way.
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )

    await expect(loadNearbyTrails(true)).resolves.toBeNull()
  })

  it('asks for the key the pipeline publishes', async () => {
    // The client end of the contract pipeline/publish.py's NEARBY_TRAILS_KEY
    // holds up. A name that drifts is a silent 404, and silent is exactly
    // what this path already is.
    serve({ manifest: { artifacts: { [NEARBY_TRAILS_KEY]: { sha256: 'anything' } } } })

    await loadNearbyTrails(true)

    expect(fetchedUrls()).toContain(`https://data.example/${NEARBY_TRAILS_KEY}`)
  })
})

describe('the nearby-trail network, from the store (#1082)', () => {
  it('serves the stored copy without signal, and says it was not revalidated', async () => {
    // The offline launch that used to draw no nearby lines at all. False on
    // `revalidated` is the caller's cue to ask again when signal arrives.
    await aStoredCopy()
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('should not be called'))),
    )

    await expect(loadNearbyTrails(false)).resolves.toEqual({
      url: 'blob:nearby',
      hash: await networkHash(),
      revalidated: false,
    })
    expect(vi.mocked(fetch)).not.toHaveBeenCalled()
  })

  it('serves nothing without signal when nothing is stored - the old offline launch', async () => {
    await expect(loadNearbyTrails(false)).resolves.toBeNull()
  })

  it('does not fetch the artifact when the manifest still names the stored hash', async () => {
    // The whole point of the store, priced: since #1019 this is the
    // difference between a ~KB manifest read and 7.3 MB gzipped on every
    // launch (pipeline/README.md's "one number wants watching").
    await aStoredCopy()
    serve({
      manifest: { artifacts: { [NEARBY_TRAILS_KEY]: { sha256: await networkHash() } } },
    })

    await expect(loadNearbyTrails(true)).resolves.toEqual({
      url: 'blob:nearby',
      hash: await networkHash(),
      revalidated: true,
    })
    expect(fetchedUrls()).not.toContain(`https://data.example/${NEARBY_TRAILS_KEY}`)
  })

  it('replaces the stored copy when the manifest names a new hash', async () => {
    // A publish landed since the last launch. The stored hash no longer
    // matches, so the artifact is fetched, verified against the NEW hash,
    // and the store rewritten - the same door every stored copy came in by.
    await aStoredCopy('an-earlier-release')
    serve({
      manifest: { artifacts: { [NEARBY_TRAILS_KEY]: { sha256: await networkHash() } } },
    })

    await expect(loadNearbyTrails(true)).resolves.toEqual({
      url: 'blob:nearby',
      hash: await networkHash(),
      revalidated: true,
    })
    expect(fetchedUrls()).toContain(`https://data.example/${NEARBY_TRAILS_KEY}`)
    expect(vi.mocked(set)).toHaveBeenCalledWith(
      NEARBY_TRAILS_STORE_KEY,
      expect.objectContaining({ hash: await networkHash() }),
    )
  })

  it('keeps the stored copy when the refresh cannot verify what it fetched - unrevalidated', async () => {
    // The manifest moved on but the bucket serves bytes that match neither
    // hash - a publish half-landed, or a tampered response. The fresh bytes
    // are not drawn and not stored (#197); the last verified copy stands,
    // exactly as it would have offline - and `revalidated: false` is what
    // lets the caller ask again on the next reconnection, because the
    // artifact carries trail_status and a stale copy can be missing a
    // closure. The fetch-only version retried on every online flip until a
    // fetch succeeded; a failure being terminal would be the regression.
    await aStoredCopy('an-earlier-release')
    serve({ manifest: { artifacts: { [NEARBY_TRAILS_KEY]: { sha256: 'newer-still' } } } })

    await expect(loadNearbyTrails(true)).resolves.toEqual({
      url: 'blob:nearby',
      hash: 'an-earlier-release',
      revalidated: false,
    })
    expect(vi.mocked(set)).not.toHaveBeenCalled()
  })

  it('keeps the stored copy when the bucket has gone quiet - unrevalidated', async () => {
    // The 404 that is ordinary for a fresh phone outlives its ordinariness
    // once a copy is held: the lines were verified on the day they were
    // fetched, and a bucket mid-publish is no reason to take them down. Not
    // revalidated: the manifest promised newer bytes the bucket did not
    // serve, so the question is still open.
    await aStoredCopy('an-earlier-release')
    serve({
      network: 'missing',
      manifest: { artifacts: { [NEARBY_TRAILS_KEY]: { sha256: 'newer' } } },
    })

    await expect(loadNearbyTrails(true)).resolves.toEqual({
      url: 'blob:nearby',
      hash: 'an-earlier-release',
      revalidated: false,
    })
  })

  it('keeps the stored copy when the manifest names no hash any more - unrevalidated', async () => {
    // The question was asked and got NO answer, which is not the same as an
    // answer: `revalidated: false`, and the loop that answering false here
    // could cause is the caller's to prevent (useTrailData asks once per
    // online spell), not this module's to paper over with a wrong claim.
    await aStoredCopy()
    serve({ manifest: { artifacts: {} } })

    await expect(loadNearbyTrails(true)).resolves.toEqual({
      url: 'blob:nearby',
      hash: await networkHash(),
      revalidated: false,
    })
  })

  it('still serves fresh verified bytes when the store refuses the write', async () => {
    // A full phone must not cost the session its lines: the bytes in hand
    // are verified whether or not they could be kept, and the next launch
    // simply fetches again - which is every launch before this cache.
    vi.mocked(set).mockRejectedValue(new Error('QuotaExceededError'))
    serve({
      manifest: { artifacts: { [NEARBY_TRAILS_KEY]: { sha256: await networkHash() } } },
    })

    await expect(loadNearbyTrails(true)).resolves.toEqual({
      url: 'blob:nearby',
      hash: await networkHash(),
      revalidated: true,
    })
  })

  it('treats an unreadable store as the no-store case', async () => {
    // A record another version wrote, or a store that throws: the fetch path
    // still answers, and the next verified fetch rewrites the record.
    vi.mocked(get).mockRejectedValue(new Error('not today'))
    serve({
      manifest: { artifacts: { [NEARBY_TRAILS_KEY]: { sha256: await networkHash() } } },
    })

    await expect(loadNearbyTrails(true)).resolves.toEqual({
      url: 'blob:nearby',
      hash: await networkHash(),
      revalidated: true,
    })
  })

  it('hands nothing back on abort, stored copy or not', async () => {
    // The abort is the caller unmounting: nothing would revoke a URL handed
    // back now.
    await aStoredCopy()
    const controller = new AbortController()
    vi.stubGlobal(
      'fetch',
      vi.fn(() => {
        controller.abort()
        const error = new Error('aborted')
        error.name = 'AbortError'
        return Promise.reject(error)
      }),
    )

    await expect(loadNearbyTrails(true, controller.signal)).resolves.toBeNull()
  })
})
