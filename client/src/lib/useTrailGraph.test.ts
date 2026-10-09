// The junction graph a phone holds, cell by cell (#1257 stage 3): what the
// hook loads, when, and what the door is told meanwhile.
//
// The loader is mocked at its own boundary - lib/trailGraphData.test.ts
// holds what a shard is and how one merges - so every wait here is on a
// mocked call having happened or a merged graph having grown, never on a
// timer. The sequences are the subject: one cell at a time, once each, and
// again only when the rule says so.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  DATA_CONFIGURED: true,
}))
vi.mock('./trailGraphData', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./trailGraphData')>()),
  loadGraphShard: vi.fn(),
}))
vi.mock('./trailGraphStore', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./trailGraphStore')>()),
  forgetWholeGraph: vi.fn(async () => undefined),
  newestStoredGraphVersion: vi.fn(async () => null),
}))

const { loadGraphShard } = await import('./trailGraphData')
const { forgetWholeGraph, newestStoredGraphVersion } = await import('./trailGraphStore')
const { parseCellIndex } = await import('./coverageCells')
const { useTrailGraph } = await import('./useTrailGraph')

type Inputs = Parameters<typeof useTrailGraph>[0]
type Shard = Extract<
  Awaited<ReturnType<typeof loadGraphShard>>,
  { kind: 'shard' }
>['shard']
type Absence = Extract<
  Awaited<ReturnType<typeof loadGraphShard>>,
  { kind: 'absent' }
>['because']

/** Three cells of the graph's index, as cut_trail_graph.py publishes it. */
const PUBLISHED = {
  cell_degrees: 1.0,
  seam_margin_km: 3.0,
  context_zoom: 0,
  context: null,
  cells: [
    { name: 'n41w075', key: 'trail_graph_cell_n41w075.json', bounds: [-75, 41, -74, 42] },
    { name: 'n41w074', key: 'trail_graph_cell_n41w074.json', bounds: [-74, 41, -73, 42] },
    { name: 'n42w075', key: 'trail_graph_cell_n42w075.json', bounds: [-75, 42, -74, 43] },
  ],
}
const INDEX = parseCellIndex(PUBLISHED)!
const [A, B, C] = INDEX.cells
const EMPTY_INDEX = parseCellIndex({ ...PUBLISHED, cells: [] })!

const edge = (from: number, to: number, name: string) => ({
  from,
  to,
  length_m: 800,
  trail_id: null,
  source: 'oprhp_trails',
  name,
  blaze_color: null,
})

/** One edge per cell; B shares a junction with A, C stands alone. */
const SHARDS: Record<string, Shard> = {
  n41w075: {
    nodes: [
      [-74.5, 41.5],
      [-74.4, 41.5],
    ],
    node_ids: [0, 1],
    edges: [edge(0, 1, 'A')],
    edge_ids: [0],
  },
  n41w074: {
    nodes: [
      [-74.4, 41.5],
      [-73.5, 41.5],
    ],
    node_ids: [1, 2],
    edges: [edge(0, 1, 'B')],
    edge_ids: [1],
  },
  n42w075: {
    nodes: [
      [-74.5, 42.5],
      [-74.4, 42.5],
    ],
    node_ids: [3, 4],
    edges: [edge(0, 1, 'C')],
    edge_ids: [2],
  },
}

/** The release every shard below is served from, unless a test says otherwise
 *  (#1828: a session's graph takes cells from one release). */
const RELEASE_9 = { version: 'release-9' }
const RELEASE_10 = { version: 'release-10' }

/** The bucket: every cell's shard, except those named absent. */
function serving(absent: Record<string, Absence> = {}) {
  vi.mocked(loadGraphShard).mockImplementation(async (cell) => {
    const because = absent[cell.name]
    return because === undefined
      ? { kind: 'shard', shard: SHARDS[cell.name], release: RELEASE_9 }
      : { kind: 'absent', because }
  })
}

/** A load this test finishes by hand. */
function deferred() {
  let settle!: (value: Awaited<ReturnType<typeof loadGraphShard>>) => void
  const promise = new Promise<Awaited<ReturnType<typeof loadGraphShard>>>((resolve) => {
    settle = resolve
  })
  return { promise, settle }
}

