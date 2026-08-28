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
}))

const { get } = await import('idb-keyval')
const { storedTrailData } = await import('./onThisPhone')
const { TRAILS_BLOB_KEY, POIS_KEY, ELEVATION_STORE_KEY } = await import('./trailData')
const { NEARBY_TRAILS_STORE_KEY, NETWORK_OVERVIEW_STORE_KEY } =
  await import('./nearbyTrailData')
const { TRAIL_DATA_LABEL } = await import('../screens/Downloads')

beforeEach(() => {
  vi.mocked(get).mockReset()
  vi.mocked(get).mockResolvedValue(undefined)
})

/** Answers per key, everything else absent. */
function store(values: Record<string, unknown>): void {
  vi.mocked(get).mockImplementation((key) => Promise.resolve(values[String(key)]))
}

describe('storedTrailData', () => {
  it('measures what the store actually holds - bytes for blobs, counts for records', async () => {
    store({
      [TRAILS_BLOB_KEY]: new Blob(['x'.repeat(1234)]),
      [POIS_KEY]: [{ id: 'a' }, { id: 'b' }, { id: 'c' }],
      [ELEVATION_STORE_KEY]: { samples: [1, 2, 3, 4] },
      [NEARBY_TRAILS_STORE_KEY]: { bytes: new Blob(['y'.repeat(999)]), hash: 'h' },
      // Two of the four graph artifacts, which is a real state: the routing
      // half arrives at launch and the geometry only when a builder opens.
      // They sum into one row - see storedTrailData for why.
      'ourhike:trail-graph': { bytes: new Blob(['g'.repeat(500)]), hash: 'g' },
      'ourhike:trail-graph-geometry': { bytes: new Blob(['v'.repeat(200)]), hash: 'v' },
      [NETWORK_OVERVIEW_STORE_KEY]: { bytes: new Blob(['o'.repeat(321)]), hash: 'o' },
    })

    const assets = await storedTrailData()

    expect(assets).toEqual([
      { id: 'trail-line', bytes: 1234, count: null, present: true },
      { id: 'waypoints', bytes: null, count: 3, present: true },
      { id: 'elevation', bytes: null, count: 4, present: true },
      { id: 'day-hike-routing', bytes: 700, count: null, present: true },
      { id: 'nearby-trails', bytes: 999, count: null, present: true },
      { id: 'network-overview', bytes: 321, count: null, present: true },
    ])
  })

  it('counts the corridor-view sketch as its own row, not folded into the network', async () => {
    // The two nearby-network artifacts draw at different zooms, so losing
    // only the sketch is a distinguishable thing to be missing: the map opens
    // A.T.-only and the detail arrives as you zoom in. A hiker checking what
    // is on the phone can only see that if it has a line of its own.
    store({
      [NEARBY_TRAILS_STORE_KEY]: { bytes: new Blob(['y'.repeat(999)]), hash: 'h' },
    })

    const assets = await storedTrailData()

    expect(assets.find((asset) => asset.id === 'nearby-trails')?.present).toBe(true)
    expect(assets.find((asset) => asset.id === 'network-overview')).toEqual({
      id: 'network-overview',
      bytes: null,
      count: null,
      present: false,
    })
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

  it('shape-checks the nearby record, because every past version of that module wrote it', async () => {
    store({ [NEARBY_TRAILS_STORE_KEY]: { bytes: 'not a blob', hash: 'h' } })

    const assets = await storedTrailData()

    const nearby = assets.find((asset) => asset.id === 'nearby-trails')
    expect(nearby).toEqual({
      id: 'nearby-trails',
      bytes: null,
      count: null,
      present: false,
    })
  })
})
