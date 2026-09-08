// Loading the junction graph one cell at a time (#1257 stage 3), and the one
// place this is STRICTER than the artifact it is derived from (#975).
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
//
// SINCE THE CUT, "a graph" means "a shard": a cell's own nodes and edges plus
// where each sits in the whole (pipeline/cut_trail_graph.py). The whole-file
// artifact earlier releases published has the first half of that shape and
// not the second, and is refused here on purpose - a phone that merged it
// would be parsing the 78,595,556 bytes the cut exists to keep off the main
// thread.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { CoverageCell } from './coverageCells'

// The store, mocked at its own boundary rather than at idb-keyval's, so these
// tests say what the LOADER does with a stored copy rather than re-testing
// lib/trailGraphStore.test.ts's decisions about IndexedDB. The key builder
// is the real one: which record a cell's half lands under IS the contract.
vi.mock('./trailGraphStore', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./trailGraphStore')>()),
  readStoredGraph: vi.fn(async () => null),
  writeStoredGraph: vi.fn(async () => true),
  forgetStoredGraph: vi.fn(async () => undefined),
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
  emptyMergedGraph,
  fetchTrailGraphElevationCells,
  fetchTrailGraphGeometryCells,
  fetchTrailGraphProfileCells,
  isSettledAbsence,
  loadGraphShard,
  loadTrailGraphCells,
  mergeGraphShard,
} = await import('./trailGraphData')
const { trailGraphCellKey } = await import('./config')
const { graphCellStoreKey, readStoredGraph, writeStoredGraph } =
  await import('./trailGraphStore')
const { buildGraphIndex } = await import('./trailGraph')
const { LAUNCH_ARTIFACT_BUDGET_BYTES } = await import('./artifactBudget')

// Two cells either side of the 74°W seam, as cut_trail_graph.py would file
// them from one whole graph of four nodes and three edges:
//
//   0 -- 1 --|-- 2 -- 3      Pine Meadow Trail, west to east
//         seam at -74
//
// Edge 1 crosses the seam, so both cells carry it whole (an edge is never
// cut); node 1 is west's and node 2 is east's, and each shard carries the
// other end of the seam edge as well.
const WEST: CoverageCell = {
  name: 'n41w075',
  key: trailGraphCellKey('n41w075', 'graph'),
  bounds: [-75, 41, -74, 42],
}
const EAST: CoverageCell = {
  name: 'n41w074',
  key: trailGraphCellKey('n41w074', 'graph'),
  bounds: [-74, 41, -73, 42],
}

const edge = (from: number, to: number) => ({
  from,
  to,
  length_m: 836,
  trail_id: 'oprhp_trails:1',
  source: 'oprhp_trails',
  name: 'Pine Meadow Trail',
  blaze_color: 'blue',
})

const NODE: Array<[number, number]> = [
  [-74.1, 41.25],
  [-74.01, 41.25],
  [-73.99, 41.25],
  [-73.9, 41.25],
]

const WEST_SHARD = JSON.stringify({
  nodes: [NODE[0], NODE[1], NODE[2]],
  node_ids: [0, 1, 2],
  edges: [edge(0, 1), edge(1, 2)],
  edge_ids: [0, 1],
})
const EAST_SHARD = JSON.stringify({
  nodes: [NODE[1], NODE[2], NODE[3]],
  node_ids: [1, 2, 3],
  edges: [edge(0, 1), edge(1, 2)],
  edge_ids: [1, 2],
})

/** Each cell's edges' vertices, in the shard's own edge order. The seam
 *  edge's bend is in both, as the cutter writes it. */
const SEAM_EDGE: Array<[number, number]> = [NODE[1], [-74, 41.254], NODE[2]]
const WEST_GEOMETRY = JSON.stringify([[NODE[0], NODE[1]], SEAM_EDGE])
const EAST_GEOMETRY = JSON.stringify([SEAM_EDGE, [NODE[2], NODE[3]]])

