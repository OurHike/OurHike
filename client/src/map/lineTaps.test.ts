import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { ATC_UPDATE_LAYER_ID } from '../lib/atcUpdateStyle'
import { ATC_UPDATE_ID_PROPERTY } from './atcUpdateLayers'
import { POI_ID_PROPERTY, POI_LAYER_ID } from './poiLayers'
import { BLAZE_LAYER_ID } from './style'
import { CORRIDOR_HIGHLIGHT_LAYER_ID, HIGHLIGHT_ID_PROPERTY } from './corridorLayers'
import { attachLineTaps, LINE_TAP_SLOP_PX, tappedLineAt } from './lineTaps'

// The behaviour under test is "a hiker touches a trail line and the shell
// learns which line that was" (#134) - so these drive real events through
// the map, as poiTaps.test.ts does, and assert on what the shell is told.

function buildMap(): MockMap {
  const map = new MockMap({})
  map.layerIds = [
    BLAZE_LAYER_ID,
    POI_LAYER_ID,
    ATC_UPDATE_LAYER_ID,
    CORRIDOR_HIGHLIGHT_LAYER_ID,
  ]
  return map
}

function line(
  id: string,
  source: string,
  blaze = 'Blue',
  name: string | null = null,
  coordinates: Array<[number, number]> = [],
) {
  return {
    properties: { id, source, name, blaze_color: blaze },
    geometry: { type: 'LineString', coordinates },
  }
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
      lengthMiles: null,
      park: null,
      trailStatus: null,
      // No geometry on this fixture, so there is nothing to snap to and the
      // touch itself is the honest answer - the mock projects identically.
      at: [120, 240],
    })
  })

  it('carries a nearby trail’s length, park and status through to the sheet', () => {
    // The data path #783 needs end to end: the network artifact publishes
    // these three, and a sheet that cannot see them says nothing about a
    // trail's extent or its closure. Named with the pipeline's normalized
    // keys, not OPRHP's own Miles/Unit/Status columns.
    const map = buildMap()
    const onSelect = vi.fn()
    map.renderedFeatures.set(BLAZE_LAYER_ID, [
      {
        properties: {
          id: 'oprhp_trails:8812',
          source: 'oprhp_trails',
          name: 'Suffern–Bear Mountain Trail',
          blaze_color: 'Yellow',
          length_miles: 24,
          park: 'Harriman State Park',
          trail_status: 'Closed',
        },
        geometry: { type: 'LineString', coordinates: [] },
      },
    ])
    attachLineTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(10, 10))

    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({
        source: 'oprhp_trails',
        lengthMiles: 24,
        park: 'Harriman State Park',
        trailStatus: 'Closed',
      }),
    )
  })

  it('refuses a length that arrives as text rather than coercing it', () => {
    // A figure arriving as a string means the export changed shape. Coercing
    // it would hide that behind a plausible number on a sheet a hiker reads
    // to decide whether to walk somewhere.
    const map = buildMap()
    const onSelect = vi.fn()
    map.renderedFeatures.set(BLAZE_LAYER_ID, [
      {
        properties: {
          id: 'oprhp_trails:8813',
          source: 'oprhp_trails',
          name: null,
          blaze_color: 'Red',
          length_miles: '24',
        },
        geometry: { type: 'LineString', coordinates: [] },
      },
    ])
    attachLineTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(10, 10))

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ lengthMiles: null }))
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
      // An A.T. line publishes none of the nearby-trail facts (#783), and
      // reads them as absent rather than as zero or "Unknown".
      lengthMiles: null,
      park: null,
      trailStatus: null,
      at: [10, 10],
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

/**
 * `at` exists so the corridor view can turn a tap into a MILE (#598), and it
 * is snapped to the line rather than being the touch itself.
 *
 * The reason is the seam. LINE_TAP_SLOP_PX is about a thumb's width at every
 * zoom, but in ground terms it is roughly 90 miles at the corridor view's
 * opening camera - where one pixel spans some 4.6 miles. lib/trailPosition.ts
 * refuses anything more than MAX_OFF_TRAIL_MILES (3) from the centerline, so
 * an unsnapped point would be rejected for most of the taps this exists to
 * serve, and the club sheet would simply not open.
 */
describe('where the tap landed on the line', () => {
  it('snaps to the line’s nearest vertex, not to the touch', () => {
    const map = buildMap()
    map.renderedFeatures.set(BLAZE_LAYER_ID, [
      line('centerline:chain:0', 'centerline', 'White', null, [
        [100, 200],
        [130, 260],
        [160, 320],
      ]),
    ])
    const onSelect = vi.fn()

    attachLineTaps(map as unknown as MapLibreMap, onSelect)
    // The mock projects identically, so this touch is 5 units from the middle
    // vertex and further from both others.
    map.emit('click', touchAt(133, 264))

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ at: [130, 260] }))
  })

  it('walks every part of a MultiLineString, which the real geometry has', () => {
    // export_trails.py's geometry_to_wkt makes the same point: treating the
    // two shapes as one is how real trail mileage gets dropped.
    const map = buildMap()
    map.renderedFeatures.set(BLAZE_LAYER_ID, [
      {
        properties: {
          id: 'centerline:chain:1',
          source: 'centerline',
          blaze_color: 'White',
        },
        geometry: {
          type: 'MultiLineString',
          coordinates: [
            [
              [10, 10],
              [20, 20],
            ],
            [
              [300, 300],
              [310, 310],
            ],
          ],
        },
      },
    ])
    const onSelect = vi.fn()

    attachLineTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(305, 302))

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ at: [300, 300] }))
  })

  it('falls back to the touch when the feature carries no coordinates', () => {
    // A clipped tile can hand back a feature whose geometry this cannot read.
    // The touch is then the only answer there is, and trailPosition will
    // decline it honestly if it is too far off the trail.
    const map = buildMap()
    map.renderedFeatures.set(BLAZE_LAYER_ID, [line('x', 'centerline', 'White')])
    const onSelect = vi.fn()

    attachLineTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(42, 43))

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ at: [42, 43] }))
  })
})

describe('yielding to a highlight mark (#858)', () => {
  it('reports no line when a highlight is under the thumb', () => {
    // A mark is a small, aimed-at target sitting ON the corridor, and the
    // line is always under it. Same rule the pins and the ATC notices get,
    // and it is also what dismisses an open line sheet when the hiker moves
    // on to a mark.
    const map = buildMap()
    map.renderedFeatures.set(BLAZE_LAYER_ID, [
      line('centerline:0', 'centerline', 'White'),
    ])
    map.renderedFeatures.set(CORRIDOR_HIGHLIGHT_LAYER_ID, [
      { properties: { [HIGHLIGHT_ID_PROPERTY]: 'mcafee-knob' } },
    ])
    const onSelect = vi.fn()

    attachLineTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(120, 240))

    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it('still answers with the line when no mark is there', () => {
    const map = buildMap()
    map.renderedFeatures.set(BLAZE_LAYER_ID, [
      line('centerline:0', 'centerline', 'White'),
    ])
    const onSelect = vi.fn()

    attachLineTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touchAt(120, 240))

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 'centerline:0' }))
  })
})
