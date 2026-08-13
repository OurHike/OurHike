import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { POI_DOT_LAYER_ID, POI_ID_PROPERTY, POI_LAYER_ID } from './poiLayers'
import { attachPoiTaps, POI_DOT_TAP_SLOP_PX, POI_TAP_SLOP_PX } from './poiTaps'

// The behaviour under test is "a hiker touches a waypoint and the app knows
// which POI that was" - so these drive real events through the map rather than
// calling the handler directly, and assert on what the shell is told.

function buildMap(): MockMap {
  const map = new MockMap({})
  map.layerIds = [POI_DOT_LAYER_ID, POI_LAYER_ID, 'trail-lines']
  return map
}

function pin(id: string, type = 'water') {
  return { properties: { [POI_ID_PROPERTY]: id, poi_type: type, confidence: 'high' } }
}

/** A dot, which unlike a pin has to carry a position: the tap rule picks the
 *  nearest one to the thumb, so a test without coordinates is not testing it. */
function dot(id: string, lngLat: [number, number], type = 'water') {
  return {
    properties: { [POI_ID_PROPERTY]: id, poi_type: type, confidence: 'high' },
    geometry: { type: 'Point', coordinates: lngLat },
  }
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

  it('asks only about waypoints, so a touch on a trail line opens nothing', () => {
    const map = buildMap()
    map.renderedFeatures.set('trail-lines', [{ properties: { blaze: 'White' } }])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(50, 50))

    expect(onSelect).toHaveBeenCalledWith(null)
    // Both ranks are asked about since #597 - a miss on the pins falls through
    // to the dots - so this asserts that nothing OUTSIDE the two is ever
    // queried, which is the property that was actually worth having.
    expect(map.featureQueries).not.toHaveLength(0)
    for (const query of map.featureQueries) {
      expect(query.layers).toEqual(
        expect.arrayContaining([expect.stringMatching(/^poi-(pins|dots)$/)]),
      )
      expect(query.layers).toHaveLength(1)
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

describe('tapping a dot (#597)', () => {
  // The rank that exists so a waypoint losing a collision is still on the map.
  // Reaching it is the whole point - a dot nobody can tap is a smaller way of
  // being absent.

  it('opens the waypoint when the touch lands on a dot and no pin', () => {
    const map = buildMap()
    map.renderedFeatures.set(POI_DOT_LAYER_ID, [dot('opentrail_at:spring', [-75, 40])])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(100, 100))

    expect(onSelect).toHaveBeenCalledWith('opentrail_at:spring')
  })

  it('gives a dot the room a 4 px mark needs to be tappable at all', () => {
    // 38 px of pin needs 3 px of help; 4 px of dot needs 20. A dot queried at
    // the pin's slop would be a mark that only opens when hit dead centre,
    // which is the state POI_TAP_SLOP_PX exists to prevent for pins.
    const map = buildMap()
    map.renderedFeatures.set(POI_DOT_LAYER_ID, [dot('opentrail_at:spring', [-75, 40])])

    attachPoiTaps(map as unknown as MapLibreMap, vi.fn())
    map.emit('click', touchAt(100, 100))

    expect(POI_DOT_TAP_SLOP_PX).toBeGreaterThan(POI_TAP_SLOP_PX)
    expect(map.featureQueries.at(-1)?.geometry).toEqual([
      [100 - POI_DOT_TAP_SLOP_PX, 100 - POI_DOT_TAP_SLOP_PX],
      [100 + POI_DOT_TAP_SLOP_PX, 100 + POI_DOT_TAP_SLOP_PX],
    ])
  })

  it('opens the pin rather than the dot when the thumb covers both', () => {
    // #597's stated rule. A pin is the rank a hiker can see and aim at, so a
    // touch that reached one was meant for it - and the dot box is five times
    // wider, so without this rule the bigger box would routinely out-vote the
    // thing the hiker was looking straight at.
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:visible')])
    map.renderedFeatures.set(POI_DOT_LAYER_ID, [dot('opentrail_at:nearer', [-75, 40])])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(100, 100))

    expect(onSelect).toHaveBeenCalledWith('atc_shelters:visible')
  })

  it('picks the dot nearest the centre of the touch, not the first listed', () => {
    // At 20 px of slop the box routinely holds two waypoints, and "whichever
    // the renderer listed first" is a coin toss the hiker cannot see. Listed
    // deliberately far-first, so a [0] would return the wrong one.
    const map = buildMap()
    map.projection = ([lng]) => ({ x: lng === -75 ? 118 : 102, y: 100 })
    map.renderedFeatures.set(POI_DOT_LAYER_ID, [
      dot('opentrail_at:far', [-75, 40]),
      dot('atc_campsites:near', [-76, 40]),
    ])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(100, 100))

    expect(onSelect).toHaveBeenCalledWith('atc_campsites:near')
  })

  it('never answers a touch on a malformed pin with a neighbouring dot', () => {
    // A pin carrying no id is bare map, and must not fall through: the dot box
    // around it holds the NEXT waypoint along, and landing somebody on a
    // waypoint they did not touch is worse than opening nothing.
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [{ properties: { poi_type: 'water' } }])
    map.renderedFeatures.set(POI_DOT_LAYER_ID, [
      dot('atc_campsites:elsewhere', [-76, 40]),
    ])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(100, 100))

    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it('is silent on a style built before the dot rank existed', () => {
    // Querying a layer the style does not hold fires an error event in real
    // MapLibre. A pin-only style is a map, not a fault.
    const map = buildMap()
    map.layerIds = [POI_LAYER_ID]
    map.renderedFeatures.set(POI_DOT_LAYER_ID, [dot('opentrail_at:spring', [-75, 40])])
    const onSelect = vi.fn()

    attachPoiTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(100, 100))

    expect(onSelect).toHaveBeenCalledWith(null)
    expect(map.featureQueries.map((query) => query.layers)).not.toContainEqual([
      POI_DOT_LAYER_ID,
    ])
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