const WEST_KEYS = {
  graph: trailGraphCellKey('n41w075', 'graph'),
  geometry: trailGraphCellKey('n41w075', 'geometry'),
  elevation: trailGraphCellKey('n41w075', 'elevation'),
  profile: trailGraphCellKey('n41w075', 'profile'),
}
const EAST_KEYS = {
  graph: trailGraphCellKey('n41w074', 'graph'),
  geometry: trailGraphCellKey('n41w074', 'geometry'),
  elevation: trailGraphCellKey('n41w074', 'elevation'),
  profile: trailGraphCellKey('n41w074', 'profile'),
}

/** Both cells merged, west first - what a phone holds after both landed. */
function merged() {
  const west = mergeGraphShard(emptyMergedGraph(), WEST.name, JSON.parse(WEST_SHARD))
  return mergeGraphShard(west, EAST.name, JSON.parse(EAST_SHARD))
}

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

/** A manifest naming every file's hash - the ordinary published state. */
async function hashed(
  files: Record<string, string>,
  extra: Record<string, unknown> = {},
): Promise<unknown> {
  const artifacts: Record<string, unknown> = {}
  for (const [key, body] of Object.entries(files)) {
    artifacts[key] = { sha256: await hashOf(body) }
  }
  return { artifacts, ...extra }
}

/**
 * A bucket holding exactly `files`, answering 404 for everything else, with
 * `manifest` at latest.json. `failing` is no signal at all.
 */
function serve({
  files = {},
  manifest,
  failing = false,
}: {
  files?: Record<string, string>
  manifest?: unknown
  failing?: boolean
} = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (failing) return Promise.reject(new TypeError('Failed to fetch'))
      if (String(url).includes('latest.json')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(manifest ?? { artifacts: {} }),
        } as unknown as Response)
      }
      const body = Object.entries(files).find(([key]) =>
        String(url).endsWith(`/${key}`),
      )?.[1]
      if (body === undefined) {
        return Promise.resolve({ ok: false, status: 404 } as unknown as Response)
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        arrayBuffer: () => Promise.resolve(new TextEncoder().encode(body).buffer),
      } as unknown as Response)
    }),
  )
}

/** The bucket as it is when both cells are published whole. */
async function serveBoth(extra: Record<string, string> = {}) {
  const files = {
    [WEST_KEYS.graph]: WEST_SHARD,
    [EAST_KEYS.graph]: EAST_SHARD,
    [WEST_KEYS.geometry]: WEST_GEOMETRY,
    [EAST_KEYS.geometry]: EAST_GEOMETRY,
    ...extra,
  }
  serve({ files, manifest: await hashed(files) })
}

