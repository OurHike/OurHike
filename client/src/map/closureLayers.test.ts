import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import type { Feature, FeatureCollection } from 'geojson'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { buildTrailIndex } from '../lib/trailPosition'
import type { Closure } from '../lib/closureBanner'
import { MAX_BAND_MILES } from '../lib/closureSpan'
import {
  attachClosureData,
  buildClosureSource,
  closureBands,
  closureFeatureCollection,
  CLOSURE_ID_PROPERTY,
  CLOSURE_SOURCE_ID,
} from './closureLayers'

// The band is the half of a closure warning that survives not knowing which
// way a hiker is walking. lib/closureBanner.ts needs a mile AND a direction
// before it can say anything; this needs neither, so a closure is on the map
// from the moment it is known - including for someone who has not started
// walking, and for someone whose direction tracker has not made up its mind.

const MILE_IN_DEGREES_LAT = 1 / 69.05

function line(coordinates: Array<[number, number]>): Feature {
  return {
    type: 'Feature',
    properties: { source: 'centerline' },
    geometry: { type: 'LineString', coordinates },
  }
}

function collection(features: Feature[]): FeatureCollection {
  return { type: 'FeatureCollection', features }
}

function straightTrail(miles: number) {
  return buildTrailIndex(
    collection([
      line(
        Array.from({ length: miles + 1 }, (_, i): [number, number] => [
          -77,
          39 + i * MILE_IN_DEGREES_LAT,
        ]),
      ),
    ]),
  )
}

/** Ten miles of trail with a vertex every mile, so a mile is an index. */
const INDEX = straightTrail(10)

/**
 * Long enough that a closure over the band ceiling is still PLACEABLE.
 *
 * Needed to tell the ceiling apart from the centerline index simply running
 * out: against `INDEX` a 60-mile closure is dropped either way, and a test that
 * cannot distinguish the two would pass with the ceiling removed.
 */
const LONG_INDEX = straightTrail(120)

function closure(overrides: Partial<Closure> = {}): Closure {
  return {
    id: 'c1',
    reason_type: 'storm_damage',
    note: null,
    status: 'closed',
    start_mile_marker: 2.5,
    end_mile_marker: 5.5,
    ...overrides,
  }
}

describe('closureBands', () => {
  it('turns a mile range into the trail that runs through it', () => {
    const [band] = closureBands([closure()], INDEX)

    expect(band.id).toBe('c1')
    expect(band.lines).toHaveLength(1)
    expect(band.lines[0].length).toBeGreaterThan(1)
  })

  it('draws a reroute, because somewhere else to walk is not a passable trail', () => {
    // The same call lib/closureBanner.ts makes on the same field. A hiker with
    // a detour still must not walk down the closed stretch.
    expect(closureBands([closure({ status: 'reroute_available' })], INDEX)).toHaveLength(
      1,
    )
  })

  it('draws nothing for a closure that has been reopened', () => {
    // A barred red band across a trail somebody has just reopened is the same
    // class of false statement as no band across one that is shut.
    expect(closureBands([closure({ status: 'open' })], INDEX)).toEqual([])
  })

  it('leaves out a closure the centerline index cannot place', () => {
    // Silent on purpose, and safe because the BANNER needs only a mile number:
    // a closure this cannot draw is still one the hiker is told about
    // (App.tsx). Drawing it at a guessed position would be worse than not
    // drawing it.
    const off = closure({ start_mile_marker: 400, end_mile_marker: 402 })

    expect(closureBands([off], INDEX)).toEqual([])
  })

  it('draws nothing for a closure too long to be a band, even where it fits', () => {
    // #462. A 398-mile advisory drawn along the centerline paints a fifth of
    // the trail as closed at every zoom, and buries the nine-mile closure a
    // hiker has to walk around. The hiker still gets it: the banner needs only
    // a mile number.
    //
    // Placed against LONG_INDEX so this is the ceiling talking and not the
    // index running out - the assertion below proves the same index draws a
    // shorter closure happily.
    const broad = closure({
      start_mile_marker: 1,
      end_mile_marker: 1 + MAX_BAND_MILES + 10,
    })

    expect(closureBands([broad], LONG_INDEX)).toEqual([])
    expect(
      closureBands(
        [closure({ start_mile_marker: 1, end_mile_marker: 10.2 })],
        LONG_INDEX,
      ),
    ).toHaveLength(1)
  })

  it('keeps each closure its own feature, so two are never merged into one', () => {
    const bands = closureBands(
      [
        closure({ id: 'a', start_mile_marker: 1, end_mile_marker: 2 }),
        closure({ id: 'b', start_mile_marker: 7, end_mile_marker: 8 }),
      ],
      INDEX,
    )

    expect(bands.map((band) => band.id)).toEqual(['a', 'b'])
  })
})

