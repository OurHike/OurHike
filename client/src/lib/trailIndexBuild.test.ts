// The off-thread build (#1192), driven where a worker cannot run: the whole
// build, the sliced fallback, the cache in front of both, and the worker's
// handler through a fake channel - lib/sha256Rpc.test.ts's arrangement.

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { get, set } from 'idb-keyval'
import {
  AXIS_DRIFT_SAMPLE,
  axisDrift,
  buildTrailIndexInSlices,
  buildTrailIndexNow,
  createTrailIndexRequestHandler,
  loadTrailIndex,
  packPois,
  resolveTrailIndex,
  TRAIL_INDEX_CACHE_KEY,
  type TrailIndexRequest,
} from './trailIndexBuild'
import {
  buildTrailIndex,
  deserializeTrailIndex,
  mileOnTrail,
  serializeTrailIndex,
} from './trailPosition'

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn() }))

const MILE_LAT = 1 / 69.05
const HASH = 'c'.repeat(64)

/** A ten-mile due-north centerline with a vertex per mile, and a spur. */
function trailsText(): string {
  return JSON.stringify({
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { source: 'centerline', id: 'centerline:chain:0' },
        geometry: {
          type: 'LineString',
          coordinates: Array.from({ length: 11 }, (_, i) => [-77, 39 + i * MILE_LAT]),
        },
      },
      {
        type: 'Feature',
        properties: { source: 'side_trails', id: 'side:1' },
        geometry: {
          type: 'LineString',
          coordinates: [
            [-77.001, 39.001],
            [-77.002, 39.002],
          ],
        },
      },
    ],
  })
}

/** The pipeline's miles for that line: a hundred miles in, to be unmistakable. */
function milesText(): string {
  return JSON.stringify({
    format: 1,
    trails_sha256: HASH,
    miles: { 'centerline:chain:0': Array.from({ length: 11 }, (_, i) => 100 + i) },
  })
}

const POIS = [
  // On the line at mile 3, carrying the pipeline's own answer.
  { lon: -77, lat: 39 + 3 * MILE_LAT, mile: 103 },
  // On the line at mile 5, no published mile.
  { lon: -77, lat: 39 + 5 * MILE_LAT },
  // Nowhere near the line.
  { lon: -70, lat: 30, mile: undefined },
]

function request(overrides: Partial<TrailIndexRequest> = {}): TrailIndexRequest {
  return {
    trails: new Blob([trailsText()]),
    trailMiles: null,
    pois: packPois(POIS),
    trailsHash: HASH,
    ...overrides,
  }
}

/** The fixture's line on the pipeline axis, built synchronously. */
function serializeTrailIndexFor() {
  const miles = new Map([
    ['centerline:chain:0', Array.from({ length: 11 }, (_, i) => 100 + i)],
  ])
  return serializeTrailIndex(buildTrailIndex(JSON.parse(trailsText()), miles))
}

const store = new Map<string, unknown>()

beforeEach(() => {
  store.clear()
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
  vi.mocked(get).mockClear()
  vi.mocked(set).mockClear()
})

describe.each([
  ['whole', buildTrailIndexNow],
  ['in slices', buildTrailIndexInSlices],
])('the build, %s', (_, build) => {
  it('indexes the line and places every waypoint by search on the phone axis', async () => {
    const built = await build(request())
    const index = deserializeTrailIndex(built.index)

    expect(index.onPipelineAxis).toBe(false)
    expect(index.lons.length).toBe(11)
    expect(index.tread.lons.length).toBe(13)
    expect(index.totalMiles).toBeCloseTo(10, 1)
    expect(built.poiMiles.length).toBe(3)
    // Placed by search, not read off the record: a published mile means
    // nothing on an axis the phone measured itself.
    expect(built.poiMiles[0]).toBeCloseTo(3, 1)
    expect(built.poiMiles[1]).toBeCloseTo(5, 1)
    expect(built.poiMiles[2]).toBeNaN()
  })

  it('reads the pipeline miles and hands each waypoint its published mile', async () => {
    const built = await build(request({ trailMiles: new Blob([milesText()]) }))
    const index = deserializeTrailIndex(built.index)

    expect(index.onPipelineAxis).toBe(true)
    expect(mileOnTrail(index, { lon: -77, lat: 39 + 4 * MILE_LAT })).toBe(104)
    expect(built.poiMiles[0]).toBe(103)
    // No published mile is no mile, even for a waypoint standing on the line:
    // on this axis the pipeline's silence is the answer.
    expect(built.poiMiles[1]).toBeNaN()
    expect(built.poiMiles[2]).toBeNaN()
  })

  it('rejects rather than answering from half a file', async () => {
    await expect(
      build(request({ trails: new Blob(['{"type":"Feat']) })),
    ).rejects.toThrow()
  })
})

