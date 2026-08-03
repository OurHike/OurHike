import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { get, set, del } from 'idb-keyval'
import {
  downloadTrailData,
  loadTrailData,
  deleteTrailData,
  ELEVATION_STORE_KEY,
  POIS_KEY,
  SPURS_STORE_KEY,
  TRAILS_BLOB_KEY,
  type StoredPoi,
} from './trailData'
import { ELEVATION_KEY, POI_TYPES, SPURS_KEY } from './config'
import type { ElevationProfile } from './elevationProfile'

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

/** Serves trail lines for any trails URL, the given POIs for poi_*, the given
 *  spur detail for spurs.json and the given samples for
 *  elevation_profile.json. The elevation default is an empty array, which is
 *  "this release publishes no usable profile" - the tests that care about one
 *  pass their own. */
function serve(
  pois: string = poiCollection([]),
  spurs: string = '{}',
  elevation: string = '[]',
) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        status: 200,
        blob: () => Promise.resolve(new Blob(['{"type":"FeatureCollection"}'])),
        text: () =>
          Promise.resolve(
            url.includes('poi_')
              ? pois
              : url.includes(SPURS_KEY)
                ? spurs
                : url.includes(ELEVATION_KEY)
                  ? elevation
                  : '{}',
          ),
      }),
    ),
  )
}

/** Serves everything but elevation_profile.json, which gets the given failure. */
function serveUntilElevationFails(status: number, statusText: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      Promise.resolve(
        url.includes(ELEVATION_KEY)
          ? { ok: false, status, statusText }
          : {
              ok: true,
              status: 200,
              blob: () => Promise.resolve(new Blob(['{"type":"FeatureCollection"}'])),
              text: () => Promise.resolve(poiCollection([])),
            },
      ),
    ),
  )
}

const TWO_SAMPLES = JSON.stringify([
  { distance_mi: 0, elevation_ft: 3782.2 },
  { distance_mi: 1, elevation_ft: 3000 },
])

/** Serves trail lines, then fails on the POI type named. */
function serveUntilPoiFails(failing: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      Promise.resolve(
        url.includes(`poi_${failing}`)
          ? { ok: false, status: 503, statusText: 'Service Unavailable' }
          : {
              ok: true,
              blob: () => Promise.resolve(new Blob(['{"type":"FeatureCollection"}'])),
              text: () => Promise.resolve(poiCollection([])),
            },
      ),
    ),
  )
}

