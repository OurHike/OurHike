// Tests for routeLayers.ts (#755) - the shapes handed to MapLibre, and the
// two rules the wireframes and the style stack depend on: solid lines
// (dashes belong to closures alone), and roles as properties rather than
// feature ids.

import { describe, expect, it } from 'vitest'

import {
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
