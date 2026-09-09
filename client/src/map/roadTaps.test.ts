// A tap that landed on a road (#931).
//
// WHAT THIS SUITE IS REALLY PINNING is a copy rule with a safety edge on it,
// so the assertions are about what the sentence SAYS as much as about what the
// query finds. The refusal has to name what the hiker tapped, say the app has
// no evidence about it, and say what they can do instead - and it must not,
// in any wording, imply the road is safe to walk or unsafe to walk. That
// judgement is MAP_OPTIONS.md §2's tiers, which stay unbuilt for want of
// evidence, and a sentence here that leant either way would be making the
// claim the whole module refuses to make.

import { beforeEach, describe, expect, it } from 'vitest'

import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { LIVE_TOPO_LAYER_IDS } from './liveTopo'
import { roadRefusal, tappedRoadAt } from './roadTaps'

function buildMap(): MockMap {
  const map = new MockMap({})
  map.layerIds = [
    LIVE_TOPO_LAYER_IDS.track,
    LIVE_TOPO_LAYER_IDS.roadMinor,
    LIVE_TOPO_LAYER_IDS.roadMajor,
  ]
  return map
}

function feature(layer: string, name: string | null) {
  return {
    properties: name === null ? {} : { name },
    layer: { id: layer },
    geometry: { type: 'LineString', coordinates: [] },
  }
}

beforeEach(() => {
  resetMapLibreMock()
})

describe('what the tap found', () => {
  it('names the road when OSM named it', () => {
    const map = buildMap()
    map.renderedFeatures.set(LIVE_TOPO_LAYER_IDS.roadMajor, [
      feature(LIVE_TOPO_LAYER_IDS.roadMajor, 'Seven Lakes Drive'),
    ])

    expect(tappedRoadAt(map as never, { x: 10, y: 10 })).toEqual({
      name: 'Seven Lakes Drive',
      kind: 'road',
    })
  })

  it('reports an unnamed one as unnamed rather than inventing a name', () => {
    // Most forest roads and tracks are unnamed. "Unnamed road" would read as
    // a data error rather than the ordinary state it is.
    const map = buildMap()
    map.renderedFeatures.set(LIVE_TOPO_LAYER_IDS.track, [
      feature(LIVE_TOPO_LAYER_IDS.track, null),
    ])

    expect(tappedRoadAt(map as never, { x: 10, y: 10 })).toEqual({
      name: null,
      kind: 'track',
    })
  })

  it('prefers a named feature at the same touch', () => {
    // The sentence is worth much more with a name in it: "Seven Lakes Drive
    // is a road" tells a hiker where they are, "that's a road" tells them
    // what they could already see.
    const map = buildMap()
    map.renderedFeatures.set(LIVE_TOPO_LAYER_IDS.roadMinor, [
      feature(LIVE_TOPO_LAYER_IDS.roadMinor, null),
      feature(LIVE_TOPO_LAYER_IDS.roadMinor, 'Tiorati Brook Road'),
    ])

    expect(tappedRoadAt(map as never, { x: 10, y: 10 })?.name).toBe('Tiorati Brook Road')
  })

  it('finds nothing on a sheet that draws no roads', () => {
    // The downloaded raster, or a style with the live layers off. The builder
    // falls back to its own off-network sentence, which is honest when the
    // app cannot see what the hiker is pointing at either.
    const map = buildMap()
    map.layerIds = []

    expect(tappedRoadAt(map as never, { x: 10, y: 10 })).toBeNull()
  })

  it('asks only for the layers the style holds', () => {
    // Querying a layer the style does not hold fires an error event rather
    // than throwing - the guard poiTaps.ts states and lineTaps.ts repeats.
    const map = buildMap()
    map.layerIds = [LIVE_TOPO_LAYER_IDS.roadMajor]
    map.renderedFeatures.set(LIVE_TOPO_LAYER_IDS.roadMajor, [
      feature(LIVE_TOPO_LAYER_IDS.roadMajor, 'Route 202'),
    ])

    tappedRoadAt(map as never, { x: 10, y: 10 })

    expect(map.featureQueries.at(-1)?.layers).toEqual([LIVE_TOPO_LAYER_IDS.roadMajor])
  })
})

describe('what it tells the hiker', () => {
  it('names the road, and says the app has no evidence rather than no interest', () => {
    const said = roadRefusal({ name: 'Seven Lakes Drive', kind: 'road' })

    expect(said).toContain('Seven Lakes Drive is a road')
    expect(said).toContain('no organization maintains it for walking')
  })

  it('says what the hiker can do instead', () => {
    // #935's segments model is the answer, and a refusal that does not name
    // it leaves somebody stuck at a loop they know how to close.
    expect(roadRefusal({ name: null, kind: 'road' })).toContain('start a new stretch')
  })

  it('tells a track from a road, because they read differently on the ground', () => {
    expect(roadRefusal({ name: null, kind: 'track' })).toContain("That's a track")
    expect(roadRefusal({ name: null, kind: 'road' })).toContain("That's a road")
  })

  it('makes no claim either way about whether it can be walked', () => {
    // THE LOAD-BEARING ASSERTION. A road with a shoulder and a road with a
    // guardrail at 55 mph are the same OSM line class, so the app has no
    // basis for "safe", "dangerous", "busy" or "quiet" - and MAP_OPTIONS.md
    // §2's tiers stay unbuilt for exactly that reason.
    for (const road of [
      { name: 'Seven Lakes Drive', kind: 'road' as const },
      { name: null, kind: 'track' as const },
    ]) {
      const said = roadRefusal(road).toLowerCase()
      for (const forbidden of [
        'safe',
        'dangerous',
        'busy',
        'quiet',
        'shoulder',
        'traffic',
        'careful',
      ]) {
        expect(said).not.toContain(forbidden)
      }
    }
  })
})
