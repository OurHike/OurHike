import { describe, it, expect } from 'vitest'
import { buildMapStyle } from './style'
import { POI_DOT_LAYER_ID, POI_LAYER_ID, POI_STALENESS_LAYER_ID } from './poiLayers'
import { POI_LABEL_LAYER_ID } from './poiLabels'
import { DISPUTE_LAYER_ID } from './disputeLayers'
import { WAYPOINT_LAYER_IDS } from './waypointLayerVisibility'

/**
 * The lever behind the legend picker's "None" (2026-09-20).
 *
 * What is worth pinning here is not the flip - `setLayoutProperty` does that -
 * but the LIST. A waypoint layer added later and left out of it would keep
 * drawing after a hiker switched the points off, and nothing else in the tree
 * would notice.
 */
describe('which layers the waypoint gate reaches', () => {
  it('names every waypoint layer the style builds, and nothing else', () => {
    // Derived from the style rather than restated, so a new waypoint rank
    // fails here instead of silently escaping the switch. The prefix is the
    // detector; the list is the decision.
    const built = buildMapStyle({ background: 'offline_topo' } as never)
    const waypointish = built.layers
      .map((layer) => layer.id)
      .filter((id) => id.startsWith('poi-'))

    for (const id of waypointish) {
      expect({ id, reached: WAYPOINT_LAYER_IDS.includes(id) }).toEqual({
        id,
        reached: true,
      })
    }
    // And every id in the list is real, so the switch cannot be quietly
    // pointing at a layer that was renamed out from under it.
    const ids = built.layers.map((layer) => layer.id)
    for (const id of WAYPOINT_LAYER_IDS) {
      expect({ id, inStyle: ids.includes(id) }).toEqual({ id, inStyle: true })
    }
  })

  it('carries all three ranks, the names and the dispute marks', () => {
    // Spelled out as well as derived: the derivation above would still pass if
    // the style lost a rank and the list lost it too, which is the one way
    // both halves can agree and be wrong.
    expect([...WAYPOINT_LAYER_IDS].sort()).toEqual(
      [
        POI_LABEL_LAYER_ID,
        POI_DOT_LAYER_ID,
        POI_STALENESS_LAYER_ID,
        POI_LAYER_ID,
        DISPUTE_LAYER_ID,
      ].sort(),
    )
  })

  it('leaves the safety layers alone, because the switch is about waypoints', () => {
    // A hiker switching waypoints off is asking for a cleaner map, not for
    // the closures and the serious warnings to go with them. Those are the
    // marks CLAUDE.md's "four ways this app can hurt somebody" turns on, and
    // no control on this screen may take them away.
    for (const id of ['closure-band', 'serious-warning-pins', 'work-project-pins']) {
      expect({ id, reached: WAYPOINT_LAYER_IDS.includes(id) }).toEqual({
        id,
        reached: false,
      })
    }
  })
})
