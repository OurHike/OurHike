import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import type { Feature } from 'geojson'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { buildTrailIndex, trailPointAtMile } from '../lib/trailPosition'
import { closureBands } from './closureLayers'
import {
  atcBandCandidates,
  atcBandId,
  atcPointNotices,
  type AtcUpdate,
} from '../lib/atcUpdates'
import { MAX_BAND_MILES } from '../lib/closureSpan'
import { ATC_UPDATE_LAYER_ID, ATC_UPDATE_POINT_LAYER_ID } from '../lib/atcUpdateStyle'
import {
  ATC_UPDATE_ID_PROPERTY,
  ATC_UPDATE_SOURCE_ID,
  ATC_TAP_SLOP_PX,
  atcBandIdAt,
  atcFeatureCollection,
  atcTapBox,
  atcUpdatePoints,
  attachAtcUpdateData,
  attachAtcUpdateTaps,
  buildAtcUpdateSource,
} from './atcUpdateLayers'

// features/ATC_TRAIL_UPDATES.md, #461.
//
// The ATC's notices ride the geometry path closures already had, so almost
// nothing here is about geometry - it is about the two things a second source
// buys: a rhythm of its own, and a tap that can say which kind of band it
// landed on.

const MILE_IN_DEGREES_LAT = 1 / 69.05

function line(coordinates: Array<[number, number]>): Feature {
  return {
    type: 'Feature',
    properties: { source: 'centerline' },
    geometry: { type: 'LineString', coordinates },
  }
}

/** A straight centerline running north, one point per mile. */
function straightTrail(miles: number) {
  const coordinates: Array<[number, number]> = []
  for (let mile = 0; mile <= miles; mile += 1) {
    coordinates.push([-80, 35 + mile * MILE_IN_DEGREES_LAT])
  }
  return buildTrailIndex({ type: 'FeatureCollection', features: [line(coordinates)] })
}

function update(overrides: Partial<AtcUpdate> = {}): AtcUpdate {
  return {
    atc_id: 'va-creeper-trail-closure-detour',
    title: 'SW Virginia: VA Creeper Trail Closure/Detour',
    category: 'Closure',
    states: ['VA'],
    start_mile_marker: 4,
    end_mile_marker: 8,
    obstructs_trail: true,
    updated_at: '2026-07-17T00:00:00Z',
    source_url: 'https://appalachiantrail.org/trail-updates/va-creeper/',
    ...overrides,
  }
}

function band(id: string) {
  return { properties: { [ATC_UPDATE_ID_PROPERTY]: id } }
}

/** A map whose style holds the ATC layer, with `features` drawn on it. */
function tappableMap(features: unknown[]): MockMap {
  const map = new MockMap({})
  map.layerIds = [ATC_UPDATE_LAYER_ID, 'trail-lines']
  map.renderedFeatures.set(ATC_UPDATE_LAYER_ID, features)
  return map
}

beforeEach(() => resetMapLibreMock())
afterEach(() => vi.restoreAllMocks())

describe('the source', () => {
  it('starts empty, like every other source the shell fills later', () => {
    // Re-reading a style to add bands would drop the WebGL context out from
    // under the hiker.
    const source = buildAtcUpdateSource()

    expect(source.type).toBe('geojson')
    expect(source.data).toEqual({ type: 'FeatureCollection', features: [] })
  })

  it('is not the closures source', () => {
    // One source could not carry two dasharrays, and a tap against it could
    // not say which kind of band it hit without parsing an id to recover a
    // type - which is how the wrong sheet eventually opens over the wrong
    // thing.
    expect(ATC_UPDATE_SOURCE_ID).not.toBe('closures')
  })
})

