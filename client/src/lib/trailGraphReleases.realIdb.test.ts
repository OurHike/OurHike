// One release per merged graph (#1828 - A phone merges trail-graph cells from
// two releases by node number, and a new release renumbers them), against a
// REAL IndexedDB.
//
// lib/trailGraphData.test.ts mocks the store at its own boundary, and
// lib/useTrailGraph.test.ts mocks the loader. The hazard #1828 names lives in
// the seam between the three: a cell WRITTEN under one release, a cell
// written under the next, both read back by the loader and handed to the
// hook that merges them. So this file runs the real idb-keyval over
// fake-indexeddb (lib/archiveDownload.realIdb.test.ts's method), the real
// store, the real loader and the real hook. Only the bucket - `fetch` - and
// the build's data base URL stand in.
//
// THE FOUR PLACES, as lib/trailGraphData.test.ts lays them out: P0 and P1 west
// of the 74°W seam, P2 and P3 east of it, one trail through all four. Release
// 9 numbers them 0, 1, 2, 3. Release 10 is the same ground numbered by a
// build that walked the input in another order - 3, 2, 1, 0 - which is what
// build_trail_graph.py does between publishes.
//
// Every test here that names "before #1828" fails against the code before
// it: the loader handed back whatever the store held and the hook merged it.

import 'fake-indexeddb/auto'

import { Blob as NodeBlob } from 'node:buffer'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { clear } from 'idb-keyval'

// jsdom's Blob is opaque to structuredClone, so fake-indexeddb stores it as an
// empty object; node's own Blob round-trips (archiveDownload.realIdb.test.ts
// measured this). The store and the loader make their Blobs through the
// global, so they make node's.
vi.stubGlobal('Blob', NodeBlob)

vi.mock('./config', async (importOriginal) => {
  // The release layout is the real one; only the base is substituted, as in
  // lib/trailGraphData.test.ts.
  const { releasePath, RELEASE_MANIFEST_PATH } = await import('./dataRelease')
  return {
    ...(await importOriginal<typeof import('./config')>()),
    DATA_BASE_URL: 'https://data.example',
    DATA_CONFIGURED: true,
    dataUrl: (key: string) => `https://data.example/${releasePath(key)}`,
    releaseManifestUrl: () => `https://data.example/${RELEASE_MANIFEST_PATH}`,
  }
})

const { RELEASE_MANIFEST_PATH } = await import('./dataRelease')
const { trailGraphCellKey } = await import('./config')
const { parseCellIndex } = await import('./coverageCells')
const { graphCellStoreKey, readStoredGraph, writeStoredGraph } =
  await import('./trailGraphStore')
const { loadTrailGraphCells } = await import('./trailGraphData')
const { useTrailGraph } = await import('./useTrailGraph')

type Inputs = Parameters<typeof useTrailGraph>[0]

const INDEX = parseCellIndex({
  cell_degrees: 1.0,
  seam_margin_km: 3.0,
  context_zoom: 0,
  context: null,
  cells: [
    {
      name: 'n41w075',
      key: trailGraphCellKey('n41w075', 'graph'),
      bounds: [-75, 41, -74, 42],
    },
    {
      name: 'n41w074',
      key: trailGraphCellKey('n41w074', 'graph'),
      bounds: [-74, 41, -73, 42],
    },
    {
      name: 'n42w075',
      key: trailGraphCellKey('n42w075', 'graph'),
      bounds: [-75, 42, -74, 43],
    },
  ],
})!
const [WEST, EAST, NORTH] = INDEX.cells

const P: Array<[number, number]> = [
  [-74.1, 41.25],
  [-74.01, 41.25],
  [-73.99, 41.25],
  [-73.9, 41.25],
]

const edge = (from: number, to: number) => ({
  from,
  to,
  length_m: 836,
  trail_id: 'oprhp_trails:1',
  source: 'oprhp_trails',
  name: 'Pine Meadow Trail',
  blaze_color: 'blue',
})

