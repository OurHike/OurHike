import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { POI_ID_PROPERTY, POI_LAYER_ID } from './poiLayers'
import { WARNING_ID_PROPERTY, WARNING_LAYER_ID } from './warningLayers'
import { CLOSURE_ID_PROPERTY } from './closureLayers'
import { CLOSURE_LAYER_ID } from '../lib/closureStyle'
import { attachMapTaps, CLOSURE_TAP_SLOP_PX, POI_TAP_SLOP_PX } from './taps'

// The behaviour under test is "a hiker touches the map and the app knows
// what that was" - so these drive real events through the map rather than
// calling the handler directly, and assert on what the shell is told.

function buildMap(): MockMap {
  const map = new MockMap({})
  map.layerIds = [POI_LAYER_ID, WARNING_LAYER_ID, CLOSURE_LAYER_ID, 'trail-lines']
  return map
}

function pin(id: string, type = 'water') {
  return { properties: { [POI_ID_PROPERTY]: id, poi_type: type, confidence: 'high' } }
}

function warning(id: string) {
  return { properties: { [WARNING_ID_PROPERTY]: id } }
}

function band(id: string) {
  return { properties: { [CLOSURE_ID_PROPERTY]: id } }
}

/** What MapLibre hands a click handler: where on the canvas it landed. */
function touchAt(x: number, y: number) {
  return { point: { x, y } }
}

/** All three handlers, so a test can assert both the winner and the nulls. */
function handlers() {
  return {
    onSelectPoi: vi.fn(),
    onSelectWarning: vi.fn(),
    onSelectClosure: vi.fn(),
  }
}

beforeEach(() => {
  resetMapLibreMock()
})

describe('tapping a pin', () => {
  it('tells the shell which POI was touched', () => {
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])
    const on = handlers()

    attachMapTaps(map as unknown as MapLibreMap, on)
    map.emit('click', touchAt(120, 240))

    expect(on.onSelectPoi).toHaveBeenCalledWith('atc_shelters:abc')
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
    const on = handlers()

    attachMapTaps(map as unknown as MapLibreMap, on)
    map.emit('click', touchAt(10, 10))

    expect(on.onSelectPoi).toHaveBeenCalledWith('opentrail_at:1234')
  })

  it('reports a touch on bare map as null to every handler - the shared dismissal', () => {
    // Tap-elsewhere-to-put-it-away is the gesture every floating map card
    // teaches. Only taps say so - MapLibre withholds 'click' for a drag, so
    // panning around with a card open never throws it away.
    const map = buildMap()
    const on = handlers()

    attachMapTaps(map as unknown as MapLibreMap, on)
    map.emit('click', touchAt(400, 400))

    expect(on.onSelectPoi).toHaveBeenCalledWith(null)
    expect(on.onSelectWarning).toHaveBeenCalledWith(null)
    expect(on.onSelectClosure).toHaveBeenCalledWith(null)
  })

  it('asks only about its layers, so a touch on a trail line opens nothing', () => {
    const map = buildMap()
    map.renderedFeatures.set('trail-lines', [{ properties: { blaze: 'White' } }])
    const on = handlers()

    attachMapTaps(map as unknown as MapLibreMap, on)
    map.emit('click', touchAt(50, 50))

    expect(on.onSelectPoi).toHaveBeenCalledWith(null)
    for (const query of map.featureQueries) {
      expect(query.layers).not.toContain('trail-lines')
    }
  })

  it('allows for a thumb: a touch beside the pin still opens it', () => {
    // The pins are drawn at 38px and this app is used with gloves on, in rain,
    // one-handed. A hit area of exactly the pin means a pin that mostly does
    // nothing, which is the state this feature replaces.
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])

    attachMapTaps(map as unknown as MapLibreMap, { onSelectPoi: vi.fn() })
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
    const on = handlers()

    attachMapTaps(map as unknown as MapLibreMap, on)
    map.emit('click', touchAt(100, 100))

    expect(on.onSelectPoi).toHaveBeenCalledTimes(1)
    expect(on.onSelectPoi).toHaveBeenCalledWith('opentrail_at:spring')
  })

  it('never queries a map whose layers have not been built yet', () => {
    // Querying a layer the style does not hold fires an error event in real
    // MapLibre. A touch on a map with nothing on it yet is bare map - a
    // dismissal, not an error and not a warning in the console.
    const map = buildMap()
    map.layerIds = []
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])
    const on = handlers()

    attachMapTaps(map as unknown as MapLibreMap, on)
    map.emit('click', touchAt(100, 100))

    expect(on.onSelectPoi).toHaveBeenCalledWith(null)
    expect(map.featureQueries).toHaveLength(0)
  })

  it('treats a pin carrying no id as bare map, rather than opening an empty card', () => {
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [{ properties: { poi_type: 'water' } }])
    const on = handlers()

    attachMapTaps(map as unknown as MapLibreMap, on)
    map.emit('click', touchAt(100, 100))

    expect(on.onSelectPoi).toHaveBeenCalledWith(null)
  })
})

