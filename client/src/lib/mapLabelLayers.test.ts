// Tests for lib/mapLabelLayers.ts and map/labelLadder.ts - the builder's
// label toggles and the one ordering behind them (#1194).
//
// THE RULE THIS FILE EXISTS TO KEEP is that a toggle here takes off a LABEL
// and never a pin or a line. Three controls in this app hide things - the
// legend's waypoint filters, the sheet's detail level, and this - and giving
// two of them authority over one layer is how a toggle comes to look broken
// because another screen has already turned its target off.
//
// It also pins the rung that has NO DATA, so that adding a toggle for it
// fails here rather than shipping a switch that changes nothing. There were
// two; #1197 published the trailheads and filled the top one.

import { describe, expect, it } from 'vitest'

import {
  ALL_LABEL_LAYER_IDS,
  ALL_LABELS_SHOWN,
  BUILDER_ONLY_LAYER_IDS,
  hiddenPoiLabelTypes,
  labelVisibilityPlan,
  LABEL_LAYERS,
  labelLayerShown,
  tierBadge,
  toggleLabelLayer,
} from './mapLabelLayers'
import { LABEL_TIER, TIER_MIN_ZOOM, ZOOM_BAND_TEXT, zoomBand } from '../map/labelLadder'
import { LIVE_TOPO_LAYER_IDS, liveTopoLayers } from '../map/liveTopo'
import { POI_LAYER_ID, POI_DOT_LAYER_ID } from '../map/poiLayers'
import {
  NEARBY_TRAIL_CASING_LAYER_ID,
  BLAZE_LAYER_ID,
  TRAIL_CASING_LAYER_ID,
} from '../map/style'

/** map/liveTopo.test.ts's own fixture shape - the two tile templates the
 *  sheet needs to build its terrain layers. */
const TERRAIN = {
  demUrl: 'dem://shared/{z}/{x}/{y}',
  contourTilesUrl: 'contour://40ft/{z}/{x}/{y}',
}

describe('what the toggles have authority over', () => {
  it('never names a pin layer, only labels', () => {
    // A hiker who turns off "Campsites" here still sees campsite pins.
    for (const id of ALL_LABEL_LAYER_IDS) {
      expect(id).not.toBe(POI_LAYER_ID)
      expect(id).not.toBe(POI_DOT_LAYER_ID)
    }
  })

  it('never names a trail LINE layer, only trail names', () => {
    // The lines are map/style.ts's and map/mapDetail.ts's. Two controls over
    // one layer is the failure mode this asserts against.
    for (const id of ALL_LABEL_LAYER_IDS) {
      expect(id).not.toBe(BLAZE_LAYER_ID)
      expect(id).not.toBe(TRAIL_CASING_LAYER_ID)
      expect(id).not.toBe(NEARBY_TRAIL_CASING_LAYER_ID)
    }
  })

  it('never names the contour LINES, which is why the toggle is not called "Contours"', () => {
    // The toggle takes off the elevation FIGURES. A control named "Contours"
    // that left every contour drawn is a control a hiker stops trusting.
    expect(ALL_LABEL_LAYER_IDS).not.toContain(LIVE_TOPO_LAYER_IDS.contour)
    expect(ALL_LABEL_LAYER_IDS).not.toContain(LIVE_TOPO_LAYER_IDS.contourIndex)
    expect(ALL_LABEL_LAYER_IDS).toContain(LIVE_TOPO_LAYER_IDS.contourLabel)
  })

  it('names only layers the style actually builds', () => {
    // A toggle pointing at a layer id nothing draws is a switch that changes
    // nothing - the same failure as shipping the two rungs with no data.
    const built = new Set(
      liveTopoLayers({ terrain: TERRAIN, units: 'imperial' }).map((layer) => layer.id),
    )
    for (const id of ALL_LABEL_LAYER_IDS) {
      if (!id.startsWith('topo-')) continue
      expect(built, `${id} must be a layer the sheet builds`).toContain(id)
    }
  })

  it('offers no toggle for the one rung nothing publishes', () => {
    // Junctions exist only as graph nodes: pipeline/build_trail_graph.py
    // splits every line at every crossing, so they route the walk and nothing
    // publishes them as features. Recorded on #1194 and #1213 rather than
    // shipped as an inert switch.
    const keys = LABEL_LAYERS.map((spec) => spec.key)

    expect(keys).not.toContain('junctions')
  })

  it('offers the trailhead toggle now that something publishes trailheads', () => {
    // THIS ASSERTION IS THE DELETED HALF OF THE ONE ABOVE, and it is here
    // rather than absent because the rule was "if either ever gains data,
    // this line is where the toggle's arrival should be argued". The argument:
    // #1197 gave pipeline/lib/poi_schema.py a ninth type and OPRHP's 287
    // trailheads ship in `nearby_poi.geojson`, so the switch has features to
    // act on. It goes first in the row because it is the top rung of
    // map/labelLadder.ts - the class the whole ladder was ordered around.
    const keys = LABEL_LAYERS.map((spec) => spec.key)

    expect(keys[0]).toBe('trailheads')
    expect(LABEL_LAYERS[0].poiType).toBe('trailhead')
    expect(tierBadge(LABEL_LAYERS[0].tier)).toBe('T1')
  })
})