describe('the bands', () => {
  it('places an update against the centerline through the shared path', () => {
    const bands = closureBands(atcBandCandidates([update()]), straightTrail(20))

    expect(bands).toHaveLength(1)
    // Derived rather than typed out. #1083 moved the prefix from the
    // abbreviation `atc:` to the registry key, and a literal here is a second
    // copy of a format only lib/atcUpdates.ts should own.
    expect(bands[0].id).toBe(atcBandId(update()))
    expect(bands[0].lines[0].length).toBeGreaterThan(1)
  })

  it('inherits the length ceiling that keeps a 398-mile advisory off the map', () => {
    // #462, applied to the data that made it necessary. Hurricane Helene
    // spans NOBO 239.4 to 637.8 - drawn, that is a fifth of the trail barred
    // at every zoom, burying the nine-mile closure a hiker has to walk round.
    const helene = update({
      atc_id: 'hurricane-helene',
      start_mile_marker: 1,
      end_mile_marker: 1 + MAX_BAND_MILES + 1,
    })

    expect(
      closureBands(atcBandCandidates([helene]), straightTrail(MAX_BAND_MILES + 5)),
    ).toHaveLength(0)
  })

  it('draws nothing for a notice that does not obstruct the trail', () => {
    // A closed shelter is a `Closure` on ATC's page and leaves the trail open,
    // which is why the band asks the reviewer rather than the category.
    const shelter = update({ category: 'Closure', obstructs_trail: false })

    expect(closureBands(atcBandCandidates([shelter]), straightTrail(20))).toHaveLength(0)
  })

  it('pushes the bands onto a live map', () => {
    const map = new MockMap({})
    map.sourceIds = [ATC_UPDATE_SOURCE_ID]
    map.styleLoaded = true
    const bands = closureBands(atcBandCandidates([update()]), straightTrail(20))

    attachAtcUpdateData(map as never, bands)

    const data = map.sourceData.get(ATC_UPDATE_SOURCE_ID) as {
      features: Array<{ properties: Record<string, string> }>
    }
    expect(data.features[0].properties[ATC_UPDATE_ID_PROPERTY]).toBe(atcBandId(update()))
  })

  it('still lands them when the style is busy at the moment they arrive', () => {
    // The same failure closures have: an ATC band dropped into a busy window
    // is a closed stretch of trail drawn open until the app next finds signal.
    const map = new MockMap({})
    map.sourceIds = []
    map.emit('load')
    map.styleLoaded = false

    attachAtcUpdateData(map as never, [{ id: 'atc:x', lines: [[[-77, 39]]] }])
    expect(map.sourceData.get(ATC_UPDATE_SOURCE_ID)).toBeUndefined()

    map.sourceIds = [ATC_UPDATE_SOURCE_ID]
    map.emit('styledata')

    expect(map.sourceData.get(ATC_UPDATE_SOURCE_ID)).toBeDefined()
  })
})

describe('tapping one', () => {
  it('tells the shell which update was touched', () => {
    const map = tappableMap([band('atc:va-creeper')])
    const onSelect = vi.fn()

    attachAtcUpdateTaps(map as never, onSelect)
    map.emit('click', { point: { x: 120, y: 240 } })

    expect(onSelect).toHaveBeenCalledWith('atc:va-creeper')
  })

  it('reports the band under a touch', () => {
    expect(
      atcBandIdAt(tappableMap([band('atc:va-creeper')]) as never, { x: 10, y: 10 }),
    ).toBe('atc:va-creeper')
  })

  it('queries a box, not a pixel', () => {
    // A 10px band on a screen somebody is squinting at in the sun, hit with a
    // gloved thumb. A band that only opens when hit dead centre reads as one
    // that does not open.
    expect(atcTapBox({ x: 100, y: 50 })).toEqual([
      [100 - ATC_TAP_SLOP_PX, 50 - ATC_TAP_SLOP_PX],
      [100 + ATC_TAP_SLOP_PX, 50 + ATC_TAP_SLOP_PX],
    ])
  })

  it('is silent before the style holds the layer', () => {
    // Querying a layer the style does not have fires an error event rather
    // than throwing - a touch on a map with no bands yet should be silent,
    // not a warning in the console.
    const map = new MockMap({})
    map.layerIds = []
    const query = vi.spyOn(map, 'queryRenderedFeatures')

    expect(atcBandIdAt(map as never, { x: 10, y: 10 })).toBeNull()
    expect(query).not.toHaveBeenCalled()
  })

  it('answers null for bare map', () => {
    expect(atcBandIdAt(tappableMap([]) as never, { x: 10, y: 10 })).toBeNull()
  })

  it('answers null for a band carrying no id', () => {
    expect(
      atcBandIdAt(tappableMap([{ properties: {} }]) as never, { x: 10, y: 10 }),
    ).toBeNull()
  })

  it('only reports hits, so a tap on bare map is left to other handlers', () => {
    const map = tappableMap([])
    const onSelect = vi.fn()

    attachAtcUpdateTaps(map as never, onSelect)
    map.emit('click', { point: { x: 1, y: 1 } })

    expect(onSelect).not.toHaveBeenCalled()
  })

  it('stops listening when detached', () => {
    const map = tappableMap([band('atc:x')])
    const onSelect = vi.fn()

    const detach = attachAtcUpdateTaps(map as never, onSelect)
    detach()
    map.emit('click', { point: { x: 1, y: 1 } })

    expect(onSelect).not.toHaveBeenCalled()
  })
})

