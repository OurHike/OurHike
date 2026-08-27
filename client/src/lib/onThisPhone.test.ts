// The trail-data account (#1103): every figure measured off the store, every
// absence stated, and an unreadable store answering like an empty one. The
// list's contract is completeness - all four artifacts, present or not - so
// the window can never quietly forget one.

import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
}))

const { get } = await import('idb-keyval')
const { storedTrailData } = await import('./onThisPhone')
const { TRAILS_BLOB_KEY, POIS_KEY, ELEVATION_STORE_KEY } = await import('./trailData')
const { NEARBY_TRAILS_STORE_KEY } = await import('./nearbyTrailData')

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
    })

    const assets = await storedTrailData()

    expect(assets).toEqual([
      { id: 'trail-line', bytes: 1234, count: null, present: true },
      { id: 'waypoints', bytes: null, count: 3, present: true },
      { id: 'elevation', bytes: null, count: 4, present: true },
      { id: 'nearby-trails', bytes: 999, count: null, present: true },
    ])
  })

  it('reports the whole list on an empty phone, each row a stated absence', async () => {
    const assets = await storedTrailData()

    expect(assets).toHaveLength(4)
    for (const asset of assets) {
      expect(asset.present).toBe(false)
      expect(asset.bytes).toBe(null)
    }
  })

  it('treats an unreadable store as an empty one rather than throwing', async () => {
    vi.mocked(get).mockRejectedValue(new Error('not today'))

    const assets = await storedTrailData()

    expect(assets).toHaveLength(4)
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
