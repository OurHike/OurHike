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
const {
  graphCellStoreKey,
  olderCopyKey,
  readStoredGraph,
  storedGraphBytes,
  writeStoredGraph,
} = await import('./trailGraphStore')
const {
  fetchTrailGraphElevationCells,
  fetchTrailGraphGeometryCells,
  forgetVerifiedCompanions,
  loadTrailGraphCells,
} = await import('./trailGraphData')
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

// THE #1828 REVIEW'S THREE PLACES, and what the same review found beside them.
//
// One bar of signal reads the manifest - a few hundred KB - and fails the
// multi-MB cells. A release can publish a cell byte-identical to the one a
// phone holds, and measured 2026-10-09 UA's releases 2026-10-03, 2026-10-03-2
// and 2026-10-08 did exactly that for all 779 routing cells. And a release
// folder can answer 404 for everything: data.ourhike.org does for the
// release this build pins, measured the same day. Each test below names the
// way the code before the review failed it. Every one of those failures is
// the same one in the woods: a followed hike with no graph to resolve
// against, or a graph whose edges have no vertices, which no point snaps to.

type Half = 'graph' | 'geometry' | 'elevation'
/** One release's files, by cell and half. */
type ReleaseFiles = Record<string, Partial<Record<Half, string>>>

const SEAM: Array<[number, number]> = [P[1], [-74, 41.254], P[2]]

/** Release 9's three halves of the two cells, each in its cell's edge order. */
const R9_FILES: ReleaseFiles = {
  [WEST.name]: {
    graph: SHARD[RELEASE_9].west,
    geometry: JSON.stringify([[P[0], P[1]], SEAM]),
    elevation: JSON.stringify([
      [12, 0],
      [3, 3],
    ]),
  },
  [EAST.name]: {
    graph: SHARD[RELEASE_9].east,
    geometry: JSON.stringify([SEAM, [P[2], P[3]]]),
    elevation: JSON.stringify([
      [3, 3],
      [0, 9],
    ]),
  },
}

/** Release 10 renumbered, as above. The west cell keeps its edge order, so
 *  its other halves are byte-identical; the east cell lists its own trail
 *  first, so they are not. */
const R10_FILES: ReleaseFiles = {
  [WEST.name]: { ...R9_FILES[WEST.name], graph: SHARD[RELEASE_10].west },
  [EAST.name]: {
    graph: SHARD[RELEASE_10].east,
    geometry: JSON.stringify([[P[2], P[3]], SEAM]),
    elevation: JSON.stringify([
      [0, 9],
      [3, 3],
    ]),
  },
}

/** A release that renamed the east cell's own trail and touched nothing
 *  else: the west cell is byte-identical, the east cell's routing half is
 *  not. */
const R10_EAST_RENAMED: ReleaseFiles = {
  ...R9_FILES,
  [EAST.name]: {
    ...R9_FILES[EAST.name],
    graph: JSON.stringify({
      nodes: [P[1], P[2], P[3]],
      node_ids: [1, 2, 3],
      edges: [edge(0, 1), { ...edge(1, 2), name: 'Pine Meadow Trail (relocated)' }],
      edge_ids: [1, 2],
    }),
  },
}

const NORTH_FILES: ReleaseFiles = { [NORTH.name]: { graph: NORTH_SHARD } }

const keyOf = (name: string, half: Half) => trailGraphCellKey(name, half)
const routingKeys = (...names: string[]) => names.map((name) => keyOf(name, 'graph'))

/** What a launch of `version`'s build stored: every half in `files`. */
async function keep(files: ReleaseFiles, version: string, fetchedAt: number) {
  for (const [name, halves] of Object.entries(files)) {
    for (const [half, body] of Object.entries(halves) as Array<[Half, string]>) {
      const written = await writeStoredGraph(graphCellStoreKey(name, half), {
        bytes: new Blob([body]),
        hash: await hashOf(body),
        version,
        fetchedAt,
      })
      expect(written).toBe(true)
    }
  }
}

/**
 * The bucket publishing `files` as release `version`. Only the keys in
 * `serving` answer; every other request fails the way one bar of signal
 * fails a multi-MB request, or answers `refusal` when that is a status.
 * `manifestStatus` other than 200 is a release folder that is not there.
 */
