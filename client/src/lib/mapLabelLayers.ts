// Which classes of label the hiker wants on the map (#1194).
//
// The design handoff's second functional addition: a row of toggles, one per
// label class, so a hiker who wants to see where to park is not reading past
// every spring in the park to find it. This module is the model - the keys,
// what each controls, and the default - with no React and no MapLibre in it.
//
// EVERY TOGGLE HERE TAKES OFF A LABEL AND NEVER A PIN OR A LINE, and that is
// the rule that keeps this control comprehensible next to the two that
// already exist:
//
//   - the legend's waypoint filters (lib/waypointVisibility.ts) take PINS off
//     the map. A category hidden there is gone.
//   - the sheet's detail level (map/mapDetail.ts) thins the LIVE SHEET's
//     lines and fine grain in three fixed steps.
//   - this takes NAMES off, and nothing else.
//
// A hiker who turns off "Campsites" here still sees campsite pins; they just
// stop being labelled. Conflating the three would make a label row feel like
// it was deleting the map, and would give two controls authority over one
// layer - which is how a toggle comes to look broken because another screen
// has already turned its target off.
//
// TWO OF THE HANDOFF'S NINE ARE ABSENT, and are absent rather than present
// and inert. `trailheads` and `junctions` have nothing to draw:
// pipeline/lib/poi_schema.py publishes no `trailhead` type, and junctions
// exist only as graph nodes in pipeline/build_trail_graph.py. A toggle whose
// switch changes nothing teaches a hiker the app is broken - the same
// argument chrome/DayHikePickBar.tsx makes for having no disabled buttons on
// the builder bar - so the gap is recorded on #1194 instead, where it can be
// closed by publishing the data rather than by adding a control.

import { TRAIL_LABEL_LAYER_ID, NEARBY_TRAIL_LABEL_LAYER_ID } from '../map/trailLabels'
import { LIVE_TOPO_LAYER_IDS } from '../map/liveTopo'
import { TIER_MIN_ZOOM, type LabelTier } from '../map/labelLadder'

export type LabelLayerKey =
  'parking' | 'roads' | 'shelters' | 'campsites' | 'trails' | 'water' | 'contours'

export interface LabelLayerSpec {
  key: LabelLayerKey
  /** What the toggle says. */
  label: string
  /** Which rung of map/labelLadder.ts this class sits on, for the tier badge. */
  tier: LabelTier
  /**
   * The waypoint type this controls, for the classes that live on the POI
   * source. Absent for the classes that are whole map layers.
   */
  poiType?: string
  /**
   * The map layers this hides, for the classes that are not waypoints. Empty
   * for the POI classes, which are filtered by type instead - one layer draws
   * all of them, so hiding a class is a filter rather than a visibility.
   */
  layerIds: readonly string[]
}

/**
 * The seven, in the order the panel shows them: tier 1 first.
 *
 * "Contour ft" rather than the handoff's "Contours", because this toggle
 * takes off the elevation FIGURES and leaves the contour lines drawn. A
 * control named "Contours" whose switch leaves every contour on the screen is
 * a control a hiker stops trusting. The lines are map/mapDetail.ts's, and
 * giving this row authority over them too would be the two-controls-one-layer
 * problem the header warns about.
 */
export const LABEL_LAYERS: readonly LabelLayerSpec[] = [
  {
    key: 'parking',
    label: 'Parking',
    tier: 'gateway',
    poiType: 'parking',
    layerIds: [],
  },
  {
    key: 'roads',
    label: 'Roads',
    tier: 'gateway',
    layerIds: [LIVE_TOPO_LAYER_IDS.roadLabel],
  },
  {
    key: 'shelters',
    label: 'Shelters',
    tier: 'landmark',
    poiType: 'shelter',
    layerIds: [],
  },
  {
    key: 'campsites',
    label: 'Campsites',
    tier: 'landmark',
    poiType: 'campsite',
    layerIds: [],
  },
  {
    key: 'trails',
    label: 'Trail names',
    tier: 'routeTrail',
    layerIds: [TRAIL_LABEL_LAYER_ID, NEARBY_TRAIL_LABEL_LAYER_ID],
  },
  {
    key: 'water',
    // THE FINEST BAND, with the junctions, and not with the shelters. The
    // handoff's z2 "route" adds named trails, peaks, shelters and campsites;
    // its z3 "section" adds "junction markers and water". Water names are a
    // section-level detail on a topo sheet rather than something a hiker
    // picks a start point by - which is the question this whole ladder
    // orders labels for.
    label: 'Water',
    tier: 'junction',
    layerIds: [LIVE_TOPO_LAYER_IDS.waterLabel],
  },
  {
    key: 'contours',
    label: 'Contour ft',
    tier: 'junction',
    layerIds: [LIVE_TOPO_LAYER_IDS.contourLabel],
  },
]

/**
 * Which are off. An absent key means ON - the handoff's own convention
 * ("absent key means on"), and the one that makes the default state the empty
 * object rather than seven booleans somebody has to keep in step with
 * {@link LABEL_LAYERS}.
 */
