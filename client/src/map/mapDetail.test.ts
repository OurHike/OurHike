import { describe, it, expect } from 'vitest'
import { DETAIL_HIDDEN_LAYERS, DETAIL_MANAGED_LAYERS, attachMapDetail } from './mapDetail'
import { LIVE_TOPO_LAYER_IDS } from './liveTopo'
import { MockMap } from '../test/mocks/maplibre-gl'

// MAP_STYLE_SPEC.md's detail matrix, asserted per level as the spec asks.
// These are cartographic decisions, not implementation details: which layers
// a level drops decides what a hiker stops seeing, so each level's exact set
// is pinned rather than derived.

describe('the detail matrix', () => {
  it('hides nothing at full - the whole sheet, borders included', () => {
    expect(DETAIL_HIDDEN_LAYERS.full).toEqual([])
  })

  it('hides exactly the admin borders at standard', () => {
    // Wanted sometimes, distracting mostly - and standard is the default, so
    // this line is what everyone on the defaults sees.
    expect([...DETAIL_HIDDEN_LAYERS.standard].sort()).toEqual(
      [LIVE_TOPO_LAYER_IDS.boundary].sort(),
    )
  })

  it('hides the fine grain at minimal, and only the fine grain', () => {
    expect([...DETAIL_HIDDEN_LAYERS.minimal].sort()).toEqual(
      [
        LIVE_TOPO_LAYER_IDS.boundary,
        LIVE_TOPO_LAYER_IDS.track,
        LIVE_TOPO_LAYER_IDS.roadMinor,
        LIVE_TOPO_LAYER_IDS.contour,
        LIVE_TOPO_LAYER_IDS.contourLabel,
        LIVE_TOPO_LAYER_IDS.waterLabel,
        LIVE_TOPO_LAYER_IDS.scrub,
      ].sort(),
    )
  })

  it('keeps terrain and navigation out of reach of every level', () => {
    // The spec's own floor: index contours so the land still has shape, paths
    // because a side trail is hiker signal, and the layers a hiker orients by
    // - peaks, places, water, major roads. A level that could hide one of
    // these has stopped being a detail control.
    for (const kept of [
      LIVE_TOPO_LAYER_IDS.contourIndex,
      LIVE_TOPO_LAYER_IDS.path,
      LIVE_TOPO_LAYER_IDS.peak,
      LIVE_TOPO_LAYER_IDS.place,
      LIVE_TOPO_LAYER_IDS.roadMajor,
      LIVE_TOPO_LAYER_IDS.water,
      LIVE_TOPO_LAYER_IDS.waterway,
      LIVE_TOPO_LAYER_IDS.wood,
      LIVE_TOPO_LAYER_IDS.hillshade,
    ]) {
      expect(DETAIL_MANAGED_LAYERS, kept).not.toContain(kept)
    }
  })

  it('nests the levels: everything standard hides, minimal hides too', () => {
    for (const layer of DETAIL_HIDDEN_LAYERS.standard) {
      expect(DETAIL_HIDDEN_LAYERS.minimal).toContain(layer)
    }
  })
})

describe('attachMapDetail', () => {
  const liveSheet = () => {
    const m = new MockMap({})
    m.layerIds = [LIVE_TOPO_LAYER_IDS.wood, ...DETAIL_MANAGED_LAYERS]
    return m
  }

  it('writes every managed layer, hidden or shown, so a level change restores', () => {
    // `visibility` is sticky: a loop that only wrote `none` would make the
    // detail control a one-way ratchet, minimal forever.
    const m = liveSheet()

    attachMapDetail(m as never, 'minimal')
    for (const layer of DETAIL_MANAGED_LAYERS) {
      expect(m.layoutProperties.get(`${layer}/visibility`)).toBe('none')
    }

    attachMapDetail(m as never, 'full')
    for (const layer of DETAIL_MANAGED_LAYERS) {
      expect(m.layoutProperties.get(`${layer}/visibility`)).toBe('visible')
    }
  })

  it('leaves the layers standard keeps alone in the hidden sense, not the write sense', () => {
    const m = liveSheet()

    attachMapDetail(m as never, 'standard')

    expect(m.layoutProperties.get(`${LIVE_TOPO_LAYER_IDS.boundary}/visibility`)).toBe(
      'none',
    )
    expect(m.layoutProperties.get(`${LIVE_TOPO_LAYER_IDS.track}/visibility`)).toBe(
      'visible',
    )
  })

  it('rebuilds nothing - detail is visibility, never a style swap', () => {
    const m = liveSheet()

    attachMapDetail(m as never, 'minimal')

    expect(m.styles).toEqual([])
  })

  it('skips the terrain layers a style built without a DEM does not have', () => {
    // The probe is the wood layer; proving it exists proves nothing about the
    // contour layers the no-terrain filter dropped, and the mock throws on a
    // write to an absent layer exactly as MapLibre does.
    const m = new MockMap({})
    m.layerIds = [
      LIVE_TOPO_LAYER_IDS.wood,
      LIVE_TOPO_LAYER_IDS.boundary,
      LIVE_TOPO_LAYER_IDS.track,
      LIVE_TOPO_LAYER_IDS.roadMinor,
      LIVE_TOPO_LAYER_IDS.waterLabel,
      LIVE_TOPO_LAYER_IDS.scrub,
    ]

    attachMapDetail(m as never, 'minimal')

    expect(m.layoutProperties.get(`${LIVE_TOPO_LAYER_IDS.boundary}/visibility`)).toBe(
      'none',
    )
    expect(
      m.layoutProperties.get(`${LIVE_TOPO_LAYER_IDS.contour}/visibility`),
    ).toBeUndefined()
  })

  it('leaves an offline-background style alone', async () => {
    // None of the sheet's layers is in it, which is a normal state rather
    // than a failure - the wait simply never resolves and detach ends it.
    const m = new MockMap({})
    m.layerIds = ['backdrop', 'topo']

    const detach = attachMapDetail(m as never, 'minimal')
    m.emit('styledata')
    detach()

    expect(m.layoutProperties.size).toBe(0)
  })
})
