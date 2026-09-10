// Builds the MapLibre style for the trail map.
//
// Two rules from WIREFRAMES.md's "Trail line rendering — blazes" are
// load-bearing rather than cosmetic:
//
//  1. ONE `match` expression drives line-color across every trail source, so a
//     source imported later inherits the rule instead of needing its own layer.
//     That expression lives in lib/blaze.ts and is imported, never re-spelled.
//
//  2. EVERY trail line is SOLID and one colour end to end. Lines used to be
//     dashed on a per-blaze rhythm, and the rhythm was the map's second
//     hue-independent channel. What that actually produced on screen was a
//     line alternating between its blaze colour and the dark casing showing
//     through each gap - and on the AT centerline, whose blaze is very
//     nearly white, the gaps read as the line. A hiker looking for the trail
//     they are standing on found a dotted grey-and-white thread through the
//     contours. A solid line over a casing is the older, plainer
//     cartographic answer and it is legible at a glance, which is the
//     property that matters most.
//
//     THE DOTS CAME BACK ONCE AND WENT AGAIN, and the split they left is
//     still here. #1283 (the maintainer's design handoff, 2026-09-08) drew
//     every line outside the chosen system as a dot rhythm on a layer of
//     its own under the solid one, to say at the opening camera which of a
//     country's worth of trails the map was about; #1306 then inked an
//     untaken near-white line dark, because a dotted white line has nothing
//     between its two rails. The maintainer took both back on a Hudson
//     Highlands frame at z13 (2026-09-10): "the dashes are distracting" and
//     "the AT is now black, and not its white blaze - make it white". So
//     every line is solid again, a white blaze is white with its casing on
//     every layer that has a casing, and the dark ink survives only on the
//     two corridor-view sketches, which have no casing pair
//     (DARK_INKED_BLAZE_LAYER_IDS). What the split still carries is one
//     number and one order: an untaken line below the seam draws at the
//     network's far weight rather than its own tier
//     (untakenTrailWidthExpression), and sits UNDER the taken trail's pair.
//     Folding that into one layer per source is possible - the width is a
//     data-driven expression and the order a sort key - and has not been
//     done, because the split's names are in every tap handler, probe and
//     test, and what the maintainer asked for was the picture, not the
//     layer count. map/nearbyTrails.ts owns the two filters the split is
//     built from.
//
//     WIDTH carries the hue-independent channel, and carries more than the
//     rhythm did: a system's through-route is drawn markedly wider than the
//     side trails hanging off it, so the line the map is about is findable with
//     colour removed entirely - by glare, by greyscale (WIREFRAMES.md `9d`), or
//     by colour vision deficiency. Width is keyed off the pipeline's own
//     `source` attribute, in one data-driven expression, for the same reason
//     the colour is keyed off `blaze_color` in one expression.
//
//     Through-route is a role, not a name: today the AT holds it alone, so the
//     widest line on the map is the AT, but the map is not promised one
//     system (the NYNJTC maintains several). See PRIMARY_TRAIL_SOURCES for
//     what a second one costs this channel.
//
//     What this gives up is real and worth naming: yellow, orange and red side
//     trails were separable by rhythm and are now separable by hue alone, and
//     an undecoded blaze no longer reads as uncertain from its dotted rhythm.
//     Closures are unaffected by that change and have since moved further
//     away from it: lib/closureStyle.ts now draws barrier tape, so against a
//     solid line the distinction is texture rather than a second rhythm to
//     tell apart.
//
//  3. A side trail is never drawn over the through-route it hangs off. One
//     layer means one painter's order, and where two features share geometry
//     that order decides which colour a hiker sees - so it is decided here, by
//     `line-sort-key`, rather than by whichever feature the export wrote last.
//     See TRAIL_SORT_KEY_EXPRESSION.
//
//  4. Two trails on one treadway are drawn as two halves of one line (#1384,
//     the maintainer's choice of 2026-09-10). The pipeline publishes each
//     shared stretch as a pair of features on one chord with opposite signs;
//     two layers over both trail-line stacks draw an opaque casing over the
//     stretch and each half offset to its own side, and the network split
//     stops drawing the pairs as plain lines. See map/sharedGround.ts, which
//     also says why nothing is cut out of the original lines.
//
// Not handled here: the POI pins, which are their own two modules -
// poiLayers.ts for the source, layer and density rules, poiIcons.ts for the
// pin images themselves. This file composes them in rather than spelling them
// out, for the same reason the blaze expression is imported: the rendering
// rule for a category should live in one place.
//
// Nor the background cartography, on the same principle - liveTopo.ts owns the
// hiking sheet's layers and terrain.ts the contour intervals. What this file
// does own is the ORDER, which is where the map's real guarantees live and the
// one thing no single module can enforce alone. Bottom to top: paper backdrop,
// downloaded archive, live sheet, trail, pins. Each step of that is load-
// bearing and commented at the layer it applies to.
//
// Not handled here either: blaze "Black" (code 8). WIREFRAMES.md's table describes it
// as "wide casing, no fill — drawn by absence," but the real data has zero
// Black features today and lib/blaze.ts has no colour for it, so it falls to
// the neutral-grey defensive fallback and logs a warning. Giving it a real
// treatment needs a design decision and at least one real feature to look at.