const DEFAULTS: Inputs = {
  online: true,
  gate: true,
  cellIndex: INDEX,
  cellIndexSettled: true,
  cellIndexUnreachable: false,
  wanted: [],
  attempt: 0,
}

function mount(overrides: Partial<Inputs> = {}) {
  return renderHook((props: Inputs) => useTrailGraph(props), {
    initialProps: { ...DEFAULTS, ...overrides },
  })
}

const askedFor = () => vi.mocked(loadGraphShard).mock.calls.map(([cell]) => cell.name)

beforeEach(() => {
  vi.mocked(loadGraphShard).mockReset()
  vi.mocked(forgetWholeGraph).mockClear()
  vi.mocked(newestStoredGraphVersion).mockReset()
  vi.mocked(newestStoredGraphVersion).mockResolvedValue(null)
  serving()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('what the door is told', () => {
  it('answers from the index, before any cell has loaded', () => {
    // The whole graph used to answer by ARRIVING - 78.6 MB parsed on the
    // main thread before the door could open. The index is the answer now.
    const { result } = mount()

    expect(result.current.trailNetwork).toEqual({ kind: 'ready' })
    expect(result.current.graphIndex).toBeNull()
    expect(loadGraphShard).not.toHaveBeenCalled()
  })

  it('is still looking until the index has settled', () => {
    const { result } = mount({ cellIndex: null, cellIndexSettled: false })
    expect(result.current.trailNetwork).toEqual({ kind: 'looking' })
  })

  it('separates a release with no graph from no signal', () => {
    // #1048's bug one surface over: "needs a connection" over a release
    // that has no cells is a promise nothing will keep.
    expect(
      mount({ cellIndex: null, cellIndexSettled: true }).result.current.trailNetwork,
    ).toEqual({ kind: 'absent', because: 'not-in-release' })
    expect(
      mount({ cellIndex: null, cellIndexSettled: true, cellIndexUnreachable: true })
        .result.current.trailNetwork,
    ).toEqual({ kind: 'absent', because: 'unreachable' })
  })

  it('calls an index with no cells empty rather than ready (#1044 review)', () => {
    // A valid index is not a routable one: a door opened onto a builder
    // that can answer no tap reads as a broken app.
    expect(mount({ cellIndex: EMPTY_INDEX }).result.current.trailNetwork).toEqual({
      kind: 'absent',
      because: 'empty',
    })
  })
})

describe('loading the wanted cells', () => {
  it('loads them one at a time, and merges each as it lands', async () => {
    // One at a time rather than all at once: the densest cell is 12.7 MB of
    // JSON, and a phone parsing four of those together is the frozen page
    // this whole cut exists to prevent, one artifact further down.
    const first = deferred()
    vi.mocked(loadGraphShard).mockReturnValueOnce(first.promise)

    const { result } = mount({ wanted: [A, B] })

    await waitFor(() => expect(askedFor()).toEqual(['n41w075']))
    // Nothing more is asked for while the first is still arriving.
    expect(askedFor()).toEqual(['n41w075'])

    first.settle({ kind: 'shard', shard: SHARDS.n41w075, release: RELEASE_9 })

    await waitFor(() => expect(askedFor()).toEqual(['n41w075', 'n41w074']))
    await waitFor(() => expect(result.current.graphIndex?.graph.edges).toHaveLength(2))
    expect(result.current.graphMerged?.cells.map((cell) => cell.name)).toEqual([
      'n41w075',
      'n41w074',
    ])
  })

  it('asks for a cell once, however often the same set is wanted', async () => {
    const { result, rerender } = mount({ wanted: [A, B] })
    await waitFor(() => expect(result.current.graphIndex?.graph.edges).toHaveLength(2))

    // The shell hands in a fresh array on every render; the SET is what is
    // compared.
    rerender({ ...DEFAULTS, wanted: [B, A] })
    rerender({ ...DEFAULTS, wanted: [A, B, A] })
    expect(askedFor()).toEqual(['n41w075', 'n41w074'])

    rerender({ ...DEFAULTS, wanted: [A, B, C] })
    await waitFor(() => expect(askedFor()).toEqual(['n41w075', 'n41w074', 'n42w075']))
    await waitFor(() => expect(result.current.graphIndex?.graph.edges).toHaveLength(3))
  })

  it('keeps what a draft indexed where it was when a cell lands (append-only)', async () => {
    // `GraphPoint.edgeIndex` in a live draft is a position in the merged
    // graph. A cell landing mid-build must not move it.
    const { result, rerender } = mount({ wanted: [A] })
    await waitFor(() => expect(result.current.graphIndex?.graph.edges).toHaveLength(1))
    const before = result.current.graphIndex!.graph.edges[0]

    rerender({ ...DEFAULTS, wanted: [A, B] })
    await waitFor(() => expect(result.current.graphIndex?.graph.edges).toHaveLength(2))

    expect(result.current.graphIndex!.graph.edges[0]).toBe(before)
    expect(result.current.graphIndex!.graph.edges[1].name).toBe('B')
  })

  it('does not ask again for a cell the bucket refused, until the door’s retry', async () => {
    // A settled absence re-requested on every render is a hammer on a bucket
    // that has already answered; the retry is the one thing that forgives it.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    serving({ n41w074: 'not-in-release' })

    const { result, rerender } = mount({ wanted: [A, B] })
    await waitFor(() => expect(askedFor()).toEqual(['n41w075', 'n41w074']))
    await waitFor(() => expect(result.current.graphIndex?.graph.edges).toHaveLength(1))

    rerender({ ...DEFAULTS, wanted: [A, B, C] })
    await waitFor(() => expect(askedFor()).toEqual(['n41w075', 'n41w074', 'n42w075']))
    expect(warn).toHaveBeenCalledTimes(1)
    expect(String(warn.mock.calls[0][0])).toContain('n41w074')

    rerender({ ...DEFAULTS, wanted: [A, B, C], attempt: 1 })
    await waitFor(() =>
      expect(askedFor().filter((name) => name === 'n41w074')).toHaveLength(2),
    )
  })

  it('asks again for a cell the request never reached, on the next run', async () => {
    // The one absence a connection cures, and the one the shell keeps asking
    // about - the next reconnection, the next change of what is wanted.
    serving({ n41w074: 'unreachable' })
    const { rerender } = mount({ wanted: [A, B] })
    await waitFor(() => expect(askedFor()).toEqual(['n41w075', 'n41w074']))

    serving()
    rerender({ ...DEFAULTS, wanted: [A, B, C] })
    await waitFor(() =>
      expect(askedFor()).toEqual(['n41w075', 'n41w074', 'n41w074', 'n42w075']),
    )
  })
})

// #1828 - A phone merges trail-graph cells from two releases by node number,
// and a new release renumbers them. lib/trailGraphData.test.ts shows what a
// merge across releases builds; these pin how the hook keeps one release.
describe('one release per session’s graph (#1828)', () => {
  it('passes the first merged cell’s release to loadGraphShard for every later cell', async () => {
    const { result } = mount({ wanted: [A, B] })
    await waitFor(() => expect(result.current.graphIndex?.graph.edges).toHaveLength(2))

    const releasesAskedFor = vi.mocked(loadGraphShard).mock.calls.map((call) => call[3])
    expect(releasesAskedFor).toEqual([undefined, RELEASE_9])
    expect(result.current.graphMerged?.release).toEqual(RELEASE_9)
  })

  it('asks the first cells for the newest release stored among them, before anything has merged', async () => {
    // The maintainer's newest-wins rule, read across the cells this run
    // wants (lib/trailGraphStore.ts's newestStoredGraphVersion says why not
    // the whole store).
    vi.mocked(newestStoredGraphVersion).mockResolvedValue(RELEASE_10)
    vi.mocked(loadGraphShard).mockImplementation(async (cell) => ({
      kind: 'shard',
      shard: SHARDS[cell.name],
      release: RELEASE_10,
    }))

    mount({ wanted: [A, B], online: false })

    await waitFor(() => expect(askedFor()).toEqual(['n41w075', 'n41w074']))
    expect(newestStoredGraphVersion).toHaveBeenCalledWith(['n41w075', 'n41w074'])
    expect(vi.mocked(loadGraphShard).mock.calls[0][3]).toEqual(RELEASE_10)
  })

  it('leaves a release-10 cell out of a release-9 graph and never re-asks it, retry included', async () => {
    // Signal came back with a newer release than the graph this session
    // built. Joining would put the new cell's trails on whatever junctions
    // release 9 gave those numbers; rebuilding would move a live draft's
    // taps. So it waits for the next launch, and the console says why.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    vi.mocked(loadGraphShard).mockImplementation(async (cell) => ({
      kind: 'shard',
      shard: SHARDS[cell.name],
      release: cell.name === 'n41w074' ? RELEASE_10 : RELEASE_9,
    }))

    const { result, rerender } = mount({ wanted: [A, B] })
    await waitFor(() => expect(warn).toHaveBeenCalledTimes(1))
    expect(String(warn.mock.calls[0][0])).toContain('n41w074')
    expect(String(warn.mock.calls[0][0])).toContain('release-10')
    await waitFor(() =>
      expect(result.current.graphMerged?.cells.map((cell) => cell.name)).toEqual([
        'n41w075',
      ]),
    )
    expect(result.current.graphMerged?.release).toEqual(RELEASE_9)

    rerender({ ...DEFAULTS, wanted: [A, B, C], attempt: 1 })
    await waitFor(() => expect(askedFor()).toEqual(['n41w075', 'n41w074', 'n42w075']))
    await waitFor(() => expect(result.current.graphMerged?.cells).toHaveLength(2))
    expect(askedFor().filter((name) => name === 'n41w074')).toHaveLength(1)
  })

  it('names a cell held only from another release in the console once, however often it is re-asked', async () => {
    // No signal, and the copy on the phone is from another release than the
    // graph: the loader answers `unreachable` - the absence a connection
    // cures - so the cell is asked again on every run, and the console line
    // must not repeat with it.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    vi.mocked(loadGraphShard).mockImplementation(async (cell) =>
      cell.name === 'n41w074'
        ? { kind: 'absent', because: 'unreachable', heldRelease: RELEASE_10 }
        : { kind: 'shard', shard: SHARDS[cell.name], release: RELEASE_9 },
    )

    const { rerender } = mount({ wanted: [A, B], online: false })
    await waitFor(() => expect(warn).toHaveBeenCalledTimes(1))
    expect(String(warn.mock.calls[0][0])).toContain('n41w074')

    rerender({ ...DEFAULTS, online: false, wanted: [A, B, C] })
    await waitFor(() =>
      expect(askedFor()).toEqual(['n41w075', 'n41w074', 'n41w074', 'n42w075']),
    )
    expect(warn).toHaveBeenCalledTimes(1)
  })
})