describe('closureFeatureCollection', () => {
  it('is a MultiLineString, so two pieces of trail are never bridged', () => {
    // trailSlice returns one run per centerline piece precisely because the
    // pieces are not joined on the ground. A LineString here would put the
    // straight line back.
    const geojson = closureFeatureCollection([
      { id: 'c1', lines: [[[-77, 39]], [[-77, 40]]] },
    ])

    expect(geojson.features[0].geometry.type).toBe('MultiLineString')
    expect(geojson.features[0].geometry.coordinates).toHaveLength(2)
  })

  it('carries the closure id in the properties, where a tap could read it', () => {
    // Not in the GeoJSON feature id alone: MapLibre runs a string feature id
    // through parseInt, and a closure id is a UUID.
    const geojson = closureFeatureCollection([{ id: 'c1', lines: [[[-77, 39]]] }])

    expect(geojson.features[0].properties[CLOSURE_ID_PROPERTY]).toBe('c1')
  })

  it('is empty for no closures, rather than absent', () => {
    expect(closureFeatureCollection([])).toEqual({
      type: 'FeatureCollection',
      features: [],
    })
  })
})

describe('the source', () => {
  it('starts empty, because closures arrive over the network after the map', () => {
    expect(buildClosureSource()).toEqual({
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  })

  it('hands each style its own features array rather than one shared object', () => {
    expect(buildClosureSource().data).not.toBe(buildClosureSource().data)
  })
})

describe('pushing bands onto a live map', () => {
  let map: MockMap

  beforeEach(() => {
    resetMapLibreMock()
    map = new MockMap({})
    map.sourceIds = [CLOSURE_SOURCE_ID]
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('pushes the bands into the source as GeoJSON', () => {
    map.styleLoaded = true
    const bands = [{ id: 'c1', lines: [[[-77, 39] as [number, number]]] }]

    attachClosureData(map as never, bands)

    expect(map.sourceData.get(CLOSURE_SOURCE_ID)).toEqual(closureFeatureCollection(bands))
  })

  it('still lands them when the style is busy at the moment they arrive', () => {
    // The same failure #129 found for the POIs, and closures are worse: they
    // arrive from the network once per connection, so a write dropped into a
    // busy window is a closed stretch of trail drawn open until the next time
    // the app finds signal.
    map.sourceIds = []
    map.emit('load')
    map.styleLoaded = false

    attachClosureData(map as never, [{ id: 'c1', lines: [[[-77, 39]]] }])
    expect(map.sourceData.get(CLOSURE_SOURCE_ID)).toBeUndefined()

    map.sourceIds = [CLOSURE_SOURCE_ID]
    map.emit('styledata')

    expect(map.sourceData.get(CLOSURE_SOURCE_ID)).toBeDefined()
  })

  it('keeps the map alive when the write fails, and says so', () => {
    // This runs inside a React effect on the map screen. An exception here
    // would take the whole map down over a band, which is the one outcome
    // worse than a missing band.
    //
    // A source that IS there and still refuses the write - a style swapped out
    // from under the call. A source that is merely absent means "not yet", and
    // waiting is the right answer to that.
    map.styleLoaded = true
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    map.sources.set(CLOSURE_SOURCE_ID, {
      setData: () => {
        throw new Error('style replaced mid-write')
      },
    })

    expect(() => attachClosureData(map as never, [])).not.toThrow()
    expect(warn).toHaveBeenCalled()
  })

  it('leaves no listener behind when detached before the source arrives', () => {
    map.sourceIds = []

    attachClosureData(map as never, [])()

    expect(map.listenerCount('styledata')).toBe(0)
  })
})
