// Builds the MapLibre style for the trail map.
//
// Two rules from WIREFRAMES.md's "Trail line rendering — blazes" are
// load-bearing rather than cosmetic:
//
//  1. ONE `match` expression drives line-color across every trail source, so a
//     source imported later inherits the rule instead of needing its own layer.
//     That expression lives in lib/blaze.ts and is imported, never re-spelled.
//
//  2. Every trail line is SOLID and one colour end to end. It used to be
//     dashed, on a per-blaze rhythm, and the rhythm was the map's second
//     hue-independent channel. What that actually produced on screen was a
//     line alternating between its blaze colour and the dark casing showing
//     through each gap - and on the AT centerline, whose blaze is very nearly
//     white, the gaps read as the line. A hiker looking for the trail they are
//     standing on found a dotted grey-and-white thread through the contours.
//     A solid line over a casing is the older, plainer cartographic answer and
//     it is legible at a glance, which is the property that matters most.
//
//     WIDTH carries the hue-independent channel instead, and carries more than
//     the rhythm did: a system's through-route is drawn markedly wider than the
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
//     Closures are unaffected - lib/closureStyle.ts keeps its barred band, and
//     with every blaze now solid that band is a stronger distinction than it
//     was, not a weaker one.
//
//  3. A side trail is never drawn over the through-route it hangs off. One
//     layer means one painter's order, and where two features share geometry
//     that order decides which colour a hiker sees - so it is decided here, by
//     `line-sort-key`, rather than by whichever feature the export wrote last.
//     See TRAIL_SORT_KEY_EXPRESSION.
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

import type { StyleSpecification } from '@maplibre/maplibre-gl-style-spec'
import { BLAZE_MATCH_EXPRESSION } from '../lib/blaze'
import { buildAtcUpdateLayers } from '../lib/atcUpdateStyle'
import { buildClosureLayers } from '../lib/closureStyle'
import { buildDroughtLayer } from '../lib/droughtStyle'
import { buildAtcUpdateSource, ATC_UPDATE_SOURCE_ID } from './atcUpdateLayers'
import { buildClosureSource, CLOSURE_SOURCE_ID } from './closureLayers'
import { buildDroughtSource, DROUGHT_SOURCE_ID } from './droughtLayers'
import {
  buildPoiDotLayer,
  buildPoiLayer,
  buildPoiSource,
  POI_SOURCE_ID,
} from './poiLayers'
import { buildWarningLayer, buildWarningSource, WARNING_SOURCE_ID } from './warningLayers'
import type { BackgroundSource, MapStyle, Theme } from '../lib/userPreferences'
import {
  BUNDLED_GLYPHS,
  attachSheetAppearance,
  liveTopoLayers,
  liveTopoSources,
  sheetVariant,
  type SheetAppearance,
} from './liveTopo'
import { OSM_CREDIT, USGS_TOPO_CREDIT } from './credits'
import { whenStyleReady } from './styleReady'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import type { ResolvedTheme } from '../lib/theme'
import type { ContourUnits, TerrainUrls } from './terrain'

export const TOPO_SOURCE_ID = 'usgs-topo'
export const TRAILS_SOURCE_ID = 'trails'

export const BACKDROP_LAYER_ID = 'backdrop'
export const TOPO_LAYER_ID = 'topo'
export const TRAIL_CASING_LAYER_ID = 'trail-casing'
export const BLAZE_LAYER_ID = 'trail-blaze'

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