async function publishing(
  version: string,
  files: ReleaseFiles,
  {
    serving = [] as string[],
    manifestStatus = 200,
    refusal = 'throw' as 'throw' | number,
  } = {},
) {
  const bodies: Record<string, string> = {}
  const artifacts: Record<string, { sha256: string }> = {}
  for (const [name, halves] of Object.entries(files)) {
    for (const [half, body] of Object.entries(halves) as Array<[Half, string]>) {
      bodies[keyOf(name, half)] = body
      artifacts[keyOf(name, half)] = { sha256: await hashOf(body) }
    }
  }
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.includes(RELEASE_MANIFEST_PATH)) {
      return manifestStatus === 200
        ? new Response(JSON.stringify({ version, artifacts }), { status: 200 })
        : new Response('Not Found', { status: manifestStatus })
    }
    const key = serving.find((each) => url.endsWith(`/${each}`))
    if (key !== undefined) {
      return new Response(bodies[key], {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }
    if (refusal === 'throw') throw new TypeError('Failed to fetch')
    return new Response('Not Found', { status: refusal })
  })
}

/** Whether this phone holds `name`'s `half` (the routing half unless named)
 *  as a copy of `version` - stored under it, or recorded since as published
 *  in it. */
async function heldAs(
  name: string,
  version: string,
  half: Half = 'graph',
): Promise<boolean> {
  const held = (await readStoredGraph(graphCellStoreKey(name, half))) as {
    version: string | null
    alsoPublishedIn?: unknown[]
  } | null
  return held?.version === version || (held?.alsoPublishedIn ?? []).includes(version)
}

const cellNames = (result: { current: ReturnType<typeof useTrailGraph> }) =>
  result.current.graphMerged?.cells.map((cell) => cell.name) ?? []

function inputs(overrides: Partial<Inputs>): Inputs {
  return {
    online: false,
    gate: true,
    cellIndex: INDEX,
    cellIndexSettled: true,
    cellIndexUnreachable: false,
    wanted: [],
    attempt: 0,
    ...overrides,
  }
}

describe('one bar of signal: the manifest answers and every cell fetch fails (#1828 review)', () => {
  it('useTrailGraph merges both release-9 cells of a hike stored whole after release 10 renumbered them, as with no signal at all', async () => {
    // Before the review: each stored cell's hash was not release 10's, so
    // each was refused and nothing merged - where the same phone with no
    // signal merged both.
    await keep(R9_FILES, RELEASE_9, 1_000)
    await publishing(RELEASE_10, R10_FILES)

    const { result } = mount({ online: true, wanted: [WEST, EAST] })

    await waitFor(() => expect(cellNames(result)).toEqual([WEST.name, EAST.name]))
    expect(result.current.graphMerged?.release).toEqual({ version: RELEASE_9 })
    expect(result.current.graphIndex?.graph.nodes).toEqual(P)
  })

  it('useTrailGraph merges both release-9 cells when release 10 changed the east cell and left the west cell byte-identical', async () => {
    // Before the review: the west cell was taken as release 10's by its
    // hash, which fixed the graph's release at the first cell, and the east
    // cell - release 9's only - could never join it. The hike's far end was
    // missing for the whole session.
    await keep(R9_FILES, RELEASE_9, 1_000)
    await publishing(RELEASE_10, R10_EAST_RENAMED)

    const { result } = mount({ online: true, wanted: [WEST, EAST] })

    await waitFor(() => expect(cellNames(result)).toEqual([WEST.name, EAST.name]))
    expect(result.current.graphMerged?.release).toEqual({ version: RELEASE_9 })
  })

  it('useTrailGraph adds a stored release-9 cell to a graph it built from release 9 with no signal, once release 10 is published', async () => {
    // Before the review: with the manifest answering, a stored copy stood in
    // for a failed fetch only by release 10's hash, so the session's own
    // release could not take its own cell.
    await keep(R9_FILES, RELEASE_9, 1_000)
    const { result, rerender } = mount({ online: false, wanted: [WEST] })
    await waitFor(() => expect(cellNames(result)).toEqual([WEST.name]))

    await publishing(RELEASE_10, R10_FILES)
    rerender(inputs({ online: true, wanted: [WEST, EAST] }))

    await waitFor(() => expect(cellNames(result)).toEqual([WEST.name, EAST.name]))
    expect(result.current.graphMerged?.release).toEqual({ version: RELEASE_9 })
  })

  it('loads the merged graph’s geometry and elevation when release 10 published every file byte-identical', async () => {
    // Before the review: the routing halves merged as release 10's by their
    // hash, and the geometry and elevation halves - the same bytes, stored
    // under release 9 - were refused, so both came back undecided and the
    // graph had no vertices to snap a point to.
    await keep(R9_FILES, RELEASE_9, 1_000)
    await publishing(RELEASE_10, R9_FILES)

    const { result } = mount({ online: true, wanted: [WEST, EAST] })
    await waitFor(() => expect(cellNames(result)).toEqual([WEST.name, EAST.name]))
    const merged = result.current.graphMerged!

    expect(await fetchTrailGraphGeometryCells(merged, undefined, true)).toMatchObject({
      kind: 'loaded',
    })
    expect(await fetchTrailGraphElevationCells(merged, undefined, true)).toMatchObject({
      kind: 'loaded',
    })
  })

  it('joins a byte-identical stored cell, with its geometry, to the release-10 graph a fetched cell started', async () => {
    // The east cell gets through and fixes the graph at release 10. The west
    // cell's fetch fails, and its release-9 copy is release 10's bytes, so it
    // joins. Before the review the routing half joined and its geometry was
    // refused, so the whole graph had none.
    await keep({ [WEST.name]: R9_FILES[WEST.name] }, RELEASE_9, 1_000)
    await publishing(RELEASE_10, R9_FILES, {
      serving: [keyOf(EAST.name, 'graph'), keyOf(EAST.name, 'geometry')],
    })

    const { result } = mount({ online: true, wanted: [WEST, EAST] })

    // Either order: which cell merges first is not what this is about.
    await waitFor(() =>
      expect([...cellNames(result)].sort()).toEqual([EAST.name, WEST.name].sort()),
    )
    expect(result.current.graphMerged?.release).toEqual({ version: RELEASE_10 })
    expect(
      await fetchTrailGraphGeometryCells(result.current.graphMerged!, undefined, true),
    ).toMatchObject({ kind: 'loaded' })
  })
})

