// The other organizations' trail lines: stricter than the sketch it is
// modelled on, and since #1082 a cache of the last verified fetch.
//
// SINCE #1257 THE MECHANISM CARRIES THE NETWORK'S CORRIDOR-VIEW SKETCH AND
// NOTHING ELSE. The whole-file network artifact these tests were written
// around was promoted at 228,820,578 bytes on 2026-09-07 and crashed every
// phone that fetched it (#1254); its lines are vector tiles now
// (map/networkTiles.ts) and never pass through here. Every test below that
// used to load the network loads the sketch instead - same store shape, same
// manifest question, same strictness, because the sketch is drawn under the
// hiker's dot at the opening zooms exactly as the lines are above the seam.
// What this module still does for the old copy is delete it, tested at the
// end.
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
import { RELEASE_MANIFEST_PATH, releasePath } from './dataRelease'

vi.mock('./config', async (importOriginal) => {
  // The release layout is the real one, not a flattened stand-in: a mock
  // that put artifacts at the root while the module under test read the
  // manifest from releases/<pin>/ would agree with neither the bucket nor
  // itself. Only the base is substituted.
  const { releasePath, RELEASE_MANIFEST_PATH } = await import('./dataRelease')
  return {
    ...(await importOriginal<typeof import('./config')>()),
    DATA_BASE_URL: 'https://data.example',
    DATA_CONFIGURED: true,
    dataUrl: (key: string) => `https://data.example/${releasePath(key)}`,
    releaseManifestUrl: () => `https://data.example/${RELEASE_MANIFEST_PATH}`,
  }
})

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
}))

const { del, get, set } = await import('idb-keyval')
const {
  forgetNearbyTrails,
  loadNetworkOverview,
  NEARBY_TRAILS_STORE_KEY,
  NETWORK_OVERVIEW_STORE_KEY,
} = await import('./nearbyTrailData')
const { NETWORK_OVERVIEW_KEY } = await import('./config')
const { LAUNCH_ARTIFACT_BUDGET_BYTES } = await import('./artifactBudget')

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
      if (String(url).includes(RELEASE_MANIFEST_PATH)) {
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
  vi.mocked(del).mockReset()
  vi.mocked(get).mockResolvedValue(undefined)
  vi.mocked(set).mockResolvedValue(undefined)
  vi.mocked(del).mockResolvedValue(undefined)
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

describe('the network sketch, online with nothing stored', () => {
  it('hands back a URL for bytes that match what was published, and stores them', async () => {
    serve({
      manifest: {
        artifacts: { [NETWORK_OVERVIEW_KEY]: { sha256: await networkHash() } },
      },
    })

    await expect(loadNetworkOverview(true)).resolves.toEqual({
      url: 'blob:nearby',
      hash: await networkHash(),
      revalidated: true,
    })
    // The half that makes the next launch cheap and the next dead spot lit:
    // the verified bytes and the hash they matched, under the store's key.
    expect(vi.mocked(set)).toHaveBeenCalledWith(
      NETWORK_OVERVIEW_STORE_KEY,
      expect.objectContaining({ hash: await networkHash() }),
    )
  })

  it('draws nothing when the bytes are not what was published - and stores nothing', async () => {
    // A corrupted trail line is a trail drawn where the trail is not, and a
    // hiker at a junction cannot tell which organization drew the line they
    // are looking at. Somebody else's trail gets the same check ours does -
    // and a store holding unverified bytes would serve them for launches.
    serve({ manifest: { artifacts: { [NETWORK_OVERVIEW_KEY]: { sha256: 'nope' } } } })

    await expect(loadNetworkOverview(true)).resolves.toBeNull()
    expect(vi.mocked(set)).not.toHaveBeenCalled()
  })

  it('draws nothing when the manifest names no hash for it', async () => {
    // THE DEPARTURE FROM lib/trailOverview.ts, and the reason this file is
    // not a copy of its tests. There, unverifiable bytes are drawn, because
    // the sketch is worth three seconds and is never read for a position.
    // These lines are read for a position, so unverifiable means undrawn.
    serve({ manifest: { artifacts: {} } })

    await expect(loadNetworkOverview(true)).resolves.toBeNull()
  })

  it('says nothing when the bucket holds no network', async () => {
    // A 404 stays an ordinary answer: a release predating the artifact, or a
    // bucket a publish has not reached. Quiet, like the day it was the only
    // answer.
    serve({
      network: 'missing',
      manifest: { artifacts: { [NETWORK_OVERVIEW_KEY]: { sha256: 'ahead' } } },
    })

    await expect(loadNetworkOverview(true)).resolves.toBeNull()
  })

  it('says nothing when the fetch fails outright', async () => {
    // No signal after all, a refused origin. Nobody asked for these lines -
    // the chosen trail is drawn either way.
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )

    await expect(loadNetworkOverview(true)).resolves.toBeNull()
  })

  it('asks for the key the pipeline publishes', async () => {
    // The client end of the contract pipeline/publish.py's NETWORK_OVERVIEW_KEY
    // holds up. A name that drifts is a silent 404, and silent is exactly
    // what this path already is.
    serve({ manifest: { artifacts: { [NETWORK_OVERVIEW_KEY]: { sha256: 'anything' } } } })

    await loadNetworkOverview(true)

    expect(fetchedUrls()).toContain(
      `https://data.example/${releasePath(NETWORK_OVERVIEW_KEY)}`,
    )
  })
})

