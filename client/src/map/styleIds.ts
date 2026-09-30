// The names of the map's own sources and layers, and the lists the shell
// walks over them (#1591).
//
// A LEAF, ON PURPOSE: strings and arrays of strings, importing nothing that
// builds a layer. map/style.ts re-exports every one of them, so a reader
// that imported an id from there still does - what changes is that a module
// the shell loads before its first frame (map/liveSourceHealth.ts for the
// archive's source id, map/drawnBlazes.ts for the blaze layers it counts) no
// longer brings the whole style module, and every layer builder it imports,
// into the eager bundle with it. Measured 2026-09-30 by attributing the built
// chunks to their sources: map/style.ts and the builders it reaches were
// 18,925 gzip bytes of the closure a Today launch parses, for three modules
// that read six strings between them. The comments below travelled with the
// ids they describe.

import { CLOSURE_LAYER_ID, LONG_TERM_CLOSURE_LAYER_ID } from '../lib/closureStyle'
import {
  SHARED_GROUND_BLAZE_LAYER_ID,
  SHARED_GROUND_CASING_LAYER_ID,
} from './sharedGround'

export const TOPO_SOURCE_ID = 'usgs-topo'
export const TRAILS_SOURCE_ID = 'trails'
export const TRAIL_OVERVIEW_SOURCE_ID = 'trail-overview'

/**
 * The trail lines other organizations maintain (#950,
 * features/NEARBY_TRAILS.md, pipeline/export_nearby_trails.py).
 *
 * ITS OWN SOURCE, AND NOT BECAUSE THE MAP WANTED ONE. These lines belong in
 * the same source as the A.T.'s - they are drawn by the same expressions off
 * the same properties, and a single source would have meant a single set of
 * layers. They are separated because they are separately LICENSED: NYS OPRHP
 * states terms and NYNJTC, Mohonk Preserve and NYS DEC state none, so the
 * pipeline publishes them as their own artifact and publish.py holds that
 * artifact back entirely while ANY steward in it is outstanding (the
 * `reaches_hikers` gate lib/config.ts's NEARBY_TRAILS_TILES_KEY describes).
 *
 * A VECTOR SOURCE SINCE #1257, where the A.T.'s is GeoJSON. The artifact grew
 * to 228,820,578 bytes on 2026-09-07 (nationwide USFS, #1231) and a GeoJSON
 * source takes its `data` whole - parsed on the main thread, indexed in the
 * worker, every phone that tried crashed (#1254). So these lines are cut into
 * z9-z14 tiles (lib/config.ts's NEARBY_TRAILS_TILES_KEY) and this source
 * declares a network:// template that map/networkTiles.ts answers by byte
 * range, the way the hiking sheet's basemap:// is answered. What the map
 * holds is the tiles under the camera and nothing else. The A.T.'s own line
 * stays GeoJSON because it is 3.9 MB and the thing every entry step is about;
 * it is not this problem.
 *
 * The one thing a vector source needs that a GeoJSON one does not is the name
 * of the layer inside the tiles: every layer over this source carries
 * `source-layer: NETWORK_TILES_LAYER` (onSourceLayer below), and a layer that
 * did not would draw nothing and say nothing.
 *
 * WHAT THAT COSTS, stated so nobody rediscovers it: the layers below are a
 * second instance of the trail line's casing, blaze, closure band and label.
 * Every expression in them is imported from where the first instance gets it
 * rather than copied, so the two cannot drift in appearance - but a new
 * channel added to one is a channel somebody has to remember to add to the
 * other, and nothing mechanical catches that. style.test.ts holds the two
 * paint objects against each other for exactly this reason.
 */
export const NEARBY_TRAILS_SOURCE_ID = 'nearby-trails'

/**
 * The corridor-view sketch of that whole network (#1135, lib/config.ts's
 * NETWORK_OVERVIEW_KEY) - what the opening camera draws, since the full
 * network's layers carry `minzoom` at the seam and the A.T.'s own sketch
 * covers only the A.T.
 *
 * A third source rather than folded into NEARBY_TRAILS_SOURCE_ID because
 * the two are on the map AT ONCE with disjoint zoom ranges - the sketch below
 * the seam, the full lines above it - and since #1257 because the two are
 * different kinds of source: the sketch is one GeoJSON handed over whole, the
 * lines are tiles read by range. Same stewards, so the same attribution rides
 * it - the licence condition follows the lines, not the artifact.
 */
export const NETWORK_OVERVIEW_SOURCE_ID = 'network-overview'

