import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import type { Feature } from 'geojson'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { buildTrailIndex } from '../lib/trailPosition'
import { closureBands } from './closureLayers'
import { atcBandCandidates, type AtcUpdate } from '../lib/atcUpdates'
import { MAX_BAND_MILES } from '../lib/closureSpan'
import { ATC_UPDATE_LAYER_ID } from '../lib/atcUpdateStyle'
import {
  ATC_UPDATE_ID_PROPERTY,
  ATC_UPDATE_SOURCE_ID,
  ATC_TAP_SLOP_PX,
  atcBandIdAt,
  atcTapBox,
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
    expect(bands[0].id).toBe('atc:va-creeper-trail-closure-detour')
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
    const parking = update({ category: 'Parking' })

    expect(closureBands(atcBandCandidates([parking]), straightTrail(20))).toHaveLength(0)
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
    expect(data.features[0].properties[ATC_UPDATE_ID_PROPERTY]).toBe(
      'atc:va-creeper-trail-closure-detour',
    )
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