describe('the network sketch, from the store (#1082)', () => {
  it('serves the stored copy without signal, and says it was not revalidated', async () => {
    // The offline launch that used to draw no nearby lines at all. False on
    // `revalidated` is the caller's cue to ask again when signal arrives.
    await aStoredCopy()
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('should not be called'))),
    )

    await expect(loadNetworkOverview(false)).resolves.toEqual({
      url: 'blob:nearby',
      hash: await networkHash(),
      revalidated: false,
    })
    expect(vi.mocked(fetch)).not.toHaveBeenCalled()
  })

  it('serves nothing without signal when nothing is stored - the old offline launch', async () => {
    await expect(loadNetworkOverview(false)).resolves.toBeNull()
  })

  it('does not fetch the artifact when the manifest still names the stored hash', async () => {
    // The whole point of the store, priced: since #1019 this is the
    // difference between a ~KB manifest read and 7.3 MB gzipped on every
    // launch (pipeline/README.md's "one number wants watching").
    await aStoredCopy()
    serve({
      manifest: {
        artifacts: { [NETWORK_OVERVIEW_KEY]: { sha256: await networkHash() } },
      },
    })

    await expect(loadNetworkOverview(true)).resolves.toEqual({
      url: 'blob:nearby',
      hash: await networkHash(),
      revalidated: true,
    })
    expect(fetchedUrls()).not.toContain(`https://data.example/${NETWORK_OVERVIEW_KEY}`)
  })

  it('replaces the stored copy when the manifest names a new hash', async () => {
    // A publish landed since the last launch. The stored hash no longer
    // matches, so the artifact is fetched, verified against the NEW hash,
    // and the store rewritten - the same door every stored copy came in by.
    await aStoredCopy('an-earlier-release')
    serve({
      manifest: {
        artifacts: { [NETWORK_OVERVIEW_KEY]: { sha256: await networkHash() } },
      },
    })

    await expect(loadNetworkOverview(true)).resolves.toEqual({
      url: 'blob:nearby',
      hash: await networkHash(),
      revalidated: true,
    })
    expect(fetchedUrls()).toContain(
      `https://data.example/${releasePath(NETWORK_OVERVIEW_KEY)}`,
    )
    expect(vi.mocked(set)).toHaveBeenCalledWith(
      NETWORK_OVERVIEW_STORE_KEY,
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
    serve({
      manifest: { artifacts: { [NETWORK_OVERVIEW_KEY]: { sha256: 'newer-still' } } },
    })

    await expect(loadNetworkOverview(true)).resolves.toEqual({
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
      manifest: { artifacts: { [NETWORK_OVERVIEW_KEY]: { sha256: 'newer' } } },
    })

    await expect(loadNetworkOverview(true)).resolves.toEqual({
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

    await expect(loadNetworkOverview(true)).resolves.toEqual({
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
      manifest: {
        artifacts: { [NETWORK_OVERVIEW_KEY]: { sha256: await networkHash() } },
      },
    })

    await expect(loadNetworkOverview(true)).resolves.toEqual({
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
      manifest: {
        artifacts: { [NETWORK_OVERVIEW_KEY]: { sha256: await networkHash() } },
      },
    })

    await expect(loadNetworkOverview(true)).resolves.toEqual({
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

    await expect(loadNetworkOverview(true, controller.signal)).resolves.toBeNull()
  })
})

describe('what is left of the whole-file network copy (#1257)', () => {
  it('deletes the copy an earlier release stored, and touches nothing else', async () => {
    // Up to 228.8 MB under this one key on a phone that fetched 2026-09-07's
    // artifact before #1254's budget existed. Nothing draws from it now.
    await forgetNearbyTrails()

    expect(del).toHaveBeenCalledTimes(1)
    expect(del).toHaveBeenCalledWith(NEARBY_TRAILS_STORE_KEY)
    expect(set).not.toHaveBeenCalled()
  })

  it('treats a store that refuses the delete as one with nothing to forget', async () => {
    vi.mocked(del).mockRejectedValue(new Error('no IndexedDB here'))

    await expect(forgetNearbyTrails()).resolves.toBeUndefined()
  })

  it('keeps the sketch under its own record, so the delete cannot take it', () => {
    // The sketch is the OPENING view's lines. The two artifacts never shared a
    // record, and the key spelling is the other half of the contract
    // pipeline/tests/test_published_key_contract.py checks from its side.
    expect(NETWORK_OVERVIEW_STORE_KEY).not.toBe(NEARBY_TRAILS_STORE_KEY)
  })
})

describe('an artifact the phone cannot hold (#1254)', () => {
  // 2026-09-07: nearby_trails.geojson published at 228,820,578 bytes decoded,
  // and every phone that fetched it crashed its map. The manifest carried
  // that size the whole time; nothing read it before fetching. That file is
  // tiles now (#1257) and never comes through here; the door stays, because
  // the sketch is on the same road - 10,804,839 bytes decoded on 2026-09-04,
  // 80.6% of it one nationwide USFS feature (lib/config.ts's
  // NETWORK_OVERVIEW_KEY), which is a third of the way to the budget.
  const TOO_BIG = LAUNCH_ARTIFACT_BUDGET_BYTES + 1

  function quietWarnings() {
    return vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  }

  it('does not fetch what the manifest says is over the budget, and says so once', async () => {
    const warn = quietWarnings()
    serve({
      manifest: {
        artifacts: {
          [NETWORK_OVERVIEW_KEY]: { sha256: await networkHash(), size_bytes: TOO_BIG },
        },
      },
    })

    await expect(loadNetworkOverview(true)).resolves.toBeNull()

    expect(fetchedUrls()).toEqual([`https://data.example/${RELEASE_MANIFEST_PATH}`])
    expect(set).not.toHaveBeenCalled()
    expect(warn).toHaveBeenCalledTimes(1)
    expect(String(warn.mock.calls[0][0])).toContain(NETWORK_OVERVIEW_KEY)
  })

  it('keeps serving the last copy that fit, unrevalidated, so the asking resumes when a smaller one is published', async () => {
    quietWarnings()
    await aStoredCopy('the-hash-of-a-copy-that-fit')
    serve({
      manifest: {
        artifacts: {
          [NETWORK_OVERVIEW_KEY]: { sha256: await networkHash(), size_bytes: TOO_BIG },
        },
      },
    })

    await expect(loadNetworkOverview(true)).resolves.toEqual({
      url: 'blob:nearby',
      hash: 'the-hash-of-a-copy-that-fit',
      revalidated: false,
    })
    expect(fetchedUrls()).toEqual([`https://data.example/${RELEASE_MANIFEST_PATH}`])
  })

  it('weighs the bytes themselves where the manifest named no size', async () => {
    // A manifest from before size_bytes existed, or one that is wrong about
    // it. The body is the backstop: not hashed, not stored, not drawn.
    const warn = quietWarnings()
    serve({
      network: { arrayBuffer: () => Promise.resolve(new ArrayBuffer(TOO_BIG)) },
      manifest: {
        artifacts: { [NETWORK_OVERVIEW_KEY]: { sha256: await networkHash() } },
      },
    })

    await expect(loadNetworkOverview(true)).resolves.toBeNull()

    expect(set).not.toHaveBeenCalled()
    expect(String(warn.mock.calls[0][0])).toContain('response')
  })

  it('forgets a stored copy it cannot hold rather than serving it, signal or no signal', async () => {
    // Written by a launch before the budget existed: verified, stored, and a
    // crash waiting for the next launch to hand it to the map.
    const warn = quietWarnings()
    vi.mocked(get).mockResolvedValue({
      bytes: new Blob([new ArrayBuffer(TOO_BIG)]),
      hash: 'stored-before-the-budget',
    })

    await expect(loadNetworkOverview(false)).resolves.toBeNull()

    expect(del).toHaveBeenCalledWith(NETWORK_OVERVIEW_STORE_KEY)
    expect(String(warn.mock.calls[0][0])).toContain('store')
  })
})