describe('trail data', () => {
  it('stores the trail lines and every POI type', async () => {
    serve()
    await downloadTrailData()

    expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob)
    // Every POI type, plus the trail lines, plus the spur detail, plus the
    // elevation profile.
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(POI_TYPES.length + 3)
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

  it('stores nothing at all when a POI fetch fails partway', async () => {
    // The bug: the trail lines were committed the moment they arrived, so
    // signal dropping during the POI fetches - the ordinary way this fails,
    // not an edge case - left new trail lines behind with no POIs. That state
    // is invisible on the next launch: the map draws its trail, and search and
    // the legend are just empty, with the error long gone from React state.
    serveUntilPoiFails('campsite')

    await expect(downloadTrailData()).rejects.toThrow(/poi_campsite/)

    expect(store.has(TRAILS_BLOB_KEY)).toBe(false)
    expect(store.has(POIS_KEY)).toBe(false)
  })

  it('leaves a working download alone when a re-download fails partway', async () => {
    // Worse than an empty store: someone who already had the whole set and
    // re-downloaded got the new trail lines written over the old ones while
    // their POIs stayed at the previous version - two halves of different
    // downloads, with nothing saying so.
    serve(
      poiCollection([{ id: 'a', poi_type: 'water', name: 'Spring', lat: 39, lon: -77 }]),
    )
    await downloadTrailData()
    const originalTrails = store.get(TRAILS_BLOB_KEY)
    const originalPois = store.get(POIS_KEY)

    serveUntilPoiFails('resupply')
    await expect(downloadTrailData()).rejects.toThrow(/poi_resupply/)

    expect(store.get(TRAILS_BLOB_KEY)).toBe(originalTrails)
    expect(store.get(POIS_KEY)).toBe(originalPois)
  })

  // Everything below is one POI row being wrong in a file where the other rows
  // are fine. Dropping the whole download over one bad shelter would cost a
  // hiker every other shelter in the file.
  it('drops a POI with no usable coordinates rather than carrying a broken row', async () => {
    // Nothing can be done with it: it cannot be drawn, found by search, or
    // reported against.
    serve(
      poiCollection([
        { id: 'a', name: 'No position', lat: 'not a number', lon: -77 },
        { id: 'b', name: 'Fine', lat: 39, lon: -77 },
        { id: 'c', name: 'Missing lon', lat: 39 },
      ]),
    )
    await downloadTrailData()

    // serve() hands the same file to every POI type, so the one good row
    // arrives once per type - what matters is that only it survived.
    const pois = (await loadTrailData())?.pois ?? []
    expect([...new Set(pois.map((p) => p.id))]).toEqual(['b'])
    expect(pois).toHaveLength(POI_TYPES.length)
  })

  it('falls back to the file it came from when a row does not name its own type', async () => {
    serve(poiCollection([{ id: 'a', name: 'Unnamed type', lat: 39, lon: -77 }]))
    await downloadTrailData()

    const pois = (await loadTrailData())?.pois ?? []
    expect(pois[0].type).toBe(POI_TYPES[0])
  })

  it('ignores a poi_type that is not a string', async () => {
    serve(poiCollection([{ id: 'a', poi_type: 42, name: 'Odd', lat: 39, lon: -77 }]))
    await downloadTrailData()

    const pois = (await loadTrailData())?.pois ?? []
    expect(pois[0].type).toBe(POI_TYPES[0])
  })

  it('shows a nameless POI as Unnamed rather than as blank or undefined', async () => {
    serve(poiCollection([{ id: 'a', lat: 39, lon: -77 }]))
    await downloadTrailData()

    const pois = (await loadTrailData())?.pois ?? []
    expect(pois[0].name).toBe('Unnamed')
  })

  it('builds an id from the position when the row carries none', async () => {
    // Two POIs sharing a synthetic id would collapse into one in search, so it
    // is derived from something that differs per row.
    serve(poiCollection([{ name: 'Anonymous spring', lat: 39, lon: -77 }]))
    await downloadTrailData()

    const pois = (await loadTrailData())?.pois ?? []
    expect(pois[0].id).toBe(`${POI_TYPES[0]}:39,-77`)
  })

  it('treats a file with no features array at all as simply empty', async () => {
    serve(JSON.stringify({ type: 'FeatureCollection' }))
    await downloadTrailData()

    expect((await loadTrailData())?.pois).toEqual([])
  })

  it('returns no POIs, rather than throwing, when the trail lines are there but the POIs are not', async () => {
    serve()
    await downloadTrailData()
    store.delete(POIS_KEY)

    expect((await loadTrailData())?.pois).toEqual([])
  })

  it('skips a feature carrying no properties at all', async () => {
    // GeoJSON allows `properties: null`, and a feature with nothing on it has
    // no coordinates either - so it drops out rather than throwing on the way
    // to reading them.
    serve(
      JSON.stringify({
        type: 'FeatureCollection',
        features: [
          { type: 'Feature', geometry: null },
          { type: 'Feature', properties: null, geometry: null },
          { type: 'Feature', properties: { id: 'ok', name: 'Real', lat: 39, lon: -77 } },
        ],
      }),
    )
    await downloadTrailData()

    const pois = (await loadTrailData())?.pois ?? []
    expect([...new Set(pois.map((p) => p.id))]).toEqual(['ok'])
  })
})

describe('spur detail', () => {
  it('stores what each spur leads to, keyed by trail id', async () => {
    serve(
      poiCollection([]),
      JSON.stringify({ 'side_trails:abc': { destination_poi_id: 'shelter:x' } }),
    )

    await downloadTrailData()

    expect(store.get(SPURS_STORE_KEY)).toEqual({
      'side_trails:abc': { destination_poi_id: 'shelter:x' },
    })
  })

  it('treats a release with no spurs.json as no spur detail, not a failure', async () => {
    // spurs.json did not exist before export_spurs.py. A phone pointed at an
    // older release must still get its trails and POIs - the map draws every
    // spur either way, it just cannot say where one goes.
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve(
          url.includes(SPURS_KEY)
            ? { ok: false, status: 404, statusText: 'Not Found' }
            : {
                ok: true,
                status: 200,
                blob: () => Promise.resolve(new Blob(['{"type":"FeatureCollection"}'])),
                text: () => Promise.resolve(poiCollection([])),
              },
        ),
      ),
    )

    await downloadTrailData()

    expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob)
    expect(store.get(SPURS_STORE_KEY)).toEqual({})
  })

  it('still fails on a broken spurs fetch that is not a 404', async () => {
    // Only "this release predates the feature" is excused. A 503 is a failed
    // download and must not be swallowed along with it.
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve(
          url.includes(SPURS_KEY)
            ? { ok: false, status: 503, statusText: 'Service Unavailable' }
            : {
                ok: true,
                status: 200,
                blob: () => Promise.resolve(new Blob(['{"type":"FeatureCollection"}'])),
                text: () => Promise.resolve(poiCollection([])),
              },
        ),
      ),
    )

    await expect(downloadTrailData()).rejects.toThrow(/503/)
    // Nothing committed, same rule the POI failure already follows.
    expect(store.get(TRAILS_BLOB_KEY)).toBeUndefined()
  })

  it('loads spur detail back with the rest of the trail data', async () => {
    serve(poiCollection([]), JSON.stringify({ 'side_trails:abc': { length_ft: 385 } }))
    await downloadTrailData()

    const loaded = await loadTrailData()

    expect(loaded?.spurs['side_trails:abc']).toEqual({ length_ft: 385 })
  })

  it('reads a release whose spur detail was never stored as an empty map', async () => {
    // Data downloaded by a build before this feature: the blob and POIs are in
    // IndexedDB, the spur key is not. That must load, not throw.
    store.set(TRAILS_BLOB_KEY, new Blob(['{}']))
    store.set(POIS_KEY, [])

    const loaded = await loadTrailData()

    expect(loaded?.spurs).toEqual({})
  })

  it('forgets spur detail when the download is deleted', async () => {
    serve(poiCollection([]), JSON.stringify({ 'side_trails:abc': {} }))
    await downloadTrailData()

    await deleteTrailData()

    expect(store.has(SPURS_STORE_KEY)).toBe(false)
  })
})