describe('the cache', () => {
  it('builds once per release and answers from the store after that', async () => {
    const build = vi.fn(buildTrailIndexNow)

    const first = await loadTrailIndex(request(), build)
    const second = await loadTrailIndex(request(), build)

    expect(build).toHaveBeenCalledTimes(1)
    expect(second.poiMiles).toEqual(first.poiMiles)
    expect(store.has(TRAIL_INDEX_CACHE_KEY)).toBe(true)
  })

  it('rebuilds for another release of the lines', async () => {
    const build = vi.fn(buildTrailIndexNow)
    await loadTrailIndex(request(), build)

    await loadTrailIndex(request({ trailsHash: 'd'.repeat(64) }), build)

    expect(build).toHaveBeenCalledTimes(2)
  })

  it('rebuilds when the waypoints or the miles sidecar changed under the same lines', async () => {
    const build = vi.fn(buildTrailIndexNow)
    await loadTrailIndex(request(), build)

    await loadTrailIndex(request({ pois: packPois(POIS.slice(0, 2)) }), build)
    await loadTrailIndex(request({ trailMiles: new Blob([milesText()]) }), build)

    expect(build).toHaveBeenCalledTimes(3)
  })

  it("rebuilds when a waypoint's own coordinates or published mile changed, same count", async () => {
    const build = vi.fn(buildTrailIndexNow)
    await loadTrailIndex(request(), build)

    // Same count, same lines - only a waypoint's own coordinates or published
    // mile changed, the shape a pipeline correction takes (trailsHash never
    // covers the POI files - useTrailData.ts's `readTheRest`).
    const corrected = [POIS[0], { ...POIS[1], mile: 5.5 }, POIS[2]]
    await loadTrailIndex(request({ pois: packPois(corrected) }), build)

    expect(build).toHaveBeenCalledTimes(2)
  })

  it('neither reads nor writes a cache for a store with no release record', async () => {
    const build = vi.fn(buildTrailIndexNow)

    await loadTrailIndex(request({ trailsHash: null }), build)
    await loadTrailIndex(request({ trailsHash: null }), build)

    expect(build).toHaveBeenCalledTimes(2)
    expect(store.has(TRAIL_INDEX_CACHE_KEY)).toBe(false)
  })

  it('ignores an entry another build wrote', async () => {
    store.set(TRAIL_INDEX_CACHE_KEY, {
      trailsHash: HASH,
      poiCount: 3,
      index: 'old shape',
    })
    const build = vi.fn(buildTrailIndexNow)

    await loadTrailIndex(request(), build)

    expect(build).toHaveBeenCalledTimes(1)
  })

  it('still answers when the store cannot be read or written', async () => {
    vi.mocked(get).mockRejectedValue(new Error('quota'))
    vi.mocked(set).mockRejectedValue(new Error('quota'))

    const built = await loadTrailIndex(request())

    expect(built.poiMiles[0]).toBeCloseTo(3, 1)
  })
})

