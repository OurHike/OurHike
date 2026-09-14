import { describe, it, expect } from 'vitest'
import {
  NO_PLACES,
  PLACE_MATCH_LIMIT,
  placeKindLabel,
  searchPlaces,
  validatePlace,
  validatePlaces,
  type Place,
} from './places'

const PARK: Place = {
  id: 'oprhp_park_polygons:1',
  name: 'Harriman State Park',
  kind: 'park',
  lon: -74.1,
  lat: 41.25,
}

describe('validatePlaces', () => {
  it('keeps every row that carries an id, a name, a kind and a point, and drops the rest', () => {
    const document = validatePlaces({
      generated_at: '2026-09-10T12:00:00Z',
      trailRadiusMiles: 5,
      trailMilesMeasured: true,
      places: [
        {
          ...PARK,
          trailMiles: 46.3,
          bbox: [-74.2, 41.2, -74.0, 41.3],
          category: 'State Park',
        },
        { id: 'x', name: 'No kind', kind: 'ridge', lon: 0, lat: 0 },
        { id: 'y', name: '', kind: 'town', lon: 0, lat: 0 },
        { id: 'z', name: 'Off the planet', kind: 'town', lon: 400, lat: 0 },
        'junk',
      ],
    })

    expect(document.places).toHaveLength(1)
    expect(document.places[0]).toMatchObject({
      name: 'Harriman State Park',
      trailMiles: 46.3,
      bbox: [-74.2, 41.2, -74.0, 41.3],
      category: 'State Park',
    })
    expect(document.trailRadiusMiles).toBe(5)
    expect(document.trailMilesMeasured).toBe(true)
    expect(document.generatedAt).toBe('2026-09-10T12:00:00Z')
  })

  it('reads a document with nothing measured as unknown, never zero', () => {
    const document = validatePlaces({ places: [PARK] })

    expect(document.trailMilesMeasured).toBe(false)
    expect(document.places[0].trailMiles).toBeUndefined()
  })

  it('reads junk as no places at all', () => {
    expect(validatePlaces(null)).toBe(NO_PLACES)
    expect(validatePlaces('nope')).toBe(NO_PLACES)
    expect(validatePlaces({ places: 'nope' }).places).toEqual([])
  })

  it('drops a bbox that is not four finite numbers in order rather than fitting a map to it', () => {
    expect(validatePlace({ ...PARK, bbox: [1, 2, 0, 3] })?.bbox).toBeUndefined()
    expect(validatePlace({ ...PARK, bbox: ['a', 2, 3, 4] })?.bbox).toBeUndefined()
    expect(validatePlace({ ...PARK, bbox: [-74.2, 41.2, -74.0, 41.3] })?.bbox).toEqual([
      -74.2, 41.2, -74.0, 41.3,
    ])
  })
})

describe('searchPlaces', () => {
  const PLACES: Place[] = [
    PARK,
    {
      id: 't1',
      name: 'Reeves Meadow Visitor Center',
      kind: 'trailhead',
      lon: -74.1,
      lat: 41.2,
    },
    { id: 'p1', name: 'Harriman parking', kind: 'parking', lon: -74.1, lat: 41.2 },
    { id: 'c1', name: 'Harriman', kind: 'town', lon: -84.5, lat: 35.9, state: 'TN' },
    { id: 'lp', name: 'Long Path', kind: 'trail', lon: -74, lat: 41.5 },
  ]

  it('matches anywhere in the name and puts an earlier match first', () => {
    expect(searchPlaces(PLACES, 'meadow').map((p) => p.id)).toEqual(['t1'])
    expect(searchPlaces(PLACES, 'harriman').map((p) => p.id)).toEqual([
      'oprhp_park_polygons:1',
      'c1',
      'p1',
    ])
  })

  it('offers a park or a town before a lot at the same match, and nothing for no query', () => {
    expect(searchPlaces(PLACES, 'harr')[0].kind).toBe('park')
    expect(searchPlaces(PLACES, '   ')).toEqual([])
  })

  it('caps the list at what fits under the field', () => {
    const many = Array.from({ length: 20 }, (_, i) => ({
      ...PARK,
      id: `p${i}`,
      name: `Park ${i}`,
    }))

    expect(searchPlaces(many, 'park')).toHaveLength(PLACE_MATCH_LIMIT)
  })
})

describe('placeKindLabel', () => {
  it('prints the publisher’s own category where one was published, else the kind', () => {
    expect(placeKindLabel({ ...PARK, category: 'State Park' })).toBe('State Park')
    expect(placeKindLabel(PARK)).toBe('park')
  })
})