import type {
  LayerSpecification,
  StyleSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import { BLAZE_MATCH_EXPRESSION } from '../lib/blaze'
import { buildAtcUpdateLayers } from '../lib/atcUpdateStyle'
import {
  buildClosureLayers,
  LONG_TERM_CLOSED_FILTER,
  LONG_TERM_CLOSURE_LAYER_ID,
} from '../lib/closureStyle'
import { buildDroughtLayer } from '../lib/droughtStyle'
import { buildAtcUpdateSource, ATC_UPDATE_SOURCE_ID } from './atcUpdateLayers'
import { buildClosureSource, CLOSURE_SOURCE_ID } from './closureLayers'
import {
  buildCorridorLayers,
  buildCorridorSource,
  CORRIDOR_SOURCE_ID,
} from './corridorLayers'
import {
  SHARED_GROUND_BLAZE_LAYER_ID,
  SHARED_GROUND_CASING_LAYER_ID,
  SHARED_GROUND_FILTER,
  SHARED_GROUND_PARTNER_SOURCE_PROPERTY,
  sharedGroundSideExpression,
} from './sharedGround'
import {
  buildDayHikeCasingLayers,
  buildDayHikePointLayers,
  buildDayHikeSource,
  buildDayHikeTickLayers,
  buildDayHikeTickSource,
  DAY_HIKE_SOURCE_ID,
  DAY_HIKE_TICK_SOURCE_ID,
} from './dayHikeLayers'
import { buildRouteLayers, buildRouteSource, ROUTE_SOURCE_ID } from './routeLayers'
import { buildDroughtSource, DROUGHT_SOURCE_ID } from './droughtLayers'
import {
  buildCoverageSeamLayers,
  buildCoverageSeamSource,
  COVERAGE_SEAM_LABEL_LAYER_ID,
  COVERAGE_SEAM_LAYER_ID,
  COVERAGE_SEAM_SOURCE_ID,
} from './coverageLayers'
import {
  buildPoiDotLayer,
  buildPoiLayer,
  buildPoiSource,
  buildPoiStalenessLayer,
  POI_PIN_MIN_ZOOM,
  POI_SOURCE_ID,
} from './poiLayers'
import { buildPoiLabelLayer } from './poiLabels'
import { buildWarningLayer, buildWarningSource, WARNING_SOURCE_ID } from './warningLayers'
import { buildWorkdayLayer, buildWorkdaySource, WORKDAY_SOURCE_ID } from './workdayLayers'
import { buildDisputeLayer, buildDisputeSource, DISPUTE_SOURCE_ID } from './disputeLayers'
import {
  CHOSEN_SYSTEM_SOURCES,
  chosenSystemFilter,
  chosenSystemSources,
  nearbyTrailFilter,
  nearbyTrailOpacityExpression,
} from './nearbyTrails'
import {
  badgeHaloColor,
  badgePlateImageId,
  badgeTextColor,
  buildTrailBadgeLayer,
  buildTrailBadgeSource,
  TRAIL_BADGE_LAYER_ID,
  TRAIL_BADGE_SOURCE_ID,
} from './trailBadges'
import { NETWORK_TILES_LAYER, NETWORK_TILES_URL } from './networkTiles'
import { NEARBY_TRAILS_TILES_MAX_ZOOM, NEARBY_TRAILS_TILES_MIN_ZOOM } from '../lib/config'
import {
  buildTrailLabelLayer,
  NEARBY_TRAIL_LABEL_LAYER_ID,
  TRAIL_LABEL_LAYER_ID,
  TRAIL_LABEL_MIN_ZOOM,
  trailLabelSortKeyExpression,
} from './trailLabels'
import type { BackgroundSource, MapStyle, Theme } from '../lib/userPreferences'
import {
  BUNDLED_GLYPHS,
  attachSheetAppearance,
  liveTopoLayers,
  liveTopoSources,
  sheetVariant,
  type SheetAppearance,
} from './liveTopo'
import {
  DEC_CREDIT,
  MOHONK_CREDIT,
  NYNJTC_CREDIT,
  OPRHP_CREDIT,
  OSM_CREDIT,
  USGS_TOPO_CREDIT,
} from './credits'
import { whenStyleReady } from './styleReady'
import { TRAILS } from '../lib/trails'
import type { GeoJSONSource, Map as MapLibreMap, MapSourceDataEvent } from 'maplibre-gl'
import type { ResolvedTheme } from '../lib/theme'
import type { ContourUnits, TerrainUrls } from './terrain'

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

/**
 * What the map paints wherever it has no topo ink to paint.
 *
 * White, the field sheet's own paper (MAP_STYLE_SPEC.md - the palette's
 * halos and hillshade highlight are the same #ffffff, so uncovered ground,
 * label halos and lit slopes read as one sheet). It used to be the chrome's
 * `--paper-100` cream; the field palette was reviewed on white, and a cream
 * ground under white-haloed labels reads as two papers. Named rather than
 * inlined because chrome.css's pre-WebGL fallback has to agree on the same
 * paper - see `.map-view` there.
 *
 * Uncovered ground is not an edge case, and reaching it does not need the
 * pipeline's transparent-nodata tiles to be involved at all - the corridor
 * archive is a 30-mile strip, so panning off it, zooming out below the
 * archive's own minzoom, opening the app before the download finishes, or
 * simply moving faster than tiles decode each leave a hole too.
 */
export const MAP_BACKGROUND_COLOR = '#ffffff'

/*
 * THE CANVAS'S HALF OF MAP APPEARANCE
 *
 * Everything in the chrome follows `data-theme` through the design tokens
 * (design-system/tokens/colors.css). The map cannot: it is WebGL, its colours
 * are paint properties on a style specification, and a style has never heard
 * of a CSS variable. So the resolved theme comes down as a value
 * (lib/useTheme.ts -> App -> MapScreen -> MapView) - joined since
 * MAP_STYLE_SPEC.md by the map style and red-light preferences, which never
 * touch the chrome at all - and the definitions below are what the three of
 * them mean once they get here.
 *
 * The layers they touch beyond the sheet are this file's own - the backdrop,
 * the downloaded archive, and the trail's casing and blaze - which is why
 * this lives here rather than in a module of its own: a fifth file holding a
 * table of layer ids owned by this one is indirection, not separation. The
 * live sheet's twenty-one layers are handled where their palette is
 * (liveTopo.ts's attachSheetAppearance), the same way liveTopo.ts already
 * owns the unit switch for its own labels.
 *
 * THE ARCHIVE CANNOT GO DARK, AND IS DIMMED INSTEAD
 *
 * TECHNICAL_ARCHITECTURE.md recorded this trade-off when the corridor
 * background was chosen: US Topo quads are pre-rendered raster, their ink is
 * pixels, and no semantic swap is available - there is no "draw the contours
 * brown-on-ink instead", because nothing here knows which pixels are contours.
 * That note named canvas-level filters as the fallback, and this is that
 * fallback taken one step better: MapLibre's own raster paint properties dim
 * the archive LAYER, on the GPU, leaving the trail lines, the pins and the
 * chrome over it at full strength. A CSS filter on the canvas would have
 * dimmed those too - which would make the one safety-critical thing on the
 * screen the thing dark mode faded out.
 *
 * So under a dark sheet the archive is a dimmed paper map rather than a dark
 * one, and that limitation is not hidden: a hiker on the downloaded background
 * gets a quieter version of the same sheet, a hiker on the live background
 * gets a genuinely dark one. "Dark sheet" rather than "dark theme" since the
 * style preference arrived: night_hike picked under a light theme dims the
 * archive exactly as the dark theme does, because what the dimming serves is
 * the sheet the archive sits under, not the chrome around the canvas.
 */

/** Whether an appearance resolves to a dark sheet - night_hike outright (red
 *  light included) or the dark theme. Defined as "not the day palette" so it
 *  cannot drift from the variant table's own composition. */
export function sheetIsDark(appearance: SheetAppearance): boolean {
  return sheetVariant(appearance).dark
}

/** Whether the red-light sub-mode is actually in force - armed AND on the
 *  style it refines. The toggle alone means nothing under field, exactly as
 *  the variant table treats it. */
export function redLightActive(appearance: SheetAppearance): boolean {
  return sheetVariant(appearance).redLight
}

/**
 * The backdrop, per theme.
 *
 * chrome.css paints `.map-view` with the same pair as its pre-WebGL fallback,
 * and that identity is load-bearing rather than tidy: the handover from the
 * DOM's background to the style's backdrop layer has to be invisible in BOTH
 * themes, not only the one these were picked in. (The dark value is also
 * `--bg-page` under the dark theme; the light one stopped being a token when
 * the field sheet moved the map onto white paper - see MAP_BACKGROUND_COLOR.)
 *
 * Per THEME, while the sheet's palette is per appearance - which is why
 * mapBackdrop() below exists and callers with an appearance in hand use it
 * instead. This record stays because the two explicit sheets it names are
 * real anchor points the tests and the CSS pin against.
 */
export const MAP_BACKDROP: Record<ResolvedTheme, string> = {
  light: MAP_BACKGROUND_COLOR,
  // night_hike's ink - the sheet the DEFAULT dark path lands on (field's
  // auto-dark is night_hike), which is what makes it the right pre-WebGL
  // fallback for the dark theme. Individual sheets carry their own backdrops
  // in SHEET_VARIANTS; this pair is the anchor chrome.css and the tests pin.
  dark: '#0c1410',
}

/**
 * The backdrop, per appearance: each sheet's own paper, straight from its
 * card in the variant table - parchment's warm quad paper, red light's
 * near-black red ink, and everything between.
 */
export function mapBackdrop(appearance: SheetAppearance): string {
  return sheetVariant(appearance).backdrop
}

/**
 * How far the downloaded archive is turned down, per theme.
 *
 * Light is the spec's own defaults, written out rather than left implicit,
 * because these get applied to a LIVE map: switching back out of dark has to
 * restore the property, and "restore" needs a value to restore to.
 *
 * The dark numbers are a judgement, and the judgement is that legibility wins.
 * 0.62 takes the quads' white paper to about the lightness of a slate roof -
 * clearly no longer a lamp, still clearly a map. Pushing it to 0.3 makes a
 * handsome screenshot and a sheet whose 1:24,000 contour labels cannot be
 * read, which is the wrong trade on the one screen a hiker uses to decide
 * where to walk. The desaturation stops the water layers' blue glowing out of
 * the dimmed sheet, and the contrast nudge puts back some of the separation
 * the dimming costs.
 */
export const ARCHIVE_RASTER_PAINT: Record<
  ResolvedTheme,
  Readonly<Record<string, number>>
> = {
  light: {
    'raster-brightness-max': 1,
    'raster-saturation': 0,
    'raster-contrast': 0,
  },
  dark: {
    'raster-brightness-max': 0.62,
    'raster-saturation': -0.2,
    'raster-contrast': 0.08,
  },
}

/** The archive's dimming for an appearance: dark-sheet appearances dim, day
 *  sheets do not - see the header note on why this follows the sheet rather
 *  than the theme. */
export function archiveRasterPaint(
  appearance: SheetAppearance,
): Readonly<Record<string, number>> {
  return ARCHIVE_RASTER_PAINT[sheetIsDark(appearance) ? 'dark' : 'light']
}

/**
 * The hairline under every blaze, per appearance - each sheet inks its own
 * (SheetVariant.casing). Day sheets carry it near their label ink so the
 * near-white centerline keeps an edge on pale paper; dark sheets drop it to
 * near-black so the casing recedes into ground and the blaze itself is the
 * edge.
 */
export function trailCasingColor(appearance: SheetAppearance): string {
  return sheetVariant(appearance).casing
}

/**
 * What red light does to the blazes: one red-amber, every trail
 * (MAP_STYLE_SPEC.md). A blaze colour is a fact about the ground, and
 * recolouring facts is exactly what this map exists not to do - but under red
 * light every hue would render as a barely-distinguishable dark red anyway,
 * which is the same information loss drawn less legibly. So the loss is taken
 * honestly: the line stays the most legible thing on the screen, in the one
 * hue the mode permits, and blaze identity moves to the tapped trail's
 * details rather than pretending to survive on the line.
 */
export const RED_LIGHT_BLAZE_COLOR = '#e8804a'

/**
 * Blazes with no edge of their own on white paper. Today: White (#1283).
 *
 * lib/blaze.ts measures White against the field sheet's paper at 1.02:1 and
 * keeps it because "its width and casing are what carry it". On a layer
 * with a casing that is the whole answer, and since 2026-09-10 it is the
 * only answer for a real line: the maintainer's "make it white" on the
 * frame (this file's header, rule 2). Where a layer has NO casing - the two
 * corridor-view sketches - a near-white blaze on a DAY sheet is inked in the
 * casing colour instead, one dark line rather than no visible line, which
 * is the empty frame #1291 exists to prevent. Blaze identity there moves to
 * the badge's chip, the legend's swatch and the tapped line's sheet: the
 * same trade blazeLineColor already makes for red light.
 *
 * DARK SHEETS ARE LEFT ALONE, and the guard is the whole reason this is a
 * function of the appearance: trailCasingColor is near-black on every dark
 * sheet, so inking White in it would make the A.T. invisible on ink. There
 * a white line has exactly the surround it needs.
 */
export const NEAR_WHITE_BLAZES: readonly string[] = ['White']

/** Whether the sheet inks near-white blazes in the casing colour on a layer
 *  with no casing: day sheets only, red light included in the dark half by
 *  construction. */
export function inksNearWhiteAsCasing(appearance: SheetAppearance): boolean {
  return !sheetIsDark(appearance)
}

function nearWhiteBlazeCondition(): unknown[] {
  return ['in', ['get', 'blaze_color'], ['literal', [...NEAR_WHITE_BLAZES]]]
}

/**
 * `line-color` for every blaze layer, per appearance: red light's one hue,
 * or the shared blaze match - with near-white swapped for the sheet's
 * casing ink on day sheets where the layer draws with no casing under it
 * (`cased: false`, the sketches; see NEAR_WHITE_BLAZES). A cased line is
 * the match on every sheet: white stays white, and the casing is its edge.
 */
export function blazeLineColor(appearance: SheetAppearance, cased: boolean): unknown {
  if (redLightActive(appearance)) return RED_LIGHT_BLAZE_COLOR
  if (cased || !inksNearWhiteAsCasing(appearance)) return BLAZE_MATCH_EXPRESSION
  return [
    'case',
    nearWhiteBlazeCondition(),
    trailCasingColor(appearance),
    BLAZE_MATCH_EXPRESSION,
  ]
}

/**
 * Applies an appearance - theme, map style, red light - to a map that is
 * already built, and hands back a detach.
 *
 * Repaints rather than rebuilds, which is not an optimisation but the same
 * rule MapView.tsx keeps for the scale bar's units and contours.ts keeps for
 * the contour interval: a preference change must not cost a WebGL context.
 * Swapping the style out drops that context and takes with it the POI source
 * pushed in from IndexedDB, every archive tile in flight, and the camera - so
 * a hiker who taps "Dark" while walking would watch the map they were reading
 * disappear and rebuild itself.
 *
 * Two waits, not one. The backdrop is in the style from the first frame; the
 * sheet's layers are absent entirely on the downloaded background, and one
 * shared probe would leave the backdrop waiting on a layer that is never
 * coming.
 */
export function attachMapAppearance(
  map: MapLibreMap,
  appearance: SheetAppearance,
): () => void {
  const detachBase = whenStyleReady(
    map,
    () => map.getLayer(BACKDROP_LAYER_ID) !== undefined,
    () => {
      map.setPaintProperty(BACKDROP_LAYER_ID, 'background-color', mapBackdrop(appearance))

      // Guarded on its own: the backdrop proves the style is parsed and takes
      // writes, not that this particular layer is in it. It always is today -
      // both backgrounds stack over the archive - and a guard that costs
      // nothing is cheaper than finding out the day one of them does not.
      if (map.getLayer(TOPO_LAYER_ID) !== undefined) {
        for (const [property, value] of Object.entries(archiveRasterPaint(appearance))) {
          map.setPaintProperty(TOPO_LAYER_ID, property as never, value as never)
        }
      }

      // Every trail casing and every blaze-coloured line, same per-layer
      // guards - the lists rather than two named layers, for the reason
      // TRAIL_LINE_LAYER_IDS gives. Writing the blaze colour unconditionally
      // is what makes leaving red light an actual restore: the match
      // expression goes back exactly as buildMapStyle spelled it. The casing
      // WIDTH is not repainted: it stopped being a function of the
      // appearance on 2026-09-10, when the zero-under-near-white casing went
      // with the dot rhythm (this file's header, rule 2).
      for (const layerId of TRAIL_CASING_LAYER_IDS) {
        if (map.getLayer(layerId) === undefined) continue
        map.setPaintProperty(layerId, 'line-color', trailCasingColor(appearance) as never)
      }
      for (const layerId of BLAZE_LINE_LAYER_IDS) {
        if (map.getLayer(layerId) === undefined) continue
        // Per layer: the two sketches ink a near-white line dark, because
        // they have no casing to edge it; every cased line leaves it white.
        // One colour for all of them would put the black line back on the
        // A.T. at every theme switch (DARK_INKED_BLAZE_LAYER_IDS).
        map.setPaintProperty(
          layerId,
          'line-color',
          blazeLineColor(
            appearance,
            !DARK_INKED_BLAZE_LAYER_IDS.includes(layerId),
          ) as never,
        )
      }

      // The through-route badge (#1283): its plate is an image per sheet
      // family and its ink a paint property, both swapped here so a badge
      // never sits paper-white on a night sheet after a switch.
      if (map.getLayer(TRAIL_BADGE_LAYER_ID) !== undefined) {
        map.setLayoutProperty(
          TRAIL_BADGE_LAYER_ID,
          'icon-image',
          badgePlateImageId(appearance) as never,
        )
        map.setPaintProperty(
          TRAIL_BADGE_LAYER_ID,
          'text-color',
          badgeTextColor(appearance) as never,
        )
        map.setPaintProperty(
          TRAIL_BADGE_LAYER_ID,
          'text-halo-color',
          badgeHaloColor(appearance) as never,
        )
      }

      // The trail labels' two colours (#930). Repainted here rather than left
      // to a rebuild for the same reason the three above are: a theme switch
      // repaints in place, so a label layer omitted from this list would keep
      // the previous theme's ink and halo — dark text with a dark halo after
      // switching to the dark sheet, which is a name nobody can read.
      if (map.getLayer(TRAIL_LABEL_LAYER_ID) !== undefined) {
        map.setPaintProperty(
          TRAIL_LABEL_LAYER_ID,
          'text-color',
          trailCasingColor(appearance) as never,
        )
        map.setPaintProperty(
          TRAIL_LABEL_LAYER_ID,
          'text-halo-color',
          mapBackdrop(appearance) as never,
        )
      }

      // The coverage seam's ink and halo (#557), on the same reasoning as the
      // labels above: it is inked in the casing colour so a theme switch
      // that leaves it behind draws a dark dashed line across a dark sheet.
      if (map.getLayer(COVERAGE_SEAM_LAYER_ID) !== undefined) {
        map.setPaintProperty(
          COVERAGE_SEAM_LAYER_ID,
          'line-color',
          trailCasingColor(appearance) as never,
        )
      }
      if (map.getLayer(COVERAGE_SEAM_LABEL_LAYER_ID) !== undefined) {
        map.setPaintProperty(
          COVERAGE_SEAM_LABEL_LAYER_ID,
          'text-color',
          trailCasingColor(appearance) as never,
        )
        map.setPaintProperty(
          COVERAGE_SEAM_LABEL_LAYER_ID,
          'text-halo-color',
          mapBackdrop(appearance) as never,
        )
      }
    },
    'Map appearance',
  )

  const detachSheet = attachSheetAppearance(map, appearance)

  return () => {
    detachBase()
    detachSheet()
  }
}

/**
 * Re-points the trail source at a different set of lines, on a live map.
 *
 * The same promise `attachPoiData` makes, for data that arrives on the same
 * clock: the lines are read out of IndexedDB well after the map is built, and
 * feeding them in by rebuilding the map drops the WebGL context, every tile in
 * flight and the camera along with them. A hiker watching that sees the map
 * blink and re-frame itself a second after it appeared, which is what this
 * exists to stop - see App.mapLifecycle.test.tsx.
 *
 * `setData` takes a URL as readily as a feature collection, so the blob URL the
 * shell mints for the downloaded lines can be handed straight over - MapLibre
 * fetches it and re-tiles the source in place.
 */
export function attachTrailData(map: MapLibreMap, trailsUrl: string): () => void {
  return whenStyleReady(
    map,
    // The source itself, like the POIs: getting it back proves the style spec
    // is parsed and that this write is legal, and it is the narrowest question
    // that answers "can this land".
    () => map.getSource(TRAILS_SOURCE_ID) !== undefined,
    () => {
      // `getSource` answers with the union of every source kind, and only the
      // GeoJSON one takes new data.
      const source = map.getSource<GeoJSONSource>(TRAILS_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(trailsUrl as never)
    },
    'Trail lines',
  )
}

/**
 * The corridor-view centerline, or nothing (#869) - drawn until THIS map has
 * the real line on screen (#1291).
 *
 * Pushed and cleared through the same source, because "the sketch is gone"
 * is a state this has to be able to reach: an empty collection rather than a
 * removed source, so there is one shape of style whatever a launch is doing.
 *
 * WHO DECIDES IT IS GONE. The shell used to: lib/useTrailData.ts withdrew the
 * URL the moment it held the real lines. But the shell holding an object URL
 * for trails.geojson is not the map having drawn it - the worker still has
 * to fetch, parse and tile 11.5 MB - and a map mounted after that moment was
 * handed nothing and drew nothing for seconds (the measurement is on the
 * hook). So the shell hands the sketch over for as long as it has one, says
 * separately whether it holds real lines (`trailLinesHeld`), and this
 * empties the sketch when the map's own trails source reports loaded:
 * checked on attach, on every `sourcedata` for that source, and on `idle`,
 * which is the render after the last tile. Per map instance, which is the
 * point - a rebuilt map gets the sketch again for exactly the seconds it
 * needs it.
 *
 * `trailLinesHeld` false means the trails source still holds the empty
 * placeholder the style is seeded with, which loads instantly and must not
 * count: without the flag the sketch would be emptied on the first idle of
 * every cold launch, before the real line had even been requested.
 *
 * See lib/config.ts's TRAILS_OVERVIEW_KEY for what this line is worth -
 * 100 m of tolerance, which is a sketch at the corridor view and a lie at
 * z14. The layer's `maxzoom` is the other half of keeping that true.
 */
export function attachTrailOverview(
  map: MapLibreMap,
  overviewUrl: string | null,
  trailLinesHeld: boolean,
): () => void {
  let stopWatching: (() => void) | null = null
  const detach = whenStyleReady(
    map,
    () => map.getSource(TRAIL_OVERVIEW_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(TRAIL_OVERVIEW_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      const clear = () => source.setData(emptyTrailOverview() as never)
      if (overviewUrl === null || (trailLinesHeld && trailLinesDrawn(map))) {
        clear()
        return
      }
      source.setData(overviewUrl as never)
      if (!trailLinesHeld) return

      function stop() {
        map.off('sourcedata', onSourceData)
        map.off('idle', check)
        stopWatching = null
      }
      function check() {
        if (!trailLinesDrawn(map)) return
        clear()
        stop()
      }
      function onSourceData(event: MapSourceDataEvent) {
        if (event.sourceId === TRAILS_SOURCE_ID) check()
      }
      stopWatching = stop
      map.on('sourcedata', onSourceData)
      map.on('idle', check)
    },
    'Corridor-view centerline',
  )
  return () => {
    detach()
    stopWatching?.()
  }
}

/** Whether this map's own trails source has loaded what it was handed and
 *  has every tile the camera needs - MapLibre's `isSourceLoaded`, guarded
 *  because asking about a source the style does not hold logs an error.
 *  MapLibre counts a source that FAILED to load as loaded, so a real line
 *  that never arrives drops the sketch too - which is the frame the old
 *  design showed in every case, and is at least an honest empty map. */
function trailLinesDrawn(map: MapLibreMap): boolean {
  if (map.getSource(TRAILS_SOURCE_ID) === undefined) return false
  return map.isSourceLoaded(TRAILS_SOURCE_ID)
}

/** Whether the A.T.'s own sketch draws as an untaken line: it does whenever
 *  the A.T.'s through-route source is not in the chosen system - nothing
 *  taken, or some other trail taken (#1306). */
function sketchUntaken(chosen: readonly string[]): boolean {
  return !PRIMARY_TRAIL_SOURCES.some((source) => chosen.includes(source))
}

/**
 * The A.T. sketch's `line-width`: the untaken taper while the A.T. is not
 * taken, its own tier once it is (#1306).
 *
 * Not a third rule - the SAME expression the real untaken line takes
 * (untakenTrailWidthExpression carries the argument and the frame), because
 * the sketch's whole contract is that a hiker cannot see the moment the
 * real line replaces it. A taken A.T. is at TRAIL_WIDTH_EXPRESSION,
 * unchanged from before #1306: 4.5 px is the emphasis the prototype's
 * x2.1 is for. Whether a hiker reads a 1.5 px dark line from Georgia to
 * Maine as the A.T., with no badge below the seam (#1292) to name it, is
 * @unvalidated beyond the preview frame.
 */
export function sketchWidthExpression(chosen: readonly string[]): unknown {
  return sketchUntaken(chosen)
    ? untakenTrailWidthExpression()
    : solidTrailWidthExpression()
}

/**
 * Re-points every line split, the ghosting, the labels' priority and the
 * badge at a newly taken trail, on a live map (#1306).
 *
 * The same shape as attachMapAppearance and for the same reason: taking a
 * trail is a preference change, and a preference change that rebuilt the
 * map would drop the WebGL context - App.mapLifecycle.test.tsx's regression.
 * So the filters and paints buildMapStyle spelled out for one `chosenTrailId`
 * are written again for another, through setFilter and setPaintProperty,
 * each layer guarded on its own presence. CHOSEN_TRAIL_SPLIT_LAYERS below is
 * every line layer that reads the chosen system; style.test.ts holds it
 * against the style so a split added later cannot be left on the previous
 * trail.
 */
export function attachChosenTrail(
  map: MapLibreMap,
  chosenTrailId: string | null,
): () => void {
  const chosen = chosenSystemSources(chosenTrailId)
  return whenStyleReady(
    map,
    () => map.getLayer(BLAZE_LAYER_ID) !== undefined,
    () => {
      const solid = chosenSystemFilter(chosen) as never
      const untaken = nearbyTrailFilter(chosen) as never
      const opacity = nearbyTrailOpacityExpression(chosen) as never
      const casingOpacity = ['*', 0.7, nearbyTrailOpacityExpression(chosen)] as never
      for (const [id, side] of CHOSEN_TRAIL_SPLIT_LAYERS) {
        if (map.getLayer(id) === undefined) continue
        map.setFilter(id, side === 'chosen' ? solid : untaken)
        map.setPaintProperty(
          id,
          'line-opacity',
          TRAIL_CASING_LAYER_IDS.includes(id) ? casingOpacity : opacity,
        )
      }
      if (map.getLayer(TRAIL_OVERVIEW_LAYER_ID) !== undefined) {
        map.setPaintProperty(TRAIL_OVERVIEW_LAYER_ID, 'line-opacity', opacity)
        map.setPaintProperty(
          TRAIL_OVERVIEW_LAYER_ID,
          'line-width',
          sketchWidthExpression(chosen) as never,
        )
      }
      for (const id of [TRAIL_LABEL_LAYER_ID, NEARBY_TRAIL_LABEL_LAYER_ID]) {
        if (map.getLayer(id) === undefined) continue
        map.setLayoutProperty(
          id,
          'symbol-sort-key',
          trailLabelSortKeyExpression(chosen) as never,
        )
        map.setPaintProperty(id, 'text-opacity', opacity)
      }
      if (map.getLayer(TRAIL_BADGE_LAYER_ID) !== undefined) {
        map.setPaintProperty(TRAIL_BADGE_LAYER_ID, 'icon-opacity', opacity)
        map.setPaintProperty(TRAIL_BADGE_LAYER_ID, 'text-opacity', opacity)
      }
    },
    'Taken trail',
  )
}

/** Every line layer whose filter reads the chosen system, and which side of
 *  its split it is - the three splits, in the order the style draws them. */
export const CHOSEN_TRAIL_SPLIT_LAYERS: ReadonlyArray<readonly [string, TrailLineSide]> =
  [
    [NETWORK_OVERVIEW_UNTAKEN_LAYER_ID, 'nearby'],
    [NETWORK_OVERVIEW_LAYER_ID, 'chosen'],
    [NEARBY_TRAIL_CASING_UNTAKEN_LAYER_ID, 'nearby'],
    [NEARBY_BLAZE_UNTAKEN_LAYER_ID, 'nearby'],
    [NEARBY_TRAIL_CASING_LAYER_ID, 'chosen'],
    [NEARBY_BLAZE_LAYER_ID, 'chosen'],
    [TRAIL_CASING_UNTAKEN_LAYER_ID, 'nearby'],
    [BLAZE_UNTAKEN_LAYER_ID, 'nearby'],
    [TRAIL_CASING_LAYER_ID, 'chosen'],
    [BLAZE_LAYER_ID, 'chosen'],
  ]

/**
 * Which half of the trail-line split a pair of layers draws (#1283).
 *
 * The chosen system, at its own tier; or every other line, at the network's
 * far weight below the seam. The filter and the width taper follow from
 * this one word, so a caller cannot pair the nearby filter with the taken
 * weight or the chosen filter with the untaken one - the split is only
 * honest as a partition, and this is what keeps it one.
 */
export type TrailLineSide = 'chosen' | 'nearby'

/**
 * The casing-and-blaze pair that draws one side of one source's trail lines.
 *
 * ONE TREATMENT, NOT TWO THAT CURRENTLY AGREE - lib/closureStyle.ts's
 * buildClosureLayers has the same shape for the same reason, and this was
 * extracted (#950) at the moment a second trail source appeared. Before that
 * there was one caller and the layers were written inline; the risk this
 * removes is not hypothetical, because the alternative on the table was
 * copying forty lines of paint expressions and hoping the next person who
 * adds a channel remembers there are two of them. Since #1283 there are FOUR
 * instances of it (two sources, two sides each), which is the same argument
 * twice over.
 *
 * Every argument below is an id, a source, or the side of the split. Nothing
 * about how a trail LOOKS is a parameter, which is the property that makes
 * the ghosting honest: a nearby trail is the same line drawn dimmer, and
 * finer below the seam, and both come from expressions reading the
 * feature's own `source` - the opacity from nearbyTrailOpacityExpression,
 * the side from the filter pair in map/nearbyTrails.ts - not from this
 * function being called differently.
 */
function buildTrailLineLayers(
  sourceId: string,
  casingId: string,
  blazeId: string,
  appearance: SheetAppearance,
  side: TrailLineSide,
  minzoom?: number,
  chosen: readonly string[] = CHOSEN_SYSTEM_SOURCES,
): LayerSpecification[] {
  const filter = (
    side === 'chosen' ? chosenSystemFilter(chosen) : nearbyTrailFilter(chosen)
  ) as never
  const untaken = side === 'nearby'
  return [
    {
      // Hairline dark casing, drawn under every blaze so the trail stays
      // readable over busy topo contours. It is doing more work than it used
      // to: with the line solid, the casing is the ONLY thing giving the
      // near-white centerline an edge against near-white paper, so it is
      // carried at a firmer opacity than when a gap in the line let it
      // through every few pixels.
      id: casingId,
      type: 'line',
      source: sourceId,
      filter,
      ...(minzoom === undefined ? {} : { minzoom }),
      layout: {
        'line-cap': 'round',
        'line-join': 'round',
        // Sorted like the blaze layer above it, though nothing visible
        // depends on it while every casing is the same colour. It is here so
        // that the day one is not - a heavier casing for a through-route, the
        // "drawn by absence" treatment WIREFRAMES.md reserves for Black - the
        // ordering rule is already in place rather than being a second bug
        // with the same shape as the first.
        'line-sort-key': TRAIL_SORT_KEY_EXPRESSION as unknown as number,
      },
      paint: {
        'line-color': trailCasingColor(appearance),
        // Tapered below the seam on the untaken side since #1306, so the
        // hairline stays a hairline under a line that is 1.5 px there. Under
        // every blaze, white included: the zero-under-near-white casing went
        // with the dot rhythm on 2026-09-10 (this file's header, rule 2).
        'line-width': (untaken
          ? untakenTrailCasingWidthExpression()
          : solidTrailCasingWidthExpression()) as unknown as number,
        // The casing's own 0.7, MULTIPLIED by the line's ghosting rather
        // than replaced by it. Both facts are true at once and they compose:
        // a casing is always slightly softer than the blaze it carries, and
        // a nearby trail's whole stack - blaze and casing together - sits
        // back from the chosen trail's. Replacing the 0.7 would give a
        // ghosted line a FIRMER edge than the chosen trail's, which is the
        // opposite of what this channel is for.
        'line-opacity': [
          '*',
          0.7,
          nearbyTrailOpacityExpression(chosen),
        ] as unknown as number,
      },
    },
    {
      id: blazeId,
      type: 'line',
      source: sourceId,
      filter,
      ...(minzoom === undefined ? {} : { minzoom }),
      // Round, matching the casing beneath it. Butt caps were what the dash
      // rhythm needed to keep its measured on/off lengths honest; on a solid
      // line they only leave a nick at every joint between two segments of
      // the same trail.
      //
      // The sort key is what keeps a side trail off the through-route it
      // branches from, where the two share geometry - see
      // TRAIL_SORT_KEY_EXPRESSION.
      layout: {
        'line-cap': 'round',
        'line-join': 'round',
        'line-sort-key': TRAIL_SORT_KEY_EXPRESSION as unknown as number,
      },
      paint: {
        // Through blazeLineColor rather than the match expression directly,
        // so a cold start under red light is red in its first frame - the
        // same reason `appearance` seeds the backdrop above. Cased, on both
        // sides: a white blaze is white here, with the casing as its edge
        // (NEAR_WHITE_BLAZES).
        'line-color': blazeLineColor(appearance, true) as unknown as string,
        // Its own tier, except on the untaken side below the seam, where
        // the tier is a rope and the network's far weight is what the
        // handoff drew (untakenTrailWidthExpression, #1306).
        'line-width': (untaken
          ? untakenTrailWidthExpression()
          : solidTrailWidthExpression()) as unknown as number,
        // The third channel (#783). Hue still says which blaze and width
        // still says which line the map is about; opacity says which SYSTEM,
        // which is the distinction an A.T.-only map never had to draw. See
        // map/nearbyTrails.ts for why it is opacity and not a halo or a hue.
        // No fourth: the dot rhythm #1283 put here went on 2026-09-10 (this
        // file's header, rule 2).
        'line-opacity': nearbyTrailOpacityExpression(chosen) as unknown as number,
      },
    },
  ]
}

/**
 * Both sides of one source's split, in draw order: the untaken pair UNDER
 * the taken pair, so the taken trail is never crossed by a line that is not
 * it. Four layers, one builder, and the only thing the two calls differ in
 * is the side.
 */
function buildTrailLineSplit(
  sourceId: string,
  ids: {
    casing: string
    blaze: string
    casingUntaken: string
    blazeUntaken: string
  },
  appearance: SheetAppearance,
  minzoom?: number,
  chosen: readonly string[] = CHOSEN_SYSTEM_SOURCES,
): LayerSpecification[] {
  return [
    ...buildTrailLineLayers(
      sourceId,
      ids.casingUntaken,
      ids.blazeUntaken,
      appearance,
      'nearby',
      minzoom,
      chosen,
    ),
    ...buildTrailLineLayers(
      sourceId,
      ids.casing,
      ids.blaze,
      appearance,
      'chosen',
      minzoom,
      chosen,
    ),
  ]
}

/**
 * The two layers that draw a shared stretch as two halves of one line
 * (header rule 4, map/sharedGround.ts). From the network tiles, since that
 * is where the pairs ride; over BOTH trail-line stacks, since the casing is
 * the mask that hides the plain lines under it. Widths are each half's own
 * tier through the same expressions the lines use, so the halves taper
 * where the lines taper.
 */
function buildSharedGroundLayers(
  appearance: SheetAppearance,
  minzoom: number,
  chosen: readonly string[] = CHOSEN_SYSTEM_SOURCES,
): LayerSpecification[] {
  const side = sharedGroundSideExpression()
  return [
    {
      id: SHARED_GROUND_CASING_LAYER_ID,
      type: 'line',
      source: NEARBY_TRAILS_SOURCE_ID,
      filter: SHARED_GROUND_FILTER as never,
      minzoom,
      layout: {
        'line-cap': 'round',
        'line-join': 'round',
        'line-sort-key': TRAIL_SORT_KEY_EXPRESSION as unknown as number,
      },
      paint: {
        'line-color': trailCasingColor(appearance),
        'line-width': sharedGroundCasingWidthExpression() as unknown as number,
        // Opaque: this casing is drawn OVER two lines, and a translucent rim
        // would be a different colour over the white half than over paper.
        'line-opacity': 1,
      },
    },
    {
      id: SHARED_GROUND_BLAZE_LAYER_ID,
      type: 'line',
      source: NEARBY_TRAILS_SOURCE_ID,
      filter: SHARED_GROUND_FILTER as never,
      minzoom,
      layout: {
        // Butt caps, unlike every other blaze: a round cap on an offset
        // half swings past the chord's end on its own side, and the two
        // halves' caps would cross.
        'line-cap': 'butt',
        'line-join': 'round',
        'line-sort-key': TRAIL_SORT_KEY_EXPRESSION as unknown as number,
      },
      paint: {
        'line-color': blazeLineColor(appearance, true) as unknown as string,
        'line-width': sharedGroundHalfWidthExpression() as unknown as number,
        'line-offset': sharedGroundOffsetExpression(side) as unknown as number,
        'line-opacity': nearbyTrailOpacityExpression(chosen) as unknown as number,
      },
    },
  ]
}

/**
 * One side of the network overview's split (#1135, #1283): the sketch has no
 * casing and its own tapering width, so it is not buildTrailLineLayers, but
 * it takes the same filter pair for the same reason.
 */
function buildNetworkOverviewLayer(
  layerId: string,
  appearance: SheetAppearance,
  side: TrailLineSide,
  chosen: readonly string[] = CHOSEN_SYSTEM_SOURCES,
): LayerSpecification {
  return {
    id: layerId,
    type: 'line',
    source: NETWORK_OVERVIEW_SOURCE_ID,
    filter: (side === 'chosen'
      ? chosenSystemFilter(chosen)
      : nearbyTrailFilter(chosen)) as never,
    maxzoom: POI_PIN_MIN_ZOOM,
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      // Uncased, so a near-white line is inked dark on a day sheet
      // (DARK_INKED_BLAZE_LAYER_IDS).
      'line-color': blazeLineColor(appearance, false) as unknown as string,
      'line-width': NETWORK_OVERVIEW_WIDTH_EXPRESSION as unknown as number,
      'line-opacity': nearbyTrailOpacityExpression(chosen) as unknown as number,
    },
  }
}

/**
 * The network's corridor-view sketch, or nothing (#1135).
 *
 * attachTrailOverview's shape but not its clock: that overview is pushed and
 * then CLEARED, because it exists only until the real centerline lands. Once
 * these lines are on the map they stay, because nothing better replaces them
 * below the seam - the full network's tiles start where this one stops. `null`
 * means "there is no sketch" - an older release, or a bucket holding the
 * artifact back with its parent - and draws as the A.T.-only opening view
 * this app had before the artifact existed.
 *
 * The full lines above the seam have no attach function since #1257: they are
 * a vector source (NEARBY_TRAILS_SOURCE_ID) whose tiles map/networkTiles.ts
 * reads as the camera asks, so there is no URL to hand over and no moment to
 * hand it over at.
 */
export function attachNetworkOverview(
  map: MapLibreMap,
  networkOverviewUrl: string | null,
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(NETWORK_OVERVIEW_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(NETWORK_OVERVIEW_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData((networkOverviewUrl ?? emptyTrailOverview()) as never)
    },
    'Network overview',
  )
}

/** What the overview source holds before there is one and after it is done.
 *  A function rather than a shared constant: MapLibre's typings want a
 *  mutable feature list, and one object handed to both the style and every
 *  later `setData` is one object two of them could write to. */
function emptyTrailOverview(): GeoJSON.FeatureCollection {
  return { type: 'FeatureCollection', features: [] }
}

/**
 * The same layers, told which layer inside a vector tile they draw from.
 *
 * The builders below (buildTrailLineLayers, buildClosureLayers,
 * buildTrailLabelLayer) were written for GeoJSON sources, which have no inner
 * layers, and they still serve the A.T.'s that way. A vector source's layers
 * need `source-layer` besides, and a layer without one draws nothing, without
 * an error - so it is set here in one place over the whole set rather than
 * threaded through three builders as a parameter two of their callers would
 * have to pass as undefined. style.test.ts checks every layer over the
 * network source carries it.
 */
function onSourceLayer(
  layers: LayerSpecification[],
  sourceLayer: string,
): LayerSpecification[] {
  return layers.map(
    (layer) => ({ ...layer, 'source-layer': sourceLayer }) as LayerSpecification,
  )
}

/** The pipeline's own key for ATC's trail-centerline feed (pipeline/sources.json). */
export const CENTERLINE_SOURCE = 'centerline'

/** The pipeline's own key for NYNJTC's Long Path feed (pipeline/sources.json),
 *  the trail that source `owns_route_names` - the first import to join
 *  CENTERLINE_SOURCE in PRIMARY_TRAIL_SOURCES below (#1307). */
export const LONG_PATH_SOURCE = 'nynjtc_long_path'

/**
 * Trail sources drawn at the primary width: the through-route of a trail
 * system, as against the side trails and spurs hanging off it.
 *
 * This is a ROLE, and deliberately a list rather than a single source. It
 * held only ATC's `centerline` until #1307, when the Long Path became the
 * first import to join it - the NYNJTC alone maintains several trail
 * systems, so a Highlands Trail import joins this tier the same way, and a
 * `centerline` feed that itself grows past the AT needs no change here at
 * all. Joining this tier is a claim about which trail a LINE is, and a
 * narrower one than being takeable (map/trailBadges.ts's TAKEABLE_SOURCES) -
 * the Long Path draws at through-route width and wears a badge with nothing
 * here saying a hiker can stand on it as their trail yet.
 *
 * What the first join costs is named where the claim is made (WIREFRAMES.md
 * §3): with one through-route on the map, the widest line IS the AT. With
 * two, width answers "through-route or spur" and stops answering "which
 * trail is this" - still a hue-independent channel, but a coarser one.
 */
export const PRIMARY_TRAIL_SOURCES: readonly string[] = [
  CENTERLINE_SOURCE,
  LONG_PATH_SOURCE,
]

/** The two width tiers, in CSS pixels. */
export const PRIMARY_TRAIL_WIDTH = 4.5
export const SIDE_TRAIL_WIDTH = 2.5

/**
 * Line width in CSS pixels, per trail source.
 *
 * A through-route is the subject of this map and everything else is context,
 * so it is drawn close to twice the width of a side trail. That is the
 * hierarchy a paper trail map has always drawn, and it is also the map's
 * hue-independent channel now that the dash rhythms are gone: the widest lines
 * on screen are the trails the map is about, whatever the light is doing to
 * the colours.
 *
 * Keyed off `source` - the attribute export_trails.py already publishes on
 * every feature - rather than off `blaze_color`, because this is a question
 * about which trail a line IS, not about how it is blazed. (Those two nearly
 * coincide today, since the centerline is flat-defaulted to White, but only
 * nearly: WIREFRAMES.md's own table notes centerline features carrying Purple
 * and Other, and a White-blazed side trail should still be drawn as a side
 * trail.)
 */
export const TRAIL_LINE_WIDTHS: Record<string, number> = {
  ...Object.fromEntries(
    PRIMARY_TRAIL_SOURCES.map((source) => [source, PRIMARY_TRAIL_WIDTH]),
  ),
  side_trails: SIDE_TRAIL_WIDTH,
}

/**
 * What a source this build has never heard of is drawn at.
 *
 * The side-trail width deliberately, not a through-route's: a later import
 * should reach the map rather than be invisible, and should not claim the top
 * tier on its way there. Joining PRIMARY_TRAIL_SOURCES is how a trail becomes
 * a through-route, and that is a decision someone makes rather than a default
 * an unrecognised source falls into.
 */
export const DEFAULT_TRAIL_LINE_WIDTH = SIDE_TRAIL_WIDTH

/**
 * Draw order inside a trail layer: through-routes over everything else.
 *
 * Every trail line lives in ONE layer, so within that layer the painter's
 * order is decided by the order the features happen to arrive in - which is
 * export order, which is nobody's decision. Where a side trail shares geometry
 * with the through-route it hangs off (and they share a lot of it: a spur that
 * leaves the AT is digitized from the AT's own vertices, and ATC's side_trails
 * often run coincident with the centerline for a stretch before branching),
 * whichever feature is drawn last wins the pixels.
 *
 * What that looked like on screen is the bug this fixes: the AT, drawn white,
 * with grey and blue stretches punched through it wherever an unblazed or
 * blue-blazed side trail happened to be exported after the centerline. The
 * hiker reads that as "the trail changes blaze here", which is exactly the
 * false statement at a junction that this map exists not to make.
 *
 * `line-sort-key` decides it instead, off the same `source` attribute that
 * decides width - higher sorts on top, so a through-route is painted last and
 * a side trail can never cover it. The two tiers are all that is needed:
 * within a tier, one line covering another is two lines of equal standing
 * overlapping, which is honest.
 */
export const PRIMARY_TRAIL_SORT_KEY = 1
export const SIDE_TRAIL_SORT_KEY = 0

export const TRAIL_SORT_KEY_EXPRESSION = [
  'case',
  ['in', ['get', 'source'], ['literal', [...PRIMARY_TRAIL_SOURCES]]],
  PRIMARY_TRAIL_SORT_KEY,
  SIDE_TRAIL_SORT_KEY,
]

/** How far the dark casing shows past each side of the line it sits under. */
export const CASING_OVERHANG = 1

/**
 * The widest a blaze is ever drawn, and the width a closure has to stay
 * markedly clear of (lib/closureStyle.ts and its tests read this).
 *
 * Derived from the table rather than written down twice, so widening a
 * through-route - or admitting a new one - cannot quietly narrow the gap that
 * keeps a closure from reading as a trail.
 */
export const BLAZE_LINE_WIDTH = Math.max(
  DEFAULT_TRAIL_LINE_WIDTH,
  ...Object.values(TRAIL_LINE_WIDTHS),
)
export const CASING_LINE_WIDTH = BLAZE_LINE_WIDTH + CASING_OVERHANG * 2

/**
 * `line-width` for the blaze layer, and for the casing under it.
 *
 * One expression each, built from the one table above. The casing is the same
 * expression plus a constant overhang, which is what keeps the hairline a
 * hairline on a 2.5px side trail and on a 4.5px through-route alike - a casing
 * scaled proportionally would be twice as heavy under a through-route as under
 * everything else.
 */
function trailWidthExpression(
  extra: number,
  scale = 1,
  /** Which property names the tier - `source` for a line's own; a shared
   *  stretch's half also asks its partner's (SHARED_GROUND_PARTNER_SOURCE_PROPERTY).
   *  Read through `to-string` for any other property, since `match` refuses
   *  a null input and a plain line carries none. */
  property = 'source',
): unknown[] {
  return [
    'match',
    property === 'source' ? ['get', 'source'] : ['to-string', ['get', property]],
    ...Object.entries(TRAIL_LINE_WIDTHS).flatMap(([source, width]) => [
      source,
      width * scale + extra,
    ]),
    DEFAULT_TRAIL_LINE_WIDTH * scale + extra,
  ]
}

export const TRAIL_WIDTH_EXPRESSION = trailWidthExpression(0)
export const TRAIL_CASING_WIDTH_EXPRESSION = trailWidthExpression(CASING_OVERHANG * 2)

/**
 * The network overview's width, tapering across the representational band
 * (#1135) - the one paint expression that layer does not share with the
 * lines it sketches, and the reason is drawn rather than argued: at the
 * side-trail width the opening camera's dense park clusters render as a
 * cloud of coloured dots over New York, which is the exact texture #1135
 * just took off this view (a sub-pixel segment under round caps IS a dot).
 * Measured on a local serve_processed.py build, 2026-08-27.
 *
 * The seam-end stop is DEFAULT_TRAIL_LINE_WIDTH by name, not by value:
 * every source in the overview takes the side-trail tier from
 * TRAIL_WIDTH_EXPRESSION (none is a through-route), so landing on that
 * constant at the seam makes the handoff to the full network's layers
 * pixel-seamless - and style.test.ts pins it so the two cannot drift apart.
 *
 * The far end was 0.8 px, picked against that local build for SOLID lines
 * as the mockup's own weight for the mass. Under the dot rhythm (#1283) it
 * stopped working: a dot is the line's own diameter, and 0.8 px dots at 45%
 * are a sub-pixel haze - the tenth preview build of #1285 showed the whole
 * New York network as a faint speckle, and the maintainer read the opening
 * camera as the A.T. alone ("at least the Long Path should be visible",
 * 2026-09-09, #1306). It is now the prototype's own weight for an untaken
 * line at the continental camera: `Opening Map Options.html` frame 2a draws
 * every untaken line at `lineWidth: 1.5` at the `us` scope. The dots went
 * on 2026-09-10 (this file's header, rule 2) and the weight stayed: a
 * solid 1.5 px line is at least the dots' own diameter, so nothing about
 * the haze argument got weaker. Whether 1.5 px solid lines over the park
 * clusters read as trails or as a smear is @unvalidated beyond the preview
 * frame; #1307 is where the long-distance trails get their own weight and
 * the clusters stop mattering.
 *
 * The A.T.'s own sketch takes the same far end while the A.T. is not taken
 * (sketchWidthExpression, #1306) - frame 2a draws the untaken A.T. at this
 * weight too, and a heavier line there is a rope.
 */
export const NETWORK_OVERVIEW_FAR_WIDTH = 1.5

/** The zoom the far end of every taper is pinned at: the overview band's
 *  own floor, the widest the corridor camera ever gets. */
export const OVERVIEW_FAR_ZOOM = 4

/**
 * One line-width taper across the representational band: `far` at the
 * continental camera, `atSeam` at POI_PIN_MIN_ZOOM, linear between.
 *
 * Written once because three layers take it and they have to agree to the
 * pixel: the network overview sketch, the A.T.'s own sketch while it is
 * untaken, and the real untaken lines that replace both at the seam
 * (sketchWidthExpression and untakenTrailWidthExpression, #1306). The seam
 * stop is always the layer's own tier, so every taper lands where the
 * un-tapered layers start and no handoff is a restyle.
 *
 * `atSeam` may be a data-driven expression - MapLibre allows that in an
 * interpolate's stops for a data-driven property, which `line-width` is -
 * but the whole taper must stay TOP LEVEL: a zoom expression nested inside
 * a `case` is a style error, which is why the near-white casing's `case`
 * goes inside each stop rather than around the interpolate.
 */
function overviewTaper(far: unknown, atSeam: unknown): unknown[] {
  return [
    'interpolate',
    ['linear'],
    ['zoom'],
    OVERVIEW_FAR_ZOOM,
    far,
    POI_PIN_MIN_ZOOM,
    atSeam,
  ]
}

/**
 * The far end for a network overview line published with a `through_route`
 * flag - export_nearby_trails.py's write_overview, on a trail that cleared
 * NAMED_TRAIL_THRESHOLD_MILES (#1307). "#1307 is where the long-distance
 * trails get their own weight and the clusters stop mattering" (this file's
 * own line, above) - this is that weight.
 *
 * Twice NETWORK_OVERVIEW_FAR_WIDTH, picked the same way that constant's own
 * far end was: legible over the generic haze without approaching a
 * chosen system's own weight, should one of these trails ever be
 * takeable (map/trailBadges.ts's TAKEABLE_SOURCES says none but the AT is,
 * yet). `@unvalidated` the same way NETWORK_OVERVIEW_FAR_WIDTH's own history
 * records: nobody has watched this weight against the generic haze on a
 * phone, only reasoned it from the two constants either side of it.
 */
export const NETWORK_OVERVIEW_THROUGH_ROUTE_FAR_WIDTH = NETWORK_OVERVIEW_FAR_WIDTH * 2

/**
 * NETWORK_OVERVIEW_FAR_WIDTH, made data-driven on `through_route` - nested
 * INSIDE overviewTaper's `far` stop rather than wrapped around the whole
 * taper, because a zoom expression inside a `case` is a style error
 * (overviewTaper's own header: "the whole taper must stay TOP LEVEL").
 * Absent or false reads as the generic weight: `get` on a missing property
 * is null, and `null === true` is false, never a thrown expression.
 */
export const NETWORK_OVERVIEW_FAR_WIDTH_EXPRESSION = [
  'case',
  ['==', ['get', 'through_route'], true],
  NETWORK_OVERVIEW_THROUGH_ROUTE_FAR_WIDTH,
  NETWORK_OVERVIEW_FAR_WIDTH,
]

export const NETWORK_OVERVIEW_WIDTH_EXPRESSION: unknown[] = overviewTaper(
  NETWORK_OVERVIEW_FAR_WIDTH_EXPRESSION,
  DEFAULT_TRAIL_LINE_WIDTH,
)

/**
 * `line-width` for an UNTAKEN blaze and the casing under it (#1306).
 *
 * The same taper the sketches take, and for the reason the maintainer
 * reported rather than one drawn in advance. The A.T. is 51,068 vertices
 * over 2,190 miles and the corridor camera gives it some 700 px, so about
 * three miles of trail per pixel - the line folds back inside a pixel, and
 * its width is the only thing that decides how it reads: at the
 * through-route tier the eleventh preview build drew the untaken A.T. as a
 * black rope from Georgia to Maine ("the AT is now black", 2026-09-09).
 * The handoff never drew it that way - frame 2a of `Opening Map
 * Options.html`, the chosen option, gives EVERY untaken line
 * `lineWidth: 1.5` at the `us` scope and reserves the heavier weight
 * (`baseW * 2.1`) for the trail that has been taken. (The frame's dots are
 * gone since 2026-09-10 - this file's header, rule 2 - and the weight
 * argument never depended on them.)
 *
 * So below the seam every untaken line is drawn as the overview sketches
 * are: NETWORK_OVERVIEW_FAR_WIDTH at the continental camera, its own tier
 * at the seam. Two consequences worth naming:
 *
 * - The A.T.'s sketch and its real line carry the SAME width at every
 *   zoom (sketchWidthExpression takes this expression), so the swap when
 *   trails.geojson finally parses stays the invisible one #1291 asked for.
 * - The nearby network's tiles start AT the seam, so this taper is a no-op
 *   over them - it exists for the sources that draw below it.
 */
export function untakenTrailWidthExpression(): unknown {
  return overviewTaper(NETWORK_OVERVIEW_FAR_WIDTH, TRAIL_WIDTH_EXPRESSION)
}

/**
 * How much of its own tier a line keeps at the continental camera (#1306).
 *
 * Derived, not picked: it is the factor that lands the SIDE-TRAIL tier
 * exactly on NETWORK_OVERVIEW_FAR_WIDTH, so a solid side trail and the
 * network overview's dots are the same weight where they run side by side,
 * and no third number decides the far end. The through-route tier follows
 * from the same factor at 4.5 x 0.6 = 2.7 px, which is the prototype's own
 * hierarchy at that scope: `Opening Map Options.html` draws the taken line
 * at `baseW * 2.1` against 1.5 for everything else.
 *
 * WHY A SOLID LINE NEEDS THIS TOO, which the first cut of #1306 missed.
 * Only the untaken side tapered, so a TAKEN A.T. still drew at 4.5 px from
 * Georgia to Maine - the maintainer's "it looks like a black line",
 * reproduced on the built app at a 1512 px desktop window with
 * `chosen_trail_id` set (2026-09-09). Taking a trail is meant to move a
 * line from the network's weight to its own tier at the seam, not from a
 * fine line to a rope at the continental camera.
 *
 * That preference is gone since #1352 and this paragraph is left as the
 * dated record it is. To reproduce the rope again, put the app on an active
 * hike whose `trailId` is `AT` - what `chosenTrailId` now reads.
 */
export const OVERVIEW_WIDTH_SCALE = NETWORK_OVERVIEW_FAR_WIDTH / DEFAULT_TRAIL_LINE_WIDTH

/** `line-width` for a SOLID blaze: its tier at the seam, that tier scaled
 *  down at the continental camera (#1306). */
export function solidTrailWidthExpression(): unknown {
  return overviewTaper(
    trailWidthExpression(0, OVERVIEW_WIDTH_SCALE),
    TRAIL_WIDTH_EXPRESSION,
  )
}

/** The casing under it, keeping the same hairline overhang at both stops.
 *  Under every blaze, white included: a white blaze keeps its casing on
 *  every sheet, which is the edge that lets it stay white. */
export function solidTrailCasingWidthExpression(): unknown {
  return overviewTaper(
    trailWidthExpression(CASING_OVERHANG * 2, OVERVIEW_WIDTH_SCALE),
    TRAIL_CASING_WIDTH_EXPRESSION,
  )
}

/** The width a shared stretch is drawn at, at one stop: the HEAVIER of the
 *  two trails' tiers (map/sharedGround.ts says why the heavier), each read
 *  off its own property of the half. */
function sharedGroundTierExpression(scale: number): unknown[] {
  return [
    'max',
    trailWidthExpression(0, scale),
    trailWidthExpression(0, scale, SHARED_GROUND_PARTNER_SOURCE_PROPERTY),
  ]
}

/** `line-width` for one half of a shared stretch (header rule 4): half the
 *  stretch's width at both stops, so the halves taper where the lines taper.
 *  Built as its own taper rather than as half OF a line's, because a zoom
 *  interpolation inside arithmetic is a style error. */
export function sharedGroundHalfWidthExpression(): unknown {
  return overviewTaper(
    ['/', sharedGroundTierExpression(OVERVIEW_WIDTH_SCALE), 2],
    ['/', sharedGroundTierExpression(1), 2],
  )
}

/** `line-offset` for that half: a quarter of the stretch's width - half of
 *  the half - times the feature's own side, so the two halves of one chord
 *  sit edge to edge along it. The side is multiplied into each stop, for the
 *  reason the width above is built the way it is. MapLibre offsets positive
 *  to the right of the line's direction; the pipeline made the two signs
 *  opposite on one geometry. */
export function sharedGroundOffsetExpression(side: unknown): unknown {
  return overviewTaper(
    ['*', side, ['/', sharedGroundTierExpression(OVERVIEW_WIDTH_SCALE), 4]],
    ['*', side, ['/', sharedGroundTierExpression(1), 4]],
  )
}

/** The casing under both halves - the mask - at the stretch's cased width:
 *  the same hairline overhang every casing carries, around the heavier tier. */
export function sharedGroundCasingWidthExpression(): unknown {
  return overviewTaper(
    ['+', sharedGroundTierExpression(OVERVIEW_WIDTH_SCALE), CASING_OVERHANG * 2],
    ['+', sharedGroundTierExpression(1), CASING_OVERHANG * 2],
  )
}

/** The casing under an untaken blaze: the same hairline overhang at both
 *  of untakenTrailWidthExpression's stops. It took the appearance until
 *  2026-09-10, for a zero-under-near-white case that went with the dot
 *  rhythm (this file's header, rule 2). */
export function untakenTrailCasingWidthExpression(): unknown {
  return overviewTaper(
    NETWORK_OVERVIEW_FAR_WIDTH + CASING_OVERHANG * 2,
    TRAIL_CASING_WIDTH_EXPRESSION,
  )
}

export interface MapStyleOptions {
  /** `pmtiles://` URL for the downloaded topo archive. */
  topoArchiveUrl: string
  /** Local URL of the exported trail lines. No network path. */
  trailsUrl: string
  /**
   * Which background to draw. Defaults to the live topographic sheet, which
   * is what someone who has not downloaded anything yet should be looking at.
   */
  background?: BackgroundSource
  /**
   * DEM and contour URLs from `registerTerrain()`.
   *
   * Optional so that `buildMapStyle` stays a pure function tests and callers
   * can build without registering a protocol first. Omitting them costs the
   * hillshade and the contour lines and NOTHING else - the live sheet's OSM
   * half is drawn either way. See liveTopo.ts's LiveTopoOptions for why that
   * split is where it is.
   */
  terrain?: TerrainUrls
  /** Decides whether contours and summit heights are in feet or metres. */
  units?: ContourUnits
  /**
   * Which appearance the canvas is drawn in - see mapBackdrop above.
   *
   * All optional and defaulting to the field day sheet, so every caller
   * that has no opinion builds exactly the style it always built. Present at
   * all so that a cold start under a dark appearance is dark in its FIRST
   * frame: attachMapAppearance can repaint a live map, but it necessarily
   * runs after the map exists, and a white flash on a phone at night is the
   * thing these preferences exist to avoid. `themeChoice` is the stored
   * theme preference before resolution - liveTopo.ts's sheetVariant needs it
   * to tell a chosen dark from a sunset one.
   */
  theme?: ResolvedTheme
  themeChoice?: Theme
  mapStyle?: MapStyle
  redLight?: boolean
  /** Whether the hiker has asked for the drought wash (#720). Off by
   *  default: it is context, and an unasked-for tint over the whole map is
   *  the opposite of "find information faster". */
  showDrought?: boolean
  /**
   * Whether the trails data behind `trailsUrl` has the merged-chain shape
   * (#161, lib/trailShape.ts) - which decides the trails source's
   * `tolerance`. False by default and false whenever the caller cannot
   * tell, because the conservative direction (`tolerance: 0`) only ever
   * costs worker time, while the optimistic one over pre-merge data
   * reopens #160's miles-long gaps.
   */
  trailsMerged?: boolean
  /**
   * The taken trail, by lib/trails.ts registry id, or null for nothing taken
   * (#1306). Decides which side of every line split a source lands on, what
   * is ghosted, and whether the A.T.'s own sketch draws at the untaken
   * weight. MapView always passes the preference; the default here is the
   * TAKEN state, because it is what the style suite describes and what a
   * phone is in from the moment a hiker takes the trail - a caller wanting
   * the all-untaken first launch says so.
   */
  chosenTrailId?: string | null
}

export function buildMapStyle({
  topoArchiveUrl,
  trailsUrl,
  background = 'hiking_topo_live',
  terrain,
  units = 'imperial',
  theme = 'light',
  themeChoice = 'auto',
  mapStyle = 'field',
  redLight = false,
  showDrought = false,
  trailsMerged = false,
  chosenTrailId = TRAILS.AT.id,
}: MapStyleOptions): StyleSpecification {
  const chosen = chosenSystemSources(chosenTrailId)
  const appearance: SheetAppearance = { theme, themeChoice, mapStyle, redLight }
  // Asked for, and that is the whole question. Terrain used to be half of it -
  // `background === 'hiking_topo_live' && terrain !== undefined` - on the
  // reasoning that a style must not reference sources resolving to nothing.
  // True of the DEM and the contour tiles, and liveTopo.ts now drops exactly
  // those two sources and the four layers reading them. It was never true of
  // the other seventeen: the OSM vector sheet needs a URL and a schema, not an
  // elevation model.
  //
  // What the old spelling cost is the bug this fixes. An elevation model that
  // would not build took the landcover, the parks, the water, the path and
  // road network, the summits and every place name down with it, leaving the
  // flat paper of BACKDROP_LAYER_ID - and for a hiker who has downloaded
  // nothing, the archive underneath is empty too, so the whole screen is
  // paper. That contradicted what terrain.ts and MapView.tsx each promise in
  // their own words: a failure there costs a layer, never the map.
  const live = background === 'hiking_topo_live'
  const liveOptions = live
    ? { terrain, units, theme, themeChoice, mapStyle, redLight }
    : null

  return {
    version: 8,
    // Set unconditionally. The endpoint is the app's own origin (#188), so
    // this was never about a host dependency - the rule it encodes is that a
    // style declares the endpoints its layers use.
    //
    // IT USED TO BE KEYED ON `live`, and the reason given was exact: "the
    // raster background has no symbol layer to use this one". That was true
    // while every symbol layer - summits, water names, place names - came off
    // the OSM source, which only the live sheet has. #930's trail-name labels
    // are the first symbol layer bound to the TRAILS source, and the trails
    // draw on both sheets, so the offline style now has a symbol layer too.
    //
    // Left keyed on `live`, the offline sheet would have shipped labels with
    // no font to render them in - which MapLibre reports as a per-glyph load
    // failure, exactly the kind of error the old comment warned would be
    // impossible to connect back to its cause. The glyph ranges are bundled
    // under `public/glyphs/` and precached by vite.config.ts's globPatterns,
    // so the offline sheet has them on disk; only the declaration was missing.
    glyphs: BUNDLED_GLYPHS,
    sources: {
      [TOPO_SOURCE_ID]: {
        type: 'raster',
        url: topoArchiveUrl,
        // 256, not the tiles' own 512 pixels - the @2x convention (#191).
        // Declared at 512 every tile was drawn across 512 CSS px, which a
        // DPR-2 phone upscales 2x: the top of the archive's own resolution
        // never reached the screen. At 256 a 512px tile spans 256 CSS px,
        // 1:1 with a retina phone's device pixels, and MapLibre asks for
        // tiles one level deeper than the camera - which is why
        // lib/archiveCoverage.ts's floor arithmetic carries a matching
        // CAMERA_ZOOM_TILE_OFFSET. Old archives already on phones gain the
        // same sharpness: the declaration is the client's, not the file's.
        tileSize: 256,
        // This source alone is the USGS survey. It used to carry the composed
        // "USGS US Topo · © OpenStreetMap contributors" that every other
        // source carried too, which made the corner's job impossible: three
        // sources declaring one string cannot say which of them is drawing.
        attribution: USGS_TOPO_CREDIT,
      },
      [TRAILS_SOURCE_ID]: {
        type: 'geojson',
        data: trailsUrl,
        // What is dropped here is the "USGS US Topo" half of that string: no
        // USGS survey is in this source, and a credit that says otherwise is
        // the thing this change exists to stop.
        //
        // What is NOT added is an ATC credit, and that gap is deliberate
        // rather than an oversight. The trail geometry is ATC's, and ATC's
        // redistribution and attribution terms are one of the two unresolved
        // data-terms questions this project already carries (#98,
        // features/SOURCE_REGISTRY.md) - there is no agreed attribution string
        // to render, and inventing one would be a claim about a permission
        // nobody has confirmed. It is a real hole, it predates this file, and
        // it is not closed by guessing.
        attribution: OSM_CREDIT,
        // Never simplify a trail away. MapLibre tiles GeoJSON through
        // geojson-vt, whose per-zoom simplification does two things under
        // this one knob: it thins vertices within a line (harmless - the
        // error is bounded sub-pixel), and it DROPS WHOLE FEATURES whose
        // projected length falls under that same bar - ~1.4 km at z4,
        // ~700 m at z5, ~350 m at z6 with the 0.375 px default.
        //
        // The pre-merge centerline was not one feature. ATC surveys it as
        // ~3,000 segments averaging ~1.2 km, so at corridor zooms much of
        // the trail was under the bar, consecutive short segments vanished
        // TOGETHER, and the AT rendered with miles-long gaps (#160) - on
        // this map, a false statement about where the trail is. Zero is
        // the only value that makes the drop rule structurally impossible
        // for data of that shape.
        //
        // #161's durable answer is the data's: the export now merges the
        // centerline into maximal chains, far above the drop bar at every
        // zoom, and for THAT shape the default tolerance is safe and buys
        // back the vertex thinning `tolerance: 0` disables (~220 ms of
        // worker time and 30-50x the displayable geometry across the z4-z6
        // tiles, measured pre-merge). Which shape THIS phone actually holds
        // is `trailsMerged` - detected from the stored bytes themselves at
        // download time (lib/trailShape.ts), never assumed from the app's
        // build, because a phone that downloaded before the merge keeps the
        // segmented shape until its next download however new the app is.
        ...(trailsMerged ? {} : { tolerance: 0 }),
      },
      // The corridor-view sketch of that same line (#869), empty until the
      // shell has one and empty again the moment the real centerline lands.
      // Its own source rather than a first `setData` on the one above, because
      // the two have to be able to be on the map at once for exactly as long
      // as it takes to swap them - one source would mean a frame with no trail
      // on it at the moment first run is being told there is one.
      //
      // Attributed like the trails it sketches: same geometry, same
      // provenance, same unresolved ATC question (see above).
      [TRAIL_OVERVIEW_SOURCE_ID]: {
        type: 'geojson',
        data: emptyTrailOverview(),
        attribution: OSM_CREDIT,
      },
      // The other organizations' trails (#950), empty until
      // lib/nearbyTrailData.ts has an artifact to hand over - which today it
      // usually does not, because publish.py holds that artifact back while
      // either steward's terms are unresolved. An empty source rather than an
      // absent one so there is one shape of style whatever the bucket holds,
      // which is the same reason the overview above is declared empty.
      //
      // ATTRIBUTED TO ITS OWN STEWARDS, which is a licence condition and not
      // a courtesy: OPRHP's terms require credit on "any maps... created using
      // OPRHP data" (pipeline/sources.json's `oprhp_licence` quotes them in
      // full). It carried OSM_CREDIT while nothing shipped, which was a
      // placeholder that would have become a breach the moment it did.
      //
      // The corner strip is assembled by map/credits.ts's mapCredits() rather
      // than from these declarations, so this is the second half of the same
      // fact rather than the mechanism - see that module for why one source
      // cannot be credited in one file and go uncredited in another.
      //
      // A VECTOR SOURCE, not a GeoJSON one (#1257): the tiles are asked for
      // through a scheme map/networkTiles.ts answers by byte range off the
      // published archive, and the zoom range is the archive's (lib/config.ts
      // holds both ends against the pipeline's). One shape of style whatever
      // the bucket holds - a bucket with no archive answers every tile empty.
      [NEARBY_TRAILS_SOURCE_ID]: {
        type: 'vector',
        tiles: [NETWORK_TILES_URL],
        minzoom: NEARBY_TRAILS_TILES_MIN_ZOOM,
        maxzoom: NEARBY_TRAILS_TILES_MAX_ZOOM,
        attribution: `${OPRHP_CREDIT} · ${NYNJTC_CREDIT} · ${MOHONK_CREDIT} · ${DEC_CREDIT}`,
      },
      // The same network as a corridor-view sketch (#1135), empty until
      // lib/nearbyTrailData.ts hands one over. The SAME attribution string as
      // its parent above, and that is a licence condition rather than
      // tidiness: OPRHP's credit is owed whenever their lines are drawn, and
      // below the seam these are the only drawing of them.
      [NETWORK_OVERVIEW_SOURCE_ID]: {
        type: 'geojson',
        data: emptyTrailOverview(),
        attribution: `${OPRHP_CREDIT} · ${NYNJTC_CREDIT} · ${MOHONK_CREDIT} · ${DEC_CREDIT}`,
      },
      // The through-route badges (#1283): points map/trailsInView.ts computes
      // from what the trail layers are actually drawing, one per named
      // through-route on screen, rewritten as the camera settles. Empty in
      // the style for the reason every runtime-filled source here is. No
      // `attribution`: the geometry is a vertex of a line already credited
      // through its own source, and the name is that line's.
      [TRAIL_BADGE_SOURCE_ID]: buildTrailBadgeSource(),
      // Declared empty and filled in later - see buildPoiSource. Attributed
      // like the trails, and for the same reasons: the POIs are ATC and
      // OpenStreetMap-derived, only one of those two has a settled credit to
      // render, and a source with no attribution at all is one release away
      // from shipping uncredited.
      [POI_SOURCE_ID]: { ...buildPoiSource(), attribution: OSM_CREDIT },
      // Also empty until the shell fills them, and for a sharper reason than
      // the POIs have: these two arrive over the network from OurHike's own
      // backend (lib/api.ts), so on the trail they very often never arrive at
      // all. An empty source is the honest opening state.
      //
      // No `attribution`, and that is not an oversight. What these draw is
      // hikers' own reports, moderated by the clubs that maintain the trail -
      // there is no third party to credit, and a corner reading "© OpenStreetMap"
      // over a closure somebody walked up to and photographed would be a false
      // statement about where it came from.
      [CLOSURE_SOURCE_ID]: buildClosureSource(),
      [CORRIDOR_SOURCE_ID]: buildCorridorSource(),
      // The route being built (#755). Empty until the hiker drops points, and
      // no `attribution`: what it draws is the hiker's own intent, and there
      // is no third party to credit for a line they chose themselves.
      [ROUTE_SOURCE_ID]: buildRouteSource(),
      // No attribution, for ROUTE_SOURCE_ID's reason: runtime geometry the
      // hiker made, not somebody's data.
      [DAY_HIKE_SOURCE_ID]: buildDayHikeSource(),
      // The mile marks, a source of their own rather than more features on
      // the route's: they are points on a line the route already draws, and
      // one source holding both would make every tick rebuild whenever the
      // line moved - which is on every tap.
      [DAY_HIKE_TICK_SOURCE_ID]: buildDayHikeTickSource(),
      // The drought bands (#720). Empty until the shell fills them, like the
      // two above, and carrying no `attribution` for a third reason again:
      // NDMC's permission asks for a specific four-partner credit sentence,
      // which is far too long for the map corner and is rendered on the
      // credits screen instead (map/credits.ts). A truncated version of a
      // credit somebody asked for in particular wording is worse than putting
      // it where it fits.
      [DROUGHT_SOURCE_ID]: buildDroughtSource(),
      // Where the downloaded map ends (#557), empty until the shell knows
      // which cells are on the phone and empty on every phone that holds the
      // whole sheet or nothing. No attribution: the line is a fact about
      // this phone, not anybody's data.
      [COVERAGE_SEAM_SOURCE_ID]: buildCoverageSeamSource(),
      // The ATC's notices, and this one DOES have a third party to credit -
      // which is why it is a separate source rather than more features in the
      // one above. No `attribution` here either, though: a corner credit is
      // the wrong surface for it. What a hiker needs is not "© ATC" under the
      // whole map but the organisation's name on the specific claim, with the
      // date they last edited it and a link to their page, which is what
      // chrome/OrgNoticeSheet.tsx renders (#461).
      [ATC_UPDATE_SOURCE_ID]: buildAtcUpdateSource(),
      [WARNING_SOURCE_ID]: buildWarningSource(),
      [WORKDAY_SOURCE_ID]: buildWorkdaySource(),
      [DISPUTE_SOURCE_ID]: buildDisputeSource(),
      // Each of these carries its own credit (OpenFreeMap's terms, the AWS
      // Terrain Tiles requirement), like the three above - a source names the
      // data IT is, and map/credits.ts assembles the corner out of whichever
      // of them are actually on screen.
      ...(liveOptions === null ? {} : liveTopoSources(liveOptions)),
    },
    layers: [
      {
        // Under everything, because the topo tiles are transparent outside the
        // corridor (lib/raster_tiles.py's encode_webp) and a 30-mile ribbon
        // leaves most of a zoomed-out view uncovered. Without this that ground
        // is empty canvas; with it, it reads as unmapped paper - which is what
        // it honestly is. Paper rather than a neutral grey so the uncovered
        // area belongs to the same map as the parts that are covered.
        //
        // First in the list, and the only layer here bound to no source: it
        // covers the whole canvas at every zoom and every camera position, so
        // the "never black" guarantee survives a missing archive and an
        // off-corridor pan as well as the transparent ground it was added for.
        id: BACKDROP_LAYER_ID,
        type: 'background',
        paint: { 'background-color': mapBackdrop(appearance) },
      },
      {
        id: TOPO_LAYER_ID,
        type: 'raster',
        source: TOPO_SOURCE_ID,
        // The archive is pre-rendered paper and cannot be restyled, so under
        // a dark sheet it is dimmed rather than redrawn - see
        // ARCHIVE_RASTER_PAINT above, including why this is a layer property
        // and not a filter over the canvas.
        paint: { ...archiveRasterPaint(appearance) },
      },
      // The live sheet goes OVER the downloaded raster, and that ordering is
      // the whole offline story rather than a cosmetic preference.
      //
      // Stacked this way, the two never have to be chosen between at runtime
      // and there is no online/offline branch anywhere: with signal, the
      // vector sheet covers the corridor with something sharp and styled and
      // keeps going past its edge, where there used to be nothing but blank
      // paper. Without signal, these layers simply draw nothing, the archive
      // shows through underneath exactly as it always has, and the flat paper
      // colour still marks where the download does not reach. Every state is
      // at least as good as it was before, and none of them needs to be detected.
      //
      // Still true, and worth keeping true: nothing observed at runtime reaches
      // this function. map/liveSourceHealth.ts does watch whether these sources
      // ever load, but only so the status strip can SAY so - what is composed
      // here stays a pure function of the preference, Data Saver, and whether a
      // DEM could be built.
      ...(liveOptions === null ? [] : liveTopoLayers(liveOptions)),
      // The drought wash, and its place in the stack is the argument (#720).
      //
      // OVER the background sheets, so it tints the ground a hiker reads the
      // terrain off; UNDER the trail, every pin and every closure, so nothing
      // that carries a decision is ever seen through it. That ordering is the
      // difference between a background layer and an overlay, and this is
      // emphatically the first: it colours where you are, it never annotates
      // what is there.
      //
      // Off unless the hiker asked (`layout.visibility`), which is why it can
      // sit in the style unconditionally - see lib/droughtStyle.ts for why the
      // switch is a visibility flip rather than an add and remove.
      buildDroughtLayer(DROUGHT_SOURCE_ID, sheetIsDark(appearance), showDrought),
      // The edge of what is downloaded (#557), and its place in the stack is
      // features/OFFLINE_COVERAGE.md §8 in paint: OVER the ground it is an
      // edge of, UNDER every trail line, closure and pin. A seam takes away
      // the sheet and never the hazard, so nothing that carries a decision
      // may sit under it - and it is dashed and named rather than muting the
      // ground beyond it, which would read as a rendering fault.
      ...buildCoverageSeamLayers(trailCasingColor(appearance), mapBackdrop(appearance)),
      // The whole network's corridor-view sketch (#1135), UNDER everything
      // the A.T. draws - the ordering argument the full network's layers
      // make below, one zoom band earlier: a nearby trail must never cover
      // the trail the map is about, and below the seam that includes the
      // A.T.'s own sketch.
      //
      // `maxzoom` is the A.T. sketch's safety rule, unchanged: no point on
      // this line is more than 100 m from the exported line
      // (pipeline/export_nearby_trails.py's write_overview), which is a
      // fraction of a pixel down here and a line in the wrong place at
      // navigation zooms. At the seam the full network's own layers take
      // over - same properties, same expressions, so the handoff is not a
      // restyle.
      //
      // No casing pair, exactly like the A.T. sketch and unlike the full
      // lines: one layer per side of the split, the shared colour and ghost
      // expressions - so every organization's trails read as context around
      // the A.T. from the first frame.
      //
      // WIDTH IS THE ONE EXPRESSION THIS LAYER DOES NOT SHARE, and the
      // deviation was drawn before it was coded: rendered at the full
      // side-trail width, the opening camera's dense park clusters - DEC's
      // and OPRHP's short segments, sub-pixel long at z5 under round caps -
      // read as a cloud of coloured dots over New York, which is the exact
      // texture #1135 just took off this view (measured on a local
      // serve_processed.py build, 2026-08-27). So the width tapers across
      // the representational band and lands on the side-trail width AT the
      // seam, where the full network's layers take over - the handoff stays
      // pixel-seamless, and the deviation cannot leak into a zoom a hiker
      // navigates by.
      //
      // SPLIT LIKE EVERY OTHER TRAIL SOURCE (#1283): untaken under taken.
      // The taken half is empty today - every line in this artifact is
      // another organization's by construction - and it is built anyway, by
      // the same builder, so admitting a source to the chosen system cannot
      // leave the overview drawing it as untaken while the full lines draw
      // it as taken.
      buildNetworkOverviewLayer(
        NETWORK_OVERVIEW_UNTAKEN_LAYER_ID,
        appearance,
        'nearby',
        chosen,
      ),
      buildNetworkOverviewLayer(NETWORK_OVERVIEW_LAYER_ID, appearance, 'chosen', chosen),
      // Closed ground stays closed-looking below the seam: the sketch keeps
      // `trail_status` per feature (48.4 line-miles of it, measured
      // 2026-08-27), so the same barrier tape draws over it - over its own
      // ghosted line, under everything the A.T. draws, and capped at the
      // seam where the full network's own tape takes over.
      ...buildClosureLayers(NETWORK_OVERVIEW_SOURCE_ID, {
        bandId: NETWORK_OVERVIEW_CLOSURE_LAYER_ID,
        filter: LONG_TERM_CLOSED_FILTER,
      }).map((layer) => ({ ...layer, maxzoom: POI_PIN_MIN_ZOOM })),
      {
        // The corridor-view sketch (#869), UNDER the real trail's casing, so
        // on the one frame where both exist the real line is what a hiker
        // sees.
        //
        // `maxzoom` is the safety rule, not a performance one. No point on
        // this line is more than 100 m from the surveyed centerline
        // (pipeline/export_trails.py's write_overview), which is 0.43 px at
        // this zoom and 14 px at z14 - a trail drawn somewhere it does not
        // go. The seam is where the map stops being an overview and starts
        // being something a hiker reads a position off, which is the same
        // place waypoints start drawing as pins, so it is the same constant.
        //
        // Above it the sketch is simply absent: a first run that zooms in
        // during the seconds before the real line arrives sees no trail,
        // which is true, rather than a line that is nearly right.
        id: TRAIL_OVERVIEW_LAYER_ID,
        type: 'line',
        source: TRAIL_OVERVIEW_SOURCE_ID,
        maxzoom: POI_PIN_MIN_ZOOM,
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          // The same expressions the real line is painted with, off the same
          // two published properties - so the sketch is not a second
          // appearance to keep in step, and the swap is not a colour change.
          // Uncased, so a near-white line is inked dark on a day sheet
          // (DARK_INKED_BLAZE_LAYER_IDS): the one place the sketch and the
          // real line differ, and the frame #1291 is about.
          'line-color': blazeLineColor(appearance, false) as unknown as string,
          // The one departure, and only while the A.T. is not taken: the
          // network's taper rather than the line's own tier, because 4.5 px
          // on this line at z4 is a black rope (sketchWidthExpression has
          // the frame and the handoff's own number).
          'line-width': sketchWidthExpression(chosen) as unknown as number,
          // Ghosted here too, for the reason the two lines above are shared:
          // the sketch is the same appearance arriving early, so a nearby
          // trail that fades when the real line loads would read as the map
          // changing its mind about which trail it is about.
          'line-opacity': nearbyTrailOpacityExpression(chosen) as unknown as number,
        },
      },
      // The other organizations' trails (#950), UNDER the chosen trail's own
      // pair below. Order is the half of this that opacity cannot do: ghosting
      // says which system a line belongs to, but where a nearby trail runs
      // coincident with the chosen one - and in Harriman half the A.T.'s
      // length is within 150 m of another marked trail (#771) - the one drawn
      // last still owns the pixels. Drawn first, a nearby trail can never
      // cover the trail the map is about, whatever its opacity.
      // UNDER both trail-line stacks, and that placement is the point
      // (#978, frame `1j`): the day-hike highlight is a translucent casing
      // beneath the lines, never a recolour of a blaze - a green route drawn
      // over a yellow trail lies about which paint a hiker is following.
      // map/dayHikeLayers.ts carries the full argument; style.test.ts pins
      // the order by index.
      ...buildDayHikeCasingLayers(),
      ...onSourceLayer(
        buildTrailLineSplit(
          NEARBY_TRAILS_SOURCE_ID,
          {
            casing: NEARBY_TRAIL_CASING_LAYER_ID,
            blaze: NEARBY_BLAZE_LAYER_ID,
            casingUntaken: NEARBY_TRAIL_CASING_UNTAKEN_LAYER_ID,
            blazeUntaken: NEARBY_BLAZE_UNTAKEN_LAYER_ID,
          },
          appearance,
          // ABOVE THE SEAM ONLY (features/NEARBY_TRAILS.md §8). "Forty short
          // trails are not a below-seam subject - at z7 Harriman is one green
          // shape", and 3,663 lines drawn across the corridor view would be a
          // smear over the thing that view is actually about, which is the
          // thirty club sections tiling the A.T.
          //
          // HALF OF §8, and the missing half is named rather than hidden: it
          // also says the marquee routes - the A.T., the Long Path - should
          // still be drawn through the parks below the seam, with the PARK as
          // the subject there. That needs the park polygons exported and a way
          // to tell a marquee route from a short park trail, neither of which
          // exists. Until it does, the Long Path is absent below z9 rather than
          // drawn at the wrong prominence. Cutting the smear is the half worth
          // having first; the other half is #557's ground.
          POI_PIN_MIN_ZOOM,
          chosen,
        ),
        NETWORK_TILES_LAYER,
      ),
      // A nearby trail marked closed long-term gets the same barrier tape the
      // A.T.'s closures get (features/NEARBY_TRAILS.md §3: a hiker learns ONE
      // mark for "do not walk this"). Over its own blaze for the reason the
      // chosen trail's band is over its own - a barrier under the line is a
      // picture of an open trail - and still under everything about the
      // chosen trail, per the ordering argument above.
      ...onSourceLayer(
        buildClosureLayers(NEARBY_TRAILS_SOURCE_ID, {
          bandId: NEARBY_LONG_TERM_CLOSURE_LAYER_ID,
          filter: LONG_TERM_CLOSED_FILTER,
        }),
        NETWORK_TILES_LAYER,
      ),
      ...buildTrailLineSplit(
        TRAILS_SOURCE_ID,
        {
          casing: TRAIL_CASING_LAYER_ID,
          blaze: BLAZE_LAYER_ID,
          casingUntaken: TRAIL_CASING_UNTAKEN_LAYER_ID,
          blazeUntaken: BLAZE_UNTAKEN_LAYER_ID,
        },
        appearance,
        undefined,
        chosen,
      ),
      // Two trails on one treadway, as two halves of one line (header rule
      // 4, #1384): over BOTH stacks, because the opaque casing is what hides
      // the two plain lines still drawn on the stretch beneath it, and under
      // the names, badges and closure tape, which say things about the
      // trail rather than draw it. Nothing until a release carries the
      // pairs - map/sharedGround.ts, "guarded on absence".
      ...onSourceLayer(
        buildSharedGroundLayers(appearance, POI_PIN_MIN_ZOOM, chosen),
        NETWORK_TILES_LAYER,
      ),
      // Trail names (#930), directly over the lines they name and UNDER every
      // pin on this map. Both halves of that are deliberate.
      //
      // PLACEMENT, which is the half that matters and is the opposite way
      // round from what it looks like: MapLibre declutters symbols across the
      // whole style, and `PauseablePlacement` starts at `order.length - 1` and
      // decrements — so placement runs TOP-DOWN and the LAST symbol layer has
      // priority. That is liveTopo.test.ts's finding, checked rather than
      // assumed, and it is why our own pins sit at the end of this list.
      //
      // A trail's name is the lowest-priority symbol on the map: a waypoint, a
      // workday, a serious warning and an ATC notice each say something a
      // hiker acts on, and a name only says which line is which. So it goes
      // EARLY — before every one of them — and loses the collision it should
      // lose. Put last, it would have suppressed a water source to print
      // "Kakiat Tr.", which is the exact failure liveTopo.test.ts's
      // pins-last case exists to catch, and did catch when this layer was
      // first written into the wrong end of the stack.
      //
      // DRAW ORDER follows from the same ranking: under the pins, so a pin
      // covers a name rather than a name covering a pin.
      // The nearby network's names, BEFORE the chosen trail's below.
      // Placement runs top-down (see above), so the later layer wins a
      // contested label - and where a nearby trail's name and the chosen
      // trail's name cannot both be placed, the one the map is about is the
      // one that should survive. Same layer, same expressions, same opacity
      // rule; only the id and the source differ.
      ...onSourceLayer(
        [
          buildTrailLabelLayer(
            NEARBY_TRAILS_SOURCE_ID,
            trailCasingColor(appearance),
            mapBackdrop(appearance),
            TRAIL_LABEL_MIN_ZOOM,
            NEARBY_TRAIL_LABEL_LAYER_ID,
            chosen,
          ),
        ],
        NETWORK_TILES_LAYER,
      ),
      buildTrailLabelLayer(
        TRAILS_SOURCE_ID,
        trailCasingColor(appearance),
        mapBackdrop(appearance),
        TRAIL_LABEL_MIN_ZOOM,
        TRAIL_LABEL_LAYER_ID,
        chosen,
      ),
      // The through-route badge (#1283), AFTER both label layers and BEFORE
      // every pin - which, placement running top-down, is exactly the claim
      // on space a badge should have: it beats an along-line name for a
      // contested spot (a name says which line; a badge says which line AND
      // is the thumb target the design chose it for) and loses to a
      // waypoint, a workday, a warning and an ATC notice, each of which says
      // something a hiker acts on. Drawn over the names for the same reason.
      // map/trailBadges.ts has why it is a point source and not a
      // line-center symbol on the trail layer.
      buildTrailBadgeLayer(appearance, chosen),
      // The corridor view's attribution, over the blaze and under everything
      // else (#598). Over, because the grey on an unattributed run has to
      // COVER the white blaze rather than sit beside it; under the route and
      // the closures, because a barrier or a hiker's own line crossing this
      // stretch matters more than who maintains it. Every layer here stops at
      // the seam - see corridorLayers.ts's CORRIDOR_MAX_ZOOM.
      ...buildCorridorLayers({
        casingColor: trailCasingColor(appearance),
        blazeWidth: BLAZE_LINE_WIDTH,
        casingWidth: CASING_LINE_WIDTH,
      }),
      // The route being built, over the blaze it retraces - a route drawn
      // UNDER the trail line would be invisible along its whole length -
      // and beneath the closure bands, deliberately: a closure crossing the
      // stretch a hiker is planning is exactly the thing they are planning
      // around, and a picture where their own green line covered the barrier
      // would be a picture of an open trail (#755).
      ...buildRouteLayers(),
      // The day hike's tapped points ride above the lines like every marker;
      // only its casing lives below.
      ...buildDayHikePointLayers(),
      // Over the blaze, and that ordering is the closure's entire job. Tape
      // UNDER the trail line would be a closure the trail is drawn straight
      // through - which is a picture of an open trail. See lib/closureStyle.ts
      // for why the tape differs from a blaze in width and texture rather than
      // only in colour, and why the trail still shows THROUGH it: the gaps are
      // transparent, so being drawn over is not the same as being hidden.
      // The long-term closures a steward marks on the trail line itself
      // (features/NEARBY_TRAILS.md §3) - 125 of them statewide in OPRHP's
      // layer, a different FEED from the live temporary closures above but
      // deliberately the SAME treatment, because a hiker learns one mark for
      // "do not walk this". Which kind it is lives in the sheet, never in the
      // line. Drawn from the trails source, since the geometry IS the trail.
      //
      // Immediately after the temporary closures so the two are one band in
      // the stack: where a temporary closure sits on a trail already marked
      // closed long-term, whichever draws last wins pixels that look
      // identical either way. Two tapes at the same cadence stack without a
      // seam, because they are the same image.
      ...buildClosureLayers(CLOSURE_SOURCE_ID),
      ...buildClosureLayers(TRAILS_SOURCE_ID, {
        bandId: LONG_TERM_CLOSURE_LAYER_ID,
        filter: LONG_TERM_CLOSED_FILTER,
      }),
      // Then the waypoints, in their two ranks (#597). The dots go down first
      // so every pin that wins its collision sits on top of its own dot and
      // hides it, and every waypoint that loses one still leaves a dot behind.
      // Reversing these two would put a 2.5 px dot over the middle of a 38 px
      // pin, which reads as a defect rather than as a rank.
      //
      // Both are above the closure bands for the same reason as before: a
      // waypoint is never buried under the trail line it sits on. See
      // poiLayers.ts for why the pins are one layer rather than one per
      // category, and why a non-colliding circle layer beside them does not
      // undo that argument.
      // Waypoint NAMES and the walk's mile marks, BEFORE the pins (#1194).
      //
      // BEFORE IS THE LOAD-BEARING WORD. MapLibre ranks symbol layers for
      // placement by their order in the style, later winning, which is why
      // liveTopo.test.ts asserts that our own pins are the LAST symbol layers
      // of all: "so they win collisions against our labels". These two are
      // labels. Putting them after the pins - which is where they first went
      // - would have let a shelter's NAME suppress a shelter's PIN, the exact
      // inversion that test exists to catch, and it caught it.
      //
      // Within the pair, the ticks come second and so outrank the names: on
      // the builder's screen the hiker's own route is tier 2 of
      // map/labelLadder.ts and a waypoint they did not choose is tier 4.
      buildPoiLabelLayer(),
      ...buildDayHikeTickLayers(),
      buildPoiDotLayer(),
      // The staleness rings between the two ranks (#759's nudge surface):
      // over the dots, so a ring is never sliced by its own waypoint's dot,
      // and under the pins, so the pin's artwork stays whole and the ring
      // reads as a rim around it rather than a wash over it.
      buildPoiStalenessLayer(),
      buildPoiLayer(),
      // The dispute mark (#876) immediately over the pins it annotates, and
      // under everything else: it is a footnote on a waypoint, so it has to
      // sit on the waypoint - but a hazard or a closure is a bigger claim
      // than "somebody says this is not here" and wins the pixels.
      buildDisputeLayer(),
      // Volunteer workdays (#760) OVER the waypoints and UNDER the warning
      // pins - later in this list means drawn on top, so the order here is
      // the claim. Over the waypoints because a pin nobody can see is the
      // state this layer exists to end; under the warnings because when a
      // hazard and an invitation land on the same pixels, the hazard is the
      // one a hiker needs. Unlike the warning it submits to the collision
      // engine rather than shoving a shelter aside (workdayLayers.ts).
      buildWorkdayLayer(),
      // And the serious-warning pins over every waypoint and over those. The
      // collision engine already keeps them from being dropped
      // (warningLayers.ts); this keeps them from being covered, which is the
      // same guarantee by the other mechanism.
      buildWarningLayer(),
      // The ATC's own notices last of all, so nothing on this map can cover
      // one.
      //
      // THEY USED TO SIT HERE DIRECTLY AFTER THE CLOSURE BANDS, under both pin
      // layers, and the point notices are what made that untenable. A band is
      // hundreds of pixels of barrier tape and a pin cannot hide it; a dot at a
      // single mile is exactly the size of the thing drawn on top of it, and
      // most of what ATC publishes is a dot - five of the six reviewed rows on
      // 2026-08-12. A closed shelter reported by the organisation that
      // maintains the shelter, drawn underneath OurHike's own pin for that
      // shelter, is the failure in one sentence.
      //
      // Which of the two barrier sources sits on top where they overlap is
      // still not a statement about which is more true -
      // features/SOURCE_REGISTRY.md's rule for two organisations describing
      // the same ground is show one and disclose the other, and disclosing is
      // the sheet's job. The ATC is second only because it is the upstream
      // authority on the A.T., and something had to be.
      //
      // OurHike's own closure bands are deliberately NOT moved up with them.
      // Not because they matter less - lib/atcUpdateStyle.ts refuses that
      // distinction at length - but because a band is not a dot, so it does
      // not have the problem this move fixes, and re-ordering a layer nobody
      // reported a fault with is how a fix turns into two.
      ...buildAtcUpdateLayers(ATC_UPDATE_SOURCE_ID),
    ],
  }
}
