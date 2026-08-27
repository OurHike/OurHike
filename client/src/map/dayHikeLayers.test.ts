// Tests for map/dayHikeLayers.ts - the day-hike highlight (#978, frame `1j`).
//
// The one rule worth a suite: the casing draws UNDER both trail-line stacks
// and never recolours a blaze. The order is asserted BY INDEX IN THE BUILT
// STYLE, not by watching map.addLayer - the maplibre mock's addLayer takes one
// argument and always appends, so any ordering assertion written against a
// runtime-inserted layer would assert the opposite of the truth. Baking the
// layer into buildMapStyle is what makes the order testable at all.

import { describe, expect, it } from 'vitest'

import {
  buildDayHikeCasingLayers,
  buildDayHikePointLayers,
  DAY_HIKE_CASING_LAYER_ID,
  DAY_HIKE_GAP_LAYER_ID,
  DAY_HIKE_GAP_PROPERTY,
  DAY_HIKE_POINT_LAYER_ID,
  dayHikeFeatureCollection,
} from './dayHikeLayers'
import { ROUTE_INK, ROUTE_LINE_LAYER_ID } from './routeLayers'
import {
  BLAZE_LAYER_ID,
  buildMapStyle,
  NEARBY_BLAZE_LAYER_ID,
  NEARBY_TRAIL_CASING_LAYER_ID,
  TRAIL_CASING_LAYER_ID,
} from './style'

function layerOrder(): string[] {
  // style.test.ts's own canonical options, so this suite builds the same
  // style that suite pins everything else against.
  const style = buildMapStyle({
    topoArchiveUrl: 'pmtiles://ourhike-corridor',
    trailsUrl: '/data/trails.geojson',
    background: 'usgs_topo_offline',
  })
  return style.layers.map((layer) => layer.id)
}

describe('where the casing sits', () => {
  it('draws under both trail-line stacks', () => {
    const order = layerOrder()
    const casing = order.indexOf(DAY_HIKE_CASING_LAYER_ID)

    expect(casing).toBeGreaterThanOrEqual(0)
    for (const lineLayer of [
      NEARBY_TRAIL_CASING_LAYER_ID,
      NEARBY_BLAZE_LAYER_ID,
      TRAIL_CASING_LAYER_ID,
      BLAZE_LAYER_ID,
    ]) {
      expect(casing, `${lineLayer} must paint over the day-hike casing`).toBeLessThan(
        order.indexOf(lineLayer),
      )
    }
  })

  it('keeps the tapped points above the lines, where a marker lives', () => {
    const order = layerOrder()

    expect(order.indexOf(DAY_HIKE_POINT_LAYER_ID)).toBeGreaterThan(
      order.indexOf(BLAZE_LAYER_ID),
    )
  })

  it('shares the A.T. builder ink rather than inventing a second green', () => {
    // The maintainer's call, 2026-08-25: one colour meaning "your route".
    const [casing] = buildDayHikeCasingLayers()

    expect((casing as { paint: Record<string, unknown> }).paint['line-color']).toBe(
      ROUTE_INK,
    )
  })

  it('is translucent, because the ground under a ghosted line shows through', () => {
    const [casing] = buildDayHikeCasingLayers()
    const opacity = (casing as { paint: Record<string, unknown> }).paint['line-opacity']

    expect(typeof opacity).toBe('number')
    expect(opacity as number).toBeLessThan(0.5)
  })

  it('never restyles the blaze layers themselves', () => {
    // The whole point: the highlight is a NEW layer under the lines. Nothing
    // in this module touches the blaze layers' paint.
    for (const layer of [...buildDayHikeCasingLayers(), ...buildDayHikePointLayers()]) {
      expect(layer.id).not.toBe(BLAZE_LAYER_ID)
      expect(layer.id).not.toBe(NEARBY_BLAZE_LAYER_ID)
      expect(layer.id).not.toBe(ROUTE_LINE_LAYER_ID)
    }
  })
})

describe('the feature collection', () => {
  it('keeps one line per edge rather than concatenating across welds', () => {
    const drawing = {
      lines: [
        [
          [-74.1, 41.25],
          [-74.09, 41.25],
        ] as Array<[number, number]>,
        [
          [-74.09, 41.2501],
          [-74.09, 41.26],
        ] as Array<[number, number]>,
      ],
      points: [{ lon: -74.1, lat: 41.25, label: '1' }],
    }

    const collection = dayHikeFeatureCollection(drawing)

    const lineFeature = collection.features.find(
      (feature) => feature.geometry.type === 'MultiLineString',
    )
    expect(lineFeature?.geometry.coordinates).toHaveLength(2)
  })

  it('numbers the taps in order', () => {
    const collection = dayHikeFeatureCollection({
      lines: [],
      points: [
        { lon: -74.1, lat: 41.25, label: '1' },
        { lon: -74.09, lat: 41.25, label: '2' },
      ],
    })

    const labels = collection.features
      .filter((feature) => feature.geometry.type === 'Point')
      .map(
        (feature) => (feature.properties as Record<string, string>).day_hike_point_label,
      )
    expect(labels).toEqual(['1', '2'])
  })

  it('draws nothing for an empty draft', () => {
    expect(dayHikeFeatureCollection({ lines: [], points: [] }).features).toHaveLength(0)
  })
})

describe('the gap between stretches (#983)', () => {
  it('is drawn as neither a route nor a closure', () => {
    // The route is a solid casing because it is a statement about trail; a
    // dash is the map's word for a barrier. A gap is neither - it is the app
    // saying it has no evidence about this ground - so it borrows neither
    // vocabulary.
    const gap = buildDayHikePointLayers().find(
      (layer) => layer.id === DAY_HIKE_GAP_LAYER_ID,
    )

    expect(gap).toBeDefined()
    expect(JSON.stringify(gap?.paint)).toContain('line-dasharray')
    expect(JSON.stringify(gap?.paint)).not.toContain(ROUTE_INK)
  })

  it('is kept out of the route casing, which filters on a flag not a shape', () => {
    // MapLibre reports a MultiLineString as 'LineString', so a filter on
    // geometry alone would give the gap the route's own solid band.
    const casing = buildDayHikeCasingLayers()[0]

    expect(JSON.stringify(casing)).toContain(DAY_HIKE_GAP_PROPERTY)
  })

  it('rides the one source, flagged, so it cannot drift from the route', () => {
    const collection = dayHikeFeatureCollection({
      lines: [
        [
          [-74.1, 41.25],
          [-74.09, 41.25],
        ],
      ],
      points: [],
      gaps: [
        [
          [-74.09, 41.25],
          [-74.08, 41.26],
        ],
      ],
    })

    expect(collection.features).toHaveLength(2)
    const flagged = collection.features.filter(
      (feature) =>
        (feature.properties as Record<string, unknown>)[DAY_HIKE_GAP_PROPERTY] === true,
    )
    expect(flagged).toHaveLength(1)
  })

  it('draws nothing extra for a walk with no gap in it', () => {
    const collection = dayHikeFeatureCollection({
      lines: [
        [
          [-74.1, 41.25],
          [-74.09, 41.25],
        ],
      ],
      points: [],
    })

    expect(collection.features).toHaveLength(1)
  })
})
