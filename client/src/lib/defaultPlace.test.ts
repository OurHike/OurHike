import { describe, it, expect } from 'vitest'
import {
  DEFAULT_PLACE_ZOOM,
  defaultPlaceCamera,
  normaliseDefaultPlace,
  type DefaultPlace,
} from './defaultPlace'
import { DEFAULT_PREFERENCES, PREFERENCE_KEYS } from './userPreferences'
import { normalisePreferences } from './preferences'

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
  it('is absent on a phone that has never said where its hiker hikes', () => {
    expect(DEFAULT_PREFERENCES.default_place).toBeNull()
    expect(normalisePreferences({}).default_place).toBeNull()
  })

  it('rides the preferences blob, made safe the way the rest of it is', () => {
    expect(normalisePreferences({ default_place: HARRIMAN }).default_place).toEqual(
      HARRIMAN,
    )
    // The server sends the optional fields it did not get as null; the
    // snapshot reads them as absent.
    expect(
      normalisePreferences({
        default_place: { ...HARRIMAN, within: null, category: null } as never,
      }).default_place,
    ).toEqual(HARRIMAN)
    expect(
      normalisePreferences({ default_place: { ...HARRIMAN, lat: 95 } }).default_place,
    ).toBeNull()
  })

  it('treats a stored value short of a named point as absent rather than trusting it', () => {
    expect(normaliseDefaultPlace({ ...HARRIMAN, lon: Number.NaN })).toBeNull()
    expect(normaliseDefaultPlace({ ...HARRIMAN, lat: 95 })).toBeNull()
    expect(normaliseDefaultPlace({ ...HARRIMAN, name: '' })).toBeNull()
    expect(normaliseDefaultPlace('Harriman')).toBeNull()
    expect(normaliseDefaultPlace({ ...HARRIMAN, bbox: [1, 2, 3] })?.bbox).toBeUndefined()
  })

  it('is a synced preference - a place named, never a fix', () => {
    // The first draft kept it on the phone under its own key, reading the
    // permission card's "location is read on this phone and never sent
    // anywhere" as covering it. The maintainer decided otherwise
    // (2026-09-10, #1374): that promise is about GPS fixes, and a park chosen
    // by name from a published index is not one. So it syncs, and a second
    // device opens on it.
    expect(PREFERENCE_KEYS).toContain('default_place')
    // What must never appear on the blob is a fix: a key holding where
    // somebody is standing rather than where they said they walk.
    expect(
      PREFERENCE_KEYS.some((key: string) => /fix|position|last_seen|gps/.test(key)),
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
