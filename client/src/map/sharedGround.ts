/**
 * Two trails on one treadway, drawn as two halves of one line (#1384).
 *
 * WHAT THE DATA SAYS. pipeline/lib/concurrency.py finds every stretch where
 * one trail's lines lie within 10 m of another's for 50 m or more - both
 * numbers measured there - and publishes it as a PAIR of features on ONE
 * chord: the same coordinates, each trail's own `source`/`name`/`blaze_color`
 * and status, `concurrent_with` naming the other, and `concurrent_side` +1 on
 * one half and -1 on the other. They ride in the network's vector tiles
 * (export_nearby_trails.py's write_tiles) and nowhere else, so this module
 * reads NEARBY_TRAILS_SOURCE_ID and nothing has to change about the A.T.'s
 * own GeoJSON.
 *
 * WHAT THE MAP DOES WITH IT - the maintainer's choice of 2026-09-10, shown
 * three treatments: "two-tone, each blaze on its own side". Two layers over
 * both trail-line stacks:
 *
 *   - a CASING at the stretch's cased width, opaque, which is also the
 *     MASK: it covers the two original lines on the stretch, which still
 *     draw underneath from their own sources (nothing is cut out of them -
 *     trail_miles.json is keyed to the A.T. file's features and eleven
 *     scripts read the network file as topology). Opaque rather than the
 *     0.7 every other casing carries, because a translucent rim over a white
 *     line and over paper would be two rims of two colours.
 *   - the BLAZE halves: each pair feature at HALF the stretch's width,
 *     offset by a quarter of it to its own side, where the stretch's width
 *     is the HEAVIER of the two trails' tiers (the schematic the maintainer
 *     chose drew both halves at 2.25 px inside the A.T.'s 6.5 px casing).
 *     The heavier rather than each half's own, because width is the map's
 *     hierarchy channel: a stripe of two park trails drawn at a
 *     through-route's weight would claim a through-route, and a
 *     through-route's half drawn at a park trail's would deny one. Same
 *     chord, opposite signs, so the halves meet at the line whichever way
 *     either source digitised it, and the A.T.'s white half is on the same
 *     side of ATC's line the whole way. Painted through the same blaze
 *     expression, ghosted by the same system rule, as every line on the map.
 *
 * THE ORIGINAL LAYERS STOP DRAWING THE PAIRS. A pair feature carries a
 * `source` like any line, so without SHARED_GROUND_EXCLUDED inside both of
 * map/nearbyTrails.ts's split filters each half would ALSO draw as a plain
 * centred line under the two-tone - and be labelled, counted in view and
 * re-pointed on a trail switch as one. Inside the filters rather than
 * beside them, so every reader of the split, attachChosenTrail included,
 * carries it without knowing.
 *
 * GUARDED ON ABSENCE. A release exported before the pairing existed carries
 * no `concurrent_with` on any feature: the two layers match nothing, the
 * exclusion excludes nothing, and the map draws exactly what it drew
 * before. That is what lets the client half ship ahead of the data half.
 *
 * `line-offset` and `line-width` are data-driven paint properties in the
 * style spec this build carries (checked against
 * @maplibre/maplibre-gl-style-spec's v8.json, 2026-09-10), so a per-feature
 * sign and width are legal, not a hope.
 */

export const SHARED_GROUND_CASING_LAYER_ID = 'shared-ground-casing'
export const SHARED_GROUND_BLAZE_LAYER_ID = 'shared-ground-blaze'

/** The property a pair feature carries and a plain line never does. */
export const SHARED_GROUND_PROPERTY = 'concurrent_with'
/** +1 or -1: which side of the shared chord this half is drawn on. */
export const SHARED_GROUND_SIDE_PROPERTY = 'concurrent_side'
/** The other half's `source`, so the stretch can be weighed at the heavier
 *  of the two trails' tiers - a park trail on the A.T.'s treadway is drawn
 *  at the A.T.'s weight, two park trails at theirs. */
export const SHARED_GROUND_PARTNER_SOURCE_PROPERTY = 'concurrent_source'

/** Matches a pair feature. */
export const SHARED_GROUND_FILTER: unknown[] = ['has', SHARED_GROUND_PROPERTY]
/** Matches everything else - what the network's own layers add to theirs. */
export const SHARED_GROUND_EXCLUDED: unknown[] = ['!', SHARED_GROUND_FILTER]

/**
 * The feature's own side, +1 or -1, as a number - the sign the two halves
 * of one chord differ in. Multiplied INTO each stop of the taper the halves
 * take (style.ts's buildSharedGroundLayers) rather than around it: a zoom
 * interpolation wrapped in arithmetic is a style error ("zoom" may only be
 * used as input to a top-level step or interpolate), and a per-feature
 * factor inside a stop is not.
 */
export function sharedGroundSideExpression(): unknown[] {
  return ['to-number', ['get', SHARED_GROUND_SIDE_PROPERTY]]
}
