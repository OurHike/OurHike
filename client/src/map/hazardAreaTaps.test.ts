import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { CLOSURE_COLOR } from '../lib/closureStyle'
import { hazardAreasOf, hazardFeatureCollection } from '../lib/hazardAreas'
import type { TrailNotice } from '../lib/notices'
import {
  buildHazardLayers,
  HAZARD_EDGE_LAYER_ID,
  HAZARD_FILL_LAYER_ID,
  HAZARD_POINT_LAYER_ID,
  HAZARD_SOURCE_ID,
  hazardColor,
} from './hazardAreaLayers'
import { attachHazardData, attachHazardTaps } from './hazardAreaTaps'
import { BLAZE_LAYER_ID } from './style'
import { WARNING_ID_PROPERTY, WARNING_LAYER_ID } from './warningLayers'

// Decision 67 (the maintainer, 2026-10-04, decisions-64-67-mock.html §4
// option A): an area washed in orange under the trail, a dashed edge, and
// the trail open. These drive the map the way a hiker does - the push, and a
// touch - and assert on what the shell is told.

function huntingArea(id: string): TrailNotice {
  return {
    notice_id: id,
    source_key: 'iata_lands_hunting_regs',
    title: 'Fixture hunting area (example)',
    category: 'Open for public hunting',
    locality: '',
    place: {
      kind: 'geometry',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [-77.01, 34.3],
            [-76.99, 34.3],
            [-76.99, 34.31],
            [-77.01, 34.31],
            [-77.01, 34.3],
          ],
        ],
      },
    },
    obstructs_trail: false,
    updated_at: null,
    source_url: null,
    review_state: 'unreviewed',
    hazard: 'hunting',
  }
}

const AREAS = hazardAreasOf([huntingArea('iata_lands_hunting_regs:1')])

function areaFeature(id: string) {
  return { properties: { notice_id: id } }
}

function tappableMap(): MockMap {
  const map = new MockMap({})
  map.layerIds = [
    HAZARD_FILL_LAYER_ID,
    HAZARD_POINT_LAYER_ID,
    BLAZE_LAYER_ID,
    WARNING_LAYER_ID,
  ]
  map.renderedFeatures.set(HAZARD_FILL_LAYER_ID, [
    areaFeature('iata_lands_hunting_regs:1'),
  ])
  return map
}

beforeEach(() => {
  resetMapLibreMock()
})

describe('the drawing', () => {
  it('washes the area and dashes its edge in one orange, and draws nothing in a closure’s red', () => {
    const [fill, edge, point] = buildHazardLayers(HAZARD_SOURCE_ID, false)
    expect(fill).toMatchObject({
      id: HAZARD_FILL_LAYER_ID,
      type: 'fill',
      paint: { 'fill-color': hazardColor(false), 'fill-opacity': 0.18 },
    })
    expect(edge).toMatchObject({
      id: HAZARD_EDGE_LAYER_ID,
      type: 'line',
      paint: { 'line-color': hazardColor(false), 'line-dasharray': [4, 3] },
    })
    expect(point).toMatchObject({ id: HAZARD_POINT_LAYER_ID, type: 'circle' })
    for (const dark of [false, true]) {
      expect(JSON.stringify(buildHazardLayers(HAZARD_SOURCE_ID, dark))).not.toContain(
        CLOSURE_COLOR,
      )
    }
  })
})

describe('pushing the areas onto a live map', () => {
  it('puts each area in the source as GeoJSON, keyed by its notice id', () => {
    const map = new MockMap({})
    map.layerIds = [HAZARD_FILL_LAYER_ID]
    map.sourceIds = [HAZARD_SOURCE_ID]
    map.styleLoaded = true

    attachHazardData(map as never, AREAS)

    expect(map.sourceData.get(HAZARD_SOURCE_ID)).toEqual(hazardFeatureCollection(AREAS))
  })
})

describe('touching an area', () => {
  it('opens the area’s card when nothing else is under the thumb', () => {
    const map = tappableMap()
    const onSelect = vi.fn()

    attachHazardTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', { point: { x: 120, y: 240 } })

    expect(onSelect).toHaveBeenCalledWith('iata_lands_hunting_regs:1')
  })

  it('yields to the trail line, whose own card carries the advisory', () => {
    const map = tappableMap()
    map.renderedFeatures.set(BLAZE_LAYER_ID, [
      {
        properties: {
          id: 'centerline:1',
          source: 'centerline',
          name: null,
          blaze_color: 'White',
        },
        geometry: { type: 'LineString', coordinates: [] },
      },
    ])
    const onSelect = vi.fn()

    attachHazardTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', { point: { x: 120, y: 240 } })

    expect(onSelect).not.toHaveBeenCalled()
  })

  it('yields to a serious-warning pin drawn over it', () => {
    const map = tappableMap()
    map.renderedFeatures.set(WARNING_LAYER_ID, [
      { properties: { [WARNING_ID_PROPERTY]: 'r1' } },
    ])
    const onSelect = vi.fn()

    attachHazardTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', { point: { x: 120, y: 240 } })

    expect(onSelect).not.toHaveBeenCalled()
  })

  it('stops listening once detached', () => {
    const map = tappableMap()
    const onSelect = vi.fn()

    const detach = attachHazardTaps(map as unknown as MapLibreMap, onSelect)
    detach()
    map.emit('click', { point: { x: 120, y: 240 } })

    expect(onSelect).not.toHaveBeenCalled()
  })
})
