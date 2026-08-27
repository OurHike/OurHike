// Loading the junction graph, and the one place this is STRICTER than the
// artifact it is derived from (#975).
//
// lib/nearbyTrailData.ts draws unverified-shape lines: once the hash matches,
// the bytes go straight to MapLibre as a Blob and nothing inspects them. That
// is right there - re-serialising would draw something nobody checked.
//
// Nothing draws this file. It is parsed, indexed and then used to answer
// "can a hiker walk from here to there", so two checks have to pass rather
// than one: the bytes must be the published bytes, AND the published bytes
// must be a graph. A manifest and an artifact can be perfectly consistent
// with each other and still be the wrong file, and the failure that produces
// is a route down a trail that is not there.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// The store, mocked at its own boundary rather than at idb-keyval's, so these
// tests say what the LOADER does with a stored copy rather than re-testing
// lib/trailGraphStore.test.ts's decisions about IndexedDB.
vi.mock('./trailGraphStore', () => ({
  readStoredGraph: vi.fn(async () => null),
  writeStoredGraph: vi.fn(async () => true),
}))

vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
}))

const {
  attachTrailGraphElevation,
  attachTrailGraphGeometry,
  fetchTrailGraph,
  fetchTrailGraphElevation,
  fetchTrailGraphGeometry,
  isSettledAbsence,
  loadTrailGraph,
} = await import('./trailGraphData')
const { TRAIL_GRAPH_KEY, TRAIL_GRAPH_GEOMETRY_KEY, TRAIL_GRAPH_ELEVATION_KEY } =
  await import('./config')
const { readStoredGraph, writeStoredGraph } = await import('./trailGraphStore')

// Two nodes and the edge between them, carrying exactly what
// pipeline/build_trail_graph.py writes.
const GRAPH = JSON.stringify({
  nodes: [
    [-74.1, 41.25],
    [-74.09, 41.25],
  ],
  edges: [
    {
      from: 0,
      to: 1,
      length_m: 836,
      trail_id: 'oprhp_trails:1',
      source: 'oprhp_trails',
      name: 'Pine Meadow Trail',
      blaze_color: 'blue',
    },
  ],
})

/** Computed rather than pasted, so this file cannot drift from its bytes. */
async function hashOf(body: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(body) as unknown as BufferSource,
  )
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

function serve({ body, manifest }: { body?: string | 'missing'; manifest?: unknown }) {
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
      if (body === 'missing') {
        return Promise.resolve({ ok: false, status: 404 } as unknown as Response)
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        arrayBuffer: () =>
          Promise.resolve(new TextEncoder().encode(body ?? GRAPH).buffer),
      } as unknown as Response)
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('the junction graph', () => {
  it('indexes a graph whose bytes match what was published', async () => {
    serve({
      manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf(GRAPH) } } },
    })

    const index = await fetchTrailGraph()

    expect(index).not.toBeNull()
    expect(index?.graph.edges).toHaveLength(1)
    expect(index?.adjacency[0]).toHaveLength(1)
  })

  it('routes on nothing when the bytes are not what was published', async () => {
    // Corrupted topology is not cosmetic: it is a junction that does not
    // exist, handed to somebody deciding where to walk.
    serve({ manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: 'nope' } } } })

    await expect(fetchTrailGraph()).resolves.toBeNull()
  })

  it('routes on nothing when the manifest names no hash for it', async () => {
    // The same refusal nearbyTrailData makes, one step stronger: the module
    // both departed from (trailOverview) draws unverifiable bytes as a
    // three-second sketch. A graph has no lesser use to fall back to - it is
    // trusted for routing or it is not loaded.
    serve({ manifest: { artifacts: {} } })

    await expect(fetchTrailGraph()).resolves.toBeNull()
  })

  it('says nothing when the bucket holds no graph', async () => {
    // The ordinary case on a release older than the artifact, and on any
    // bucket a publish has not reached. Not a failure.
    serve({ body: 'missing' })

    await expect(fetchTrailGraph()).resolves.toBeNull()
  })
})