// #1828 review - one bar of signal reads the manifest and fails the multi-MB
// cells. lib/trailGraphData.ts leaves a stored copy it could not place to
// the hook (`heldRelease`), and the hook asks the store for it again, as a
// phone with no signal would, once the run knows its release.
describe('one bar of signal (#1828 review)', () => {
  type Load = Awaited<ReturnType<typeof loadGraphShard>>
  const held = (release: { version: string }): Load => ({
    kind: 'absent',
    because: 'unreachable',
    heldRelease: release,
  })
  const shard = (name: string, release: { version: string }): Load => ({
    kind: 'shard',
    shard: SHARDS[name],
    release,
  })
  /** Each call as [cell, online, release asked for]. */
  const calls = () =>
    vi
      .mocked(loadGraphShard)
      .mock.calls.map(([cell, , online, release]) => [cell.name, online, release])

  it('asks the store, with no signal and the newest stored release, for every held cell once the run fetched none', async () => {
    vi.mocked(newestStoredGraphVersion).mockResolvedValue(RELEASE_9)
    vi.mocked(loadGraphShard).mockImplementation(async (cell, _signal, online) =>
      online ? held(RELEASE_9) : shard(cell.name, RELEASE_9),
    )

    const { result } = mount({ wanted: [A, B] })

    await waitFor(() => expect(result.current.graphMerged?.cells).toHaveLength(2))
    expect(calls()).toEqual([
      ['n41w075', true, RELEASE_9],
      ['n41w074', true, RELEASE_9],
      ['n41w075', false, RELEASE_9],
      ['n41w074', false, RELEASE_9],
    ])
    expect(result.current.graphMerged?.release).toEqual(RELEASE_9)
  })

  it('asks the store for a held cell at once when the session’s graph already has a release', async () => {
    vi.mocked(loadGraphShard).mockImplementation(async (cell, _signal, online) =>
      cell.name === 'n41w074' && online ? held(RELEASE_9) : shard(cell.name, RELEASE_9),
    )

    const { result } = mount({ wanted: [A, B, C] })

    await waitFor(() => expect(result.current.graphMerged?.cells).toHaveLength(3))
    expect(calls()).toEqual([
      ['n41w075', true, undefined],
      ['n41w074', true, RELEASE_9],
      ['n41w074', false, RELEASE_9],
      ['n42w075', true, RELEASE_9],
    ])
  })

  it('asks the store for a held cell for the release a later cell’s fetch settled, not the newest stored', async () => {
    // A fetch got through, so this run's graph is the manifest's release; a
    // stored copy joins it only as a copy of that release.
    vi.mocked(newestStoredGraphVersion).mockResolvedValue(RELEASE_9)
    vi.mocked(loadGraphShard).mockImplementation(
      async (cell, _signal, online, release) => {
        if (cell.name === 'n41w074') return shard(cell.name, RELEASE_10)
        if (online) return held(RELEASE_9)
        return release?.version === RELEASE_10.version
          ? shard(cell.name, RELEASE_10)
          : held(RELEASE_9)
      },
    )

    const { result } = mount({ wanted: [A, B] })

    await waitFor(() => expect(result.current.graphMerged?.cells).toHaveLength(2))
    expect(calls().at(-1)).toEqual(['n41w075', false, RELEASE_10])
    expect(result.current.graphMerged?.release).toEqual(RELEASE_10)
  })

  it('names a held cell in the console only when the store will not take it either', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    vi.mocked(newestStoredGraphVersion).mockResolvedValue(RELEASE_9)
    vi.mocked(loadGraphShard).mockImplementation(async (cell, _signal, online) => {
      if (cell.name === 'n41w074') return held(RELEASE_10)
      return online ? held(RELEASE_9) : shard(cell.name, RELEASE_9)
    })

    const { result } = mount({ wanted: [A, B] })

    await waitFor(() => expect(warn).toHaveBeenCalledTimes(1))
    expect(String(warn.mock.calls[0][0])).toContain('n41w074')
    expect(String(warn.mock.calls[0][0])).toContain('release-10')
    expect(result.current.graphMerged?.cells.map((cell) => cell.name)).toEqual([
      'n41w075',
    ])
  })
})