function fetched(): string[] {
  return vi.mocked(fetch).mock.calls.map(([url]) => String(url))
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('the junction graph, one cell at a time', () => {
  it('indexes a shard whose bytes match what was published', async () => {
    serve({
      files: { [WEST_KEYS.graph]: WEST_SHARD },
      manifest: await hashed({ [WEST_KEYS.graph]: WEST_SHARD }),
    })

    const load = await loadGraphShard(WEST)

    expect(load.kind).toBe('shard')
    if (load.kind !== 'shard') return
    const index = buildGraphIndex(
      mergeGraphShard(emptyMergedGraph(), WEST.name, load.shard).graph,
    )
    expect(index.graph.edges).toHaveLength(2)
    expect(index.adjacency[0]).toHaveLength(1)
  })

  it('asks for the cell by the name the cutter gives it', async () => {
    // The contract with pipeline/cut_trail_graph.py's cell_key, and the
    // quietest thing in this module to get wrong: a respelt key is a 404
    // the loader reads as "this release has no such cell".
    serve({ files: { [WEST_KEYS.graph]: WEST_SHARD } })

    await loadGraphShard(WEST)

    expect(fetched()).toContain('https://data.example/trail_graph_cell_n41w075.json')
  })

  it('routes on nothing when the bytes are not what was published', async () => {
    // Corrupted topology is not cosmetic: it is a junction that does not
    // exist, handed to somebody deciding where to walk.
    serve({
      files: { [WEST_KEYS.graph]: WEST_SHARD },
      manifest: { artifacts: { [WEST_KEYS.graph]: { sha256: 'nope' } } },
    })

    await expect(loadGraphShard(WEST)).resolves.toEqual({
      kind: 'absent',
      because: 'unverifiable',
    })
  })

  it('routes on nothing when the manifest names no hash for it', async () => {
    // The same refusal nearbyTrailData makes, one step stronger: the module
    // both departed from (trailOverview) draws unverifiable bytes as a
    // three-second sketch. A graph has no lesser use to fall back to - it is
    // trusted for routing or it is not loaded.
    serve({ files: { [WEST_KEYS.graph]: WEST_SHARD }, manifest: { artifacts: {} } })

    await expect(loadGraphShard(WEST)).resolves.toEqual({
      kind: 'absent',
      because: 'unverifiable',
    })
  })

  it('says nothing when the bucket holds no such cell', async () => {
    // The ordinary case on a release older than the cut, and on any bucket a
    // publish has not reached. Not a failure.
    serve()

    await expect(loadGraphShard(WEST)).resolves.toEqual({
      kind: 'absent',
      because: 'not-in-release',
    })
  })
})

describe('bytes that pass the hash and are still not a shard', () => {
  async function refuses(body: string) {
    serve({
      files: { [WEST_KEYS.graph]: body },
      manifest: await hashed({ [WEST_KEYS.graph]: body }),
    })
    await expect(loadGraphShard(WEST)).resolves.toEqual({
      kind: 'absent',
      because: 'not-a-graph',
    })
  }

  it('refuses JSON with no nodes or edges', async () => {
    await refuses(JSON.stringify({ type: 'FeatureCollection', features: [] }))
  })

  it('refuses the whole graph an earlier release published, which is not a shard', async () => {
    // The shape before the cut: nodes and edges and nothing saying where
    // they sit in the whole. Merging it would put every edge at a made-up
    // position, and parsing it is the frozen page this module exists to
    // prevent - so a release that put the old file under a cell's name is
    // refused, not merged.
    await refuses(JSON.stringify({ nodes: [NODE[0], NODE[1]], edges: [edge(0, 1)] }))
  })

  it('refuses ids that do not describe their rows', async () => {
    // A shard whose id list is off by one merges every edge onto the wrong
    // node, which the hash cannot catch and a hiker cannot see.
    await refuses(
      JSON.stringify({
        nodes: [NODE[0], NODE[1]],
        node_ids: [0],
        edges: [edge(0, 1)],
        edge_ids: [0],
      }),
    )
    await refuses(
      JSON.stringify({
        nodes: [NODE[0], NODE[1]],
        node_ids: [0, 1],
        edges: [edge(0, 1)],
        edge_ids: ['zero'],
      }),
    )
  })

  it('refuses a node that is not a coordinate pair', async () => {
    await refuses(
      JSON.stringify({
        nodes: [{ lon: -74.1, lat: 41.25 }],
        node_ids: [0],
        edges: [],
        edge_ids: [],
      }),
    )
  })

  it('refuses an edge with no length', async () => {
    // Without length_m every route costs zero and the shortest path is
    // whichever the search happened to reach first.
    await refuses(
      JSON.stringify({
        nodes: [NODE[0], NODE[1]],
        node_ids: [0, 1],
        edges: [{ from: 0, to: 1, name: 'Pine Meadow Trail' }],
        edge_ids: [0],
      }),
    )
  })

  it('refuses bytes that are not JSON at all', async () => {
    // JSON.parse throws inside the try, which reads as reachability - one
    // retry on reconnect, then settled. The header of the module says why
    // that is accepted: bytes that matched a published hash and do not parse
    // are a release whose manifest signed off on them.
    const wrong = 'not json'
    serve({
      files: { [WEST_KEYS.graph]: wrong },
      manifest: await hashed({ [WEST_KEYS.graph]: wrong }),
    })
    const load = await loadGraphShard(WEST)
    expect(load.kind).toBe('absent')
  })

  it('accepts an empty shard, which is a real state rather than a broken file', async () => {
    // A cell with no routable trail in it publishes empty. The LOADER
    // accepts it - that is a fact about the ground, not a broken file. What
    // must not happen is the day-hike door opening on nothing, and since the
    // cut that is the INDEX's question (lib/useTrailGraph.ts reads an index
    // with no cells as the 'empty' absence), never one shard's.
    const empty = JSON.stringify({ nodes: [], node_ids: [], edges: [], edge_ids: [] })
    serve({
      files: { [WEST_KEYS.graph]: empty },
      manifest: await hashed({ [WEST_KEYS.graph]: empty }),
    })

    const load = await loadGraphShard(WEST)

    expect(load.kind).toBe('shard')
    if (load.kind !== 'shard') return
    expect(load.shard.edges).toHaveLength(0)
  })
})

describe('merging cells (#1257 stage 3)', () => {
  it('joins two cells at the junction they share, and carries the seam edge once', () => {
    const both = merged()

    // Four nodes, not six: node 1 and node 2 are in both shards and are one
    // junction each in the merge.
    expect(both.graph.nodes).toEqual([NODE[0], NODE[1], NODE[2], NODE[3]])
    // Three edges, not four: the seam edge arrived twice and was kept once.
    expect(both.edgeIds).toEqual([0, 1, 2])
    // The east cell's own edge is rewired onto the merged positions.
    expect(both.graph.edges[2]).toMatchObject({ from: 2, to: 3 })
    expect(both.edgePositions.get(2)).toBe(2)
    expect(both.nodePositions.get(3)).toBe(3)
    expect(both.cells.map((cell) => cell.name)).toEqual([WEST.name, EAST.name])
    expect(both.cells[1].edgeIds).toEqual([1, 2])
  })

  it('is append-only: what a draft indexed before a cell landed is where it was', () => {
    // `GraphPoint.edgeIndex` in a live draft is a position in this array. A
    // merge that moved edge 0 would move every tap a hiker had placed.
    const west = mergeGraphShard(emptyMergedGraph(), WEST.name, JSON.parse(WEST_SHARD))
    const both = mergeGraphShard(west, EAST.name, JSON.parse(EAST_SHARD))

    expect(both.graph.edges[0]).toBe(west.graph.edges[0])
    expect(both.graph.edges[1]).toBe(west.graph.edges[1])
    expect(both.graph.nodes.slice(0, 3)).toEqual(west.graph.nodes)
    // And the input is untouched: a caller holding the smaller graph keeps it.
    expect(west.graph.edges).toHaveLength(2)
    expect(west.cells).toHaveLength(1)
  })

  it('merges a cell once, whichever order the cells arrive in', () => {
    const both = merged()
    expect(mergeGraphShard(both, WEST.name, JSON.parse(WEST_SHARD))).toBe(both)

    const eastFirst = mergeGraphShard(
      mergeGraphShard(emptyMergedGraph(), EAST.name, JSON.parse(EAST_SHARD)),
      WEST.name,
      JSON.parse(WEST_SHARD),
    )
    // A different layout, the same graph.
    expect(eastFirst.graph.edges).toHaveLength(3)
    expect(eastFirst.graph.nodes).toHaveLength(4)
    expect([...eastFirst.edgeIds].sort()).toEqual([0, 1, 2])
  })

  it('loads and merges every cell asked for, in one call', async () => {
    await serveBoth()

    const load = await loadTrailGraphCells([WEST, EAST])

    expect(load.kind).toBe('graph')
    if (load.kind !== 'graph') return
    expect(load.index.graph.edges).toHaveLength(3)
    expect(load.merged.cells).toHaveLength(2)
  })

  it('answers empty for no cells at all, and with the first absence otherwise', async () => {
    await serveBoth()
    await expect(loadTrailGraphCells([])).resolves.toEqual({
      kind: 'absent',
      because: 'empty',
    })

    serve({
      files: { [WEST_KEYS.graph]: WEST_SHARD },
      manifest: await hashed({ [WEST_KEYS.graph]: WEST_SHARD }),
    })
    await expect(loadTrailGraphCells([WEST, EAST])).resolves.toEqual({
      kind: 'absent',
      because: 'not-in-release',
    })
  })
})

describe('the geometry half, fetched when the door opens', () => {
  it('returns each merged edge’s vertices, aligned across the cells', async () => {
    await serveBoth()

    const geometry = await fetchTrailGraphGeometryCells(merged())

    expect(geometry).not.toBeNull()
    expect(geometry).toHaveLength(3)
    expect(geometry?.[0]).toEqual([NODE[0], NODE[1]])
    expect(geometry?.[1]).toEqual(SEAM_EDGE)
    expect(geometry?.[2]).toEqual([NODE[2], NODE[3]])
    // Both cells' halves were asked for, by their own names.
    expect(fetched()).toContain(`https://data.example/${WEST_KEYS.geometry}`)
    expect(fetched()).toContain(`https://data.example/${EAST_KEYS.geometry}`)
  })

  it('refuses a cell whose count disagrees with its shard, and with it the whole', async () => {
    // The pair came from two different publishes. Edge 40 drawn from edge
    // 41's vertices is a route on the wrong trail - no highlight beats that,
    // and a highlight missing one cell's edges is a chord across whatever
    // switchback they held.
    await serveBoth({ [EAST_KEYS.geometry]: JSON.stringify([[NODE[2], NODE[3]]]) })

    await expect(fetchTrailGraphGeometryCells(merged())).resolves.toBeNull()
  })

  it('refuses unhashed or missing geometry the same way the shard is refused', async () => {
    const files = {
      [WEST_KEYS.geometry]: WEST_GEOMETRY,
      [EAST_KEYS.geometry]: EAST_GEOMETRY,
    }
    serve({ files, manifest: { artifacts: {} } })
    await expect(fetchTrailGraphGeometryCells(merged())).resolves.toBeNull()

    serve({
      files: { [WEST_KEYS.geometry]: WEST_GEOMETRY },
      manifest: await hashed(files),
    })
    await expect(fetchTrailGraphGeometryCells(merged())).resolves.toBeNull()
  })

  it('attaches onto a new index and leaves the routing-only one untouched', () => {
    const bare = buildGraphIndex(merged().graph)

    const attached = attachTrailGraphGeometry(bare, [
      [NODE[0], NODE[1]],
      SEAM_EDGE,
      [NODE[2], NODE[3]],
    ])

    expect(attached.graph.edges[1].geometry).toHaveLength(3)
    expect(bare.graph.edges[1].geometry).toBeUndefined()
  })

  it('attaching a misaligned geometry changes nothing', () => {
    const bare = buildGraphIndex(merged().graph)
    expect(attachTrailGraphGeometry(bare, [])).toBe(bare)
  })
})

describe('the climb half, fetched with the geometry (#1011)', () => {
  const WEST_CLIMB = JSON.stringify([
    [120, 40],
    [10, 5],
  ])
  const EAST_CLIMB = JSON.stringify([
    [10, 5],
    [0, 300],
  ])

  it('reads one [gain, loss] pair per merged edge when the bytes match', async () => {
    await serveBoth({
      [WEST_KEYS.elevation]: WEST_CLIMB,
      [EAST_KEYS.elevation]: EAST_CLIMB,
    })

    expect(await fetchTrailGraphElevationCells(merged())).toEqual([
      [120, 40],
      [10, 5],
      [0, 300],
    ])
  })

  it('keeps a null entry rather than reading it as a broken file', async () => {
    // The case the shape check is written around: a cell whose LEADING edges
    // sit in a DEM gap is a real artifact saying "nobody measured these",
    // and throwing it away would discard the one thing it exists to express.
    await serveBoth({
      [WEST_KEYS.elevation]: JSON.stringify([null, [10, 5]]),
      [EAST_KEYS.elevation]: EAST_CLIMB,
    })

    expect(await fetchTrailGraphElevationCells(merged())).toEqual([
      null,
      [10, 5],
      [0, 300],
    ])
  })

  it('refuses a cell whose entry count disagrees with its shard', async () => {
    // Edge 40 priced from edge 41's climb is not a visible defect - it is a
    // plausible number against the wrong trail.
    await serveBoth({
      [WEST_KEYS.elevation]: JSON.stringify([[120, 40]]),
      [EAST_KEYS.elevation]: EAST_CLIMB,
    })

    expect(await fetchTrailGraphElevationCells(merged())).toBeNull()
  })

  it('treats a cell with no climb published as no figures, rather than a failure', async () => {
    // Production today: the whole-graph companions were written for an
    // earlier graph, so the cutter refuses to cut them and the cells carry
    // none. The builder still routes and the card still prints miles.
    await serveBoth()
    expect(await fetchTrailGraphElevationCells(merged())).toBeNull()
  })

  it('refuses bytes the manifest names no hash for', async () => {
    const files = {
      [WEST_KEYS.elevation]: WEST_CLIMB,
      [EAST_KEYS.elevation]: EAST_CLIMB,
    }
    serve({ files, manifest: { artifacts: {} } })
    expect(await fetchTrailGraphElevationCells(merged())).toBeNull()
  })

  it("attaches the climb onto a new index, leaving the caller's untouched", () => {
    const bare = buildGraphIndex(merged().graph)
    const attached = attachTrailGraphElevation(bare, [
      [120, 40],
      [10, 5],
      [0, 300],
    ])
    expect(attached.graph.edges[2].climb).toEqual([0, 300])
    expect(bare.graph.edges[2].climb).toBeUndefined()
    expect(attachTrailGraphElevation(bare, [])).toBe(bare)
  })

  it('fetches the profile half the same way, one cell at a time (#1045)', async () => {
    await serveBoth({
      [WEST_KEYS.profile]: JSON.stringify([
        [900, 950],
        [950, 1000, 1050],
      ]),
      [EAST_KEYS.profile]: JSON.stringify([[950, 1000, 1050], null]),
    })

    expect(await fetchTrailGraphProfileCells(merged())).toEqual([
      [900, 950],
      [950, 1000, 1050],
      null,
    ])
  })
})

// Why there is no graph, which is a different question from whether there is
// one (#1049).
//
// The reason exists so that chrome/PlanKindSheet.tsx can say something TRUE
// to a hiker. Before it, one sentence covered every case and ended "It
// arrives with the next data sync" - which on production, where the graph was
// simply not in the release (#1048), was a promise nothing was going to keep.
//
// The distinction each case is really pinning is `isSettledAbsence`: whether
// waiting fixes it. Exactly one of these is curable by a connection, and
// getting that wrong in either direction is a lie in one direction or a
// hammer on the bucket in the other.
describe('why there is no graph', () => {
  it('separates a release with no such cell from a request that never landed', async () => {
    serve()
    await expect(loadGraphShard(WEST)).resolves.toEqual({
      kind: 'absent',
      because: 'not-in-release',
    })

    // A request that never completed at all. This is the ONLY one a hiker can
    // act on, and the only one the shell will ask again.
    serve({ failing: true })
    await expect(loadGraphShard(WEST)).resolves.toEqual({
      kind: 'absent',
      because: 'unreachable',
    })
  })

  it('separates verified bytes that are not a shard from bytes it could not verify', async () => {
    // A manifest and an artifact can be right about each other and still be
    // the wrong file.
    const notAGraph = JSON.stringify({ nodes: 'no', edges: [] })
    serve({
      files: { [WEST_KEYS.graph]: notAGraph },
      manifest: await hashed({ [WEST_KEYS.graph]: notAGraph }),
    })

    await expect(loadGraphShard(WEST)).resolves.toEqual({
      kind: 'absent',
      because: 'not-a-graph',
    })
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
      'too-large',
      'empty',
    ] as const) {
      expect(isSettledAbsence(because)).toBe(true)
    }
  })
})