describe('bytes that pass the hash and are still not a graph', () => {
  it('refuses JSON with no nodes or edges', async () => {
    const wrong = JSON.stringify({ type: 'FeatureCollection', features: [] })
    serve({
      body: wrong,
      manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf(wrong) } } },
    })

    await expect(fetchTrailGraph()).resolves.toBeNull()
  })

  it('refuses a node that is not a coordinate pair', async () => {
    const wrong = JSON.stringify({ nodes: [{ lon: -74.1, lat: 41.25 }], edges: [] })
    serve({
      body: wrong,
      manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf(wrong) } } },
    })

    await expect(fetchTrailGraph()).resolves.toBeNull()
  })

  it('refuses an edge with no length', async () => {
    // Without length_m every route costs zero and the shortest path is
    // whichever the search happened to reach first.
    const wrong = JSON.stringify({
      nodes: [
        [-74.1, 41.25],
        [-74.09, 41.25],
      ],
      edges: [{ from: 0, to: 1, name: 'Pine Meadow Trail' }],
    })
    serve({
      body: wrong,
      manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf(wrong) } } },
    })

    await expect(fetchTrailGraph()).resolves.toBeNull()
  })

  it('refuses bytes that are not JSON at all', async () => {
    const wrong = 'not json'
    serve({
      body: wrong,
      manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf(wrong) } } },
    })

    await expect(fetchTrailGraph()).resolves.toBeNull()
  })

  it('accepts an empty graph, which is a real state rather than a broken file', async () => {
    // A ring with no routable trail in it publishes empty. The LOADER accepts
    // it - that is a fact about the ground, not a broken file. What must not
    // happen is the day-hike door opening on it: lib/useTrailData.ts reads a
    // zero-edge index as the 'empty' absence, because "holds a file shaped
    // like a graph" is not "can route" and a builder that answers no tap
    // reads as a broken app (#1044 review). See the test below.
    const empty = JSON.stringify({ nodes: [], edges: [] })
    serve({
      body: empty,
      manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf(empty) } } },
    })

    const index = await fetchTrailGraph()

    expect(index).not.toBeNull()
    expect(index?.graph.edges).toHaveLength(0)
  })
})

describe('the geometry half, fetched when the door opens', () => {
  const GEOMETRY = JSON.stringify([
    [
      [-74.1, 41.25],
      [-74.095, 41.254],
      [-74.09, 41.25],
    ],
  ])

  function serveGeometry({
    body,
    manifest,
  }: {
    body?: string | 'missing'
    manifest?: unknown
  }) {
    // Same server shape as serve(), pointed at the geometry key.
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
        if (body === 'missing') {
          return Promise.resolve({ ok: false, status: 404 } as unknown as Response)
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          arrayBuffer: () =>
            Promise.resolve(new TextEncoder().encode(body ?? GEOMETRY).buffer),
        } as unknown as Response)
      }),
    )
  }

  it('returns the aligned vertices for a matching edge count', async () => {
    serveGeometry({
      manifest: {
        artifacts: { [TRAIL_GRAPH_GEOMETRY_KEY]: { sha256: await hashOf(GEOMETRY) } },
      },
    })

    const geometry = await fetchTrailGraphGeometry(1)

    expect(geometry).not.toBeNull()
    expect(geometry?.[0]).toHaveLength(3)
  })

  it('refuses a geometry whose edge count disagrees with the graph', async () => {
    // The pair came from two different publishes. Edge 40 drawn from edge
    // 41's vertices is a route on the wrong trail - no highlight beats that.
    serveGeometry({
      manifest: {
        artifacts: { [TRAIL_GRAPH_GEOMETRY_KEY]: { sha256: await hashOf(GEOMETRY) } },
      },
    })

    await expect(fetchTrailGraphGeometry(2)).resolves.toBeNull()
  })

  it('refuses unhashed or missing geometry the same way the graph is refused', async () => {
    serveGeometry({ manifest: { artifacts: {} } })
    await expect(fetchTrailGraphGeometry(1)).resolves.toBeNull()

    serveGeometry({ body: 'missing' })
    await expect(fetchTrailGraphGeometry(1)).resolves.toBeNull()
  })

  it('attaches onto a new index and leaves the routing-only one untouched', async () => {
    serve({
      manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf(GRAPH) } } },
    })
    const bare = await fetchTrailGraph()
    expect(bare).not.toBeNull()

    const attached = attachTrailGraphGeometry(bare!, [
      [
        [-74.1, 41.25],
        [-74.09, 41.25],
      ],
    ])

    expect(attached.graph.edges[0].geometry).toHaveLength(2)
    expect(bare!.graph.edges[0].geometry).toBeUndefined()
  })

  it('attaching a misaligned geometry changes nothing', async () => {
    serve({
      manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf(GRAPH) } } },
    })
    const bare = await fetchTrailGraph()

    expect(attachTrailGraphGeometry(bare!, [])).toBe(bare)
  })
})