describe('the elevation profile', () => {
  it('stores the published samples', async () => {
    serve(poiCollection([]), '{}', TWO_SAMPLES)

    await downloadTrailData()

    const profile = store.get(ELEVATION_STORE_KEY) as ElevationProfile
    expect(Array.from(profile.distanceMi)).toEqual([0, 1])
    expect(profile.elevationFt[0]).toBeCloseTo(3782.2, 3)
  })

  it('treats a release with no elevation_profile.json as no profile, not a failure', async () => {
    // It did not exist before export_elevation.py. A phone pointed at an older
    // release must still get its trails and POIs; it just has no ribbon.
    serveUntilElevationFails(404, 'Not Found')

    await downloadTrailData()

    expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob)
    expect(store.get(ELEVATION_STORE_KEY)).toBeNull()
  })

  it('still fails on a broken elevation fetch that is not a 404', async () => {
    // Only "this release predates the feature" is excused. A 503 is a failed
    // download and must not be swallowed along with it.
    serveUntilElevationFails(503, 'Service Unavailable')

    await expect(downloadTrailData()).rejects.toThrow(/503/)
    // Nothing committed, the same rule the POI failure already follows.
    expect(store.get(TRAILS_BLOB_KEY)).toBeUndefined()
  })

  it('costs the ribbon and not the map when the profile arrives malformed', async () => {
    // A truncated download of the largest vector artifact. The ribbon is a
    // decoration on a screen whose job is showing a hiker where they are, so it
    // gives itself up rather than taking the trail lines down with it.
    serve(poiCollection([]), '{}', '[{"distance_mi":0,')

    await downloadTrailData()

    expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob)
    expect(store.get(ELEVATION_STORE_KEY)).toBeNull()
  })

  it('loads the profile back with the rest of the trail data', async () => {
    serve(poiCollection([]), '{}', TWO_SAMPLES)
    await downloadTrailData()

    const loaded = await loadTrailData()

    expect(loaded?.elevation?.distanceMi.length).toBe(2)
  })

  it('reads a release whose profile was never stored as no profile', async () => {
    // Data downloaded by a build before this feature: the blob and POIs are in
    // IndexedDB, the elevation key is not. That must load, not throw.
    store.set(TRAILS_BLOB_KEY, new Blob(['{}']))
    store.set(POIS_KEY, [])

    const loaded = await loadTrailData()

    expect(loaded?.elevation).toBeNull()
  })

  it('forgets the profile when the download is deleted', async () => {
    serve(poiCollection([]), '{}', TWO_SAMPLES)
    await downloadTrailData()

    await deleteTrailData()

    expect(store.has(ELEVATION_STORE_KEY)).toBe(false)
  })
})
