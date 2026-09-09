import { describe, it, expect, vi, beforeEach } from 'vitest'
import { del, get, set } from 'idb-keyval'
import {
  DEFAULT_PLACE_KEY,
  DEFAULT_PLACE_ZOOM,
  clearDefaultPlace,
  defaultPlaceCamera,
  loadDefaultPlace,
  normaliseDefaultPlace,
  saveDefaultPlace,
  type DefaultPlace,
} from './defaultPlace'
import { PREFERENCE_KEYS } from './userPreferences'

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))

const store = new Map<string, unknown>()

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

const HARRIMAN: DefaultPlace = {
  id: 'oprhp_park_polygons:1',
  name: 'Harriman State Park',
  kind: 'park',
  lon: -74.1,
  lat: 41.25,
  state: 'NY',
  bbox: [-74.2, 41.2, -74.0, 41.3],
}

describe('defaultPlace', () => {
  it('is absent on a phone that has never said where its hiker hikes', async () => {
    expect(await loadDefaultPlace()).toBeNull()
  })

  it('round-trips the snapshot, and clears', async () => {
    await saveDefaultPlace(HARRIMAN)
    expect(await loadDefaultPlace()).toEqual(HARRIMAN)

    await clearDefaultPlace()
    expect(await loadDefaultPlace()).toBeNull()
  })

  it('treats a stored value short of a named point as absent rather than trusting it', () => {
    expect(normaliseDefaultPlace({ ...HARRIMAN, lon: Number.NaN })).toBeNull()
    expect(normaliseDefaultPlace({ ...HARRIMAN, lat: 95 })).toBeNull()
    expect(normaliseDefaultPlace({ ...HARRIMAN, name: '' })).toBeNull()
    expect(normaliseDefaultPlace('Harriman')).toBeNull()
    expect(normaliseDefaultPlace({ ...HARRIMAN, bbox: [1, 2, 3] })?.bbox).toBeUndefined()
  })

  it('never joins the synced preferences blob - a location stays on the phone', () => {
    // The permission step promises location is read on this phone and never
    // sent anywhere. The key is its own store, like lib/hikerMode.ts's, and
    // the blob's own key list must not grow a field for it.
    expect(DEFAULT_PLACE_KEY).not.toBe('ourhike:preferences')
    // `location_permission_requested` is a legitimate synced key - whether the
    // question was asked - and is not a location; what must never appear is a
    // key holding one.
    expect(
      PREFERENCE_KEYS.some((key: string) =>
        /default_(place|location)|home_(place|location)/.test(key),
      ),
    ).toBe(false)
  })

  it('opens a map on the place’s box when it has one, else its point at a planning zoom', () => {
    expect(defaultPlaceCamera(HARRIMAN)).toEqual({ bounds: HARRIMAN.bbox })
    expect(defaultPlaceCamera({ ...HARRIMAN, bbox: undefined })).toEqual({
      center: [-74.1, 41.25],
      zoom: DEFAULT_PLACE_ZOOM,
    })
  })
})