describe('the climb half, fetched with the geometry (#1011)', () => {
  it('reads one [gain, loss] pair per edge when the bytes match', async () => {
    const body = JSON.stringify([[120, 40]])
    serve({
      body,
      manifest: {
        artifacts: { [TRAIL_GRAPH_ELEVATION_KEY]: { sha256: await hashOf(body) } },
      },
    })
    expect(await fetchTrailGraphElevation(1)).toEqual([[120, 40]])
  })

  it('keeps a null entry rather than reading it as a broken file', async () => {
    // The case the shape check is written around: an artifact whose LEADING
    // edges sit in a DEM gap is a real artifact saying "nobody measured
    // these", and throwing it away would discard the one thing it exists to
    // express.
    const body = JSON.stringify([null, [10, 5]])
    serve({
      body,
      manifest: {
        artifacts: { [TRAIL_GRAPH_ELEVATION_KEY]: { sha256: await hashOf(body) } },
      },
    })
    expect(await fetchTrailGraphElevation(2)).toEqual([null, [10, 5]])
  })

  it('refuses a file whose entry count disagrees with the graph', async () => {
    // Edge 40 priced from edge 41's climb is not a visible defect - it is a
    // plausible number against the wrong trail.
    const body = JSON.stringify([
      [120, 40],
      [10, 5],
    ])
    serve({
      body,
      manifest: {
        artifacts: { [TRAIL_GRAPH_ELEVATION_KEY]: { sha256: await hashOf(body) } },
      },
    })
    expect(await fetchTrailGraphElevation(1)).toBeNull()
  })

  it('refuses bytes the manifest names no hash for', async () => {
    serve({ body: JSON.stringify([[1, 1]]), manifest: { artifacts: {} } })
    expect(await fetchTrailGraphElevation(1)).toBeNull()
  })

  it('refuses bytes that do not match the published hash', async () => {
    serve({
      body: JSON.stringify([[999, 999]]),
      manifest: {
        artifacts: {
          [TRAIL_GRAPH_ELEVATION_KEY]: { sha256: await hashOf('something else') },
        },
      },
    })
    expect(await fetchTrailGraphElevation(1)).toBeNull()
  })

  it('treats a 404 as no figures rather than a failure', async () => {
    serve({ body: 'missing' })
    expect(await fetchTrailGraphElevation(1)).toBeNull()
  })

  it("attaches the climb onto a new index, leaving the caller's untouched", async () => {
    serve({
      manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf(GRAPH) } } },
    })
    const bare = await fetchTrailGraph()
    const attached = attachTrailGraphElevation(bare!, [[120, 40]])
    expect(attached.graph.edges[0].climb).toEqual([120, 40])
    expect(bare!.graph.edges[0].climb).toBeUndefined()
  })

  it('hands back the same index when the counts disagree', async () => {
    serve({
      manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf(GRAPH) } } },
    })
    const bare = await fetchTrailGraph()
    expect(attachTrailGraphElevation(bare!, [])).toBe(bare)
  })
})

