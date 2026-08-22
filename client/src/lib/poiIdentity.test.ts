import { describe, it, expect } from 'vitest'

import {
  NO_TOMBSTONES,
  drawableType,
  parseTombstones,
  resolvePoiId,
  tombstoneFor,
} from './poiIdentity'
import { POI_TYPES } from './config'

// Reading the published tombstones (#831). The RESOLVER's behaviour is pinned
// against the pipeline's own cases in poiIdentity.contract.test.ts; what is
// tested here is everything that is this runtime's alone — parsing an artifact
// off a network, and the one question the pipeline never has to ask, which is
// whether an id it has never heard of is live or unknown.

function feature(properties: Record<string, unknown>) {
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [-74, 41] },
    properties,
  }
}

function collection(...features: unknown[]) {
  return { type: 'FeatureCollection', features }
}

const GONE = {
  id: 'atc_csi:gone',
  poi_type: 'water',
  source: 'atc_csi',
  retired: '2026-08-19',
  name: 'Water near Punchbowl Shelter',
}

describe('reading the artifact', () => {
  it('keeps every field the card is built from', () => {
    const stones = parseTombstones(
      collection(feature({ ...GONE, superseded_by: 'atc_csi:here' })),
    )

    expect(stones['atc_csi:gone']).toEqual({
      id: 'atc_csi:gone',
      poiType: 'water',
      source: 'atc_csi',
      retired: '2026-08-19',
      lon: -74,
      lat: 41,
      name: 'Water near Punchbowl Shelter',
      supersededBy: 'atc_csi:here',
    })
  })

  it('leaves an absent successor absent rather than nulling it', () => {
    // Absent means "nothing took this place's place", which is a different
    // sentence on the card from "we do not know". Every one of the 93 real
    // tombstones is this case today.
    const stones = parseTombstones(collection(feature(GONE)))

    expect('supersededBy' in stones['atc_csi:gone']).toBe(false)
  })

  it('leaves an unnamed place unnamed', () => {
    const { name: _name, ...unnamed } = GONE
    const stones = parseTombstones(collection(feature(unnamed)))

    expect('name' in stones['atc_csi:gone']).toBe(false)
  })

  it('drops a feature that cannot say who dropped the place', () => {
    // Without `source` the card cannot write its sentence, and #831 is
    // explicit that it must not fall back to "ATC" — two of the two sources
    // producing real tombstones today are not interchangeable.
    const { source: _source, ...sourceless } = GONE

    expect(parseTombstones(collection(feature(sourceless)))).toEqual({})
  })

  it('keeps where the place was, so the card can say', () => {
    // The design lists "last position" among a tombstone's fields, and it
    // rides in the geometry rather than the properties — which is what makes
    // the artifact a FeatureCollection a map can draw.
    const stones = parseTombstones(collection(feature(GONE)))

    expect(stones['atc_csi:gone'].lon).toBe(-74)
    expect(stones['atc_csi:gone'].lat).toBe(41)
  })

  it('drops a feature with no position rather than placing it at null island', () => {
    // 0,0 is in the Gulf of Guinea. A card claiming a shelter used to be
    // there is worse than no card, which is what a hiker gets today anyway.
    const stones = parseTombstones({
      type: 'FeatureCollection',
      features: [{ type: 'Feature', geometry: null, properties: GONE }],
    })

    expect(stones).toEqual({})
  })

  it('drops a malformed feature and keeps the rest', () => {
    // Lenient in one direction only: this artifact is a courtesy on top of a
    // working map, and a phone that cannot parse it should lose the
    // tombstone cards rather than the download it arrived in.
    const stones = parseTombstones(
      collection(feature({ poi_type: 'water' }), feature(GONE)),
    )

    expect(Object.keys(stones)).toEqual(['atc_csi:gone'])
  })

  it('reads a release that has retired nothing as nothing', () => {
    expect(parseTombstones(collection())).toEqual({})
  })

  it('reads rubbish as nothing rather than throwing', () => {
    expect(parseTombstones(null)).toEqual(NO_TOMBSTONES)
    expect(parseTombstones('a 404 body')).toEqual(NO_TOMBSTONES)
    expect(parseTombstones({ features: 'not an array' })).toEqual(NO_TOMBSTONES)
  })
})

describe('live, retired, or never heard of', () => {
  const stones = parseTombstones(collection(feature(GONE)))
  const live = (id: string) => id === 'atc_shelters:live'

  it('tells an unknown id from a live one, which the tombstones alone cannot', () => {
    // The reason `resolvePoiId` takes a predicate at all. A phone holds the
    // live rows as `poi_*.geojson` and the retired ones as the tombstones;
    // neither file alone can answer this, and the two answers differ.
    expect(resolvePoiId(stones, 'atc_shelters:live', live)).toBe('atc_shelters:live')
    expect(resolvePoiId(stones, 'atc_shelters:who', live)).toBeNull()
  })

  it('hands back the tombstone for a retired id', () => {
    expect(tombstoneFor(stones, 'atc_csi:gone')?.name).toBe(
      'Water near Punchbowl Shelter',
    )
    expect(tombstoneFor(stones, 'atc_shelters:live')).toBeUndefined()
  })
})

describe('drawing a tombstone', () => {
  it('narrows to a type the client actually has an icon for', () => {
    const stones = parseTombstones(collection(feature(GONE)))

    expect(drawableType(stones['atc_csi:gone'], POI_TYPES)).toBe('water')
  })

  it('gives back nothing for a type this build does not draw', () => {
    // The artifact carries the pipeline's vocabulary and the client draws a
    // subset of it. A cast would produce a React key matching no icon; this
    // lets the card fall back to a neutral treatment instead.
    const stones = parseTombstones(collection(feature({ ...GONE, poi_type: 'ferry' })))

    expect(drawableType(stones['atc_csi:gone'], POI_TYPES)).toBeUndefined()
  })
})