describe('a release that published a stored cell byte-identical (#1828 review)', () => {
  it('a stored hike’s west cell still routes offline after the east cell it shares with a second hike was refetched with signal', async () => {
    // Before the review: the refetch rewrote the east cell's record as
    // release 10's, the west cell stayed release 9's, and offline the newest
    // of the two refused the other - on bytes identical in both releases.
    await keep(R9_FILES, RELEASE_9, 1_000)
    await publishing(
      RELEASE_10,
      { ...R9_FILES, ...NORTH_FILES },
      {
        serving: routingKeys(EAST.name, NORTH.name),
      },
    )
    const planning = mount({ online: true, wanted: [EAST, NORTH] })
    await waitFor(() => expect(cellNames(planning.result)).toHaveLength(2))
    await waitFor(async () => expect(await heldAs(EAST.name, RELEASE_10)).toBe(true))
    await waitFor(async () => expect(await heldAs(NORTH.name, RELEASE_10)).toBe(true))
    planning.unmount()
    vi.mocked(globalThis.fetch).mockRestore()

    const { result } = mount({ online: false, wanted: [WEST, EAST] })

    await waitFor(() => expect(cellNames(result)).toEqual([WEST.name, EAST.name]))
  })

  it('a second hike planned on one bar routes offline, its stored cell taken by the hash release 10 publishes', async () => {
    // Before the review: the east cell joined release 10's graph by its hash
    // and stayed recorded as release 9's, so offline the second hike's
    // release-10 cell refused it.
    await keep(R9_FILES, RELEASE_9, 1_000)
    await publishing(
      RELEASE_10,
      { ...R9_FILES, ...NORTH_FILES },
      {
        serving: routingKeys(NORTH.name),
      },
    )
    const planning = mount({ online: true, wanted: [EAST, NORTH] })
    await waitFor(() => expect(cellNames(planning.result)).toHaveLength(2))
    await waitFor(async () => expect(await heldAs(NORTH.name, RELEASE_10)).toBe(true))
    planning.unmount()
    vi.mocked(globalThis.fetch).mockRestore()

    const { result } = mount({ online: false, wanted: [EAST, NORTH] })

    await waitFor(() => expect(cellNames(result)).toEqual([EAST.name, NORTH.name]))
    expect(result.current.graphMerged?.release).toEqual({ version: RELEASE_10 })
  })

  it('loads geometry and elevation offline after the hike’s routing halves alone were refetched with signal', async () => {
    // A routing half is fetched whenever its cell is wanted; the other halves
    // only while a day hike is open. Before the review the refetch moved the
    // routing halves to release 10 and left the geometry under release 9,
    // and offline the release-10 graph refused it.
    await keep(R9_FILES, RELEASE_9, 1_000)
    await publishing(RELEASE_10, R9_FILES, { serving: routingKeys(WEST.name, EAST.name) })
    const home = mount({ online: true, wanted: [WEST, EAST] })
    await waitFor(() => expect(cellNames(home.result)).toHaveLength(2))
    await waitFor(async () => expect(await heldAs(WEST.name, RELEASE_10)).toBe(true))
    await waitFor(async () => expect(await heldAs(EAST.name, RELEASE_10)).toBe(true))
    home.unmount()
    vi.mocked(globalThis.fetch).mockRestore()

    const { result } = mount({ online: false, wanted: [WEST, EAST] })
    await waitFor(() => expect(cellNames(result)).toEqual([WEST.name, EAST.name]))
    const merged = result.current.graphMerged!

    expect(await fetchTrailGraphGeometryCells(merged, undefined, false)).toMatchObject({
      kind: 'loaded',
    })
    expect(await fetchTrailGraphElevationCells(merged, undefined, false)).toMatchObject({
      kind: 'loaded',
    })
  })

  it('still refuses release 9’s geometry offline for a release-10 graph whose routing halves were renumbered', async () => {
    // The guard the above must not loosen. Release 10's east cell lists its
    // edges in another order with the same count, so release 9's east
    // geometry would draw the seam edge along the east trail. No geometry is
    // the honest answer, and it is what this phone gets.
    await keep(R9_FILES, RELEASE_9, 1_000)
    await publishing(RELEASE_10, R10_FILES, {
      serving: routingKeys(WEST.name, EAST.name),
    })
    const home = mount({ online: true, wanted: [WEST, EAST] })
    await waitFor(() => expect(cellNames(home.result)).toHaveLength(2))
    await waitFor(async () => expect(await heldAs(WEST.name, RELEASE_10)).toBe(true))
    await waitFor(async () => expect(await heldAs(EAST.name, RELEASE_10)).toBe(true))
    home.unmount()
    vi.mocked(globalThis.fetch).mockRestore()

    const { result } = mount({ online: false, wanted: [WEST, EAST] })
    await waitFor(() => expect(cellNames(result)).toEqual([WEST.name, EAST.name]))

    expect(
      await fetchTrailGraphGeometryCells(result.current.graphMerged!, undefined, false),
    ).toEqual({ kind: 'absent' })
  })
})