describe('the hidden set', () => {
  it('treats an absent key as shown', () => {
    expect(labelLayerShown(ALL_LABELS_SHOWN, 'parking')).toBe(true)
  })

  it('toggles off and back on', () => {
    const off = toggleLabelLayer(ALL_LABELS_SHOWN, 'roads')
    expect(labelLayerShown(off, 'roads')).toBe(false)

    expect(labelLayerShown(toggleLabelLayer(off, 'roads'), 'roads')).toBe(true)
  })

  it('does not mutate what it was handed', () => {
    const before = ALL_LABELS_SHOWN
    toggleLabelLayer(before, 'water')

    expect(labelLayerShown(before, 'water')).toBe(true)
  })

  it('reports a hidden waypoint class as a POI type, not a layer id', () => {
    const off = toggleLabelLayer(ALL_LABELS_SHOWN, 'shelters')

    expect(hiddenPoiLabelTypes(off)).toEqual(['shelter'])
    // One layer draws every waypoint name, so hiding a class is a filter -
    // there is no layer to switch off.
    expect(labelVisibilityPlan(off, true).hidden).toEqual([])
  })

  it('reports a hidden sheet class as a layer id, not a POI type', () => {
    const off = toggleLabelLayer(ALL_LABELS_SHOWN, 'roads')

    expect(labelVisibilityPlan(off, true).hidden).toEqual([LIVE_TOPO_LAYER_IDS.roadLabel])
    expect(hiddenPoiLabelTypes(off)).toEqual([])
  })

  it('hides nothing while building with nothing switched off', () => {
    expect(labelVisibilityPlan(ALL_LABELS_SHOWN, true).hidden).toEqual([])
    expect(hiddenPoiLabelTypes(ALL_LABELS_SHOWN)).toEqual([])
  })
})

describe('what happens when the builder closes', () => {
  // THE BUG THIS PINS: the shell used to say nothing at all when no walk was
  // being built, so the effect did nothing and every label the builder had
  // switched on stayed on over the walking map for the rest of the session.
  // A control whose OFF state is "no instruction" only ever turns things on.

  it('puts the pre-existing layers back, whatever the hiker had hidden', () => {
    const off = toggleLabelLayer(toggleLabelLayer(ALL_LABELS_SHOWN, 'trails'), 'water')
    const plan = labelVisibilityPlan(off, false)

    expect(plan.shown).toContain(LIVE_TOPO_LAYER_IDS.waterLabel)
    expect(plan.hidden).not.toContain(LIVE_TOPO_LAYER_IDS.waterLabel)
  })

  it('takes the builder’s own layers away again', () => {
    // Road names were added for the planning screen. #1135 settled what the
    // walking map draws without them, and this change does not reopen that.
    const plan = labelVisibilityPlan(ALL_LABELS_SHOWN, false)

    expect(plan.hidden).toEqual([...BUILDER_ONLY_LAYER_IDS])
  })

  it('accounts for every layer it owns, in both directions', () => {
    // Neither list may quietly drop one: a layer in neither keeps whatever
    // visibility it happened to have, which is the state this whole function
    // exists to stop.
    for (const building of [true, false]) {
      const plan = labelVisibilityPlan({ roads: true }, building)
      expect([...plan.shown, ...plan.hidden].sort()).toEqual(
        [...ALL_LABEL_LAYER_IDS].sort(),
      )
    }
  })
})

