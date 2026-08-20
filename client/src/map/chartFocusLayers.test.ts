import { describe, it, expect, beforeEach, vi } from 'vitest'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import {
  attachChartFocus,
  CHART_FOCUS_BAND_LAYER_ID,
  CHART_FOCUS_LINE_LAYER_ID,
  CHART_FOCUS_POINT_LAYER_ID,
  CHART_FOCUS_SOURCE_ID,
} from './chartFocusLayers'

// This module is the one runtime-added overlay (its header says why), so
// what the closure/route layer tests take for granted - the source is in
// the built style - is exactly what these have to prove instead: the
// attach adds it, a style swap that drops it gets it re-added with the
// focus it was holding, and detach leaves no listener running.

function liveMap(): MockMap {
  return new MockMap({})
}

function focusData(map: MockMap): { features: Array<{ geometry: { type: string } }> } {
  return map.sourceData.get(CHART_FOCUS_SOURCE_ID) as {
    features: Array<{ geometry: { type: string } }>
  }
}

beforeEach(() => {
  resetMapLibreMock()
})

describe('attachChartFocus', () => {
  it('adds its source and three layers on attach', () => {
    const map = liveMap()
    attachChartFocus(map as unknown as MapLibreMap)

    expect(map.getSource(CHART_FOCUS_SOURCE_ID)).toBeDefined()
    expect(map.getLayer(CHART_FOCUS_BAND_LAYER_ID)).toBeDefined()
    expect(map.getLayer(CHART_FOCUS_LINE_LAYER_ID)).toBeDefined()
    expect(map.getLayer(CHART_FOCUS_POINT_LAYER_ID)).toBeDefined()
  })

  it('writes the point and the stretch through, and clears them', () => {
    const map = liveMap()
    const handle = attachChartFocus(map as unknown as MapLibreMap)

    handle.setPoint([-77.1, 39.2])
    expect(focusData(map).features).toEqual([
      expect.objectContaining({
        geometry: { type: 'Point', coordinates: [-77.1, 39.2] },
      }),
    ])

    handle.setStretch([
      [
        [-77.1, 39.2],
        [-77.2, 39.3],
      ],
    ])
    expect(focusData(map).features.map((f) => f.geometry.type)).toEqual([
      'MultiLineString',
      'Point',
    ])

    handle.setPoint(null)
    handle.setStretch(null)
    expect(focusData(map).features).toEqual([])
  })

  it('re-adds itself with the focus it was holding after a style swap drops it', () => {
    const map = liveMap()
    const handle = attachChartFocus(map as unknown as MapLibreMap)
    handle.setPoint([-77.1, 39.2])

    // A setStyle swap rebuilds the style from spec, and a runtime source is
    // not in the spec: model it as the lists emptying, then styledata.
    map.sourceIds = []
    map.layerIds = []
    map.sourceData.clear()
    map.emit('styledata')

    expect(map.getSource(CHART_FOCUS_SOURCE_ID)).toBeDefined()
    expect(map.getLayer(CHART_FOCUS_POINT_LAYER_ID)).toBeDefined()
    expect(focusData(map).features).toEqual([
      expect.objectContaining({
        geometry: { type: 'Point', coordinates: [-77.1, 39.2] },
      }),
    ])
  })

  it('recovers on the next styledata when the style cannot take the write yet', () => {
    const map = liveMap()
    const addSource = vi.spyOn(map, 'addSource').mockImplementationOnce(() => {
      throw new Error('style is not done loading')
    })

    const handle = attachChartFocus(map as unknown as MapLibreMap)
    expect(map.getSource(CHART_FOCUS_SOURCE_ID)).toBeUndefined()

    map.emit('styledata')
    expect(map.getSource(CHART_FOCUS_SOURCE_ID)).toBeDefined()
    expect(addSource).toHaveBeenCalledTimes(2)

    handle.detach()
  })

  it('detaches cleanly: layers gone, source gone, listener gone, twice is safe', () => {
    const map = liveMap()
    const handle = attachChartFocus(map as unknown as MapLibreMap)
    handle.setPoint([-77.1, 39.2])

    handle.detach()
    handle.detach()

    expect(map.getSource(CHART_FOCUS_SOURCE_ID)).toBeUndefined()
    expect(map.getLayer(CHART_FOCUS_BAND_LAYER_ID)).toBeUndefined()
    expect(map.listenerCount('styledata')).toBe(0)

    // A write after detach must not resurrect anything.
    handle.setPoint([-77.5, 39.5])
    expect(map.getSource(CHART_FOCUS_SOURCE_ID)).toBeUndefined()
  })
})