const RELEASE_9 = 'release-9'
const RELEASE_10 = 'release-10'

/** Each cell's routing half, by release - as cut_trail_graph.py would cut it. */
const SHARD = {
  [RELEASE_9]: {
    west: JSON.stringify({
      nodes: [P[0], P[1], P[2]],
      node_ids: [0, 1, 2],
      edges: [edge(0, 1), edge(1, 2)],
      edge_ids: [0, 1],
    }),
    east: JSON.stringify({
      nodes: [P[1], P[2], P[3]],
      node_ids: [1, 2, 3],
      edges: [edge(0, 1), edge(1, 2)],
      edge_ids: [1, 2],
    }),
  },
  [RELEASE_10]: {
    west: JSON.stringify({
      nodes: [P[0], P[1], P[2]],
      node_ids: [3, 2, 1],
      edges: [edge(0, 1), edge(1, 2)],
      edge_ids: [1, 0],
    }),
    east: JSON.stringify({
      nodes: [P[1], P[2], P[3]],
      node_ids: [2, 1, 0],
      edges: [edge(1, 2), edge(0, 1)],
      edge_ids: [2, 0],
    }),
  },
}

/** A cell north of both, standing alone - somewhere else the phone has been. */
const NORTH_SHARD = JSON.stringify({
  nodes: [
    [-74.5, 42.5],
    [-74.4, 42.5],
  ],
  node_ids: [7, 8],
  edges: [edge(0, 1)],
  edge_ids: [9],
})

async function hashOf(body: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(body) as unknown as BufferSource,
  )
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

/** What a launch of `version`'s build wrote for one cell, at `fetchedAt`. */
async function stored(name: string, body: string, version: string, fetchedAt: number) {
  const written = await writeStoredGraph(graphCellStoreKey(name, 'graph'), {
    bytes: new Blob([body]),
    hash: await hashOf(body),
    version,
    fetchedAt,
  })
  expect(written).toBe(true)
}

/** The bucket for `version`: its manifest, and the files in `serving` - every
 *  other request fails the way a request on one bar of signal does. */
async function bucket(version: string, serving: Record<string, string>) {
  const artifacts: Record<string, { sha256: string }> = {}
  for (const [key, body] of Object.entries(releaseFiles(version))) {
    artifacts[key] = { sha256: await hashOf(body) }
  }
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.includes(RELEASE_MANIFEST_PATH)) {
      return new Response(JSON.stringify({ version, artifacts }), { status: 200 })
    }
    const body = Object.entries(serving).find(([key]) => url.endsWith(`/${key}`))?.[1]
    if (body === undefined) throw new TypeError('Failed to fetch')
    return new Response(body, {
      status: 200,
      headers: { 'content-type': 'application/json' },
    })
  })
}

/** Every routing half `version` publishes, by artifact key. */
function releaseFiles(version: string): Record<string, string> {
  const release = SHARD[version as keyof typeof SHARD]
  return {
    [trailGraphCellKey(WEST.name, 'graph')]: release.west,
    [trailGraphCellKey(EAST.name, 'graph')]: release.east,
  }
}

function mount(overrides: Partial<Inputs>) {
  const inputs: Inputs = {
    online: false,
    gate: true,
    cellIndex: INDEX,
    cellIndexSettled: true,
    cellIndexUnreachable: false,
    wanted: [],
    attempt: 0,
    ...overrides,
  }
  return renderHook((props: Inputs) => useTrailGraph(props), { initialProps: inputs })
}

