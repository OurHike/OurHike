// The map's opening padding, on its own, because the shell reads it and the
// map view weighs 5,931 bytes.
//
// WHY A MODULE FOR ONE NUMBER. `FIT_PADDING` lived in map/MapView.tsx, and
// App.tsx imported it from there - one integer, statically, out of a module
// that draws the whole map. Rollup has no way to take the constant and leave
// the file: a static value import puts the exporting module in the importer's
// chunk, so the map view rode into the eager closure on the back of the number
// 24. Measured 2026-09-15 against the eager attribution of a
// production-configured build: 5,931 raw bytes of map/MapView.tsx in
// `main-*.js`, on a Today screen that mounts no map, for a constant the shell
// uses twice.
//
// That is the same shape as #1300, which put 406 KB of MapLibre in the eager
// chunk because three modules were imported by the shell "for a string and two
// setters". scripts/check-build-output.mjs catches that one by name - it looks
// for MapLibre's own markers - and could not see this one, because nothing
// here is MapLibre. What caught it was the budget going red
// (features/LAUNCH_BUDGET.md §3) and the attribution being read afterwards.
//
// So the rule this file is an instance of: a constant the shell reads out of a
// screen-sized module belongs in a module of its own, and the screen imports
// it too. chrome/MapScreen.tsx keeps its own CHART_FIT_PADDING, which is a
// different number for a different framing and deliberately not this one.

/** Breathing room around a fitted box, on every side, when the caller asks for
 *  nothing more specific. Read by the shell's re-fit of the corridor once the
 *  entry steps end (#1296), so the map a hiker opens after first run is framed
 *  exactly as a returning hiker's is. */
export const FIT_PADDING = 24