describe('points, which is most of what ATC publishes', () => {
  // Five of the six reviewed updates live on 2026-08-12 name a single mile:
  // a shelter, a footbridge, two bear warnings, a flooded section. Drawn as
  // bands they were a few dozen feet of invisible line, which is why the
  // circle layer exists at all.

  it('places a single-mile notice on the centerline', () => {
    const shelter = update({ start_mile_marker: 6, end_mile_marker: 6 })

    const index = straightTrail(20)
    const points = atcUpdatePoints([shelter], index)

    expect(points).toHaveLength(1)
    expect(points[0].id).toBe(atcBandId(shelter))
    // Bracketed rather than compared against a flat-earth constant: the index
    // measures real distances, so its Nth vertex is not exactly at mile N.
    // What matters is that mile 6 lands between the vertices either side of
    // it, which is the interpolation actually doing its job.
    const [before, after] = [trailPointAtMile(index, 5.5), trailPointAtMile(index, 6.5)]
    expect(points[0].at[1]).toBeGreaterThan(before![1])
    expect(points[0].at[1]).toBeLessThan(after![1])
  })

  it('interpolates rather than snapping to the nearest vertex', () => {
    // The centerline's vertex spacing is coarser than the tenth of a mile ATC
    // quotes, so snapping would move a footbridge to wherever the survey
    // happened to put a point.
    const index = straightTrail(20)

    const tenths = [6.0, 6.1, 6.2, 6.3].map((mile) => trailPointAtMile(index, mile)![1])

    expect(new Set(tenths).size).toBe(4)
    expect([...tenths].sort((a, b) => a - b)).toEqual(tenths)
  })

  it('draws a point for a notice that does not obstruct the trail', () => {
    // Unlike the bands. A dot makes no claim about passability - it says the
    // ATC has posted something here - so a bear warning belongs on the map
    // and is not the barrier a band would have made it.
    const bears = update({
      obstructs_trail: false,
      start_mile_marker: 6,
      end_mile_marker: 6,
    })

    expect(atcBandCandidates([bears])).toHaveLength(0)
    expect(atcUpdatePoints(atcPointNotices([bears]), straightTrail(20))).toHaveLength(1)
  })

  it('drops one the centerline cannot place', () => {
    // A gap in what this build knows rather than a decision. The banner needs
    // only a mile number, so the hiker is told either way.
    const offTrail = update({ start_mile_marker: 900, end_mile_marker: 900 })

    expect(atcUpdatePoints([offTrail], straightTrail(20))).toHaveLength(0)
  })

  it('carries bands and points in one collection', () => {
    // One source, so a line layer and a circle layer draw from it without
    // either seeing the other's features - and the tap asks one question.
    const collection = atcFeatureCollection(
      [{ id: 'atc:band', lines: [[[-77, 39]]] }],
      [{ id: 'atc:point', at: [-80, 35] }],
    )

    const types = collection.features.map((feature) => feature.geometry.type)
    expect(types).toEqual(['MultiLineString', 'Point'])
    expect(collection.features[1].properties[ATC_UPDATE_ID_PROPERTY]).toBe('atc:point')
  })

  it('pushes both onto a live map', () => {
    const map = new MockMap({})
    map.sourceIds = [ATC_UPDATE_SOURCE_ID]
    map.styleLoaded = true

    attachAtcUpdateData(
      map as never,
      [{ id: 'atc:band', lines: [[[-77, 39]]] }],
      [{ id: 'atc:point', at: [-80, 35] }],
    )

    const data = map.sourceData.get(ATC_UPDATE_SOURCE_ID) as { features: unknown[] }
    expect(data.features).toHaveLength(2)
  })

  it('reports a tapped point, not only a tapped band', () => {
    // A hiker aiming at a notice does not know which geometry it happens to
    // be, so the tap queries both layers.
    const map = new MockMap({})
    map.layerIds = [ATC_UPDATE_POINT_LAYER_ID]
    map.renderedFeatures.set(ATC_UPDATE_POINT_LAYER_ID, [band('atc:shelter')])

    expect(atcBandIdAt(map as never, { x: 10, y: 10 })).toBe('atc:shelter')
  })
})
