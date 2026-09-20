import { describe, it, expect, beforeEach } from 'vitest'
import type {
  CircleLayerSpecification,
  SymbolLayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import type { GeolocationState } from '../lib/useGeolocation'
import { POSITION_INKS, positionMarkId } from './positionMark'
import {
  ACCURACY_FLOOR_PX,
  accuracyRadiusAtZoomZero,
  accuracyRadiusExpression,
  applyPositionInk,
  attachPositionData,
  attachPositionImages,
  buildPositionAccuracyLayer,
  buildPositionLayer,
  fixAge,
  POSITION_ACCURACY_LAYER_ID,
  POSITION_LAYER_ID,
  POSITION_SOURCE_ID,
  positionFeatureCollection,
  positionIconExpression,
  positionMarkImage,
} from './positionLayers'

// The hiker's position on the canvas (#1581). Three rules, each from the
// brief in features/mockups/hiker-mark.html:
//
//  - **Never culled, never pushing.** A mark the collision engine drops is a
//    hiker who cannot find themselves; a mark that evicts the shelter pin
//    under it hides the one place they wanted.
//  - **Honest about accuracy.** The 95 % radius draws as a ring past the
//    mark's own floor and hides under it below - never a confident point
//    under canopy, never a second ring saying nothing.
//  - **Honest about age.** A lost signal draws the last fix stale, with its
//    age, and only when there IS a last fix; every other state draws nothing.

const symbol = () => buildPositionLayer() as SymbolLayerSpecification
const circle = () => buildPositionAccuracyLayer() as CircleLayerSpecification

const NOW = new Date('2026-09-17T12:00:00Z')
const FIX = {
  at: { lon: -73.9888, lat: 41.27444 },
  accuracyFeet: 32.8084,
  accuracyM: 10,
  fixedAt: NOW,
}
const LOCATED: GeolocationState = { status: 'located', ...FIX }

/** A map whose style already holds the source and both layers, so the
 *  attach helpers apply at once rather than waiting on `styledata`. */
function readyMap() {
  return new MockMap({
    style: {
      layers: [{ id: POSITION_ACCURACY_LAYER_ID }, { id: POSITION_LAYER_ID }],
      sources: { [POSITION_SOURCE_ID]: {} },
    },
  }) as unknown as MockMap & MapLibreMap
}

beforeEach(() => {
  resetMapLibreMock()
})

describe('the mark layer', () => {
  it('is never dropped by the collision engine', () => {
    expect(symbol().layout).toMatchObject({ 'icon-allow-overlap': true })
  })

  it('never pushes a pin aside: it is a viewer, not a place', () => {
    expect(symbol().layout).toMatchObject({ 'icon-ignore-placement': true })
  })

  it('draws at every zoom, the opening camera included (#1292)', () => {
    expect(symbol().minzoom).toBeUndefined()
    expect(circle().minzoom).toBeUndefined()
  })

  it('picks the stale image off the feature, in the sheet family it was built for', () => {
    expect(symbol().layout?.['icon-image']).toEqual(positionIconExpression('day'))
    expect(positionIconExpression('night')).toEqual([
      'case',
      ['get', 'stale'],
      positionMarkId('night', true),
      positionMarkId('night', false),
    ])
  })

  it('prints the age in the family ink, edged with its paper', () => {
    const layer = buildPositionLayer('red') as SymbolLayerSpecification

    expect(layer.layout?.['text-field']).toEqual(['get', 'age'])
    expect(layer.paint?.['text-color']).toBe(POSITION_INKS.red.ink)
    expect(layer.paint?.['text-halo-color']).toBe(POSITION_INKS.red.paper)
  })
})

describe('the accuracy ring', () => {
  it('is a circle, which takes no part in symbol placement', () => {
    expect(circle().type).toBe('circle')
  })

  it('grows with the zoom from a radius fixed at zoom zero, floored at the mark', () => {
    const expression = accuracyRadiusExpression()

    expect(expression.slice(0, 3)).toEqual(['interpolate', ['exponential', 2], ['zoom']])
    // The z14 stop: the floor, or the zoom-zero radius scaled by 2^14.
    const stop = expression.indexOf(14)
    expect(expression[stop + 1]).toEqual([
      'max',
      ACCURACY_FLOOR_PX,
      ['*', ['get', 'r0'], 2 ** 14],
    ])
  })

  it('puts a 100 m canopy fix at 27 px at z14 and a good 10 m fix under the floor', () => {
    // The mockup's own table, at 40°N with MapLibre's 512 px tiles.
    const canopy = accuracyRadiusAtZoomZero(100, 40) * 2 ** 14
    const good = accuracyRadiusAtZoomZero(10, 40) * 2 ** 14

    expect(canopy).toBeCloseTo(27.3, 0)
    expect(good).toBeLessThan(ACCURACY_FLOOR_PX)
  })
})

describe('what the canvas is given to draw', () => {
  it('draws nothing for every state that has no position', () => {
    for (const status of ['idle', 'locating', 'denied', 'unsupported'] as const) {
      expect(positionFeatureCollection({ status }, NOW).features).toHaveLength(0)
    }
    expect(
      positionFeatureCollection({ status: 'unavailable' }, NOW).features,
    ).toHaveLength(0)
  })

  it('draws a live fix at its coordinates, live, with no age', () => {
    const [feature] = positionFeatureCollection(LOCATED, NOW).features

    expect(feature.geometry.coordinates).toEqual([-73.9888, 41.27444])
    expect(feature.properties.stale).toBe(false)
    expect(feature.properties.age).toBe('')
    // 32.8 ft is 10 m, at the fix's own latitude.
    expect(feature.properties.r0).toBeCloseTo(accuracyRadiusAtZoomZero(10, 41.27444), 8)
  })

  it('draws a lost signal as its last fix, stale, with the age it has reached', () => {
    const lost: GeolocationState = {
      status: 'unavailable',
      last: { ...FIX, fixedAt: new Date(NOW.getTime() - 3 * 60_000) },
    }
    const [feature] = positionFeatureCollection(lost, NOW).features

    expect(feature.geometry.coordinates).toEqual([-73.9888, 41.27444])
    expect(feature.properties.stale).toBe(true)
    expect(feature.properties.age).toBe('3 min ago')
  })
})

describe('the age', () => {
  it('reads in minutes, then hours, and never runs negative', () => {
    const at = (ms: number) => fixAge(new Date(NOW.getTime() - ms), NOW)

    expect(at(20_000)).toBe('just now')
    expect(at(3 * 60_000)).toBe('3 min ago')
    expect(at(59 * 60_000)).toBe('59 min ago')
    expect(at(2 * 3_600_000 + 5 * 60_000)).toBe('2 h ago')
    expect(at(-60_000)).toBe('just now')
  })
})

describe('on a live map', () => {
  it('registers every ink family, live and stale, once', () => {
    const map = readyMap()

    attachPositionImages(map)
    attachPositionImages(map)

    expect(map.images.size).toBe(6)
    expect(map.images.has(positionMarkId('night', true))).toBe(true)
    expect(map.images.has(positionMarkId('red', false))).toBe(true)
  })

  it('rasterises each image once per page, whichever map asks', () => {
    // The 53 ms the six cost is paid once: a second map - a rebuild, a
    // remount - gets the same bytes back rather than drawing them again.
    const first = readyMap()
    const second = readyMap()

    attachPositionImages(first)
    attachPositionImages(second)

    expect(second.images.get(positionMarkId('day', false))).toBe(
      first.images.get(positionMarkId('day', false)),
    )
    expect(positionMarkImage('red', true)).toBe(positionMarkImage('red', true))
  })

  it('pushes the fix into the source', () => {
    const map = readyMap()

    attachPositionData(map, LOCATED, NOW)

    expect(map.sourceData.get(POSITION_SOURCE_ID)).toEqual(
      positionFeatureCollection(LOCATED, NOW),
    )
  })

  it('re-inks both layers for a sheet family', () => {
    const map = readyMap()

    applyPositionInk(map, 'night')

    expect(map.layoutProperties.get(`${POSITION_LAYER_ID}/icon-image`)).toEqual(
      positionIconExpression('night'),
    )
    expect(map.paintProperties.get(`${POSITION_LAYER_ID}/text-color`)).toBe(
      POSITION_INKS.night.ink,
    )
    expect(map.paintProperties.get(`${POSITION_ACCURACY_LAYER_ID}/circle-color`)).toBe(
      POSITION_INKS.night.ink,
    )
  })

  it('leaves a map whose style has no such layers alone', () => {
    const map = new MockMap({}) as unknown as MockMap & MapLibreMap

    expect(() => applyPositionInk(map, 'day')).not.toThrow()
    expect(map.paintProperties.size).toBe(0)
  })
})