describe('a release folder that answers 404 (#1828 review)', () => {
  it('useTrailGraph merges the cells this phone stored, with signal', async () => {
    // Before the review: each cell's 404 answered `not-in-release` before
    // the store was asked, settled for the session, and still routed
    // nothing after the phone lost signal.
    await keep(R9_FILES, RELEASE_9, 1_000)
    await publishing(RELEASE_10, R9_FILES, { manifestStatus: 404, refusal: 404 })

    const { result, rerender } = mount({ online: true, wanted: [WEST, EAST] })

    await waitFor(() => expect(cellNames(result)).toEqual([WEST.name, EAST.name]))
    expect(result.current.graphMerged?.release).toEqual({ version: RELEASE_9 })
    rerender(inputs({ online: false, wanted: [WEST, EAST] }))
    expect(cellNames(result)).toEqual([WEST.name, EAST.name])
  })
})

// #1837 - After a data release changes one piece of a saved hike, the phone
// strands the rest of the hike offline until every piece is refreshed.
//
// The hike spans the west and east cells, stored whole from release 9
// (R9_FILES). Release 10 renumbers both cells' routing halves (R10_FILES).
// At home with signal the hiker looks at the east end only, so the east cell
// alone is fetched from release 10 and stored under it. At the trailhead with
// no signal, the newest release stored among the hike's cells was then
// release 10, which holds the east cell alone: the west cell, stored only
// from release 9, counted as not stored, and the east cell's release-9 copy
// had been written over. The maintainer's answer (poll, 2026-10-09): keep the
// older copy until every piece is refreshed, and build offline from the
// newest release that holds every piece.
describe('a saved hike whose east cell alone was refreshed from renumbered release 10 (#1837)', () => {
  beforeEach(() => {
    // Companion halves verified by an earlier test in this file must not
    // stand in for the fetches these tests make at home.
    forgetVerifiedCompanions()
  })

  /**
   * The hiker at home with signal, looking at the east end of the hike:
   * release 10 is published and `serving` is what gets through. With the day
   * hike open, its geometry and elevation are fetched too, as App.tsx's
   * `wantsGraphGeometry` asks. Returns once the store holds what was
   * fetched as release 10's, with the session closed and the bucket gone.
   */
  async function lookAtTheEastEndAtHome(serving: string[], { dayHikeOpen = false } = {}) {
    await publishing(RELEASE_10, R10_FILES, { serving })
    const home = mount({ online: true, wanted: [EAST] })
    await waitFor(() => expect(cellNames(home.result)).toEqual([EAST.name]))
    await waitFor(async () => expect(await heldAs(EAST.name, RELEASE_10)).toBe(true))
    if (dayHikeOpen) {
      const merged = home.result.current.graphMerged!
      expect(await fetchTrailGraphGeometryCells(merged, undefined, true)).toMatchObject({
        kind: 'loaded',
      })
      expect(await fetchTrailGraphElevationCells(merged, undefined, true)).toMatchObject({
        kind: 'loaded',
      })
      await waitFor(async () =>
        expect(await heldAs(EAST.name, RELEASE_10, 'geometry')).toBe(true),
      )
      await waitFor(async () =>
        expect(await heldAs(EAST.name, RELEASE_10, 'elevation')).toBe(true),
      )
    }
    home.unmount()
    vi.mocked(globalThis.fetch).mockRestore()
  }

  const olderRouting = (name: string) =>
    readStoredGraph(olderCopyKey(graphCellStoreKey(name, 'graph')))

  /** Every graph cell byte this phone holds - the Downloads window's figure. */
  const storedTotal = async () =>
    Object.values(await storedGraphBytes()).reduce((sum, bytes) => sum + bytes, 0)

  const sizeOf = (body: string) => new Blob([body]).size

  it('useTrailGraph merges both release-9 cells of the hike offline after the east cell alone was refreshed from release 10', async () => {
    // Before #1837: [n41w074] alone, as release 10 - no route across the
    // seam, and the west half of the hike not routable at all.
    await keep(R9_FILES, RELEASE_9, 1_000)
    await lookAtTheEastEndAtHome(routingKeys(EAST.name))

    const { result } = mount({ online: false, wanted: [WEST, EAST] })

    await waitFor(() => expect(cellNames(result)).toEqual([WEST.name, EAST.name]))
    expect(result.current.graphMerged?.release).toEqual({ version: RELEASE_9 })
    expect(result.current.graphIndex?.graph.nodes).toEqual(P)
    expect(result.current.graphIndex?.graph.edges).toHaveLength(3)
  })

  it('useTrailGraph merges both release-9 cells on one bar of signal after the east cell alone was refreshed from release 10', async () => {
    // One bar: release 10's manifest is read and every cell fetch fails, so
    // the run fetches no cell and builds what no signal would (#1828
    // review). Before #1837: [n41w074] alone, as release 10, its copy taken
    // by the hash release 10 publishes.
    await keep(R9_FILES, RELEASE_9, 1_000)
    await lookAtTheEastEndAtHome(routingKeys(EAST.name))
    await publishing(RELEASE_10, R10_FILES)

    const { result } = mount({ online: true, wanted: [WEST, EAST] })

    await waitFor(() => expect(cellNames(result)).toEqual([WEST.name, EAST.name]))
    expect(result.current.graphMerged?.release).toEqual({ version: RELEASE_9 })
  })

  it('loadTrailGraphCells builds the hike from release 9 with no signal after the east cell alone was refreshed from release 10', async () => {
    // Before #1837: absent, unreachable.
    await keep(R9_FILES, RELEASE_9, 1_000)
    await lookAtTheEastEndAtHome(routingKeys(EAST.name))

    const load = await loadTrailGraphCells([WEST, EAST], undefined, false)

    expect(load).toMatchObject({
      kind: 'graph',
      merged: {
        release: { version: RELEASE_9 },
        cells: [{ name: WEST.name }, { name: EAST.name }],
      },
    })
  })

  it('loads release 9’s geometry and elevation offline for the hike when the day hike was open while the east cell was refreshed', async () => {
    // Release 10's east halves list the east trail first. Drawn on release
    // 9's east cell, which lists the seam edge first, they would put the
    // seam edge's vertices on the east trail. Release 9's halves, kept
    // beside release 10's, are the ones that line up.
    await keep(R9_FILES, RELEASE_9, 1_000)
    await lookAtTheEastEndAtHome(
      [
        keyOf(EAST.name, 'graph'),
        keyOf(EAST.name, 'geometry'),
        keyOf(EAST.name, 'elevation'),
      ],
      { dayHikeOpen: true },
    )

    const { result } = mount({ online: false, wanted: [WEST, EAST] })
    await waitFor(() => expect(cellNames(result)).toEqual([WEST.name, EAST.name]))
    const merged = result.current.graphMerged!

    expect(await fetchTrailGraphGeometryCells(merged, undefined, false)).toEqual({
      kind: 'loaded',
      data: [[P[0], P[1]], SEAM, [P[2], P[3]]],
    })
    expect(await fetchTrailGraphElevationCells(merged, undefined, false)).toEqual({
      kind: 'loaded',
      data: [
        [12, 0],
        [3, 3],
        [0, 9],
      ],
    })
  })

  it('keeps the east cell’s release-9 routing half beside its release-10 one until the west cell is refreshed too, then holds one copy of each', async () => {
    // The stored bytes before and after, which is what this costs a phone:
    // the refresh adds release 10's east routing half and keeps release
    // 9's, and once the west cell is refreshed too nothing holds release 9
    // and the store is back to one copy of each half.
    await keep(R9_FILES, RELEASE_9, 1_000)
    const before = await storedTotal()

    await lookAtTheEastEndAtHome(routingKeys(EAST.name))

    // Before #1837: `before` - the release-9 copy was written over.
    expect(await storedTotal()).toBe(before + sizeOf(SHARD[RELEASE_10].east))
    expect(await olderRouting(EAST.name)).toMatchObject({
      version: RELEASE_9,
      hash: await hashOf(SHARD[RELEASE_9].east),
    })

    await publishing(RELEASE_10, R10_FILES, { serving: routingKeys(WEST.name) })
    const west = mount({ online: true, wanted: [WEST] })
    await waitFor(async () => expect(await heldAs(WEST.name, RELEASE_10)).toBe(true))
    await waitFor(async () => expect(await olderRouting(EAST.name)).toBeNull())
    west.unmount()

    expect(await olderRouting(WEST.name)).toBeNull()
    expect(await storedTotal()).toBe(
      before -
        sizeOf(SHARD[RELEASE_9].west) -
        sizeOf(SHARD[RELEASE_9].east) +
        sizeOf(SHARD[RELEASE_10].west) +
        sizeOf(SHARD[RELEASE_10].east),
    )
  })

  it('useTrailGraph falls back to the newest stored release, leaving the east cell out, when no release holds every cell asked for', async () => {
    // The west cell holds release 10 and, kept beside it, release 9. The
    // east cell holds release 9 alone and the north cell release 10 alone,
    // so no release holds all three, and the store builds as it did before
    // #1837: from the newest stored, release 10. Passes before and after.
    await keep(R9_FILES, RELEASE_9, 1_000)
    await stored(WEST.name, SHARD[RELEASE_10].west, RELEASE_10, 2_000)
    await stored(NORTH.name, NORTH_SHARD, RELEASE_10, 3_000)

    const { result } = mount({ online: false, wanted: [WEST, EAST, NORTH] })

    await waitFor(() => expect(cellNames(result)).toEqual([WEST.name, NORTH.name]))
    expect(result.current.graphMerged?.release).toEqual({ version: RELEASE_10 })
  })
})
