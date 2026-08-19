import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { ATC_UPDATE_LAYER_ID } from '../lib/atcUpdateStyle'
import { ATC_UPDATE_ID_PROPERTY } from './atcUpdateLayers'
import { POI_ID_PROPERTY, POI_LAYER_ID } from './poiLayers'
import { BLAZE_LAYER_ID } from './style'
import { attachLineTaps, LINE_TAP_SLOP_PX, tappedLineAt } from './lineTaps'

// The behaviour under test is "a hiker touches a trail line and the shell
// learns which line that was" (#134) - so these drive real events through
// the map, as poiTaps.test.ts does, and assert on what the shell is told.

function buildMap(): MockMap {
  const map = new MockMap({})
  map.layerIds = [BLAZE_LAYER_ID, POI_LAYER_ID, ATC_UPDATE_LAYER_ID]
  return map
}

function line(id: string, source: string, blaze = 'Blue', name: string | null = null) {
  return { properties: { id, source, name, blaze_color: blaze } }
}

function touchAt(x: number, y: number) {
  return { point: { x, y } }
}

beforeEach(() => {
  resetMapLibreMock()
})

describe('tapping a line', () => {
  it('tells the shell the published facts of the line it landed on', () => {
    const map = buildMap()
    map.renderedFeatures.set(BLAZE_LAYER_ID, [
      line('side_trails:abc', 'side_trails', 'Blue', 'Rocky Run Spur Trail'),
    ])
    const onSelect = vi.fn()

    attachLineTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(120, 240))

    expect(onSelect).toHaveBeenCalledWith({
      id: 'side_trails:abc',
      source: 'side_trails',
      name: 'Rocky Run Spur Trail',
      blazeColor: 'Blue',
    })
  })

  it('reports a touch on bare map as null, which is how the sheet is dismissed', () => {
    const map = buildMap()
    const onSelect = vi.fn()

    attachLineTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(400, 400))

    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it('queries with slop around the touch, because a 2.5px line is not a thumb-sized target', () => {
    const map = buildMap()

    tappedLineAt(map as unknown as MapLibreMap, { x: 100, y: 100 })

    const lineQuery = map.featureQueries.find((q) => q.layers.includes(BLAZE_LAYER_ID))
    expect(lineQuery?.geometry).toEqual([
      [100 - LINE_TAP_SLOP_PX, 100 - LINE_TAP_SLOP_PX],
      [100 + LINE_TAP_SLOP_PX, 100 + LINE_TAP_SLOP_PX],
    ])
    expect(LINE_TAP_SLOP_PX).toBeGreaterThan(0)
  })

  it('yields to a pin under the same thumb', () => {
    // Spurs exist to lead to shelters, so a shelter pin almost always has a
    // blue line under it - and the pin is the smaller, aimed-at target.
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [
      { properties: { [POI_ID_PROPERTY]: 'atc_shelters:abc' } },
    ])
    map.renderedFeatures.set(BLAZE_LAYER_ID, [line('side_trails:abc', 'side_trails')])

    expect(tappedLineAt(map as unknown as MapLibreMap, { x: 10, y: 10 })).toBeNull()
  })

  it('yields to an ATC notice under the same thumb', () => {
    const map = buildMap()
    map.renderedFeatures.set(ATC_UPDATE_LAYER_ID, [
      { properties: { [ATC_UPDATE_ID_PROPERTY]: 'atc:closure-1' } },
    ])
    map.renderedFeatures.set(BLAZE_LAYER_ID, [line('side_trails:abc', 'side_trails')])

    expect(tappedLineAt(map as unknown as MapLibreMap, { x: 10, y: 10 })).toBeNull()
  })

  it('prefers the side trail over the through-route at a junction', () => {
    // The AT is on screen almost everywhere and sorted above side trails, so
    // topmost-first would answer "the AT" for every tap near a junction -
    // exactly where a hiker is asking about the spur. The narrow line is the
    // deliberate target.
    const map = buildMap()
    map.renderedFeatures.set(BLAZE_LAYER_ID, [
      line('centerline:chain:0', 'centerline', 'White'),
      line('side_trails:abc', 'side_trails', 'Blue'),
    ])

    const tapped = tappedLineAt(map as unknown as MapLibreMap, { x: 10, y: 10 })

    expect(tapped?.id).toBe('side_trails:abc')
  })

  it('answers the through-route when it is the only line there', () => {
    const map = buildMap()
    map.renderedFeatures.set(BLAZE_LAYER_ID, [
      line('centerline:chain:0', 'centerline', 'White'),
    ])

    const tapped = tappedLineAt(map as unknown as MapLibreMap, { x: 10, y: 10 })

    expect(tapped).toEqual({
      id: 'centerline:chain:0',
      source: 'centerline',
      name: null,
      blazeColor: 'White',
    })
  })

  it('is silent before the style holds the layer, like every other tap handler', () => {
    const map = new MockMap({})
    map.layerIds = []

    expect(tappedLineAt(map as unknown as MapLibreMap, { x: 10, y: 10 })).toBeNull()
  })

  it('detaches cleanly', () => {
    const map = buildMap()
    map.renderedFeatures.set(BLAZE_LAYER_ID, [line('side_trails:abc', 'side_trails')])
    const onSelect = vi.fn()

    const detach = attachLineTaps(map as unknown as MapLibreMap, onSelect)
    detach()
    map.emit('click', touchAt(10, 10))

    expect(onSelect).not.toHaveBeenCalled()
  })
})