// Why there is no graph, which is a different question from whether there is
// one (#1049).
//
// The reason exists so that chrome/PlanKindSheet.tsx can say something TRUE
// to a hiker. Before it, one sentence covered every case and ended "It
// arrives with the next data sync" - which on production, where the graph is
// simply not in the release (#1048), was a promise nothing was going to keep.
//
// The distinction each case is really pinning is `isSettledAbsence`: whether
// waiting fixes it. Exactly one of these five is curable by a connection, and
// getting that wrong in either direction is a lie in one direction or a
// hammer on the bucket in the other.
describe('why there is no graph', () => {
  it('separates a release with no graph in it from a request that never landed', async () => {
    serve({ body: 'missing' })
    await expect(loadTrailGraph()).resolves.toEqual({
      kind: 'absent',
      because: 'not-in-release',
    })

    // A request that never completed at all. This is the ONLY one a hiker can
    // act on, and the only one the shell will ask again.
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )
    await expect(loadTrailGraph()).resolves.toEqual({
      kind: 'absent',
      because: 'unreachable',
    })
  })

  it('calls unverifiable bytes unverifiable, rather than not-downloaded', async () => {
    // A manifest that names no hash for the key...
    serve({ manifest: { artifacts: {} } })
    await expect(loadTrailGraph()).resolves.toEqual({
      kind: 'absent',
      because: 'unverifiable',
    })

    // ...and bytes that fail the hash it does name. Different faults, one
    // honest sentence: this is not being used, rather than not here yet.
    serve({
      manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf('other') } } },
    })
    await expect(loadTrailGraph()).resolves.toEqual({
      kind: 'absent',
      because: 'unverifiable',
    })
  })

  it('separates verified bytes that are not a graph from bytes it could not verify', async () => {
    // A manifest and an artifact can be right about each other and still be
    // the wrong file.
    const notAGraph = JSON.stringify({ nodes: 'no', edges: [] })
    serve({
      body: notAGraph,
      manifest: {
        artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf(notAGraph) } },
      },
    })

    await expect(loadTrailGraph()).resolves.toEqual({
      kind: 'absent',
      because: 'not-a-graph',
    })
  })

  it('hands back the index itself when there is one', async () => {
    serve({
      manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf(GRAPH) } } },
    })

    const load = await loadTrailGraph()

    expect(load.kind).toBe('graph')
    if (load.kind !== 'graph') return
    expect(load.index.graph.edges).toHaveLength(1)
  })

  it('marks exactly one absence as curable by waiting', () => {
    // The rule the copy and the retry both read. If this ever says a 404 is
    // curable, the sheet starts promising a sync again and the shell starts
    // re-requesting an answer the bucket has already given.
    expect(isSettledAbsence('unreachable')).toBe(false)
    for (const because of [
      'unconfigured',
      'not-in-release',
      'unverifiable',
      'not-a-graph',
    ] as const) {
      expect(isSettledAbsence(because)).toBe(true)
    }
  })
})