export const BACKDROP_LAYER_ID = 'backdrop'
export const TOPO_LAYER_ID = 'topo'
export const TRAIL_CASING_LAYER_ID = 'trail-casing'
export const BLAZE_LAYER_ID = 'trail-blaze'
export const TRAIL_OVERVIEW_LAYER_ID = 'trail-overview-line'
export const NEARBY_TRAIL_CASING_LAYER_ID = 'nearby-trail-casing'
export const NEARBY_BLAZE_LAYER_ID = 'nearby-trail-blaze'
export const NEARBY_LONG_TERM_CLOSURE_LAYER_ID = 'nearby-long-term-closure-band'
export const NETWORK_OVERVIEW_LAYER_ID = 'network-overview-line'
export const NETWORK_OVERVIEW_CLOSURE_LAYER_ID = 'network-overview-closure-band'

/**
 * The paper layer of every closure feed: the closures feed's, the A.T.'s
 * long-term-closed lines, the nearby network's and the corridor-view
 * sketch's. Each is the id lib/closureStyle.ts derives the feed's other three
 * layers from, so a sheet change repaints all four of each -
 * attachMapAppearance walks this list and the ATC band's id beside it.
 */
export const CLOSURE_BAND_IDS: readonly string[] = [
  CLOSURE_LAYER_ID,
  LONG_TERM_CLOSURE_LAYER_ID,
  NEARBY_LONG_TERM_CLOSURE_LAYER_ID,
  NETWORK_OVERVIEW_CLOSURE_LAYER_ID,
]

/**
 * The untaken half of each trail-line split (#1283, map/nearbyTrails.ts).
 *
 * The ids without a suffix keep drawing the chosen system exactly as they
 * did - which is what keeps every tap handler, probe and repaint that
 * already names them correct for the taken trail. Each has an `-untaken`
 * twin drawing every other line UNDER it, at the network's far weight below
 * the seam, so the taken trail is never crossed by a line that is not it.
 * The twins were `-dotted` until 2026-09-10 (this file's header, rule 2);
 * the suffix changed with the drawing, so a layer's name still says what it
 * draws.
 */
export const TRAIL_CASING_UNTAKEN_LAYER_ID = 'trail-casing-untaken'
export const BLAZE_UNTAKEN_LAYER_ID = 'trail-blaze-untaken'
export const NEARBY_TRAIL_CASING_UNTAKEN_LAYER_ID = 'nearby-trail-casing-untaken'
export const NEARBY_BLAZE_UNTAKEN_LAYER_ID = 'nearby-trail-blaze-untaken'
export const NETWORK_OVERVIEW_UNTAKEN_LAYER_ID = 'network-overview-line-untaken'

/** The casing under a through-route's sketch line below the seam (#1586):
 *  the corridor-view sketch's one casing, under the PRIMARY_TRAIL_SOURCES
 *  features and nothing else, so the Long Path reads at the opening camera
 *  as the untaken A.T. does - a dark-edged stroke rather than a bare thread.
 *  buildNetworkOverviewCasingLayer says the rest. */
export const NETWORK_OVERVIEW_CASING_LAYER_ID = 'network-overview-casing'
/** The sketch's two line layers, the ones sketchLineColor paints (#1586). */
export const NETWORK_OVERVIEW_LINE_LAYER_IDS: readonly string[] = [
  NETWORK_OVERVIEW_UNTAKEN_LAYER_ID,
  NETWORK_OVERVIEW_LAYER_ID,
]

/**
 * Every casing under a blaze, and every layer painting a blaze colour -
 * the two lists attachMapAppearance repaints, and the lists anything asking
 * "what is drawn on the trail lines" should query (map/trailsInView.ts,
 * map/lineTaps.ts, map/drawnBlazes.ts).
 *
 * LISTS RATHER THAN THE TWO NAMED LAYERS, because that is how the repaint
 * used to fail: attachMapAppearance wrote `line-color` on TRAIL_CASING_LAYER_ID
 * and BLAZE_LAYER_ID by name, and the nearby network's pair and both sketches
 * were left on the previous sheet's ink after every theme switch. A layer
 * added to the style is added here, or a theme switch leaves it behind.
 */
