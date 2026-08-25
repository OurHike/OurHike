import { describe, it, expect } from 'vitest'
import { MockMap } from '../test/mocks/maplibre-gl'
import { drawsNearbyTrails, TRAIL_SOURCE_PROPERTY } from './drawnBlazes'
import { BLAZE_LAYER_ID } from './style'
import type { Map as MapLibreMap } from 'maplibre-gl'

// What the map is drawing on its trail-line layer (#783). Shaped on
// drawnPois.test.ts, because the module is shaped on drawnPois.ts.
//
// This file also covered `drawnBlazeCounts` and its tile de-duplication, which
// went with the legend's blaze rows on 2026-08-25 - chrome/Legend.tsx's header
// has the decision. Nothing left here needs de-duplicating: the one question
// this module still answers stops at the first match, so a trail counted once
// per tile it crosses gives the same boolean as a trail counted once.

function mapWith(
  features: unknown[],
  layers: { id: string }[] = [{ id: BLAZE_LAYER_ID }],
) {
  const map = new MockMap({ style: { layers, sources: { trails: {} } } })
  map.renderedFeatures.set(BLAZE_LAYER_ID, features)
  return map as unknown as MapLibreMap
}

describe('drawsNearbyTrails', () => {
  // The legend's ghosting sentence asks exactly one question (#783): is any
  // line on screen not the chosen system's? A boolean, not a count - the
  // sentence explains a state rather than reporting a quantity.

  function sourced(id: number, source: string) {
    return { id, properties: { [TRAIL_SOURCE_PROPERTY]: source } }
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
    // The cold-start answer: on a first frame the legend should say nothing
    // about ghosting rather than explain a state the map has not drawn.
    const map = mapWith([sourced(1, 'oprhp_trails')], [])

    expect(drawsNearbyTrails(map)).toBe(false)
  })

  it('does not treat a feature missing its source as a nearby trail', () => {
    // Same asymmetry map/nearbyTrails.ts argues: a pipeline fault is not a
    // second network, and a legend sentence conjured by one would explain a
    // dimming that is not on screen.
    const map = mapWith([{ id: 1, properties: { name: 'Some Trail' } }])

    expect(drawsNearbyTrails(map)).toBe(false)
  })
})