export type HiddenLabelLayers = Partial<Record<LabelLayerKey, true>>

export const ALL_LABELS_SHOWN: HiddenLabelLayers = {}

export function labelLayerShown(hidden: HiddenLabelLayers, key: LabelLayerKey): boolean {
  return hidden[key] !== true
}

export function toggleLabelLayer(
  hidden: HiddenLabelLayers,
  key: LabelLayerKey,
): HiddenLabelLayers {
  const next = { ...hidden }
  if (next[key] === true) delete next[key]
  else next[key] = true
  return next
}

/** The waypoint types whose names are switched off - map/poiLabels.ts's filter. */
export function hiddenPoiLabelTypes(hidden: HiddenLabelLayers): string[] {
  return LABEL_LAYERS.filter(
    (spec) => spec.poiType !== undefined && !labelLayerShown(hidden, spec.key),
  ).map((spec) => spec.poiType as string)
}

/** Every layer this row has authority over. */
export const ALL_LABEL_LAYER_IDS: readonly string[] = LABEL_LAYERS.flatMap((spec) => [
  ...spec.layerIds,
])

/**
 * Layers that exist ONLY for the builder and are off everywhere else.
 *
 * Road names are new with #1194 and were added for the planning screen, where
 * the handoff's argument for them is that "roads exist specifically so a user
 * can find a start point". That argument does not carry to the walking map,
 * whose density was settled by #1135 without this layer in it, so the layer
 * ships hidden and the builder turns it on.
 *
 * The other four classes here - trail names, water, contour figures - were
 * already drawn before this change and must go back to being drawn when the
 * builder closes. That asymmetry is the whole reason
 * {@link labelVisibilityPlan} exists rather than a single hidden list.
 */
export const BUILDER_ONLY_LAYER_IDS: readonly string[] = [LIVE_TOPO_LAYER_IDS.roadLabel]

/**
 * Which label layers should be on and which off, right now.
 *
 * BOTH LISTS, ALWAYS, rather than a hidden list and an implied remainder.
 * The bug that shape produced: with no walk being built the shell had nothing
 * to say, so the effect did nothing, and every label the builder had switched
 * on stayed on over the walking map for the rest of the session. A control
 * whose OFF state is "no instruction" is a control that only ever turns
 * things on.
 *
 * `building` false is therefore not "leave it alone" - it is a full
 * instruction: put the pre-existing layers back and take the builder's own
 * away. That also makes the toggles ephemeral in the way App.tsx's state
 * already assumes: a hiker who hid trail names to find a lot does not find
 * them still hidden on the trail tomorrow.
 */
export function labelVisibilityPlan(
  hidden: HiddenLabelLayers,
  building: boolean,
): { shown: string[]; hidden: string[] } {
  const shownIds: string[] = []
  const hiddenIds: string[] = []

  for (const spec of LABEL_LAYERS) {
    for (const id of spec.layerIds) {
      const builderOnly = BUILDER_ONLY_LAYER_IDS.includes(id)
      const wanted = building ? labelLayerShown(hidden, spec.key) : !builderOnly
      ;(wanted ? shownIds : hiddenIds).push(id)
    }
  }

  return { shown: shownIds, hidden: hiddenIds }
}

/**
 * The badge the toggle wears: `T1`/`T2`/`T3`.
 *
 * THE BADGE IS THE ZOOM BAND, NOT THE COLLISION RUNG, and conflating the two
 * is what this got wrong first: it split at `routeTrail`, so shelters and
 * campsites wore `T3` on screen while the handoff puts them in z2 with the
 * trail names. The ladder has seven rungs because collisions need that much
 * resolution; a hiker reading a toggle needs the three the legend names.
 *
 * The split therefore follows map/labelLadder.ts's own `TIER_MIN_ZOOM`:
 * everything that draws at the gateway zoom is T1, everything that waits for
 * the landmark zoom is T2, and everything held back to the finest band is T3.
 * Derived from those numbers rather than restated, so a rung that moves
 * cannot leave a badge behind saying where it used to be.
 *
 * WHERE THIS DISAGREES WITH THE HANDOFF, IT IS BECAUSE THE MAP DOES. It puts
 * trail names in z2; they badge `T1` here, because map/trailLabels.ts has
 * drawn them from `POI_PIN_MIN_ZOOM` since #930 and this change does not move
 * them. A badge saying "z2" over a name already on screen at the park view
 * would be the display outrunning its source in miniature - and holding the
 * names back to match would take them off the wide view where a hiker picking
 * a start point most wants to know which line is which.
 */
export function tierBadge(tier: LabelTier): string {
  const zoom = TIER_MIN_ZOOM[tier]
  if (zoom <= TIER_MIN_ZOOM.gateway) return 'T1'
  if (zoom <= TIER_MIN_ZOOM.landmark) return 'T2'
  return 'T3'
}