describe('the worker handler', () => {
  it('posts the built index with its buffers listed for transfer', async () => {
    const post = vi.fn()
    const handle = createTrailIndexRequestHandler(post)

    await handle({ kind: 'build', request: request() })

    const [message, transfer] = post.mock.calls[0]
    expect(message.kind).toBe('built')
    expect(transfer).toContain(message.built.index.lons.buffer)
    expect(transfer).toContain(message.built.poiMiles.buffer)
  })

  it('posts a failure rather than dying silently', async () => {
    const post = vi.fn()
    const handle = createTrailIndexRequestHandler(post)

    await handle({ kind: 'build', request: request({ trails: new Blob(['nope']) }) })

    expect(post.mock.calls[0][0].kind).toBe('failed')
  })
})

describe('resolveTrailIndex', () => {
  it('answers a live index through the sliced build where there is no Worker', async () => {
    expect(typeof Worker).toBe('undefined')

    const { index, poiMiles } = await resolveTrailIndex(request())

    expect(index.lons.length).toBe(11)
    expect(poiMiles[0]).toBeCloseTo(3, 1)
  })

  it('falls back to the sliced build when the worker cannot be constructed', async () => {
    vi.stubGlobal(
      'Worker',
      class {
        constructor() {
          throw new Error('refused by policy')
        }
      },
    )
    try {
      const { index } = await resolveTrailIndex(request())
      expect(index.lons.length).toBe(11)
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('falls back to the sliced build when the worker reports a failure', async () => {
    vi.stubGlobal(
      'Worker',
      class {
        onmessage: ((event: { data: unknown }) => void) | null = null
        onerror: ((event: { message: string }) => void) | null = null
        postMessage() {
          queueMicrotask(() => this.onerror?.({ message: 'script failed to load' }))
        }
        terminate() {}
      },
    )
    try {
      const { index } = await resolveTrailIndex(request())
      expect(index.lons.length).toBe(11)
    } finally {
      vi.unstubAllGlobals()
    }
  })
})

describe('the axis drift check', () => {
  it('is null off the pipeline axis, where the search is the only answer', async () => {
    expect((await buildTrailIndexNow(request())).axisDrift).toBeNull()
  })

  it('reports how far published miles sit from placed ones on the pipeline axis', async () => {
    // The one waypoint with a published mile stands on vertex 3, which the
    // sidecar puts at 103: no drift. Then a sidecar that shifts the whole
    // line by a mile, which is the file/line mismatch the check exists to see.
    const agreeing = await buildTrailIndexNow(
      request({ trailMiles: new Blob([milesText()]) }),
    )
    expect(agreeing.axisDrift).toEqual({ sampled: 1, maxMiles: 0 })

    const shifted = JSON.stringify({
      format: 1,
      trails_sha256: HASH,
      miles: { 'centerline:chain:0': Array.from({ length: 11 }, (_, i) => 101 + i) },
    })
    const disagreeing = await buildTrailIndexNow(
      request({ trailMiles: new Blob([shifted]) }),
    )
    expect(disagreeing.axisDrift?.sampled).toBe(1)
    expect(disagreeing.axisDrift?.maxMiles).toBeCloseTo(1, 5)
  })

  it('samples across the whole list and skips what cannot be placed', () => {
    const index = deserializeTrailIndex(
      // A synchronous route to an on-axis index for the arithmetic alone.
      serializeTrailIndexFor(),
    )
    const many = packPois(
      Array.from({ length: 1000 }, (_, i) => ({
        lon: -77,
        lat: 39 + (i % 11) * MILE_LAT,
        mile: 100 + (i % 11) + (i === 995 ? 0.5 : 0),
      })).concat([{ lon: -70, lat: 30, mile: 5 }]),
    )

    const drift = axisDrift(index, many)

    expect(drift?.sampled).toBeLessThanOrEqual(AXIS_DRIFT_SAMPLE)
    expect(drift?.sampled).toBeGreaterThan(100)
    // Every fifth waypoint is sampled (1,001 over a sample of 200), so the
    // one at 995 - the only drifting one - is in the sample, and the
    // unplaceable one at the end is skipped rather than read as infinite.
    expect(drift?.maxMiles).toBeCloseTo(0.5, 5)
  })
})
