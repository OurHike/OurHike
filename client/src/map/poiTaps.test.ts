import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { POI_ID_PROPERTY, POI_LAYER_ID } from './poiLayers'
import { attachPoiTaps, POI_TAP_SLOP_PX } from './poiTaps'

// The behaviour under test is "a hiker touches a pin and the app knows which
// POI that was" - so these drive real events through the map rather than
// calling the handler directly, and assert on what the shell is told.

function buildMap(): MockMap {
  const map = new MockMap({})
  map.layerIds = [POI_LAYER_ID, 'trail-lines']
  return map
}

function pin(id: string, type = 'water') {
  return { properties: { [POI_ID_PROPERTY]: id, poi_type: type, confidence: 'high' } }
}

/** What MapLibre hands a click handler: where on the canvas it landed. */
function touchAt(x: number, y: number) {
  return { point: { x, y } }
}

beforeEach(() => {
  resetMapLibreMock()
})

describe('tapping a pin', () => {
  it('tells the shell which POI was touched', () => {
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(120, 240))

    expect(onSelect).toHaveBeenCalledWith('atc_shelters:abc')
  })

  it('reads the id out of the properties, not off the feature', () => {
    // The gotcha this guards: MapLibre puts a string feature id through
    // parseInt (FeatureWrapper, maplibre-gl 6), and every id the pipeline
    // publishes - "atc_shelters:<guid>" - comes back NaN. A handler reading
    // feature.id would look right and identify nothing at all.
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [
      { id: Number.NaN, properties: { [POI_ID_PROPERTY]: 'opentrail_at:1234' } },
    ])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(10, 10))

    expect(onSelect).toHaveBeenCalledWith('opentrail_at:1234')
  })

  it('says nothing when the touch lands on bare map', () => {
    const map = buildMap()
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(400, 400))

    expect(onSelect).not.toHaveBeenCalled()
  })

  it('asks only about pins, so a touch on a trail line opens nothing', () => {
    const map = buildMap()
    map.renderedFeatures.set('trail-lines', [{ properties: { blaze: 'White' } }])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(50, 50))

    expect(onSelect).not.toHaveBeenCalled()
    expect(map.featureQueries.at(-1)?.layers).toEqual([POI_LAYER_ID])
  })

  it('allows for a thumb: a touch beside the pin still opens it', () => {
    // The pins are drawn at 38px and this app is used with gloves on, in rain,
    // one-handed. A hit area of exactly the pin means a pin that mostly does
    // nothing, which is the state this feature replaces.
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])

    attachPoiTaps(map as unknown as MapLibreMap, vi.fn())
    map.emit('click', touchAt(100, 100))

    expect(map.featureQueries.at(-1)?.geometry).toEqual([
      [100 - POI_TAP_SLOP_PX, 100 - POI_TAP_SLOP_PX],
      [100 + POI_TAP_SLOP_PX, 100 + POI_TAP_SLOP_PX],
    ])
    expect(POI_TAP_SLOP_PX).toBeGreaterThan(0)
  })

  it('opens the pin drawn on top when two are under one thumb', () => {
    // MapLibre returns what is drawn first, and what is drawn on top is what
    // somebody could see well enough to aim at.
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [
      pin('opentrail_at:spring'),
      pin('atc_campsites:behind'),
    ])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(100, 100))

    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(onSelect).toHaveBeenCalledWith('opentrail_at:spring')
  })

  it('is silent on a map whose pin layer has not been built yet', () => {
    // Querying a layer the style does not hold fires an error event in real
    // MapLibre. A touch on a map with no pins on it is not an error.
    const map = buildMap()
    map.layerIds = []
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(100, 100))

    expect(onSelect).not.toHaveBeenCalled()
    expect(map.featureQueries).toHaveLength(0)
  })

  it('ignores a pin carrying no id, rather than opening an empty sheet', () => {
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [{ properties: { poi_type: 'water' } }])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(100, 100))

    expect(onSelect).not.toHaveBeenCalled()
  })
})

describe('the pointer over a pin', () => {
  it('shows the map is tappable there, and only there', () => {
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])

    attachPoiTaps(map as unknown as MapLibreMap, vi.fn())

    map.emit('mousemove', touchAt(100, 100))
    expect(map.getCanvas().style.cursor).toBe('pointer')

    map.renderedFeatures.set(POI_LAYER_ID, [])
    map.emit('mousemove', touchAt(400, 400))
    expect(map.getCanvas().style.cursor).toBe('')
  })
})

describe('detaching', () => {
  it('leaves nothing listening, so a rebuilt map is not answered twice', () => {
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])
    const onSelect = vi.fn()

    const detach = attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    detach()
    map.emit('click', touchAt(100, 100))

    expect(onSelect).not.toHaveBeenCalled()
    expect(map.listenerCount('click')).toBe(0)
    expect(map.listenerCount('mousemove')).toBe(0)
  })

  it('puts the cursor back, so it does not outlive what it pointed at', () => {
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])

    const detach = attachPoiTaps(map as unknown as MapLibreMap, vi.fn())
    map.emit('mousemove', touchAt(100, 100))
    detach()

    expect(map.getCanvas().style.cursor).toBe('')
  })
})
