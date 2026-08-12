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
// (features/POI_VISIBILITY.md Option 3): a list of what to show means a category
// a later release adds is visible by default, where a list of what to hide would
// make it invisible to everyone who had ever opened this screen. `[]` means ALL,
// which is what it has always meant and what a fresh install gets.
//
// WHY THIS IS WORTH HAVING RATHER THAN TIDY. Hiding a category hands its
// collision budget to the ones left. With #528's counts on screen that is
// visible as it happens: turn off viewpoints - 1,223 of the corridor's
// waypoints, and last in POI_PRIORITY for exactly that reason - and `4 shown`
// becomes `11 shown`. Control that visibly buys something gets used; a checklist
// of categories does not.
//
// THE SAFETY RULE IS STRUCTURAL, NOT A CHECK ANYONE HAS TO REMEMBER. Closures
// and serious warnings have no hide affordance anywhere in the app
// (features/HIKER_SAFETY.md, features/MAP_OPTIONS.md §4), and `NEVER_HIDEABLE`
// in lib/legendContents.ts stays the only guard. Every function here filters
// through it, so no stored value - not a hand-edited preference, not one synced
// from an older client, not "only water" - can produce a map with a closure
// hidden on it.

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

/** What the map and the legend consume: the categories NOT to draw. */
export function hiddenTypesFrom(shown: readonly string[]): Set<string> {
  // The all-on case, and the one a fresh install is in. Not "hide everything
  // except an empty list" - that would open the app with a blank map.
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
 * The standing sentence for a map that is filtered, or null where it is not.
 *
 * Its existence is the answer to the open question the issue raised about "Only
 * this": the filter PERSISTS - it writes the preference, so it survives a pan, a
 * reload and reaching an account - because a filter that dissolved on the first
 * pan would undo itself exactly when it started being useful ("where is the next
 * water" is answered by panning along the trail with water alone drawn). What
 * that risks is a hiker forgetting they set it, so the price of persisting is
 * that the state is always visible and always has a way out.
 */
export function filterSummary(shown: readonly string[]): string | null {
  if (!isFiltered(shown)) return null
  const showing = HIDEABLE_TYPES.filter((type) => shown.includes(type))
  if (showing.length === 1) return `Showing ${showing[0]} only`
  return `Showing ${showing.length} of ${HIDEABLE_TYPES.length} waypoint types`
}
