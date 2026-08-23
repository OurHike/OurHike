import { describe, it, expect } from 'vitest'
import { MockMap } from '../test/mocks/maplibre-gl'
import {
  drawnBlazeCounts,
  drawsNearbyTrails,
  BLAZE_COLOR_PROPERTY,
  TRAIL_SOURCE_PROPERTY,
} from './drawnBlazes'
import { BLAZE_LAYER_ID } from './style'
import type { Map as MapLibreMap } from 'maplibre-gl'

// The legend's blaze rows, finally fed (#782). Shaped on drawnPois.test.ts,
// because the module is shaped on drawnPois.ts and shares both of its traps.
//
// The de-duplication test is the one that matters most here and does NOT
// matter as much there: a waypoint is a point, so it lands in two tiles only
// by sitting near a boundary, while a trail is a line and is split across
// every tile it crosses. Counting features rather than trails would report a
// blaze count several times the real one on exactly the long trails a hiker
// most wants counted.

function mapWith(
  features: unknown[],
  layers: { id: string }[] = [{ id: BLAZE_LAYER_ID }],
) {
  const map = new MockMap({ style: { layers, sources: { trails: {} } } })
  map.renderedFeatures.set(BLAZE_LAYER_ID, features)
  return map as unknown as MapLibreMap
}

function line(id: string | number | undefined, blaze: string) {
  return { id, properties: { [BLAZE_COLOR_PROPERTY]: blaze } }
}

describe('drawnBlazeCounts', () => {
  it('counts the distinct trails of each blaze in view', () => {
    const map = mapWith([line(1, 'White'), line(2, 'Blue'), line(3, 'Blue')])

    expect(drawnBlazeCounts(map)).toEqual(
      new Map([
        ['White', 1],
        ['Blue', 2],
      ]),
    )
  })

  it('counts one trail once however many tiles it crosses', () => {
    // A GeoJSON source is tiled internally, so a long line comes back per
    // tile. Naively counted, the AT would report as dozens of white trails.
    const map = mapWith([line(7, 'White'), line(7, 'White'), line(7, 'White')])

    expect(drawnBlazeCounts(map)).toEqual(new Map([['White', 1]]))
  })

  it('counts a feature with no id rather than dropping it', () => {
    // An over-count is a wrong number; a dropped trail is a missing row, and
    // a legend that omits a blaze the map is drawing is the worse of the two.
    const map = mapWith([line(undefined, 'Aqua'), line(undefined, 'Aqua')])

    expect(drawnBlazeCounts(map)).toEqual(new Map([['Aqua', 2]]))
  })

  it('picks up a palette member admitted later, with no change here', () => {
    // #782 makes this a completion condition: "the legend's blaze rows pick
    // up new members automatically or this issue is not done". Nothing in
    // this module names a colour, so Aqua counts the day a trail wears it.
    const map = mapWith([line(1, 'Aqua'), line(2, 'Aqua')])

    expect(drawnBlazeCounts(map).get('Aqua')).toBe(2)
  })

  it('ignores a feature carrying no blaze at all', () => {
    const map = mapWith([line(1, 'White'), { id: 2, properties: {} }, { id: 3 }])

    expect(drawnBlazeCounts(map)).toEqual(new Map([['White', 1]]))
  })

  it('says nothing at all when the blaze layer is not in the style yet', () => {
    // A real cold-start state, and it has to read downstream as "nothing to
    // say" rather than as "no blazes here". Querying a layer the style does
    // not hold fires an error event rather than throwing, so the check is
    // what stops this answering zero with a console warning beside it.
    const map = mapWith([line(1, 'White')], [{ id: 'something-else' }])

    expect(drawnBlazeCounts(map)).toEqual(new Map())
  })
})

describe('drawsNearbyTrails', () => {
  // The legend's ghosting sentence asks exactly one question (#783): is any
  // line on screen not the chosen system's? A boolean, not a count - the
  // sentence explains a state rather than reporting a quantity.

  function sourced(id: number, source: string) {
    return {
      id,
      properties: { [BLAZE_COLOR_PROPERTY]: 'Blue', [TRAIL_SOURCE_PROPERTY]: source },
    }
  }

  it('is false on an A.T.-only map, however many side trails are drawn', () => {
    const map = mapWith([sourced(1, 'centerline'), sourced(2, 'side_trails')])

    expect(drawsNearbyTrails(map)).toBe(false)
  })

  it('is true as soon as one trail from another network is drawn', () => {
    const map = mapWith([sourced(1, 'centerline'), sourced(2, 'oprhp_trails')])

    expect(drawsNearbyTrails(map)).toBe(true)
  })

  it('is false before the style holds the blaze layer, rather than explaining an undrawn state', () => {
    // The cold-start answer, and it matches drawnBlazeCounts's empty map: on a
    // first frame the legend should say nothing about ghosting.
    const map = mapWith([sourced(1, 'oprhp_trails')], [])

    expect(drawsNearbyTrails(map)).toBe(false)
  })

  it('does not treat a feature missing its source as a nearby trail', () => {
    // Same asymmetry map/nearbyTrails.ts argues: a pipeline fault is not a
    // second network, and a legend sentence conjured by one would explain a
    // dimming that is not on screen.
    const map = mapWith([{ id: 1, properties: { [BLAZE_COLOR_PROPERTY]: 'White' } }])

    expect(drawsNearbyTrails(map)).toBe(false)
  })
})