describe('the gate (#1117)', () => {
  it('waits for the trail line’s launch fetch with signal', async () => {
    const { rerender } = mount({ wanted: [A], gate: false })
    // Nothing observable proves a negative, so the positive is anchored to
    // the same effect: the gate opening is what asks.
    expect(loadGraphShard).not.toHaveBeenCalled()

    rerender({ ...DEFAULTS, wanted: [A], gate: true })
    await waitFor(() => expect(askedFor()).toEqual(['n41w075']))
    expect(loadGraphShard).toHaveBeenCalledWith(A, expect.anything(), true, undefined)
  })

  it('reads the store without signal, gated on nothing', async () => {
    // A phone on a ridge routes from what it holds on the first tick; what
    // waits is a refetch, never a store read.
    mount({ wanted: [A], gate: false, online: false })
    await waitFor(() =>
      expect(loadGraphShard).toHaveBeenCalledWith(A, expect.anything(), false, undefined),
    )
  })
})

describe('what earlier releases left behind', () => {
  it('forgets the whole-file copies once per mount', async () => {
    // Up to 78.6 MB of graph and 224 MB of geometry under four keys nothing
    // reads any more, on a phone that fetched them before the budget existed.
    const { rerender } = mount()
    rerender({ ...DEFAULTS, wanted: [A] })
    await waitFor(() => expect(forgetWholeGraph).toHaveBeenCalledTimes(1))
    expect(forgetWholeGraph).toHaveBeenCalledTimes(1)
  })
})