/** `line-color` for the blaze layer, per appearance. */
export function blazeLineColor(appearance: SheetAppearance): unknown {
  return redLightActive(appearance) ? RED_LIGHT_BLAZE_COLOR : BLAZE_MATCH_EXPRESSION
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

      // The trail's two layers, same per-layer guards. Writing the blaze
      // colour unconditionally is what makes leaving red light an actual
      // restore: the match expression goes back exactly as buildMapStyle
      // spelled it.
      if (map.getLayer(TRAIL_CASING_LAYER_ID) !== undefined) {
        map.setPaintProperty(
          TRAIL_CASING_LAYER_ID,
          'line-color',
          trailCasingColor(appearance) as never,
        )
      }
      if (map.getLayer(BLAZE_LAYER_ID) !== undefined) {
        map.setPaintProperty(
          BLAZE_LAYER_ID,
          'line-color',
          blazeLineColor(appearance) as never,
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

/** The pipeline's own key for ATC's trail-centerline feed (pipeline/sources.json). */
export const CENTERLINE_SOURCE = 'centerline'

/**
 * Trail sources drawn at the primary width: the through-route of a trail
 * system, as against the side trails and spurs hanging off it.
 *
 * This is a ROLE, and deliberately a list rather than a single source. Its one
 * member today is ATC's `centerline`, whose key reads like a proper noun
 * because that feed is the AT - but nothing here is promised only one
 * through-route. The NYNJTC alone maintains several trail systems, so a Long
 * Path or Highlands Trail import joins this tier beside the AT rather than
 * displacing it, and a `centerline` feed that itself grows past the AT needs
 * no change here at all.
 *
 * What that costs is named where the claim is made (WIREFRAMES.md §3): with
 * one through-route on the map, the widest line IS the AT. With two, width
 * answers "through-route or spur" and stops answering "which trail is this" -
 * still a hue-independent channel, but a coarser one.
 */
export const PRIMARY_TRAIL_SOURCES: readonly string[] = [CENTERLINE_SOURCE]

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
function trailWidthExpression(extra: number): unknown[] {
  return [
    'match',
    ['get', 'source'],
    ...Object.entries(TRAIL_LINE_WIDTHS).flatMap(([source, width]) => [
      source,
      width + extra,
    ]),
    DEFAULT_TRAIL_LINE_WIDTH + extra,
  ]
}

export const TRAIL_WIDTH_EXPRESSION = trailWidthExpression(0)
export const TRAIL_CASING_WIDTH_EXPRESSION = trailWidthExpression(CASING_OVERHANG * 2)

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
}: MapStyleOptions): StyleSpecification {
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
    // Only set when something needs glyphs. The endpoint is the app's own
    // origin now (#188), so this stopped being about a needless host
    // dependency - what survives is the plainer rule that a style declares
    // the endpoints its layers use, and the raster background has no symbol
    // layer to use this one.
    //
    // Keyed on `live` alone, deliberately, now that terrain is no longer part
    // of it: the surviving symbol layers - summits, water names, place names -
    // are all OSM-sourced and outlive a missing DEM. Tying this to terrain
    // instead would leave a style whose labels have no font to render in,
    // which MapLibre reports as a per-glyph load failure rather than anything
    // a reader would connect back to the elevation model.
    ...(live ? { glyphs: BUNDLED_GLYPHS } : {}),
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
        // The centerline is not one feature. ATC surveys it as ~3,000
        // segments averaging ~1.2 km, so at corridor zooms much of the
        // trail is under the bar, consecutive short segments vanish
        // TOGETHER, and the AT rendered with miles-long gaps (#160) - on
        // this map, a false statement about where the trail is. Zero is
        // the only value that makes the drop rule structurally impossible,
        // for this data and for anything imported later.
        //
        // The cost lands only below ~z8, where the gaps were: low-zoom
        // tiles keep every vertex the pipeline's own 1 m simplification
        // left in (measured at this density: ~220 ms of worker time across
        // the z4-z6 tiles, once per session). #161 is the durable answer -
        // merge the centerline chains at export, then let this return to
        // the default - and owns the revert.
        tolerance: 0,
      },
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
      // The drought bands (#720). Empty until the shell fills them, like the
      // two above, and carrying no `attribution` for a third reason again:
      // NDMC's permission asks for a specific four-partner credit sentence,
      // which is far too long for the map corner and is rendered on the
      // credits screen instead (map/credits.ts). A truncated version of a
      // credit somebody asked for in particular wording is worse than putting
      // it where it fits.
      [DROUGHT_SOURCE_ID]: buildDroughtSource(),
      // The ATC's notices, and this one DOES have a third party to credit -
      // which is why it is a separate source rather than more features in the
      // one above. No `attribution` here either, though: a corner credit is
      // the wrong surface for it. What a hiker needs is not "© ATC" under the
      // whole map but the organisation's name on the specific claim, with the
      // date they last edited it and a link to their page, which is what
      // chrome/AtcUpdateSheet.tsx renders (#461).
      [ATC_UPDATE_SOURCE_ID]: buildAtcUpdateSource(),
      [WARNING_SOURCE_ID]: buildWarningSource(),
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
      {
        // Hairline dark casing, drawn under every blaze so the trail stays
        // readable over busy topo contours. It is doing more work than it used
        // to: with the line solid, the casing is the ONLY thing giving the
        // near-white centerline an edge against near-white paper, so it is
        // carried at a firmer opacity than when a gap in the line let it
        // through every few pixels.
        id: TRAIL_CASING_LAYER_ID,
        type: 'line',
        source: TRAILS_SOURCE_ID,
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
          'line-width': TRAIL_CASING_WIDTH_EXPRESSION as unknown as number,
          'line-opacity': 0.7,
        },
      },
      {
        id: BLAZE_LAYER_ID,
        type: 'line',
        source: TRAILS_SOURCE_ID,
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
          // same reason `appearance` seeds the backdrop above.
          'line-color': blazeLineColor(appearance) as unknown as string,
          'line-width': TRAIL_WIDTH_EXPRESSION as unknown as number,
        },
      },
      // Over the blaze, and that ordering is the closure's entire job. A
      // barred red band UNDER the trail line would be a closure the trail is
      // drawn straight through - which is a picture of an open trail. See
      // lib/closureStyle.ts for why the band differs from a blaze in width,
      // rhythm and casing weight rather than only in colour.
      ...buildClosureLayers(CLOSURE_SOURCE_ID),
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
      buildPoiDotLayer(),
      buildPoiLayer(),
      // And the serious-warning pins over every waypoint. The collision engine
      // already keeps them from being dropped (warningLayers.ts); this keeps
      // them from being covered, which is the same guarantee by the other
      // mechanism.
      buildWarningLayer(),
      // The ATC's own notices last of all, so nothing on this map can cover
      // one.
      //
      // THEY USED TO SIT HERE DIRECTLY AFTER THE CLOSURE BANDS, under both pin
      // layers, and the point notices are what made that untenable. A band is
      // hundreds of pixels of barred red and a pin cannot hide it; a dot at a
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
