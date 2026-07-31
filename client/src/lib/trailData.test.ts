import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { get, set, del } from 'idb-keyval'
import {
  downloadTrailData,
  loadTrailData,
  deleteTrailData,
  POIS_KEY,
  TRAILS_BLOB_KEY,
  type StoredPoi,
} from './trailData'
import { POI_TYPES } from './config'

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))

const store = new Map<string, unknown>()

function poiCollection(features: Array<Record<string, unknown>>) {
  return JSON.stringify({
    type: 'FeatureCollection',
    features: features.map((properties) => ({ type: 'Feature', properties })),
  })
}

beforeEach(() => {
  store.clear()
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
  vi.mocked(del).mockImplementation((key) => {
    store.delete(key as string)
    return Promise.resolve()
  })
})

afterEach(() => {
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

/** Serves trail lines for any trails URL and the given POIs for the rest. */
function serve(pois: string = poiCollection([])) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        blob: () => Promise.resolve(new Blob(['{"type":"FeatureCollection"}'])),
        text: () => Promise.resolve(url.includes('poi_') ? pois : '{}'),
      }),
    ),
  )
}

describe('trail data', () => {
  it('stores the trail lines and every POI type', async () => {
    serve()
    await downloadTrailData()

    expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob)
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(POI_TYPES.length + 1)
  })

  it('reads POIs into the shape the map and search both use', async () => {
    serve(
      poiCollection([
        {
          id: 'atc_shelters:abc',
          poi_type: 'shelter',
          name: 'Chairback Gap Lean-to',
          lat: 45.45,
          lon: -69.26,
          confidence: 'high',
        },
      ]),
    )
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0]).toEqual({
      id: 'atc_shelters:abc',
      type: 'shelter',
      name: 'Chairback Gap Lean-to',
      lat: 45.45,
      lon: -69.26,
      confidence: 'high',
    })
  })

  it('drops a POI with no coordinates rather than carrying a broken row', async () => {
    // It cannot be drawn, found by search, or reported against - so it is not
    // a POI, it is a row that would fail somewhere further downstream.
    serve(poiCollection([{ id: 'x', poi_type: 'water', name: 'Nowhere' }]))
    await downloadTrailData()

    expect(store.get(POIS_KEY)).toEqual([])
  })

  it('treats a missing confidence as unverified rather than vouching for it', async () => {
    // The legend renders low confidence as "Unverified". Defaulting the other
    // way would have the app vouching for a water source nobody checked.
    serve(poiCollection([{ id: 'x', poi_type: 'water', name: 'Spring', lat: 1, lon: 2 }]))
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0].confidence).toBe('low')
  })

  it('reports which file failed instead of failing anonymously', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: false, status: 404, statusText: 'Not Found' })),
    )

    await expect(downloadTrailData()).rejects.toThrow(/trails\.geojson.*404/)
  })

  it('says there is nothing downloaded rather than returning an empty map', async () => {
    expect(await loadTrailData()).toBeNull()
  })

  it('reclaims both the trail lines and the POIs on delete', async () => {
    serve()
    await downloadTrailData()
    await deleteTrailData()

    expect(await loadTrailData()).toBeNull()
    expect(store.has(POIS_KEY)).toBe(false)
  })
})
