// The two day-hike casing layers' ids, which the route-hover hook reads - and
// nothing that builds a layer.
//
// A LEAF, ON PURPOSE, for features/LAUNCH_BUDGET.md §4.4's rule: a constant
// the shell reads out of a screen-sized module belongs in a module of its
// own. chrome/useRouteHover.ts runs its hit test against these two layers and
// imported them from map/dayHikeLayers.ts, which imports ROUTE_INK from
// map/routeLayers.ts - so every launch parsed both layer builders, for two
// strings, on a Today screen that mounts no map. map/dayHikeLayers.ts
// imports them from here and re-exports them, the way map/style.ts re-exports
// map/styleIds.ts (#1591), so a reader that imported one from there still
// does. scripts/check-build-output.mjs refuses a string only each builder
// holds in any eager chunk, so neither can drift back in.

export const DAY_HIKE_CASING_LAYER_ID = 'day-hike-route-casing'

/** The wider Pine-900 casing under the first - map/dayHikeLayers.ts's
 *  OUTER_CASING_INK and the #1194 docstring above it say why it exists. */
export const DAY_HIKE_OUTER_CASING_LAYER_ID = 'day-hike-route-outer-casing'