beforeEach(async () => {
  // idb-keyval caches its connection across tests, so the store is emptied
  // through it rather than by replacing the IDBFactory under it.
  await clear()
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('a phone holding cells from two releases, with no signal', () => {
  it('useTrailGraph merges only the newer release’s cell when the west cell is stored from release 9 and the east from release 10', async () => {
    // Before #1828 both merged: release 10's east cell joined release 9's
    // west cell by node number, and its node 0 - P3 on the ground - landed
    // on release 9's node 0, P0, a junction about 17 km away.
    await stored(WEST.name, SHARD[RELEASE_9].west, RELEASE_9, 1_000)
    await stored(EAST.name, SHARD[RELEASE_10].east, RELEASE_10, 2_000)

    const { result } = mount({ wanted: [WEST, EAST] })

    await waitFor(() =>
      expect(result.current.graphMerged?.cells.map((cell) => cell.name)).toEqual([
        EAST.name,
      ]),
    )
    expect(result.current.graphMerged?.release).toEqual({ version: RELEASE_10 })
    expect(result.current.graphIndex?.graph.nodes).toEqual([P[1], P[2], P[3]])
    expect(String(vi.mocked(console.warn).mock.calls[0][0])).toContain(WEST.name)
  })

  it('useTrailGraph merges both release-9 cells when the only release-10 cell stored is one it was not asked for', async () => {
    // Newest among the cells being built from, not across the whole store: a
    // cell fetched elsewhere after an update must not cost a hiker the
    // stretch they stored before it, whose cells agree with each other.
    await stored(WEST.name, SHARD[RELEASE_9].west, RELEASE_9, 1_000)
    await stored(EAST.name, SHARD[RELEASE_9].east, RELEASE_9, 1_500)
    await stored(NORTH.name, NORTH_SHARD, RELEASE_10, 3_000)

    const { result } = mount({ wanted: [WEST, EAST] })

    await waitFor(() => expect(result.current.graphMerged?.cells).toHaveLength(2))
    expect(result.current.graphMerged?.release).toEqual({ version: RELEASE_9 })
    expect(result.current.graphIndex?.graph.nodes).toEqual(P)
    expect(result.current.graphIndex?.graph.edges).toHaveLength(3)
  })

  it('loadTrailGraphCells answers unreachable rather than a graph built from release 9’s west cell and release 10’s east cell', async () => {
    // Before #1828 this was a graph: three nodes where the ground has four,
    // P3 missing, and the east cell's own edge drawn from P1 to P0.
    await stored(WEST.name, SHARD[RELEASE_9].west, RELEASE_9, 1_000)
    await stored(EAST.name, SHARD[RELEASE_10].east, RELEASE_10, 2_000)

    await expect(loadTrailGraphCells([WEST, EAST], undefined, false)).resolves.toEqual({
      kind: 'absent',
      because: 'unreachable',
    })
  })
})

describe('a phone holding a release-9 cell, with signal and release 10 published', () => {
  it('useTrailGraph merges the fetched release-10 west cell and leaves out the release-9 east copy when the east fetch fails', async () => {
    // One bar of signal: the manifest and the west cell come through, the
    // east cell does not. Before #1828 the east cell came from the store
    // instead - release 9's numbers, merged into release 10's graph.
    await stored(EAST.name, SHARD[RELEASE_9].east, RELEASE_9, 1_000)
    await bucket(RELEASE_10, {
      [trailGraphCellKey(WEST.name, 'graph')]: SHARD[RELEASE_10].west,
    })

    const { result } = mount({ online: true, wanted: [WEST, EAST] })

    await waitFor(() => expect(vi.mocked(console.warn)).toHaveBeenCalled())
    expect(String(vi.mocked(console.warn).mock.calls[0][0])).toContain(EAST.name)
    await waitFor(() =>
      expect(result.current.graphMerged?.cells.map((cell) => cell.name)).toEqual([
        WEST.name,
      ]),
    )
    expect(result.current.graphMerged?.release).toEqual({ version: RELEASE_10 })
    // And the fetched cell is kept under the release it came from, for the
    // next launch with no signal.
    await waitFor(async () =>
      expect(
        (await readStoredGraph(graphCellStoreKey(WEST.name, 'graph')))?.version,
      ).toBe(RELEASE_10),
    )
  })
})
