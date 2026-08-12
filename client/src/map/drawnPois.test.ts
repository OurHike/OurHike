import { describe, it, expect } from 'vitest'
import { MockMap } from '../test/mocks/maplibre-gl'
import { drawnPoiCounts } from './drawnPois'
import { POI_ID_PROPERTY, POI_LAYER_ID } from './poiLayers'
import type { Map as MapLibreMap } from 'maplibre-gl'

// What the map is actually drawing, as against what is in the viewport (#528).
// The gap is the thing the legend had never said: `icon-allow-overlap: false`
// drops the pin that loses POI_PRIORITY, and at z14 that is 3% of privies.

function mapWith(features: unknown[]): MapLibreMap {
  // Built with a style holding the pin layer, which is how the mock answers
  // `getLayer` - the same way real MapLibre does, from the style it parsed.
  const map = new MockMap({
    style: { layers: [{ id: POI_LAYER_ID }], sources: { pois: {} } },
  })
  map.renderedFeatures.set(POI_LAYER_ID, features)
  return map as unknown as MapLibreMap
}

function pin(id: string, poi_type: string, confidence = 'high') {
  return { properties: { [POI_ID_PROPERTY]: id, poi_type, confidence } }
}

describe('drawnPoiCounts', () => {
  it('counts what was drawn, per type and confidence', () => {
    const map = mapWith([
      pin('w1', 'water'),
      pin('w2', 'water'),
      pin('s1', 'shelter'),
      pin('r1', 'resupply', 'low'),
    ])

    expect(drawnPoiCounts(map)).toEqual(
      new Map([
        ['water', 2],
        ['shelter', 1],
        ['resupply', 1],
      ]),
    )
  })

  it('keys exactly as the legend keys its rows - by type alone', () => {
    // The two are joined on this string. A mismatch would split one category into
    // a row that never finds its drawn figure, which reads as "0 shown" on a map
    // that is drawing them all. #580 folded the confidence split out of the
    // legend, so this folded with it.
    expect([...drawnPoiCounts(mapWith([pin('w1', 'water')])).keys()]).toEqual(['water'])
  })

  it('counts one waypoint once, however many tiles return it', () => {
    // MapLibre tiles even a GeoJSON source internally, so a point near a tile
    // boundary comes back per tile. Counted naively that reports MORE drawn than
    // present, and `Water · 14 · 17 shown` would discredit every other row.
    const map = mapWith([pin('w1', 'water'), pin('w1', 'water'), pin('w2', 'water')])

    expect(drawnPoiCounts(map).get('water')).toBe(2)
  })

  it('counts a verified and an unverified spring as two springs', () => {
    // Which is what the legend does since #580 - one row per category, because
    // which particular spring is unconfirmed is a question about one spring and
    // the map already says it per pin.
    const map = mapWith([
      { properties: { [POI_ID_PROPERTY]: 'a', poi_type: 'water', confidence: 'high' } },
      { properties: { [POI_ID_PROPERTY]: 'b', poi_type: 'water', confidence: 'low' } },
    ])

    expect(drawnPoiCounts(map).get('water')).toBe(2)
  })

  it('is empty when the pin layer is not in the style', () => {
    // A real state on a cold start, and it must not read as "nothing is drawn".
    // Also the reason the layer is checked first: querying a layer the style
    // does not hold fires an error event rather than throwing, so skipping the
    // check buys a console warning and an answer that looks like zero.
    const map = new MockMap({})
    map.renderedFeatures.set(POI_LAYER_ID, [pin('w1', 'water')])

    expect(drawnPoiCounts(map as unknown as MapLibreMap).size).toBe(0)
  })

  it('is empty when the layer is there and nothing placed', () => {
    expect(drawnPoiCounts(mapWith([])).size).toBe(0)
  })

  it('asks only about the pin layer', () => {
    const map = mapWith([pin('w1', 'water')]) as unknown as MockMap

    drawnPoiCounts(map as unknown as MapLibreMap)

    expect(map.featureQueries.at(-1)?.layers).toEqual([POI_LAYER_ID])
  })

  it('asks about the whole viewport rather than a point', () => {
    // The legend counts against the viewport rectangle, so this has to answer
    // for the same area or the two numbers are about different things.
    const map = mapWith([pin('w1', 'water')])

    drawnPoiCounts(map)

    expect((map as unknown as MockMap).featureQueries.at(-1)?.geometry).toBeUndefined()
  })

  it('skips a feature with no usable type rather than inventing a row', () => {
    const map = mapWith([
      { properties: { [POI_ID_PROPERTY]: 'a', poi_type: '' } },
      { properties: null },
      pin('w1', 'water'),
    ])

    expect(drawnPoiCounts(map)).toEqual(new Map([['water', 1]]))
  })
})
