// Which waypoint categories are drawn, as a stored preference rather than a
// `useState` that dies on reload (#530).
//
// `waypoint_types_shown` has been declared in lib/userPreferences.ts, in
// backend/app/schemas/preferences.py and in IDENTITY_AND_PRIVACY.md's canonical
// model since before any of this was built, and was READ BY NOTHING - the
// legend's toggles wrote to a `useState` set in App.tsx instead. So hiding
// privies lasted until the next reload and never reached an account.
//
// THE STORED KEY IS *SHOWN*, AND THE MAP CONSUMES *HIDDEN*. This module is the
// one translation between them, and the direction is deliberate
// (features/POI_VISIBILITY.md Option 3). `[]` means ALL, which is what it has
// always meant - though a fresh install no longer starts there. See
// DEFAULT_SHOWN_TYPES below for what it opens to instead (#865).
//
// THE REASON THAT WAS WRITTEN HERE FOR THE DIRECTION IS NOT TRUE, and #1197 is
// what made it observable rather than theoretical. It said a show-list "means a
// category a later release adds is visible by default, where a list of what to
// hide would make it invisible to everyone who had ever opened this screen".
// Read `hiddenTypesFrom` below: a stored `shown` list that predates a category
// does not contain it, so the category is HIDDEN, which is the outcome the
// sentence attributed to the rejected design. It holds only for `[]`, and #865
// is exactly what stopped `[]` being where anybody starts - so #1197's
// `trailhead` arrived invisible for every hiker who had ever opened this screen,
// which is the case the sentence promised could not happen.
//
// Left standing rather than fixed here, because changing it changes what every
// existing hiker's map draws and that is not #1197's to decide - it is
// #1214. Option 3 may still be the right call for other reasons
// (POI_VISIBILITY.md has them); this one is not among them.
//
// WHY THIS IS WORTH HAVING RATHER THAN TIDY. Hiding a category hands its
// collision budget to the ones left. With #528's counts on screen that is
// visible as it happens: turn off viewpoints - 1,223 of the corridor's
// waypoints, and last in POI_PRIORITY for exactly that reason - and `4 shown`
// becomes `11 shown`. Control that visibly buys something gets used; a checklist
// of categories does not.
//
// THE SAFETY RULE IS STRUCTURAL, NOT A CHECK ANYONE HAS TO REMEMBER. Every
// function here filters through `NEVER_HIDEABLE` in lib/legendContents.ts, so
// no stored value - not a hand-edited preference, not one synced from an older
// client, not "only water" - can produce a map with a closure hidden on it.
//
// NARROWED BY #1047, AND THIS FILE IS WHY THE NARROWING IS SAFE. The legend
// now offers an Alerts switch that does take those marks off the canvas, so
// "no hide affordance anywhere in the app" is no longer the rule. What is
// still true, and is the part a stored preference could have broken, is that
// nothing anybody can SAVE reaches a closure. The switch lives in a
// `useState` in the legend's shell until 2026-09-20 and in nothing at all
// since that switch was removed, is never written here or anywhere
// else, and is gone by the next time the map opens. A file that syncs to an
// account is exactly the wrong home for it, which is why it is not in this
// one.

import { POI_TYPES } from './config'
import { NEVER_HIDEABLE } from './legendContents'

/**
 * Every category the preference can speak about.
 *
 * The client's own POI_TYPES, which `verify_release.py` already parses as the
 * list a release must serve - so a category that reaches a phone is a category
 * this control knows about, with no second list to drift from it.
 */
export const HIDEABLE_TYPES: readonly string[] = POI_TYPES.filter(
  (type) => !NEVER_HIDEABLE.has(type),
)

/**
 * What a fresh install - or an account that has never touched this
 * preference - opens the map to. The other five (resupply, crossing,
 * viewpoint, parking, trailhead) start hidden, reachable the same way any
 * hidden category is: Settings or the legend.
 *
 * `trailhead` is the fifth and joined them by NOT being added here (#1197).
 * That is the intended answer rather than an oversight: this list is the
 * WALKING map's, a trailhead is how a hiker reached the trail rather than
 * anything they need while on it, and map/poiPriority.ts ranks it beside
 * parking at the bottom for the same reason. The planning map is where it
 * matters, and map/labelLadder.ts ranks it FIRST there - two orderings of one
 * category, each right about its own screen.
 *
 * Maintainer decision (#865), resolving the "all-on vs. a curated subset"
 * open question UX_CUSTOMIZATION.md and POI_VISIBILITY.md both carried:
 * shelter, water and campsite are where a thru-hiker's day plan is anchored
 * and privy is the fourth every one of those stops has reason to also show.
 * The four left off are also this module's own evidence for what crowds a
 * map most - viewpoint alone is 1,223 of the corridor's waypoints, last in
 * POI_PRIORITY for exactly that reason.
 */
export const DEFAULT_SHOWN_TYPES: readonly string[] = HIDEABLE_TYPES

