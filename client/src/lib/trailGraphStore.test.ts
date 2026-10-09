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

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  set: vi.fn(),
  setMany: vi.fn(),
  del: vi.fn(),
  delMany: vi.fn(),
  keys: vi.fn(),
  update: vi.fn(),
}))

import { del, delMany, get, getMany, keys, set, setMany, update } from 'idb-keyval'

import { LAUNCH_ARTIFACT_BUDGET_BYTES } from './artifactBudget'
import {
  clearStoredGraph,
  forgetStoredGraph,
  forgetWholeGraph,
  GRAPH_CELL_STORE_PREFIX,
  GRAPH_STORE_HEADROOM_BYTES,
  graphCellStoreKey,
  isCopyOf,
  LEGACY_GRAPH_STORE_KEYS,
  newestStoredGraphVersion,
  olderCopyKey,
  readStoredGraph,
  recordAlsoPublishedIn,
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
  // An empty store unless a test says otherwise. writeStoredGraph reads the
  // record it replaces (#1837), and a record another test left behind - an
  // oversized one, say - would otherwise be read by the writes below.
  vi.mocked(get).mockResolvedValue(undefined)
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

// #1828 - A phone merges trail-graph cells from two releases by node number,
// and a new release renumbers them. The version recorded beside each stored
// cell is how a phone with no signal picks the one release it builds from.
describe('which stored release is newest (#1828)', () => {
  const EAST_GRAPH = graphCellStoreKey('n41w074', 'graph')
  const NORTH_GRAPH = graphCellStoreKey('n42w075', 'graph')

  /** Routing halves by store key: the release each was fetched under, and when. */
  function holding(
    records: Record<string, { version: string | null; fetchedAt: number }>,
  ) {
    vi.mocked(get).mockImplementation((key) => {
      const record = records[String(key)]
      return Promise.resolve(
        record === undefined
          ? undefined
          : { bytes: new Blob(['{}']), hash: 'h', ...record },
      )
    })
  }

  it('newestStoredGraphVersion answers the version of the routing half fetched last among the cells asked about', async () => {
    holding({
      [GRAPH]: { version: 'release-9', fetchedAt: 1_000 },
      [EAST_GRAPH]: { version: 'release-10', fetchedAt: 2_000 },
    })

    expect(await newestStoredGraphVersion(['n41w075', 'n41w074'])).toEqual({
      version: 'release-10',
    })
  })

  it('newestStoredGraphVersion ignores a newer cell it was not asked about', async () => {
    // A cell fetched at home after an update must not decide which release a
    // stretch stored before it is read from.
    holding({
      [GRAPH]: { version: 'release-9', fetchedAt: 1_000 },
      [NORTH_GRAPH]: { version: 'release-10', fetchedAt: 3_000 },
    })

    expect(await newestStoredGraphVersion(['n41w075'])).toEqual({ version: 'release-9' })
  })

  it('newestStoredGraphVersion keeps "nothing held" (null) apart from "held under no version"', async () => {
    holding({ [GRAPH]: { version: null, fetchedAt: 1_000 } })

    expect(await newestStoredGraphVersion(['n41w075'])).toEqual({ version: null })
    expect(await newestStoredGraphVersion(['n41w074'])).toBeNull()
  })

  it('newestStoredGraphVersion reads only the routing half, never a geometry record of the same cell', async () => {
    holding({ [GEOMETRY]: { version: 'release-10', fetchedAt: 9_000 } })

    expect(await newestStoredGraphVersion(['n41w075'])).toBeNull()
    expect(vi.mocked(get).mock.calls.map(([key]) => key)).toEqual([GRAPH])
  })
})

// #1828 review - a release can publish a cell byte-identical to the copy a
// phone holds, and measured 2026-10-09 UA's last three releases did for all
// 779 routing cells. The copy is then that release's copy too, recorded
// beside the release it was stored under rather than over it.
describe('a copy a later release published byte-identical (#1828 review)', () => {
  /** The record idb-keyval holds under GRAPH, as the updater would see it. */
  function holdingRecord(record: Record<string, unknown> | undefined) {
    vi.mocked(get).mockResolvedValue(record)
    vi.mocked(update).mockImplementation(async (_key, updater) => {
      written = updater(record)
    })
  }
  let written: unknown

  beforeEach(() => {
    written = 'never written'
  })

  it('readStoredGraph reads a record written before alsoPublishedIn existed as published in no later release', async () => {
    vi.mocked(get).mockResolvedValue({
      bytes: new Blob(['{}']),
      hash: 'h',
      version: 'release-9',
    })

    expect((await readStoredGraph(GRAPH))?.alsoPublishedIn).toEqual([])
  })

  it('readStoredGraph keeps only the versions in alsoPublishedIn, dropping anything else stored there', async () => {
    vi.mocked(get).mockResolvedValue({
      bytes: new Blob(['{}']),
      hash: 'h',
      version: 'release-9',
      alsoPublishedIn: ['release-10', 7, null, { version: 'x' }],
    })

    expect((await readStoredGraph(GRAPH))?.alsoPublishedIn).toEqual(['release-10', null])
  })

  it('isCopyOf answers true for the release a copy was stored under and every one recorded since, and false for any other', () => {
    const copy = {
      bytes: new Blob(['{}']),
      hash: 'h',
      version: 'release-9',
      alsoPublishedIn: ['release-10'],
      fetchedAt: 1,
    }

    expect(isCopyOf(copy, 'release-9')).toBe(true)
    expect(isCopyOf(copy, 'release-10')).toBe(true)
    expect(isCopyOf(copy, 'release-11')).toBe(false)
    expect(isCopyOf(copy, null)).toBe(false)
  })

  it('recordAlsoPublishedIn adds the release to a copy whose hash it names, keeping the version and fetchedAt it was stored with', async () => {
    const record = {
      bytes: new Blob(['{}']),
      hash: 'h',
      version: 'release-9',
      fetchedAt: 1_000,
    }
    holdingRecord(record)

    await recordAlsoPublishedIn(GRAPH, 'h', 'release-10')

    expect(written).toEqual({ ...record, alsoPublishedIn: ['release-10'] })
  })

  it('recordAlsoPublishedIn writes nothing for a copy with another hash, or one already of that release', async () => {
    holdingRecord({ bytes: new Blob(['{}']), hash: 'other', version: 'release-9' })
    await recordAlsoPublishedIn(GRAPH, 'h', 'release-10')
    holdingRecord({
      bytes: new Blob(['{}']),
      hash: 'h',
      version: 'release-9',
      alsoPublishedIn: ['release-10'],
    })
    await recordAlsoPublishedIn(GRAPH, 'h', 'release-10')
    await recordAlsoPublishedIn(GRAPH, 'h', 'release-9')

    expect(vi.mocked(update)).not.toHaveBeenCalled()
  })

  it('recordAlsoPublishedIn leaves alone a copy rewritten with other bytes between its read and its write', async () => {
    // The check is made again inside the transaction: a release must never
    // be recorded on bytes it did not publish.
    vi.mocked(get).mockResolvedValue({
      bytes: new Blob(['{}']),
      hash: 'h',
      version: 'release-9',
    })
    const rewritten = { bytes: new Blob(['[]']), hash: 'new', version: 'release-10' }
    vi.mocked(update).mockImplementation(async (_key, updater) => {
      written = updater(rewritten)
    })

    await recordAlsoPublishedIn(GRAPH, 'h', 'release-10')

    expect(written).toBe(rewritten)
  })

  it('recordAlsoPublishedIn never throws when the store refuses the write', async () => {
    vi.mocked(get).mockResolvedValue({
      bytes: new Blob(['{}']),
      hash: 'h',
      version: 'release-9',
    })
    vi.mocked(update).mockRejectedValue(new DOMException('full', 'QuotaExceededError'))

    await expect(recordAlsoPublishedIn(GRAPH, 'h', 'release-10')).resolves.toBeUndefined()
  })
})

// #1837 - After a data release changes one piece of a saved hike, the phone
// strands the rest of the hike offline until every piece is refreshed. The
// maintainer's answer (poll, 2026-10-09): keep the older copy until every
// piece of the hike is refreshed, and build offline from the newest release
// that holds every piece.
//
// These run the store over a Map standing in for IndexedDB, so a test can
// say which records the store holds after a write. The west cell is
// n41w075 (GRAPH, GEOMETRY above), the east n41w074, the north n42w075.
describe('the older copy kept beside a refreshed cell half (#1837)', () => {
  const EAST_GRAPH = graphCellStoreKey('n41w074', 'graph')
  const NORTH_GRAPH = graphCellStoreKey('n42w075', 'graph')
  let records: Map<string, unknown>

  /** A stored record, its hash named after `body` so two bodies never share one. */
  const copy = (
    body: string,
    version: string,
    fetchedAt: number,
    alsoPublishedIn?: string[],
  ) => ({
    bytes: new Blob([body]),
    hash: `sha256 of ${body}`,
    version,
    fetchedAt,
    ...(alsoPublishedIn === undefined ? {} : { alsoPublishedIn }),
  })

  /** The release and hash of what the store holds under `key`, or null. */
  const held = (key: string) => {
    const record = records.get(key) as { version: string; hash: string } | undefined
    return record === undefined ? null : { version: record.version, hash: record.hash }
  }

  /** A browser whose estimate of usage is the bytes this store holds. */
  function quota(bytes: number) {
    Object.defineProperty(navigator, 'storage', {
      configurable: true,
      value: {
        estimate: async () => ({
          quota: bytes,
          usage: [...records.values()].reduce(
            (sum: number, record) => sum + ((record as { bytes: Blob }).bytes?.size ?? 0),
            0,
          ),
        }),
      },
    })
  }

  beforeEach(() => {
    records = new Map()
    vi.mocked(get).mockImplementation(async (key) => records.get(String(key)))
    vi.mocked(getMany).mockImplementation(async (wanted) =>
      wanted.map((key) => records.get(String(key))),
    )
    vi.mocked(set).mockImplementation(async (key, value) => {
      records.set(String(key), value)
    })
    vi.mocked(setMany).mockImplementation(async (entries) => {
      for (const [key, value] of entries) records.set(String(key), value)
    })
    vi.mocked(del).mockImplementation(async (key) => {
      records.delete(String(key))
    })
    vi.mocked(delMany).mockImplementation(async (gone) => {
      for (const key of gone) records.delete(String(key))
    })
    vi.mocked(keys).mockImplementation(async () => [...records.keys()] as never)
  })

  // The implementations above would otherwise outlive this describe.
  afterEach(() => {
    for (const fn of [get, getMany, set, setMany, del, delMany, keys]) {
      vi.mocked(fn).mockReset()
    }
  })

  it('olderCopyKey files a cell half’s older copy beside it, inside GRAPH_CELL_STORE_PREFIX', () => {
    // Inside the prefix, so storedGraphBytes counts it for the Downloads
    // window and clearStoredGraph forgets it with the rest.
    expect(olderCopyKey(GRAPH)).toBe('ourhike:trail-graph-cell:graph:n41w075:older')
    expect(olderCopyKey(GRAPH).startsWith(GRAPH_CELL_STORE_PREFIX)).toBe(true)
  })

  it('writeStoredGraph keeps the copy it replaces under olderCopyKey while another cell’s stored routing half is still that copy’s release', async () => {
    // The issue's hike: both cells stored from release 9, the west one
    // refetched from release 10, which renumbered it.
    records.set(GRAPH, copy('west 9', 'release-9', 1_000))
    records.set(EAST_GRAPH, copy('east 9', 'release-9', 1_000))

    await writeStoredGraph(GRAPH, copy('west 10', 'release-10', 2_000))

    expect(held(GRAPH)).toEqual({ version: 'release-10', hash: 'sha256 of west 10' })
    expect(records.get(olderCopyKey(GRAPH))).toMatchObject({
      version: 'release-9',
      hash: 'sha256 of west 9',
      fetchedAt: 1_000,
    })
    expect(held(EAST_GRAPH)).toEqual({ version: 'release-9', hash: 'sha256 of east 9' })
  })

  it('writeStoredGraph keeps no older copy when no other cell’s stored routing half is the replaced copy’s release', async () => {
    // Nothing else on the phone could be built with it.
    records.set(GRAPH, copy('west 9', 'release-9', 1_000))
    records.set(NORTH_GRAPH, copy('north 10', 'release-10', 1_500))

    await writeStoredGraph(GRAPH, copy('west 10', 'release-10', 2_000))

    expect(held(GRAPH)).toEqual({ version: 'release-10', hash: 'sha256 of west 10' })
    expect(records.has(olderCopyKey(GRAPH))).toBe(false)
  })

  it('writeStoredGraph keeps no older copy of bytes replaced under the release they were stored as', async () => {
    // Two different files under one version - two releases that named no
    // version read as one (lib/trailGraphData.ts's GraphRelease). Kept, the
    // two copies would both claim that release.
    records.set(GRAPH, copy('west 9', 'release-9', 1_000))
    records.set(EAST_GRAPH, copy('east 9', 'release-9', 1_000))

    await writeStoredGraph(GRAPH, copy('west 9, again', 'release-9', 2_000))

    expect(records.has(olderCopyKey(GRAPH))).toBe(false)
  })

  it('writeStoredGraph keeps a geometry half’s replaced copy while a stored routing half is still that copy’s release', async () => {
    // A graph built from release 9 needs release 9's geometry: the halves
    // line up by edge order, and release 10 may list the edges differently.
    records.set(GRAPH, copy('west 10', 'release-10', 2_000))
    records.set(olderCopyKey(GRAPH), copy('west 9', 'release-9', 1_000))
    records.set(GEOMETRY, copy('west geometry 9', 'release-9', 1_000))
    records.set(EAST_GRAPH, copy('east 9', 'release-9', 1_000))

    await writeStoredGraph(GEOMETRY, copy('west geometry 10', 'release-10', 2_100))

    expect(held(GEOMETRY)).toEqual({
      version: 'release-10',
      hash: 'sha256 of west geometry 10',
    })
    expect(held(olderCopyKey(GEOMETRY))).toEqual({
      version: 'release-9',
      hash: 'sha256 of west geometry 9',
    })
  })

  it('writeStoredGraph drops every older copy, of every half, once no stored routing half is a copy of its release', async () => {
    // The east cell refreshed too: every piece of the hike is release 10's,
    // and nothing on the phone could be built from release 9 any more.
    records.set(GRAPH, copy('west 10', 'release-10', 2_000))
    records.set(olderCopyKey(GRAPH), copy('west 9', 'release-9', 1_000))
    records.set(GEOMETRY, copy('west geometry 10', 'release-10', 2_000))
    records.set(olderCopyKey(GEOMETRY), copy('west geometry 9', 'release-9', 1_000))
    records.set(EAST_GRAPH, copy('east 9', 'release-9', 1_000))

    await writeStoredGraph(EAST_GRAPH, copy('east 10', 'release-10', 3_000))

    expect([...records.keys()].sort()).toEqual([EAST_GRAPH, GEOMETRY, GRAPH].sort())
    expect(held(EAST_GRAPH)).toEqual({ version: 'release-10', hash: 'sha256 of east 10' })
  })

  it('writeStoredGraph keeps the older copy it already held, not the one it replaces, when only the older one’s release is still a stored routing half’s', async () => {
    // Three releases. The west cell was refreshed under release 10 and again
    // under release 11; the east cell is still release 9's. Release 10's
    // west copy helps no stored cell, and release 9's still does.
    records.set(GRAPH, copy('west 10', 'release-10', 2_000))
    records.set(olderCopyKey(GRAPH), copy('west 9', 'release-9', 1_000))
    records.set(EAST_GRAPH, copy('east 9', 'release-9', 1_000))

    await writeStoredGraph(GRAPH, copy('west 11', 'release-11', 3_000))

    expect(held(GRAPH)).toEqual({ version: 'release-11', hash: 'sha256 of west 11' })
    expect(held(olderCopyKey(GRAPH))).toEqual({
      version: 'release-9',
      hash: 'sha256 of west 9',
    })
  })

  it('writeStoredGraph counts a release a later manifest named for a stored routing half (alsoPublishedIn) as still that half’s', async () => {
    // The east cell was stored from release 8 and published byte-identical
    // in release 9, so it is release 9's copy too, and the west cell's
    // release-9 copy can still be built with it.
    records.set(GRAPH, copy('west 10', 'release-10', 2_000))
    records.set(olderCopyKey(GRAPH), copy('west 9', 'release-9', 1_000))
    records.set(EAST_GRAPH, copy('east 8', 'release-8', 500, ['release-9']))

    await writeStoredGraph(NORTH_GRAPH, copy('north 10', 'release-10', 3_000))

    expect(held(olderCopyKey(GRAPH))).toEqual({
      version: 'release-9',
      hash: 'sha256 of west 9',
    })
  })

  it('writeStoredGraph gives up every older copy before declining a write for room, and keeps no older copy on that write', async () => {
    // Older copies before anything current. The older west copy is what
    // stands between this write and the room it needs.
    records.set(GRAPH, copy('west 10', 'release-10', 2_000))
    records.set(olderCopyKey(GRAPH), copy('x'.repeat(5_000), 'release-9', 1_000))
    records.set(EAST_GRAPH, copy('east 9', 'release-9', 1_000))
    quota(GRAPH_STORE_HEADROOM_BYTES + 1_000)

    const kept = await writeStoredGraph(EAST_GRAPH, copy('east 10', 'release-10', 3_000))

    expect(kept).toBe(true)
    expect([...records.keys()].sort()).toEqual([EAST_GRAPH, GRAPH].sort())
    expect(held(EAST_GRAPH)).toEqual({ version: 'release-10', hash: 'sha256 of east 10' })
  })

  it('writeStoredGraph still declines, every current copy untouched, when giving up every older copy leaves too little room', async () => {
    records.set(GRAPH, copy('west 10', 'release-10', 2_000))
    records.set(olderCopyKey(GRAPH), copy('x'.repeat(5_000), 'release-9', 1_000))
    records.set(EAST_GRAPH, copy('east 9', 'release-9', 1_000))
    quota(GRAPH_STORE_HEADROOM_BYTES + 1)

    const kept = await writeStoredGraph(EAST_GRAPH, copy('east 10', 'release-10', 3_000))

    expect(kept).toBe(false)
    expect([...records.keys()].sort()).toEqual([EAST_GRAPH, GRAPH].sort())
    expect(held(EAST_GRAPH)).toEqual({ version: 'release-9', hash: 'sha256 of east 9' })
    expect(held(GRAPH)).toEqual({ version: 'release-10', hash: 'sha256 of west 10' })
  })

  it('storedGraphBytes counts an older copy’s bytes, and clearStoredGraph forgets it', async () => {
    records.set(GRAPH, copy('x'.repeat(300), 'release-10', 2_000))
    records.set(olderCopyKey(GRAPH), copy('x'.repeat(200), 'release-9', 1_000))

    expect(await storedGraphBytes()).toEqual({ [GRAPH]: 300, [olderCopyKey(GRAPH)]: 200 })

    await clearStoredGraph()

    expect(records.size).toBe(0)
  })
})
