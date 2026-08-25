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

import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
}))

const { fetchTrailGraph } = await import('./trailGraphData')
const { TRAIL_GRAPH_KEY } = await import('./config')

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
    // Stricter than nearbyTrailData for a stronger reason: there, an
    // unverifiable line is still drawn as context. Here there is no lesser
    // use to fall back to - a graph is trusted for routing or not loaded.
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
    // A ring with no routable trail in it publishes empty. The app then finds
    // no route for any tap, which is correct and is not the same as no file.
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
