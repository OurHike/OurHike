// The junction graph's store (#1050), one cell half per record since #1257
// stage 3.
//
// WHAT THIS SUITE CANNOT SEE, stated because TESTING.md says the same thing
// about the layer underneath it: `idb-keyval` is mocked here, so eviction and
// real quota exhaustion are not exercised - only the code's own decisions
// about them. `archiveDownload.realIdb.test.ts` is where a real IndexedDB is
// driven, and a store this size arguably wants the same treatment. What is
// pinned below is that every failure path ENDS somewhere harmless, which is
// the property that matters when the thing that fails is a phone's disk on a
// mountain.

import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  keys: vi.fn(),
}))

import { del, get, getMany, keys, set } from 'idb-keyval'

import { LAUNCH_ARTIFACT_BUDGET_BYTES } from './artifactBudget'
import {
  clearStoredGraph,
  forgetStoredGraph,
  forgetWholeGraph,
  GRAPH_CELL_STORE_PREFIX,
  GRAPH_STORE_HEADROOM_BYTES,
  graphCellStoreKey,
  LEGACY_GRAPH_STORE_KEYS,
  readStoredGraph,
  storedGraphBytes,
  writeStoredGraph,
} from './trailGraphStore'

/** Harriman's cell, the four halves a phone keeps of it. */
const GRAPH = graphCellStoreKey('n41w075', 'graph')
const GEOMETRY = graphCellStoreKey('n41w075', 'geometry')

/** A storage estimate the browser is willing to give. */
function estimating(quota: number, usage: number): void {
  Object.defineProperty(navigator, 'storage', {
    configurable: true,
    value: { estimate: () => Promise.resolve({ quota, usage }) },
  })
}

/** A browser that will not say - which is most of them, some of the time. */
function estimatingNothing(): void {
  Object.defineProperty(navigator, 'storage', { configurable: true, value: undefined })
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(keys).mockResolvedValue([])
  estimating(1_000_000_000, 0)
})

describe('where it keeps them', () => {
  it('files each half of each cell under one prefix, the half before the name', () => {
    // The prefix is what lets the whole family be summed and cleared without
    // a list of cells anywhere; the half first is so a screen listing the
    // store sees a family's halves together.
    expect(GRAPH).toBe('ourhike:trail-graph-cell:graph:n41w075')
    expect(GEOMETRY).toBe('ourhike:trail-graph-cell:geometry:n41w075')
    expect(graphCellStoreKey('n42w073', 'profile')).toBe(
      'ourhike:trail-graph-cell:profile:n42w073',
    )
    for (const key of [GRAPH, GEOMETRY]) {
      expect(key.startsWith(GRAPH_CELL_STORE_PREFIX)).toBe(true)
    }
  })

  it('keeps the whole-file records’ names outside that prefix', () => {
    // So a prefix scan never counts the graph of 2026-09-07 as a cell, and
    // `forgetWholeGraph` has exactly four names to delete.
    expect(LEGACY_GRAPH_STORE_KEYS).toEqual([
      'ourhike:trail-graph',
      'ourhike:trail-graph-geometry',
      'ourhike:trail-graph-elevation',
      'ourhike:trail-graph-profile',
    ])
    for (const key of LEGACY_GRAPH_STORE_KEYS) {
      expect(key.startsWith(GRAPH_CELL_STORE_PREFIX)).toBe(false)
    }
  })
})

describe('what it keeps', () => {
  it('holds the bytes, the hash, the version and when it was fetched', async () => {
    // The hash travels WITH the bytes because a phone offline cannot reach
    // latest.json to re-derive what they should hash to.
    await writeStoredGraph(GRAPH, {
      bytes: new Blob(['{}']),
      hash: 'abc',
      version: 'release-9',
      fetchedAt: 1_700_000_000_000,
    })

    expect(vi.mocked(set)).toHaveBeenCalledWith(GRAPH, {
      bytes: expect.any(Blob),
      hash: 'abc',
      version: 'release-9',
      fetchedAt: 1_700_000_000_000,
    })
  })

  it('reads back only a record that is a blob and a hash', async () => {
    // This store is written by every past version of this module there will
    // ever be. Anything else is the no-store case, and the next verified
    // fetch rewrites it.
    for (const junk of [
      undefined,
      null,
      {},
      { bytes: 'not a blob', hash: 'h' },
      'nope',
    ]) {
      vi.mocked(get).mockResolvedValue(junk)
      expect(await readStoredGraph(GRAPH)).toBeNull()
    }
  })

  it('repairs a record with no version rather than refusing it', async () => {
    // A copy stored before the version was recorded is still a copy of the
    // cell. Dropping it would make a phone re-download what it already holds.
    vi.mocked(get).mockResolvedValue({ bytes: new Blob(['{}']), hash: 'abc' })

    const stored = await readStoredGraph(GRAPH)

    expect(stored?.hash).toBe('abc')
    expect(stored?.version).toBeNull()
  })
})