describe('a cell the phone cannot hold (#1254)', () => {
  // 2026-09-07: trail_graph.json published at 78,595,556 bytes decoded, and
  // parsing it on the main thread was the frozen first page. The manifest
  // carried that size the whole time; nothing read it before fetching. The
  // cut makes this one cell's question - the densest is 12.7 MB - and the
  // budget still stands over each.
  const TOO_BIG = LAUNCH_ARTIFACT_BUDGET_BYTES + 1

  function quietWarnings() {
    return vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  }

  beforeEach(() => {
    vi.mocked(writeStoredGraph).mockClear()
  })

  it('declines it before fetching a byte, as a settled absence', async () => {
    const warn = quietWarnings()
    serve({
      files: { [WEST_KEYS.graph]: WEST_SHARD },
      manifest: {
        artifacts: {
          [WEST_KEYS.graph]: { sha256: await hashOf(WEST_SHARD), size_bytes: TOO_BIG },
        },
      },
    })

    await expect(loadGraphShard(WEST)).resolves.toEqual({
      kind: 'absent',
      because: 'too-large',
    })

    expect(fetched()).toEqual(['https://data.example/latest.json'])
    expect(writeStoredGraph).not.toHaveBeenCalled()
    // Only a smaller publish changes it - nothing here offers a retry.
    expect(isSettledAbsence('too-large')).toBe(true)
    expect(String(warn.mock.calls[0][0])).toContain(WEST_KEYS.graph)
  })

  it('weighs the bytes themselves where the manifest named no size', async () => {
    quietWarnings()
    // The size check comes before the hash check, so a body this big is
    // declined without ever being hashed or parsed - which is the point: the
    // hash costs a pass over the bytes and the parse costs the main thread.
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (String(url).includes('latest.json')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () =>
              Promise.resolve({ artifacts: { [WEST_KEYS.graph]: { sha256: 'x' } } }),
          } as unknown as Response)
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers(),
          arrayBuffer: () => Promise.resolve(new ArrayBuffer(TOO_BIG)),
        } as unknown as Response)
      }),
    )

    await expect(loadGraphShard(WEST)).resolves.toEqual({
      kind: 'absent',
      because: 'too-large',
    })
    expect(writeStoredGraph).not.toHaveBeenCalled()
  })

  it('weighs the halves the builder fetches later the same way', async () => {
    quietWarnings()
    const west = mergeGraphShard(emptyMergedGraph(), WEST.name, JSON.parse(WEST_SHARD))
    serve({
      manifest: {
        artifacts: { [WEST_KEYS.geometry]: { sha256: 'x', size_bytes: TOO_BIG } },
      },
    })
    await expect(fetchTrailGraphGeometryCells(west)).resolves.toBeNull()
    expect(fetched()).toEqual(['https://data.example/latest.json'])

    serve({
      manifest: {
        artifacts: { [WEST_KEYS.elevation]: { sha256: 'x', size_bytes: TOO_BIG } },
      },
    })
    await expect(fetchTrailGraphElevationCells(west)).resolves.toBeNull()
    expect(fetched()).toEqual(['https://data.example/latest.json'])
  })
})

