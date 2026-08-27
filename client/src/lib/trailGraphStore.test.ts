// The junction graph's store (#1050).
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
  set: vi.fn(),
  del: vi.fn(),
}))

import { del, get, set } from 'idb-keyval'

import { TRAIL_GRAPH_GEOMETRY_KEY, TRAIL_GRAPH_KEY } from './config'
import {
  clearStoredGraph,
  GRAPH_STORE_HEADROOM_BYTES,
  readStoredGraph,
  storedGraphBytes,
  writeStoredGraph,
} from './trailGraphStore'

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
  estimating(1_000_000_000, 0)
})

describe('what it keeps', () => {
  it('holds the bytes, the hash, the version and when it was fetched', async () => {
    // The hash travels WITH the bytes because a phone offline cannot reach
    // latest.json to re-derive what they should hash to.
    await writeStoredGraph(TRAIL_GRAPH_KEY, {
      bytes: new Blob(['{}']),
      hash: 'abc',
      version: 'release-9',
      fetchedAt: 1_700_000_000_000,
    })

    expect(vi.mocked(set)).toHaveBeenCalledWith('ourhike:trail-graph', {
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
      expect(await readStoredGraph(TRAIL_GRAPH_KEY)).toBeNull()
    }
  })

  it('repairs a record with no version rather than refusing it', async () => {
    // A copy stored before the version was recorded is still a copy of the
    // graph. Dropping it would make a phone re-download 7.5 MB to learn what
    // it already holds.
    vi.mocked(get).mockResolvedValue({ bytes: new Blob(['{}']), hash: 'abc' })

    const stored = await readStoredGraph(TRAIL_GRAPH_KEY)

    expect(stored?.hash).toBe('abc')
    expect(stored?.version).toBeNull()
  })

  it('knows nothing about a key it does not store', async () => {
    expect(await readStoredGraph('some_other_artifact.json')).toBeNull()
    expect(
      await writeStoredGraph('some_other_artifact.json', {
        bytes: new Blob(['{}']),
        hash: 'abc',
        version: null,
      }),
    ).toBe(false)
  })
})

describe('room, which nothing in this codebase checked before', () => {
  it('declines rather than evicting a hiker’s downloaded map', async () => {
    // A browser under pressure evicts to make room without asking, and what
    // it evicts might be the 314 MB archive somebody downloaded at home. A
    // routing graph is not worth that trade.
    estimating(100 * 1024 * 1024, 90 * 1024 * 1024)

    const kept = await writeStoredGraph(TRAIL_GRAPH_KEY, {
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
      await writeStoredGraph(TRAIL_GRAPH_KEY, {
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
      await writeStoredGraph(TRAIL_GRAPH_KEY, {
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
      writeStoredGraph(TRAIL_GRAPH_KEY, {
        bytes: new Blob(['{}']),
        hash: 'abc',
        version: null,
      }),
    ).resolves.toBe(false)
  })

  it('never throws when the store cannot be read', async () => {
    vi.mocked(get).mockRejectedValue(new Error('not today'))

    await expect(readStoredGraph(TRAIL_GRAPH_KEY)).resolves.toBeNull()
  })
})

describe('what a screen can ask it', () => {
  it('reports the bytes of what is actually held, and omits what is not', async () => {
    // Absent is absent rather than zero: nothing stored is not the same claim
    // as an empty file.
    vi.mocked(get).mockImplementation((key) =>
      Promise.resolve(
        key === 'ourhike:trail-graph'
          ? { bytes: new Blob(['x'.repeat(400)]), hash: 'a' }
          : undefined,
      ),
    )

    const sizes = await storedGraphBytes()

    expect(sizes[TRAIL_GRAPH_KEY]).toBe(400)
    expect(sizes[TRAIL_GRAPH_GEOMETRY_KEY]).toBeUndefined()
  })

  it('forgets every artifact, and one stubborn key does not stop the others', async () => {
    vi.mocked(del).mockImplementation((key) =>
      key === 'ourhike:trail-graph'
        ? Promise.reject(new Error('no'))
        : Promise.resolve(undefined),
    )

    await expect(clearStoredGraph()).resolves.toBeUndefined()
    expect(vi.mocked(del)).toHaveBeenCalledTimes(4)
  })
})
