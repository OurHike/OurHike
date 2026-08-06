import { describe, it, expect, beforeEach } from 'vitest'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import type { Closure } from '../lib/closureBanner'
import type { TrailIndex } from '../lib/trailPosition'
import {
  attachClosureData,
  closureFeatureCollection,
  CLOSURE_ID_PROPERTY,
  CLOSURE_SOURCE_ID,
} from './closureLayers'

// The behaviour under test is "a closure's mile range becomes a band along
// the trail, and only along the trail" - the backend sends two mile markers
// and no geometry at all, so everything the map draws comes from this
// placement.

/**
 * A hand-built index rather than one from buildTrailIndex, so each vertex's
 * mile is exact and a part seam (two vertices at the SAME mile - the second
 * added no distance) can be placed deliberately.
 */
function index(vertices: Array<[number, number, number]>): TrailIndex {
  return {
    lons: Float64Array.from(vertices.map(([lon]) => lon)),
    lats: Float64Array.from(vertices.map(([, lat]) => lat)),
    miles: Float64Array.from(vertices.map(([, , mile]) => mile)),
    buckets: new Map(),
    totalMiles: vertices.length === 0 ? 0 : vertices[vertices.length - 1][2],
  }
}

function closure(partial: Partial<Closure>): Closure {
  return {
    id: 'closure-1',
    reason_type: 'storm_damage',
    note: null,
    status: 'closed',
    start_mile_marker: 1,
    end_mile_marker: 3,
    ...partial,
  }
}

/** Ten vertices, a mile apart, along a recognisable diagonal. */
const STRAIGHT = index(
  Array.from({ length: 10 }, (_, i) => [-84 + i * 0.01, 34 + i * 0.01, i]),
)

beforeEach(() => {
  resetMapLibreMock()
})

describe('closureFeatureCollection', () => {
  it('draws the vertices between the mile markers, and nothing outside them', () => {
    const fc = closureFeatureCollection([closure({})], STRAIGHT)

    expect(fc.features).toHaveLength(1)
    expect(fc.features[0].geometry.coordinates).toEqual([
      [-83.99, 34.01],
      [-83.98, 34.02],
      [-83.97, 34.03],
    ])
  })

  it('labels the band with its closure id, so a tap can find the sheet', () => {
    const fc = closureFeatureCollection([closure({ id: 'c-42' })], STRAIGHT)

    expect(fc.features[0].properties[CLOSURE_ID_PROPERTY]).toBe('c-42')
  })

  it('normalises a range whose markers arrive reversed', () => {
    // A SOBO-minded closure report can put the higher mile first; the ground
    // it closes is the same either way.
    const fc = closureFeatureCollection(
      [closure({ start_mile_marker: 3, end_mile_marker: 1 })],
      STRAIGHT,
    )

    expect(fc.features[0].geometry.coordinates).toHaveLength(3)
  })

  it('draws nothing for a reopened closure', () => {
    // status 'open' means the trail is walkable again. A barrier over
    // walkable trail is the false alarm this feature cannot afford.
    const fc = closureFeatureCollection([closure({ status: 'open' })], STRAIGHT)

    expect(fc.features).toHaveLength(0)
  })

  it('still bars a closure with a reroute - the trail itself is not passable', () => {
    const fc = closureFeatureCollection(
      [closure({ status: 'reroute_available' })],
      STRAIGHT,
    )

    expect(fc.features).toHaveLength(1)
  })

  it('splits the band at a survey seam rather than drawing across the gap', () => {
    // Two vertices at the same mile are the end of one surveyed piece and
    // the start of the next: buildTrailIndex counted no distance between
    // them, because the straight line between them is not trail. A single
    // LineString would draw a bar across ground the trail never touches.
    const seamed = index([
      [-84.0, 34.0, 0],
      [-83.99, 34.01, 1],
      [-83.98, 34.02, 2],
      // The seam: a new piece starts somewhere else, at the same mile.
      [-83.9, 34.1, 2],
      [-83.89, 34.11, 3],
      [-83.88, 34.12, 4],
    ])

    const fc = closureFeatureCollection(
      [closure({ start_mile_marker: 0, end_mile_marker: 4 })],
      seamed,
    )

    expect(fc.features).toHaveLength(2)
    expect(fc.features[0].geometry.coordinates).toEqual([
      [-84.0, 34.0],
      [-83.99, 34.01],
      [-83.98, 34.02],
    ])
    expect(fc.features[1].geometry.coordinates).toEqual([
      [-83.9, 34.1],
      [-83.89, 34.11],
      [-83.88, 34.12],
    ])
  })

  it('drops a range too short to reach two vertices rather than inventing a line', () => {
    const fc = closureFeatureCollection(
      [closure({ start_mile_marker: 1.2, end_mile_marker: 1.8 })],
      STRAIGHT,
    )

    expect(fc.features).toHaveLength(0)
  })

  it('draws nothing with no centerline index to place a mile range on', () => {
    const fc = closureFeatureCollection([closure({})], null)

    expect(fc.features).toHaveLength(0)
  })

  it('keeps each closure its own feature set', () => {
    const fc = closureFeatureCollection(
      [
        closure({ id: 'a', start_mile_marker: 0, end_mile_marker: 2 }),
        closure({ id: 'b', start_mile_marker: 5, end_mile_marker: 7 }),
      ],
      STRAIGHT,
    )

    expect(fc.features.map((feature) => feature.properties[CLOSURE_ID_PROPERTY])).toEqual(
      ['a', 'b'],
    )
  })
})

describe('attachClosureData', () => {
  it('pushes the bands into the closure source', () => {
    const map = new MockMap({})
    map.sourceIds = [CLOSURE_SOURCE_ID]

    attachClosureData(map as unknown as MapLibreMap, [closure({})], STRAIGHT)

    const pushed = map.sourceData.get(CLOSURE_SOURCE_ID) as ReturnType<
      typeof closureFeatureCollection
    >
    expect(pushed.features).toHaveLength(1)
  })

  it('waits for the source rather than dropping the write', () => {
    // The same landing-during-style-load story styleReady.ts exists for: the
    // closures arrive from the network on their own clock.
    const map = new MockMap({})

    attachClosureData(map as unknown as MapLibreMap, [closure({})], STRAIGHT)
    expect(map.sourceData.get(CLOSURE_SOURCE_ID)).toBeUndefined()

    map.sourceIds = [CLOSURE_SOURCE_ID]
    map.emit('styledata')

    expect(map.sourceData.get(CLOSURE_SOURCE_ID)).toBeDefined()
  })
})