describe('the phone that has no signal (#1050)', () => {
  beforeEach(() => {
    vi.mocked(writeStoredGraph).mockClear()
    vi.mocked(readStoredGraph).mockClear()
  })

  /** Stored copies by store key, as the store would hand them back. */
  function holding(records: Record<string, string>) {
    vi.mocked(readStoredGraph).mockImplementation(async (storeKey: string) => {
      const body = records[storeKey]
      if (body === undefined) return null
      return {
        bytes: new Blob([body]),
        hash: 'whatever-it-was-when-it-was-fetched',
        version: 'release-9',
        fetchedAt: 1,
      }
    })
  }

  it('routes from the store rather than refusing', async () => {
    // The whole point. A hiker who downloaded the corridor at home, drove to
    // Harriman and opened the app at the trailhead used to get a builder that
    // refused every tap - and since the cut, the cell they planned in is the
    // cell they hold.
    holding({ [graphCellStoreKey(WEST.name, 'graph')]: WEST_SHARD })

    const load = await loadGraphShard(WEST, undefined, false)

    expect(load.kind).toBe('shard')
    if (load.kind !== 'shard') return
    expect(load.shard.edges).toHaveLength(2)
  })

  it('does not go to the network to do it', async () => {
    // A phone offline cannot reach latest.json, so the stored hash is what it
    // has to trust - and nothing is ever written that did not match the
    // manifest when it was fetched.
    holding({ [graphCellStoreKey(WEST.name, 'graph')]: WEST_SHARD })
    serve()

    await loadGraphShard(WEST, undefined, false)

    expect(vi.mocked(fetch)).not.toHaveBeenCalled()
  })

  it('routes from the store when a request with signal never completes', async () => {
    // One bar on a ridge, a captive portal, a bucket that stopped answering:
    // `navigator.onLine` says yes and the request never gets an answer. The
    // whole-graph loader called that unreachable while the phone held the
    // graph; a cell kept is a cell that routes.
    holding({ [graphCellStoreKey(WEST.name, 'graph')]: WEST_SHARD })
    serve({ failing: true })

    const load = await loadGraphShard(WEST)

    expect(load.kind).toBe('shard')
    // And the bucket was asked first - the store is the fallback, not the
    // answer, while there is signal to ask with.
    expect(vi.mocked(fetch)).toHaveBeenCalled()
  })

  it('says unreachable when there is nothing stored either', async () => {
    // The same sentence as before this store existed, arrived at only when it
    // is true - with no signal, and with signal that answers nothing.
    holding({})

    await expect(loadGraphShard(WEST, undefined, false)).resolves.toEqual({
      kind: 'absent',
      because: 'unreachable',
    })
    serve({ failing: true })
    await expect(loadGraphShard(WEST)).resolves.toEqual({
      kind: 'absent',
      because: 'unreachable',
    })
  })

  it('refuses stored bytes that are not a shard', async () => {
    // The store is written by every past version of this module there will
    // ever be, and the shape check is not skipped just because the bytes are
    // ours - a whole graph stored under a cell's key is still refused.
    holding({ [graphCellStoreKey(WEST.name, 'graph')]: '{"nodes": "not a list"}' })

    expect(await loadGraphShard(WEST, undefined, false)).toEqual({
      kind: 'absent',
      because: 'not-a-graph',
    })
  })

  it('refuses a stored geometry whose count disagrees with the cell', async () => {
    // The check that matters MORE offline than online: a phone can hold a
    // shard from one release and a geometry cell from the next, and edge 40
    // drawn from edge 41's vertices is a route on the wrong trail. Offline
    // there is no fresh copy coming to correct it.
    const west = mergeGraphShard(emptyMergedGraph(), WEST.name, JSON.parse(WEST_SHARD))
    holding({
      [graphCellStoreKey(WEST.name, 'geometry')]: JSON.stringify([[NODE[0], NODE[1]]]),
    })
    expect(await fetchTrailGraphGeometryCells(west, undefined, false)).toBeNull()

    holding({ [graphCellStoreKey(WEST.name, 'geometry')]: WEST_GEOMETRY })
    expect(await fetchTrailGraphGeometryCells(west, undefined, false)).toHaveLength(2)
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

  it('stores the shard it just verified under its cell, with the release it came from', async () => {
    serve({
      files: { [WEST_KEYS.graph]: WEST_SHARD },
      manifest: await hashed({ [WEST_KEYS.graph]: WEST_SHARD }, { version: 'release-9' }),
    })

    await loadGraphShard(WEST)

    // WAITED ON, NOT SLEPT THROUGH. The write is fire-and-forget by design, so
    // there is a real ordering here - and CLAUDE.md's rule is that a test
    // waits on something observable rather than on a timer, because a timer
    // passes on an idle machine and fails on CI. `vi.waitFor` retries the
    // assertion until it holds.
    await vi.waitFor(() =>
      expect(vi.mocked(writeStoredGraph)).toHaveBeenCalledWith(
        graphCellStoreKey(WEST.name, 'graph'),
        expect.objectContaining({ hash: expect.any(String), version: 'release-9' }),
      ),
    )
    expect(vi.mocked(writeStoredGraph).mock.calls[0][1].hash).toBe(
      await hashOf(WEST_SHARD),
    )
  })

  it('routes this session even when the store refuses the write', async () => {
    // Storing is an improvement on the NEXT launch, never a condition of this
    // one.
    vi.mocked(writeStoredGraph).mockRejectedValue(new Error('full'))
    serve({
      files: { [WEST_KEYS.graph]: WEST_SHARD },
      manifest: await hashed({ [WEST_KEYS.graph]: WEST_SHARD }),
    })

    expect((await loadGraphShard(WEST)).kind).toBe('shard')
  })

  it('stores nothing it could not verify', async () => {
    // Bytes that are not what was published are not routed on - and not kept.
    serve({
      files: { [WEST_KEYS.graph]: WEST_SHARD },
      manifest: { artifacts: { [WEST_KEYS.graph]: { sha256: 'not-the-hash' } } },
    })

    // An ASSERTION OF ABSENCE cannot be waited on, so it is anchored to
    // something that can: the load completing is what would have triggered a
    // write, and a verified load in the same file proves the write happens by
    // then. If that ordering ever changes, the positive test above fails
    // first and this one is not left silently passing on a race.
    expect((await loadGraphShard(WEST)).kind).toBe('absent')

    expect(vi.mocked(writeStoredGraph)).not.toHaveBeenCalled()
  })
})