describe('the phone that has no signal (#1050)', () => {
  beforeEach(() => {
    vi.mocked(writeStoredGraph).mockClear()
    vi.mocked(readStoredGraph).mockClear()
  })

  /** A stored copy of `body`, as the store would hand one back. */
  function held(body: string) {
    vi.mocked(readStoredGraph).mockResolvedValue({
      bytes: new Blob([body]),
      hash: 'whatever-it-was-when-it-was-fetched',
      version: 'release-9',
      fetchedAt: 1,
    })
  }

  it('routes from the store rather than refusing', async () => {
    // The whole point. A hiker who downloaded the corridor at home, drove to
    // Harriman and opened the app at the trailhead used to get a builder that
    // refused every tap.
    held(GRAPH)

    const load = await loadTrailGraph(undefined, false)

    expect(load.kind).toBe('graph')
    if (load.kind !== 'graph') return
    expect(load.index.graph.edges).toHaveLength(1)
  })

  it('does not go to the network to do it', async () => {
    // A phone offline cannot reach latest.json, so the stored hash is what it
    // has to trust - and nothing is ever written that did not match the
    // manifest when it was fetched.
    held(GRAPH)
    serve({})

    await loadTrailGraph(undefined, false)

    expect(vi.mocked(fetch)).not.toHaveBeenCalled()
  })

  it('says unreachable when there is nothing stored either', async () => {
    // The same sentence as before this store existed, arrived at only when it
    // is true.
    vi.mocked(readStoredGraph).mockResolvedValue(null)

    const load = await loadTrailGraph(undefined, false)

    expect(load).toEqual({ kind: 'absent', because: 'unreachable' })
  })

  it('refuses stored bytes that are not a graph', async () => {
    // The store is written by every past version of this module there will
    // ever be, and the shape check is not skipped just because the bytes are
    // ours.
    held('{"nodes": "not a list"}')

    expect(await loadTrailGraph(undefined, false)).toEqual({
      kind: 'absent',
      because: 'not-a-graph',
    })
  })

  it('refuses a stored geometry whose edge count disagrees with the graph', async () => {
    // The check that matters MORE offline than online: a phone can hold a
    // graph from one release and a geometry file from the next, and edge 40
    // drawn from edge 41's vertices is a route on the wrong trail. Offline
    // there is no fresh copy coming to correct it.
    held(
      JSON.stringify([
        [
          [-74.1, 41.25],
          [-74.09, 41.25],
        ],
      ]),
    )

    expect(await fetchTrailGraphGeometry(2, undefined, false)).toBeNull()
    expect(await fetchTrailGraphGeometry(1, undefined, false)).toHaveLength(1)
  })
})

describe('keeping a verified copy (#1050)', () => {
  // The store is module-level, so its call record outlives a test unless it
  // is cleared - and "was it written" is exactly what these assert.
  beforeEach(() => {
    vi.mocked(writeStoredGraph).mockClear()
    vi.mocked(writeStoredGraph).mockResolvedValue(true)
    vi.mocked(readStoredGraph).mockResolvedValue(null)
  })

  it('stores the graph it just verified, with the release it came from', async () => {
    serve({
      manifest: {
        version: 'release-9',
        artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf(GRAPH) } },
      },
    })

    await loadTrailGraph()

    // WAITED ON, NOT SLEPT THROUGH. The write is fire-and-forget by design, so
    // there is a real ordering here - and CLAUDE.md's rule is that a test
    // waits on something observable rather than on a timer, because a timer
    // passes on an idle machine and fails on CI. `vi.waitFor` retries the
    // assertion until it holds.
    await vi.waitFor(() =>
      expect(vi.mocked(writeStoredGraph)).toHaveBeenCalledWith(
        TRAIL_GRAPH_KEY,
        expect.objectContaining({ hash: expect.any(String), version: 'release-9' }),
      ),
    )
    expect(vi.mocked(writeStoredGraph).mock.calls[0][1].hash).toBe(await hashOf(GRAPH))
  })

  it('routes this session even when the store refuses the write', async () => {
    // Storing is an improvement on the NEXT launch, never a condition of this
    // one.
    vi.mocked(writeStoredGraph).mockRejectedValue(new Error('full'))
    serve({
      manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: await hashOf(GRAPH) } } },
    })

    expect((await loadTrailGraph()).kind).toBe('graph')
  })

  it('stores nothing it could not verify', async () => {
    // Bytes that are not what was published are not drawn - and not kept.
    serve({ manifest: { artifacts: { [TRAIL_GRAPH_KEY]: { sha256: 'not-the-hash' } } } })

    // An ASSERTION OF ABSENCE cannot be waited on, so it is anchored to
    // something that can: the load completing is what would have triggered a
    // write, and a verified load in the same file proves the write happens by
    // then. If that ordering ever changes, the positive test above fails
    // first and this one is not left silently passing on a race.
    expect((await loadTrailGraph()).kind).toBe('absent')

    expect(vi.mocked(writeStoredGraph)).not.toHaveBeenCalled()
  })
})
