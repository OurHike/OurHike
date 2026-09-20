import { describe, it, expect } from 'vitest'
import { SAFETY_LAYERS, NEVER_HIDEABLE } from './legendContents'
import {
  HIDEABLE_TYPES,
  DEFAULT_SHOWN_TYPES,
  hiddenTypesFrom,
  onlyType,
  showAllTypes,
  toggleType,
} from './waypointVisibility'
import { WAYPOINT_LAYER_IDS } from '../map/waypointLayerVisibility'
import { poiFilter, POI_PIN_MIN_ZOOM } from '../map/poiLayers'
import { POI_TYPES } from './config'
import { buildMapStyle } from '../map/style'
import { CLOSURE_LAYER_ID, LONG_TERM_CLOSURE_LAYER_ID } from './closureStyle'
import { WARNING_LAYER_ID } from '../map/warningLayers'

/**
 * Nothing in this app may take a closure or a serious warning off the map.
 *
 * The maintainer, 2026-09-20: *"Never hide the closures or serious warnings.
 * There should be tests that error when the closures are hidden."* This file
 * is that, and it is written to fail LOUDLY rather than to document - each
 * case names the mechanism it is guarding, so a red line here says which door
 * was left open rather than only that one was.
 *
 * WHY ONE FILE RATHER THAN A CASE IN EACH MODULE'S OWN TESTS. There are five
 * separate ways a mark can leave this map - a stored preference, the legend's
 * per-category rows, the Show points switch, the style's filter, and a
 * layer's own zoom floor - and they are owned by five modules that do not
 * import each other. A guarantee that has to hold across all five has nowhere
 * to live except a file that knows about all five. The cost is that this file
 * reaches across the tree; the alternative is five partial guarantees and no
 * whole one.
 *
 * WHAT THIS DOES NOT COVER, said here because a reader must not mistake this
 * file for the whole promise: the legend's Alerts switch (#1047) can take
 * these marks off the canvas for the life of one view. That is a deliberate,
 * live, hiker-operated control, held in a `useState` that nothing writes
 * down, so it resets the next time the app opens - which is the property the
 * maintainer's own constraint on #1047 asked for. It is the one exception,
 * and it is raised with the maintainer rather than quietly asserted here.
 */
describe('a closure or a serious warning can never be hidden', () => {
  it('names both safety layers, so this file cannot silently cover fewer', () => {
    // If a third safety layer is ever added, every case below picks it up
    // automatically - but only if it goes in SAFETY_LAYERS. This is the line
    // that makes that the one place to add it.
    expect([...SAFETY_LAYERS].sort()).toEqual(['closure', 'serious-warning'])
    for (const layer of SAFETY_LAYERS) {
      expect({ layer, guarded: NEVER_HIDEABLE.has(layer) }).toEqual({
        layer,
        guarded: true,
      })
    }
  })

  it('keeps them out of the categories the legend can switch off', () => {
    // The per-category rows. A safety layer that appeared here would have a
    // hide affordance the moment the legend rendered it.
    for (const layer of SAFETY_LAYERS) {
      expect({ layer, hideable: HIDEABLE_TYPES.includes(layer) }).toEqual({
        layer,
        hideable: false,
      })
      expect({ layer, shownByDefault: DEFAULT_SHOWN_TYPES.includes(layer) }).toEqual({
        layer,
        shownByDefault: false,
      })
    }
  })

  it('refuses to hide them from any stored preference, however it was written', () => {
    // THE CASE THIS GUARD EXISTS FOR, in the maintainer's own words on #1047:
    // "a thru-hiker whose phone opens with the alerts already off, for days,
    // having chosen it once." A stored value is the only thing that can
    // outlive the moment, so it is the only thing that can do that harm.
    //
    // Every shape a stored value can arrive in: empty, one category, a
    // hand-edited list naming a safety layer outright, and one from a client
    // that did not know these types existed.
    const stored: Array<readonly string[]> = [
      [],
      onlyType('water'),
      showAllTypes(),
      ['closure'],
      ['serious-warning'],
      ['water', 'closure', 'serious-warning'],
      toggleType(showAllTypes(), 'shelter'),
    ]

    for (const shown of stored) {
      const hidden = hiddenTypesFrom(shown)
      for (const layer of SAFETY_LAYERS) {
        expect({ shown: [...shown], layer, hidden: hidden.has(layer) }).toEqual({
          shown: [...shown],
          layer,
          hidden: false,
        })
      }
    }
  })

  it('puts them out of the waypoint filter’s reach by construction, not by stripping', () => {
    // A FIRST DRAFT OF THIS CASE ASSERTED THE WRONG THING, and the correction
    // is the more useful fact. It expected poiFilter to strip a safety layer
    // handed to it by name; it does not, and it does not need to - a closure
    // is not a POI at all. It reaches the map as a ClosureBand on its own
    // layer, never as a feature with a `poi_type`, so no value in the
    // waypoint filter can match one.
    //
    // That is a stronger guarantee than stripping would be: stripping can be
    // forgotten at one call site, and a type that does not exist in the
    // source cannot be filtered out of it anywhere.
    for (const layer of SAFETY_LAYERS) {
      expect({
        layer,
        isPoiType: (POI_TYPES as readonly string[]).includes(layer),
      }).toEqual({ layer, isPoiType: false })
    }
    // And the filter really is a filter on poi_type, so the sentence above is
    // about this expression rather than about filters in general.
    expect(JSON.stringify(poiFilter(new Set(['water'])))).toContain('poi_type')
  })

  it('keeps them out of reach of the Show points switch', () => {
    // The switch added on 2026-09-20 turns every waypoint layer off at once.
    // A hiker asking for a cleaner map is not asking for the closures to go
    // with it, and this is the line that stops the list growing to include
    // them by someone adding "every layer with a pin" to it.
    for (const id of [CLOSURE_LAYER_ID, LONG_TERM_CLOSURE_LAYER_ID, WARNING_LAYER_ID]) {
      expect({ id, reached: WAYPOINT_LAYER_IDS.includes(id) }).toEqual({
        id,
        reached: false,
      })
    }
  })

  it('draws them at every zoom, where the waypoints have a seam', () => {
    // The fifth door, and the one this branch opened: waypoints now stop at
    // POI_PIN_MIN_ZOOM. A safety layer that picked up a floor the same way
    // would be a closure invisible on the corridor view - exactly the camera
    // a hiker plans a resupply from.
    const built = buildMapStyle({ background: 'offline_topo' } as never)
    const LADDER = [0, 2, 4.9, 6, 6.9, 7, 7.1, 8, 9, 12, 16, 22]

    for (const id of [CLOSURE_LAYER_ID, LONG_TERM_CLOSURE_LAYER_ID, WARNING_LAYER_ID]) {
      const layer = built.layers.find((candidate) => candidate.id === id)
      expect(layer, id).toBeDefined()
      for (const zoom of LADDER) {
        const drawn =
          zoom >= ((layer as { minzoom?: number }).minzoom ?? 0) &&
          zoom < ((layer as { maxzoom?: number }).maxzoom ?? 25)
        expect({ id, zoom, drawn }).toEqual({ id, zoom, drawn: true })
      }
    }
    // And the waypoints really do have a seam, so the contrast above is a
    // real one rather than two layers that happen to agree.
    expect(POI_PIN_MIN_ZOOM).toBeGreaterThan(0)
  })
})