describe('one touch, one answer', () => {
  // The three tappable layers genuinely overlap: a warning pin sits over the
  // POI pins, and both sit over a closure band along the same stretch. A
  // touch that opened two sheets would stack dialogs - so the dispatcher
  // answers once, top of the draw order first, and tells the losers null.

  it('gives a warning pin the tap when it covers a POI pin', () => {
    const map = buildMap()
    map.renderedFeatures.set(WARNING_LAYER_ID, [warning('report-1')])
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])
    const on = handlers()

    attachMapTaps(map as unknown as MapLibreMap, on)
    map.emit('click', touchAt(100, 100))

    expect(on.onSelectWarning).toHaveBeenCalledWith('report-1')
    expect(on.onSelectPoi).toHaveBeenCalledWith(null)
    expect(on.onSelectClosure).toHaveBeenCalledWith(null)
  })

  it('gives a POI pin the tap when it sits on a closure band', () => {
    // A shelter beside a closed stretch is still somewhere to sleep - the
    // pin is drawn over the band, so it wins the tap too.
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])
    map.renderedFeatures.set(CLOSURE_LAYER_ID, [band('closure-1')])
    const on = handlers()

    attachMapTaps(map as unknown as MapLibreMap, on)
    map.emit('click', touchAt(100, 100))

    expect(on.onSelectPoi).toHaveBeenCalledWith('atc_shelters:abc')
    expect(on.onSelectClosure).toHaveBeenCalledWith(null)
  })

  it('opens the closure sheet from a tap on the bare band', () => {
    const map = buildMap()
    map.renderedFeatures.set(CLOSURE_LAYER_ID, [band('closure-1')])
    const on = handlers()

    attachMapTaps(map as unknown as MapLibreMap, on)
    map.emit('click', touchAt(100, 100))

    expect(on.onSelectClosure).toHaveBeenCalledWith('closure-1')
    expect(on.onSelectPoi).toHaveBeenCalledWith(null)
    expect(on.onSelectWarning).toHaveBeenCalledWith(null)
  })

  it('gives the band the same thumb allowance the pins get', () => {
    // Ten pixels of line is not a touch target. The slop is what brings it
    // up to one, derived from the band width the same way the pin slop is
    // derived from the pin size.
    const map = buildMap()
    map.renderedFeatures.set(CLOSURE_LAYER_ID, [band('closure-1')])

    attachMapTaps(map as unknown as MapLibreMap, { onSelectClosure: vi.fn() })
    map.emit('click', touchAt(100, 100))

    expect(map.featureQueries.at(-1)?.geometry).toEqual([
      [100 - CLOSURE_TAP_SLOP_PX, 100 - CLOSURE_TAP_SLOP_PX],
      [100 + CLOSURE_TAP_SLOP_PX, 100 + CLOSURE_TAP_SLOP_PX],
    ])
    expect(CLOSURE_TAP_SLOP_PX).toBeGreaterThan(POI_TAP_SLOP_PX)
  })

  it('skips a layer nobody is handling rather than asking and discarding', () => {
    const map = buildMap()
    map.renderedFeatures.set(WARNING_LAYER_ID, [warning('report-1')])
    const onSelectPoi = vi.fn()

    attachMapTaps(map as unknown as MapLibreMap, { onSelectPoi })
    map.emit('click', touchAt(100, 100))

    // No warning handler, so the warning layer was never queried and the
    // tap fell through to the POI question.
    for (const query of map.featureQueries) {
      expect(query.layers).not.toContain(WARNING_LAYER_ID)
    }
    expect(onSelectPoi).toHaveBeenCalledWith(null)
  })
})

describe('the pointer over the map', () => {
  it('shows the map is tappable there, and only there', () => {
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])

    attachMapTaps(map as unknown as MapLibreMap, handlers())

    map.emit('mousemove', touchAt(100, 100))
    expect(map.getCanvas().style.cursor).toBe('pointer')

    map.renderedFeatures.set(POI_LAYER_ID, [])
    map.emit('mousemove', touchAt(400, 400))
    expect(map.getCanvas().style.cursor).toBe('')
  })

  it('points over a closure band too - it opens a sheet, so it must look like it', () => {
    const map = buildMap()
    map.renderedFeatures.set(CLOSURE_LAYER_ID, [band('closure-1')])

    attachMapTaps(map as unknown as MapLibreMap, handlers())
    map.emit('mousemove', touchAt(100, 100))

    expect(map.getCanvas().style.cursor).toBe('pointer')
  })
})

describe('detaching', () => {
  it('leaves nothing listening, so a rebuilt map is not answered twice', () => {
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])
    const on = handlers()

    const detach = attachMapTaps(map as unknown as MapLibreMap, on)
    detach()
    map.emit('click', touchAt(100, 100))

    expect(on.onSelectPoi).not.toHaveBeenCalled()
    expect(map.listenerCount('click')).toBe(0)
    expect(map.listenerCount('mousemove')).toBe(0)
  })

  it('puts the cursor back, so it does not outlive what it pointed at', () => {
    const map = buildMap()
    map.renderedFeatures.set(POI_LAYER_ID, [pin('atc_shelters:abc')])

    const detach = attachMapTaps(map as unknown as MapLibreMap, handlers())
    map.emit('mousemove', touchAt(100, 100))
    detach()

    expect(map.getCanvas().style.cursor).toBe('')
  })
})