describe('the ladder', () => {
  it('runs lowest-wins, which is the direction symbol-sort-key reads', () => {
    // map/trailLabels.ts's header is the standing warning: `line-sort-key`
    // runs the other way, and copying one into the other gives the most
    // important thing the worst claim on space.
    expect(LABEL_TIER.gateway).toBeLessThan(LABEL_TIER.route)
    expect(LABEL_TIER.route).toBeLessThan(LABEL_TIER.routeTrail)
    expect(LABEL_TIER.routeTrail).toBeLessThan(LABEL_TIER.landmark)
    expect(LABEL_TIER.landmark).toBeLessThan(LABEL_TIER.junction)
    expect(LABEL_TIER.junction).toBeLessThan(LABEL_TIER.otherTrail)
    expect(LABEL_TIER.otherTrail).toBeLessThan(LABEL_TIER.rest)
  })

  it('puts the way IN to a trail above the furniture on it', () => {
    // The handoff's central claim about complaint #2, and the opposite of
    // map/poiPriority.ts's ordering - which is right about a different
    // question (a hiker already walking). Both orderings are deliberate.
    expect(LABEL_TIER.gateway).toBeLessThan(LABEL_TIER.landmark)
  })

  it('leaves room between rungs, so a layer can rank within its tier', () => {
    const rungs = Object.values(LABEL_TIER).sort((a, b) => a - b)
    for (let at = 1; at < rungs.length; at += 1) {
      expect(rungs[at] - rungs[at - 1]).toBeGreaterThan(1)
    }
  })

  it('pins the road label’s sort key to the gateway rung', () => {
    // map/liveTopo.ts restates the number as a literal rather than importing
    // it (labelLadder.ts must not depend on the sheet). This is the line that
    // keeps the two from drifting.
    const roads = liveTopoLayers({ terrain: TERRAIN, units: 'imperial' }).find(
      (layer) => layer.id === LIVE_TOPO_LAYER_IDS.roadLabel,
    )

    expect(roads).toBeDefined()
    expect((roads?.layout as Record<string, unknown>)['symbol-sort-key']).toBe(
      LABEL_TIER.gateway,
    )
  })

  it('names the band a zoom is in, and has words for each', () => {
    expect(zoomBand(TIER_MIN_ZOOM.gateway)).toBe('park')
    expect(zoomBand(TIER_MIN_ZOOM.landmark)).toBe('route')
    expect(zoomBand(TIER_MIN_ZOOM.junction)).toBe('section')

    for (const band of ['park', 'route', 'section'] as const) {
      expect(ZOOM_BAND_TEXT[band].length).toBeGreaterThan(0)
    }
  })

  it('brings the gateway tier in first, and the fine grain last', () => {
    expect(TIER_MIN_ZOOM.gateway).toBeLessThanOrEqual(TIER_MIN_ZOOM.landmark)
    expect(TIER_MIN_ZOOM.landmark).toBeLessThanOrEqual(TIER_MIN_ZOOM.junction)
  })
})

describe('the tier badge', () => {
  it('is the zoom band a class arrives in, not its collision rung', () => {
    // The distinction this got wrong first: it split at `routeTrail`, so
    // shelters and campsites wore T3 while the handoff puts them in z2 with
    // the trail names. Seven rungs are what collisions need; three bands are
    // what a hiker reads.
    expect(tierBadge('gateway')).toBe('T1')
    expect(tierBadge('landmark')).toBe('T2')
    expect(tierBadge('junction')).toBe('T3')
  })

  it('badges shelters and campsites together, and water apart from them', () => {
    // The handoff's own bands: z2 "route" adds shelters and campsites, z3
    // "section" adds "junction markers and water".
    const badge = (key: string) =>
      tierBadge(LABEL_LAYERS.find((spec) => spec.key === key)?.tier ?? 'rest')

    expect(badge('shelters')).toBe('T2')
    expect(badge('campsites')).toBe('T2')
    expect(badge('water')).toBe('T3')
    expect(badge('contours')).toBe('T3')
    expect(badge('parking')).toBe('T1')
    expect(badge('roads')).toBe('T1')
  })

  it('badges a class by when it ACTUALLY draws, even where that parts from the design', () => {
    // Trail names badge T1 rather than the handoff's T2, because
    // map/trailLabels.ts has drawn them from POI_PIN_MIN_ZOOM since #930 and
    // this change does not move them. A badge is a claim about the map, so it
    // has to follow the map.
    const trails = LABEL_LAYERS.find((spec) => spec.key === 'trails')

    expect(TIER_MIN_ZOOM[trails?.tier ?? 'rest']).toBe(TIER_MIN_ZOOM.gateway)
    expect(tierBadge(trails?.tier ?? 'rest')).toBe('T1')
  })

  it('gives every shipped toggle a badge', () => {
    for (const spec of LABEL_LAYERS) {
      expect(['T1', 'T2', 'T3']).toContain(tierBadge(spec.tier))
    }
  })
})
