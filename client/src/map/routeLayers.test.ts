// Tests for routeLayers.ts (#755) - the shapes handed to MapLibre, and the
// two rules the wireframes and the style stack depend on: solid lines
// (dashes belong to closures alone), and roles as properties rather than
// feature ids.

import { describe, expect, it } from 'vitest'

import { MockMap } from '../test/mocks/maplibre-gl'
import {
  attachRouteStroke,
  buildRouteLayers,
  buildRouteSource,
  ROUTE_CASING_LAYER_ID,
  ROUTE_LINE_LAYER_ID,
  ROUTE_POINT_LAYER_ID,
  ROUTE_LABEL_LAYER_ID,
  ROUTE_POINT_LABEL_PROPERTY,
  ROUTE_POINT_ROLE_PROPERTY,
  routeFeatureCollection,
} from './routeLayers'

describe('the source and layers', () => {
  it('starts empty, like every runtime source', () => {
    expect(buildRouteSource()).toEqual({
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  })

  it('draws casing under line under points, all off one source', () => {
    const layers = buildRouteLayers()
    expect(layers.map((layer) => layer.id)).toEqual([
      ROUTE_CASING_LAYER_ID,
      ROUTE_LINE_LAYER_ID,
      ROUTE_POINT_LAYER_ID,
      ROUTE_LABEL_LAYER_ID,
    ])
    expect(new Set(layers.map((layer) => 'source' in layer && layer.source))).toEqual(
      new Set(['route']),
    )
  })

  it('never drops a mile label for collision (#973)', () => {
    // Few points, every one of them put there deliberately. Hiding one
    // because a trail label reached the spot first would be the map editing
    // the hiker's own work.
    const labels = buildRouteLayers().find((layer) => layer.id === ROUTE_LABEL_LAYER_ID)
    expect(labels?.type).toBe('symbol')
    const layout = (labels as { layout: Record<string, unknown> }).layout
    expect(layout['text-allow-overlap']).toBe(true)
    expect(layout['text-ignore-placement']).toBe(true)
  })

  it('asks only for the fontstack this app actually bundles (#986)', () => {
    // public/glyphs ships ONE stack. A layer naming any other renders no text
    // at all - and offline, which is where this app lives, there is nowhere
    // to fetch the missing glyphs from.
    for (const layer of buildRouteLayers()) {
      const font = (layer as { layout?: Record<string, unknown> }).layout?.['text-font']
      if (font === undefined) continue
      expect(font).toEqual(['Noto Sans Regular'])
    }
  })

  it('keeps the route solid - dashes are reserved for closures', () => {
    for (const layer of buildRouteLayers()) {
      expect(JSON.stringify(layer)).not.toContain('dasharray')
    }
  })
})

describe('routeFeatureCollection', () => {
  const drawing = {
    legs: [
      [
        [
          [-81.5, 36.6],
          [-81.4, 36.7],
        ],
      ] as Array<Array<[number, number]>>,
    ],
    points: [
      { lon: -81.5, lat: 36.6, role: 'start' as const, label: '470.8 mi' },
      { lon: -81.4, lat: 36.7, role: 'end' as const, label: '486.2 mi' },
    ],
  }

  it('emits one multi-part line per leg and one point per drop', () => {
    const collection = routeFeatureCollection(drawing)
    const kinds = collection.features.map((feature) => feature.geometry.type)
    expect(kinds).toEqual(['MultiLineString', 'Point', 'Point'])
  })

  it('carries the role as a property, never as the feature id', () => {
    const collection = routeFeatureCollection(drawing)
    const points = collection.features.filter(
      (feature) => feature.geometry.type === 'Point',
    )
    expect(
      points.map((feature) => feature.properties[ROUTE_POINT_ROLE_PROPERTY]),
    ).toEqual(['start', 'end'])
    expect(points.every((feature) => !('id' in feature))).toBe(true)
    // The label travels already formatted, because the hiker's unit system
    // decides it and no MapLibre expression knows about that (#973).
    expect(
      points.map((feature) => feature.properties[ROUTE_POINT_LABEL_PROPERTY]),
    ).toEqual(['470.8 mi', '486.2 mi'])
  })
})

describe('drawing a stroke (#983, frame 1k)', () => {
  /** The mock, typed as the map the module wants - it implements the parts
   *  this function touches and nothing beyond them. */
  function mapWithStroke(
    onStroke: (stroke: Array<{ lon: number; lat: number }>) => void,
  ) {
    const map = new MockMap({ center: [-74.1, 41.25], zoom: 13 })
    const detach = attachRouteStroke(map as never, onStroke)
    return { map, detach }
  }

  const at = (lng: number, lat: number) => ({ lngLat: { lng, lat } })

  it('collects the drag and reports it once, on the way up', () => {
    const strokes: Array<Array<{ lon: number; lat: number }>> = []
    const { map } = mapWithStroke((stroke) => strokes.push(stroke))

    map.emit('mousedown', at(-74.1, 41.25))
    map.emit('mousemove', at(-74.099, 41.25))
    map.emit('mousemove', at(-74.098, 41.25))
    expect(strokes).toHaveLength(0)

    map.emit('mouseup', {})

    expect(strokes).toHaveLength(1)
    expect(strokes[0]).toHaveLength(3)
    expect(strokes[0][0]).toEqual({ lon: -74.1, lat: 41.25 })
  })

  it('ignores a move that is not part of a drag', () => {
    // A pointer crossing the map with nothing pressed is not a stroke, and
    // collecting it would hand the matcher a line nobody drew.
    const strokes: unknown[] = []
    const { map } = mapWithStroke((stroke) => strokes.push(stroke))

    map.emit('mousemove', at(-74.1, 41.25))
    map.emit('mouseup', {})

    expect(strokes).toHaveLength(0)
  })

  it('reports nothing for a stroke of one point', () => {
    // A tap that happened inside draw mode. Reporting it would ask the
    // matcher to find a trail along a line with no direction, which is a
    // different question from the one it answers.
    const strokes: unknown[] = []
    const { map } = mapWithStroke((stroke) => strokes.push(stroke))

    map.emit('mousedown', at(-74.1, 41.25))
    map.emit('mouseup', {})

    expect(strokes).toHaveLength(0)
  })

  it('stops the map panning under the finger, and puts it back', () => {
    // Two interpreters per touch is the failure routeLayers.ts's tap handler
    // already records; a drag and a pan are that failure one level up.
    const { map, detach } = mapWithStroke(() => {})

    expect(map.dragPan.isEnabled()).toBe(false)
    expect(map.touchZoomRotate.isEnabled()).toBe(false)

    detach()

    expect(map.dragPan.isEnabled()).toBe(true)
    expect(map.touchZoomRotate.isEnabled()).toBe(true)
  })

  it('leaves a gesture the hiker had already turned off, off', () => {
    // The detach puts back what it found rather than assuming both were on.
    const map = new MockMap({ center: [-74.1, 41.25], zoom: 13 })
    map.touchZoomRotate.disable()

    const detach = attachRouteStroke(map as never, () => {})
    detach()

    expect(map.dragPan.isEnabled()).toBe(true)
    expect(map.touchZoomRotate.isEnabled()).toBe(false)
  })
})
