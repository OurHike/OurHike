// The trail-data account (#1103): every figure measured off the store, every
// absence stated, and an unreadable store answering like an empty one. The
// list's contract is COMPLETENESS - every stored artifact, present or not -
// so the window can never quietly forget one.
//
// It forgot one. `ourhike:network-overview` (#1135) was stored, occupied
// bytes, and appeared in no row, while these tests asserted the list's length
// and passed - a count only holds a list complete against changes that also
// edit the count, which is every change except the one that matters. So the
// lengths below are joined by `covers every id the window can label`, which
// fails when a row exists with no name and when a name exists with no row.

import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  keys: vi.fn(),
}))

const { get, keys } = await import('idb-keyval')
const { storedTrailData } = await import('./onThisPhone')
const { TRAILS_BLOB_KEY, POIS_KEY, ELEVATION_STORE_KEY } = await import('./trailData')
const { NETWORK_OVERVIEW_STORE_KEY } = await import('./nearbyTrailData')
const { graphCellStoreKey } = await import('./trailGraphStore')
const { TRAIL_DATA_LABEL } = await import('../screens/Downloads')

beforeEach(() => {
  vi.mocked(get).mockReset()
  vi.mocked(get).mockResolvedValue(undefined)
  vi.mocked(keys).mockReset()
  vi.mocked(keys).mockResolvedValue([])
})

/** Answers per key, everything else absent - and lists exactly those keys,
 *  which is how the graph's cells are found (lib/trailGraphStore.ts). */
function store(values: Record<string, unknown>): void {
  vi.mocked(get).mockImplementation((key) => Promise.resolve(values[String(key)]))
  vi.mocked(keys).mockResolvedValue(Object.keys(values))
}

describe('storedTrailData', () => {
  it('measures what the store actually holds - bytes for blobs, counts for records', async () => {
    store({
      [TRAILS_BLOB_KEY]: new Blob(['x'.repeat(1234)]),
      [POIS_KEY]: [{ id: 'a' }, { id: 'b' }, { id: 'c' }],
      [ELEVATION_STORE_KEY]: { samples: [1, 2, 3, 4] },
      // Two of the four halves of one graph cell (#1257 stage 3), which is a
      // real state: the routing half arrives where the hiker plans and the
      // geometry only when a builder opens. They sum into one row - see
      // storedTrailData for why.
      [graphCellStoreKey('n41w075', 'graph')]: {
        bytes: new Blob(['g'.repeat(500)]),
        hash: 'g',
      },
      [graphCellStoreKey('n41w075', 'geometry')]: {
        bytes: new Blob(['v'.repeat(200)]),
        hash: 'v',
      },
      [NETWORK_OVERVIEW_STORE_KEY]: { bytes: new Blob(['o'.repeat(321)]), hash: 'o' },
    })

    const assets = await storedTrailData()

    expect(assets).toEqual([
      { id: 'trail-line', bytes: 1234, count: null, present: true },
      { id: 'waypoints', bytes: null, count: 3, present: true },
      { id: 'elevation', bytes: null, count: 4, present: true },
      { id: 'day-hike-routing', bytes: 700, count: null, present: true },
      { id: 'network-overview', bytes: 321, count: null, present: true },
    ])
  })

  it('counts no whole-file graph an earlier release stored, only cells (#1257 stage 3)', async () => {
    // The 78.6 MB graph of 2026-09-07 is deleted at launch and read by
    // nothing; a phone that still holds it must not be told day hikes cost
    // that, and must not be told they work without a signal.
    store({
      'ourhike:trail-graph': { bytes: new Blob(['g'.repeat(78_000)]), hash: 'old' },
      'ourhike:trail-graph-geometry': {
        bytes: new Blob(['v'.repeat(224_000)]),
        hash: 'old',
      },
    })

    const routing = (await storedTrailData()).find(
      (asset) => asset.id === 'day-hike-routing',
    )

    expect(routing).toEqual({
      id: 'day-hike-routing',
      bytes: null,
      count: null,
      present: false,
    })
  })

  it('has no row for the whole-file network copy, and does not read its key (#1257)', async () => {
    // The lines above the seam are tiles kept in no store, so a row would
    // claim coverage the build does not have - and the copy earlier releases
    // stored is deleted at launch, so a row about it would be a row about
    // nothing. A stale one left behind must not surface as a figure either.
    store({
      'ourhike:nearby-trails': { bytes: new Blob(['y'.repeat(999)]), hash: 'h' },
    })

    const assets = await storedTrailData()

    expect(assets.map((asset) => asset.id)).not.toContain('nearby-trails')
    expect(vi.mocked(get).mock.calls.map(([key]) => key)).not.toContain(
      'ourhike:nearby-trails',
    )
    expect(assets.every((asset) => !asset.present)).toBe(true)
  })

  it('covers every id the window can label, in both directions', async () => {
    // What the lengths below cannot do. A count holds the list complete only
    // against a change that also edits the count; `network-overview` was
    // stored and rowless for a release with these tests green.
    const assets = await storedTrailData()

    expect(new Set(assets.map((asset) => asset.id))).toEqual(
      new Set(Object.keys(TRAIL_DATA_LABEL)),
    )
  })

  it('reports the whole list on an empty phone, each row a stated absence', async () => {
    const assets = await storedTrailData()

    expect(assets).toHaveLength(Object.keys(TRAIL_DATA_LABEL).length)
    for (const asset of assets) {
      expect(asset.present).toBe(false)
      expect(asset.bytes).toBe(null)
    }
  })

  it('treats an unreadable store as an empty one rather than throwing', async () => {
    vi.mocked(get).mockRejectedValue(new Error('not today'))

    const assets = await storedTrailData()

    expect(assets).toHaveLength(Object.keys(TRAIL_DATA_LABEL).length)
    expect(assets.every((asset) => !asset.present)).toBe(true)
  })

  it('shape-checks the sketch record, because every past version of that module wrote it', async () => {
    store({ [NETWORK_OVERVIEW_STORE_KEY]: { bytes: 'not a blob', hash: 'h' } })

    const assets = await storedTrailData()

    const overview = assets.find((asset) => asset.id === 'network-overview')
    expect(overview).toEqual({
      id: 'network-overview',
      bytes: null,
      count: null,
      present: false,
    })
  })
})
