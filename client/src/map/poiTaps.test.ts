import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { POI_DOT_LAYER_ID, POI_ID_PROPERTY, POI_LAYER_ID } from './poiLayers'
import { attachPoiTaps, poiIdAt, POI_DOT_TAP_SLOP_PX, POI_TAP_SLOP_PX } from './poiTaps'

// The behaviour under test is "a hiker touches a pin and the app knows which
// POI that was" - so these drive real events through the map rather than
// calling the handler directly, and assert on what the shell is told.

function buildMap(): MockMap {
  const map = new MockMap({})
  map.layerIds = [POI_LAYER_ID, POI_DOT_LAYER_ID, 'trail-lines']
  return map
}

/** A dot feature, which unlike a pin carries geometry the rule reads. */
function dot(id: string, lon: number, lat: number, type = 'viewpoint') {
  return {
    properties: { [POI_ID_PROPERTY]: id, poi_type: type, confidence: 'high' },
    geometry: { type: 'Point', coordinates: [lon, lat] },
  }
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

  it('reports a touch on bare map as null, which is how the card is dismissed', () => {
    // Tap-elsewhere-to-put-it-away is the gesture every floating map card
    // teaches. Only taps say so - MapLibre withholds 'click' for a drag, so
    // panning around with the card open never throws it away.
    const map = buildMap()
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(400, 400))

    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it('asks only about pins, so a touch on a trail line opens nothing', () => {
    const map = buildMap()
    map.renderedFeatures.set('trail-lines', [{ properties: { blaze: 'White' } }])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(50, 50))

    expect(onSelect).toHaveBeenCalledWith(null)
    // EVERY query, not just the last. There are two ranks now (#597), so a
    // touch asks about pins and then about dots; asserting on the last one
    // alone would stop noticing if the first ever widened to the whole style.
    expect(map.featureQueries.length).toBeGreaterThan(0)
    for (const query of map.featureQueries) {
      expect(query.layers).not.toContain('trail-lines')
      expect(
        query.layers?.every(
          (layer) => layer === POI_LAYER_ID || layer === POI_DOT_LAYER_ID,
        ),
      ).toBe(true)
    }
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

  it('never queries a map whose pin layer has not been built yet', () => {
    // Querying a layer the style does not hold fires an error event in real
    // MapLibre. A touch on a map with no pins on it yet is bare map - a
    // dismissal, not an error and not a warning in the console.
    const map = buildMap()
    map.layerIds = []
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(100, 100))

    expect(onSelect).toHaveBeenCalledWith(null)
    expect(map.featureQueries).toHaveLength(0)
  })

  it('treats a pin carrying no id as bare map, rather than opening an empty card', () => {
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [{ properties: { poi_type: 'water' } }])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(100, 100))

    expect(onSelect).toHaveBeenCalledWith(null)
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

describe('the two-rank tap rule (#597)', () => {
  it('gives a dot a much wider hit area than a pin, because it is much smaller', () => {
    // A 38px pin needs 3px of slop to reach the 44px touch target; a dot a few
    // pixels across needs about twenty. That difference is the reason the
    // ordering below has to be a rule at all - the dot box will routinely hold
    // more than one waypoint where the pin box almost never did.
    expect(POI_DOT_TAP_SLOP_PX).toBeGreaterThan(POI_TAP_SLOP_PX * 5)
  })

  it('RULE 1: a pin under the thumb beats a dot under the thumb', () => {
    // Resolving to the dot would make a perfectly good pin feel unreliable -
    // the hiker aimed at the thing they could see.
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [pin('the-pin')])
    map.renderedFeatures.set(POI_DOT_LAYER_ID, [dot('a-dot', 0, 0)])

    expect(poiIdAt(map as unknown as MapLibreMap, { x: 100, y: 100 })).toBe('the-pin')
  })

  it('RULE 2: among dots, the one nearest the touch wins', () => {
    // MapLibre's own ordering inside a circle layer is source order, which is
    // not an answer to "which did they mean". Listing the far one first is
    // exactly the case `[0]` would get wrong.
    const map = buildMap()
    map.projection = ([lon]) => ({ x: lon, y: 100 })
    map.renderedFeatures.set(POI_LAYER_ID, [])
    map.renderedFeatures.set(POI_DOT_LAYER_ID, [dot('far', 118, 0), dot('near', 102, 0)])

    expect(poiIdAt(map as unknown as MapLibreMap, { x: 100, y: 100 })).toBe('near')
  })

  it('falls through to a dot when no pin is under the thumb', () => {
    const map = buildMap()
    map.projection = ([lon]) => ({ x: lon, y: 100 })
    map.renderedFeatures.set(POI_LAYER_ID, [])
    map.renderedFeatures.set(POI_DOT_LAYER_ID, [dot('only-a-dot', 101, 0)])

    expect(poiIdAt(map as unknown as MapLibreMap, { x: 100, y: 100 })).toBe('only-a-dot')
  })

  it('is still bare map when neither rank has anything there', () => {
    // The null is load-bearing: it is how the waypoint card closes.
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [])
    map.renderedFeatures.set(POI_DOT_LAYER_ID, [])

    expect(poiIdAt(map as unknown as MapLibreMap, { x: 100, y: 100 })).toBeNull()
  })

  it('says bare map rather than throwing when the dot layer is not in the style yet', () => {
    // A style mid-parse holds one layer and not the other, and a touch then
    // should be silent rather than an error in the console.
    const map = buildMap()
    map.layerIds = [POI_LAYER_ID]
    map.renderedFeatures.set(POI_LAYER_ID, [])

    expect(() => poiIdAt(map as unknown as MapLibreMap, { x: 100, y: 100 })).not.toThrow()
    expect(poiIdAt(map as unknown as MapLibreMap, { x: 100, y: 100 })).toBeNull()
  })

  it('skips a dot carrying no usable id instead of selecting an empty string', () => {
    const map = buildMap()
    map.projection = ([lon]) => ({ x: lon, y: 100 })
    map.renderedFeatures.set(POI_LAYER_ID, [])
    map.renderedFeatures.set(POI_DOT_LAYER_ID, [
      {
        properties: { [POI_ID_PROPERTY]: '' },
        geometry: { type: 'Point', coordinates: [101, 0] },
      },
      dot('real', 104, 0),
    ])

    expect(poiIdAt(map as unknown as MapLibreMap, { x: 100, y: 100 })).toBe('real')
  })
})
