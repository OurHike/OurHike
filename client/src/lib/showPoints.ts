/**
 * Whether the map is drawing waypoints, and who last said so.
 *
 * THE SEAM ALONE WAS NOT ENOUGH (2026-09-20). map/poiLayers.ts's
 * POI_PIN_MIN_ZOOM floors both waypoint ranks at z7, so a hiker on the
 * corridor view sees trails and clubs and no places at all. A map that goes
 * quiet with nothing on screen to say it has is the failure
 * features/POI_VISIBILITY.md spent three reversals on, so the seam comes with
 * a switch: the hiker can always see what the map has decided, and always
 * overrule it.
 *
 * The maintainer's rule, in their own words: *"Add a toggle over the map to
 * 'Show Points'. Toggle that on and off as you zoom in."* And then, asked
 * which of two readings they meant: *"Zoom sets it, hiker overrides. But only
 * set for the hiker on first time zooming in (for that map view). Don't
 * override a setting the hiker chose."*
 *
 * So there are exactly two things that can move this switch, and they are not
 * equals:
 *
 *  1. **Crossing the seam inward, once per map view.** The first time a view
 *     goes from below z7 to at-or-above it, the switch turns itself on. Once
 *     only - a hiker who pinches back and forth is not toggled back and forth
 *     with it, which is the "only set... on first time zooming in" half.
 *  2. **The hiker tapping it.** That is final for the view. Nothing auto-sets
 *     over the top of it, which is the "Don't override a setting the hiker
 *     chose" half, and it is the half most easily lost in a refactor: an
 *     auto-rule that fires on every crossing looks identical until a hiker
 *     switches the points off and pinches.
 *
 * WHY A MACHINE RATHER THAN A BOOLEAN. The two rules above cannot be held by
 * one flag, because "on because the zoom said so" and "on because the hiker
 * said so" have to behave differently on the next crossing. {@link ShowPoints}
 * carries both facts, and {@link afterZoom} and {@link afterTap} are the only
 * ways it changes - so a component cannot set the boolean and lose the reason.
 *
 * WHAT "FOR THAT MAP VIEW" MEANS HERE, said plainly because it is a choice
 * rather than a reading: a view is one visit to the map screen. State lives in
 * the screen and goes when the screen does. It is NOT persisted to
 * lib/userPreferences.ts, and that is deliberate - a hiker who switched points
 * off to read the contours on one planning session should not find their
 * shelters missing a week later on the trail, which is the direction this app
 * refuses to fail in. `@unvalidated`: nobody has watched a hiker do this
 * twice, and if field testing (#105/#106) says the choice wants to outlive the
 * screen, this is the decision to revisit and the module to change.
 */

/** Who last decided, and what they decided. */
export type ShowPoints = {
  /** Whether the waypoint layers draw. */
  readonly shown: boolean
  /**
   * True once the hiker has tapped the switch in this view.
   *
   * The whole of rule 2: while this is true, {@link afterZoom} is a no-op.
   */
  readonly chosenByHiker: boolean
  /**
   * True once the camera has crossed the seam inward in this view.
   *
   * The whole of rule 1. Kept separately from `shown` because a hiker who
   * crosses the seam and then switches the points off has both a crossing and
   * a choice on the record, and the crossing must not fire again.
   */
  readonly crossedInward: boolean
}

/**
 * A fresh map view: nothing drawn, nobody has decided.
 *
 * `shown: false` rather than true, and the seam is why: the opening camera is
 * the whole corridor at about z4.9, well below POI_PIN_MIN_ZOOM, so a view
 * that began with `shown: true` would claim to be drawing waypoints on a
 * screen that has none. The switch says what the map is doing, so it starts
 * saying the true thing.
 */
export const NO_CHOICE_YET: ShowPoints = {
  shown: false,
  chosenByHiker: false,
  crossedInward: false,
}

/**
 * The state after the camera moved.
 *
 * @param state Where the switch stands now.
 * @param zoom The camera's zoom after the move.
 * @param seam POI_PIN_MIN_ZOOM, passed rather than imported so this module
 *   stays free of the map layer and its MapLibre-shaped dependencies - the
 *   same reason map/poiLayers.ts keeps LOCATE_MIN_ZOOM rather than the shell.
 */
export function afterZoom(state: ShowPoints, zoom: number, seam: number): ShowPoints {
  return afterSeamCrossing(state, zoom >= seam)
}

/**
 * The same rule, told which side of the seam the camera is on rather than
 * where it is.
 *
 * The shell already computes that: chrome/MapScreen.tsx takes `belowPoiZoom`
 * from App.tsx, which compares the live camera against POI_PIN_MIN_ZOOM.
 * Passing the boolean rather than re-deriving a zoom keeps ONE comparison
 * against the seam in the tree, which is the same reason
 * {@link waypointsDrawn} takes the seam instead of importing it.
 */
export function afterSeamCrossing(state: ShowPoints, atOrAbove: boolean): ShowPoints {
  // Below the seam nothing is drawn whatever anybody chose, because there is
  // nothing to draw: the layers' own floors decide that. The switch keeps its
  // memory so a hiker who turned points off and zoomed out still finds them
  // off when they come back in.
  if (!atOrAbove) return state
  // Rule 1, and both of its guards: fire once per view, and never over a
  // choice the hiker made.
  if (state.crossedInward || state.chosenByHiker) {
    return state.crossedInward ? state : { ...state, crossedInward: true }
  }
  return { shown: true, chosenByHiker: false, crossedInward: true }
}

/**
 * The state after the hiker tapped the switch.
 *
 * Always wins, and always marks the choice - so the next crossing leaves it
 * alone. There is no "un-choose": within a view, once the hiker has an
 * opinion they keep it.
 */
export function afterTap(state: ShowPoints): ShowPoints {
  return { ...state, shown: !state.shown, chosenByHiker: true }
}

/**
 * Whether the waypoint layers should draw at all right now.
 *
 * Both halves, in one place, so no caller can accidentally draw waypoints
 * below the seam by consulting the switch alone: the camera has to be at or
 * above the seam AND the switch has to be on.
 */
export function waypointsDrawn(state: ShowPoints, zoom: number, seam: number): boolean {
  return zoom >= seam && state.shown
}