export const TRAIL_CASING_LAYER_IDS: readonly string[] = [
  TRAIL_CASING_LAYER_ID,
  TRAIL_CASING_UNTAKEN_LAYER_ID,
  NEARBY_TRAIL_CASING_LAYER_ID,
  NEARBY_TRAIL_CASING_UNTAKEN_LAYER_ID,
  SHARED_GROUND_CASING_LAYER_ID,
  // The sketch's casing under its through-routes (#1586): repainted with
  // every other casing on a sheet change, ghosted by attachChosenTrail in a
  // block of its own (its filter is the source list, not the chosen system).
  NETWORK_OVERVIEW_CASING_LAYER_ID,
]
/**
 * The blaze layers that ink a near-white line in the casing's colour on a
 * day sheet: the two corridor-view sketches, which have no casing pair
 * (#1306, and the maintainer's reversal of 2026-09-10).
 *
 * The rule used to be "every day sheet", and was overruled on the frame
 * twice. First a TAKEN A.T. drawn in the casing's ink was a black line
 * across the country ("that is not a dashed line / it looks like a black
 * line", 2026-09-09), so #1306 made the ink follow the dot rhythm: dark
 * under dots, white with its casing when solid. Then the dots went
 * (2026-09-10, "the AT is now black, and not its white blaze - make it
 * white"), and with every real line solid and cased there is nothing left
 * for the dark ink to fix on them: a white blaze between two dark rails is
 * what every paper map draws, and it is what the maintainer asked for.
 *
 * BOTH SKETCHES STAY IN THE LIST WHATEVER THEY DRAW, and that is the one
 * place the old unconditional rule stands: neither has a casing pair
 * (buildNetworkOverviewLayer and the sketch layer both say so), and a white
 * line with no edge at all is the empty-looking frame #1291 exists to
 * prevent. The cost is the A.T. changing ink once at the seam, when the real
 * line replaces the sketch; at the corridor camera both read as a
 * dark-edged stroke of the same weight, which is the least bad of the three
 * options. Giving the sketches a casing pair would end the swap and this
 * list with it - not done here, because nobody has looked at a cased
 * 1.5 px line over the opening camera's park clusters, which is the texture
 * NETWORK_OVERVIEW_WIDTH_EXPRESSION's taper exists to keep off that view.
 *
 * SINCE #1586 THE NETWORK SKETCH IS CASED UNDER ITS THROUGH-ROUTES, and
 * only there (NETWORK_OVERVIEW_CASING_LAYER_ID), so its two layers ink dark
 * on the rest alone: sketchLineColor decides per feature, the cased rule on
 * a PRIMARY_TRAIL_SOURCES feature and this list's rule everywhere else. The
 * two ids stay listed, because for everything the casing does not reach the
 * argument above is unchanged.
 */
export const DARK_INKED_BLAZE_LAYER_IDS: readonly string[] = [
  NETWORK_OVERVIEW_UNTAKEN_LAYER_ID,
  NETWORK_OVERVIEW_LAYER_ID,
  TRAIL_OVERVIEW_LAYER_ID,
]

export const BLAZE_LINE_LAYER_IDS: readonly string[] = [
  BLAZE_LAYER_ID,
  BLAZE_UNTAKEN_LAYER_ID,
  NEARBY_BLAZE_LAYER_ID,
  NEARBY_BLAZE_UNTAKEN_LAYER_ID,
  SHARED_GROUND_BLAZE_LAYER_ID,
  TRAIL_OVERVIEW_LAYER_ID,
  NETWORK_OVERVIEW_LAYER_ID,
  NETWORK_OVERVIEW_UNTAKEN_LAYER_ID,
]
export const TRAIL_LINE_LAYER_IDS: readonly string[] = [
  ...TRAIL_CASING_LAYER_IDS,
  ...BLAZE_LINE_LAYER_IDS,
]

/** The blaze layers a hiker can tap or read a trail off - the full lines,
 *  both halves of both splits, plus the network overview's own split since
 *  #1307. THE A.T.'s SKETCH (TRAIL_OVERVIEW_LAYER_ID) STAYS OUT: it carries
 *  no `name` (export_trails.py's write_overview still publishes source,
 *  blaze and status only) and needs none - the header plate already names
 *  the app's own trail, which is what map/trailBadges.ts's own header means
 *  by "the header already does". The network overview's two layers DO carry
 *  `name` now, on the features export_nearby_trails.py's write_overview
 *  named for clearing NAMED_TRAIL_THRESHOLD_MILES; map/trailsInView.ts's
 *  `if (name === null) continue` is what keeps the unnamed haze out even
 *  though its layer is included here. */
export const TAPPABLE_BLAZE_LAYER_IDS: readonly string[] = [
  BLAZE_LAYER_ID,
  BLAZE_UNTAKEN_LAYER_ID,
  NEARBY_BLAZE_LAYER_ID,
  NEARBY_BLAZE_UNTAKEN_LAYER_ID,
  // The two halves of a shared stretch (#1384), first: they are drawn over
  // both stacks, and a tap on the stretch should answer with the half it
  // landed on and its `concurrent_with`, not the plain line masked under it.
  SHARED_GROUND_BLAZE_LAYER_ID,
  NETWORK_OVERVIEW_LAYER_ID,
  NETWORK_OVERVIEW_UNTAKEN_LAYER_ID,
]