describe('what it will not hand back (#1254)', () => {
  it('forgets a record the phone cannot hold rather than handing it back', async () => {
    // Written by a launch before the budget existed: the 78.6 MB graph of
    // 2026-09-07, verified and stored, and a frozen main thread waiting for
    // the next launch to parse it. A copy nothing will parse is storage taken
    // from the map, so it goes - and a cell is weighed the same way.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    vi.mocked(get).mockResolvedValue({
      bytes: new Blob([new ArrayBuffer(LAUNCH_ARTIFACT_BUDGET_BYTES + 1)]),
      hash: 'abc',
      version: 'release-9',
      fetchedAt: 1,
    })

    await expect(readStoredGraph(GRAPH)).resolves.toBeNull()

    expect(vi.mocked(del)).toHaveBeenCalledWith(GRAPH)
    expect(warn).toHaveBeenCalledTimes(1)
    warn.mockRestore()
  })

  it('forgets one record and leaves the others', async () => {
    await forgetStoredGraph(GEOMETRY)

    expect(vi.mocked(del)).toHaveBeenCalledTimes(1)
    expect(vi.mocked(del)).toHaveBeenCalledWith(GEOMETRY)
  })

  it('never throws when the store will not forget', async () => {
    vi.mocked(del).mockRejectedValue(new Error('locked'))

    await expect(forgetStoredGraph(GRAPH)).resolves.toBeUndefined()
  })
})

describe('room, which nothing in this codebase checked before', () => {
  it('declines rather than evicting a hiker’s downloaded map', async () => {
    // A browser under pressure evicts to make room without asking, and what
    // it evicts might be the 314 MB archive somebody downloaded at home. A
    // routing graph is not worth that trade.
    estimating(100 * 1024 * 1024, 90 * 1024 * 1024)

    const kept = await writeStoredGraph(GRAPH, {
      bytes: new Blob(['x'.repeat(1024)]),
      hash: 'abc',
      version: null,
    })

    expect(kept).toBe(false)
    expect(vi.mocked(set)).not.toHaveBeenCalled()
  })

  it('stores when the room is there, headroom included', async () => {
    estimating(GRAPH_STORE_HEADROOM_BYTES + 10_000, 0)

    expect(
      await writeStoredGraph(GRAPH, {
        bytes: new Blob(['x'.repeat(1000)]),
        hash: 'abc',
        version: null,
      }),
    ).toBe(true)
  })

  it('stores when the browser will not say how much room there is', async () => {
    // Refusing on a phone that never answers would make the offline builder a
    // feature only some browsers get. The write itself is still guarded.
    estimatingNothing()

    expect(
      await writeStoredGraph(GRAPH, {
        bytes: new Blob(['x'.repeat(1000)]),
        hash: 'abc',
        version: null,
      }),
    ).toBe(true)
  })

  it('never throws when the store refuses the write', async () => {
    // The session keeps working on the bytes in hand. Storing is an
    // improvement on the NEXT launch, never a condition of this one.
    vi.mocked(set).mockRejectedValue(new DOMException('quota', 'QuotaExceededError'))

    await expect(
      writeStoredGraph(GRAPH, {
        bytes: new Blob(['{}']),
        hash: 'abc',
        version: null,
      }),
    ).resolves.toBe(false)
  })

  it('never throws when the store cannot be read', async () => {
    vi.mocked(get).mockRejectedValue(new Error('not today'))

    await expect(readStoredGraph(GRAPH)).resolves.toBeNull()
  })
})

describe('what a screen can ask it', () => {
  it('reports the bytes of every cell half actually held, and nothing else', async () => {
    // Absent is absent rather than zero: nothing stored is not the same claim
    // as an empty file. And only the family's own records count - a basemap
    // cell of the same name is the map's, and the whole-file graph of an
    // earlier release is what `forgetWholeGraph` deletes, not what a hiker
    // is told day hikes cost.
    vi.mocked(keys).mockResolvedValue([
      GRAPH,
      GEOMETRY,
      'ourhike:basemap-cell:n41w075',
      'ourhike:trail-graph',
    ])
    vi.mocked(get).mockImplementation((key) =>
      Promise.resolve(
        key === GRAPH
          ? { bytes: new Blob(['x'.repeat(400)]), hash: 'a' }
          : key === 'ourhike:trail-graph'
            ? { bytes: new Blob(['x'.repeat(9000)]), hash: 'old' }
            : undefined,
      ),
    )
    // `getMany` follows whatever `get` is doing right now, so #1303's one
    // transaction in lib/trailData.ts reads this file's store like every other
    // read, and a test that re-points `get` need not re-point both.
    vi.mocked(getMany).mockImplementation((keys) =>
      Promise.all(keys.map((key) => vi.mocked(get)(key))),
    )

    const sizes = await storedGraphBytes()

    expect(sizes).toEqual({ [GRAPH]: 400 })
  })

  it('answers with nothing when the store will not list itself', async () => {
    vi.mocked(keys).mockRejectedValue(new Error('InvalidStateError'))

    expect(await storedGraphBytes()).toEqual({})
  })

  it('forgets the whole-file records once per launch, and no cell', async () => {
    vi.mocked(keys).mockResolvedValue([GRAPH, GEOMETRY])

    await forgetWholeGraph()

    expect(vi.mocked(del).mock.calls.map(([key]) => key)).toEqual([
      ...LEGACY_GRAPH_STORE_KEYS,
    ])
  })

  it('forgets every record, legacy and cell alike, and one stubborn key does not stop the others', async () => {
    vi.mocked(keys).mockResolvedValue([GRAPH, GEOMETRY])
    vi.mocked(del).mockImplementation((key) =>
      key === 'ourhike:trail-graph'
        ? Promise.reject(new Error('no'))
        : Promise.resolve(undefined),
    )

    await expect(clearStoredGraph()).resolves.toBeUndefined()
    expect(vi.mocked(del)).toHaveBeenCalledTimes(LEGACY_GRAPH_STORE_KEYS.length + 2)
    expect(vi.mocked(del)).toHaveBeenCalledWith(GRAPH)
    expect(vi.mocked(del)).toHaveBeenCalledWith(GEOMETRY)
  })
})