// EVERY CATEGORY, SINCE 2026-09-18 (#1585). The docstring above is the
// argument #865 made for a curated four, and it is kept whole because it is
// the argument that was overturned rather than forgotten: shelter, water,
// campsite and privy are where a thru-hiker's day is anchored, and the four
// left off - resupply, crossing, viewpoint, parking, later trailhead - are
// this module's own evidence for what crowds a map most.
//
// WHAT IT COST, measured against the identity ledger on 2026-09-18: 7,082 of
// the corridor's 8,469 published waypoints - 84% of them - were off the map
// on a fresh install. 5,318 crossings, 1,223 viewpoints, 482 parking areas,
// 59 A.T. Community towns. Nobody had switched any of them off. The legend
// drew their rows struck through, which is the app being honest about a
// choice the hiker never made, and the map drew nothing at all.
//
// The maintainer, 2026-09-18: "never hide anything!!!!!!!" That is a rule
// about the MAP deciding, and a default IS the map deciding - it is the one
// state no hiker ever chose. So a fresh install now opens with every
// category on, and `waypoint_types_shown` keeps doing exactly what it always
// did for the hiker who wants fewer: it is a control they can see and
// reverse, which is the one honest subtraction this app has.
//
// The crowding argument the old list rested on has not gone away and is not
// answered here - it is answered in map/poiLayers.ts, where a pin's SIZE now
// follows POI_PRIORITY so a vista never looks like a spring, and where
// nothing is culled for room any more.

/** What the map and the legend consume: the categories NOT to draw. */
export function hiddenTypesFrom(shown: readonly string[]): Set<string> {
  // The all-on case. Not "hide everything except an empty list" - that would
  // open the app with a blank map.
  if (shown.length === 0) return new Set()

  const allowed = new Set(shown)
  return new Set(HIDEABLE_TYPES.filter((type) => !allowed.has(type)))
}

/**
 * The preference after one row's toggle.
 *
 * Collapses back to `[]` the moment everything is shown again, so "all" has one
 * representation in storage rather than two that behave the same today and
 * diverge the next time a category is added.
 */
export function toggleType(shown: readonly string[], type: string): string[] {
  // A category that cannot be hidden cannot be toggled either, whatever a
  // caller thinks it is asking for.
  if (NEVER_HIDEABLE.has(type)) return [...shown]

  const hidden = hiddenTypesFrom(shown)
  const nextHidden = new Set(hidden)
  if (nextHidden.has(type)) nextHidden.delete(type)
  else nextHidden.add(type)

  if (nextHidden.size === 0) return []
  return HIDEABLE_TYPES.filter((candidate) => !nextHidden.has(candidate))
}

/**
 * The preference for "show me this one and nothing else".
 *
 * The control this whole issue is worth building for: at a crowded zoom it is
 * the difference between four water pins drawn and forty, and it answers "where
 * is the next water" in two taps instead of by zooming in and panning along the
 * trail.
 *
 * A never-hideable category asked for alone still returns "all", because the
 * alternative would be a map showing closures and nothing else - not what anyone
 * tapping a closure row means, and one tap from a map with the trail data
 * missing.
 */
export function onlyType(type: string): string[] {
  if (NEVER_HIDEABLE.has(type) || !HIDEABLE_TYPES.includes(type)) return []
  return [type]
}

/** Back to everything. */
export function showAllTypes(): string[] {
  return []
}

/** Whether a filter is in force at all - which is what decides whether the way
 *  out is on screen. */
export function isFiltered(shown: readonly string[]): boolean {
  return hiddenTypesFrom(shown).size > 0
}

/**
 * The filter as one of three states, for a control that DISPLAYS it.
 *
 * Its existence is the answer to the open question the issue raised about "Only
 * this": the filter PERSISTS - it writes the preference, so it survives a pan, a
 * reload and reaching an account - because a filter that dissolved on the first
 * pan would undo itself exactly when it started being useful ("where is the next
 * water" is answered by panning along the trail with water alone drawn). What
 * that risks is a hiker forgetting they set it, so the price of persisting is
 * that the state is always on screen.
 *
 * This returns the state rather than a sentence about it because the sentence
 * was the bug. "Showing water only · Show all · Show one only…" put a
 * description, an exit and a menu in one run-on line, and at the 272px the
 * desktop panel actually is (desktop.css) the line wrapped and orphaned its
 * separator - photographed, not guessed. A control whose selected value IS the
 * state needs no sentence beside it, so there is one thing on that row instead
 * of three.
 *
 * `some` is reachable only by toggling rows, never by this control - which is
 * why it reports counts rather than a list. Naming three of eight categories
 * takes more room than the panel has, and the rows above already say which.
 */
export type ShownSelection =
  | { kind: 'all' }
  | { kind: 'one'; type: string }
  | { kind: 'some'; shown: number; of: number }

export function shownSelection(shown: readonly string[]): ShownSelection {
  // Asked of `hiddenTypesFrom` rather than of `shown.length`, so "every type,
  // listed out" is `all` - the same collapse `toggleType` does in storage, and
  // the reason a filter turned off by hand does not leave the control claiming
  // "8 of 8 types".
  if (!isFiltered(shown)) return { kind: 'all' }

  const showing = HIDEABLE_TYPES.filter((type) => shown.includes(type))
  if (showing.length === 1) return { kind: 'one', type: showing[0] }
  return { kind: 'some', shown: showing.length, of: HIDEABLE_TYPES.length }
}
