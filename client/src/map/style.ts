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

import type {
  LayerSpecification,
  StyleSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import { BLAZE_MATCH_EXPRESSION } from '../lib/blaze'
import { buildAtcUpdateLayers } from '../lib/atcUpdateStyle'
import {
  buildClosureLayers,
  LONG_TERM_CLOSED_FILTER,
  LONG_TERM_CLOSURE_CASING_LAYER_ID,
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
import { buildRouteLayers, buildRouteSource, ROUTE_SOURCE_ID } from './routeLayers'
import { buildDroughtSource, DROUGHT_SOURCE_ID } from './droughtLayers'
import {
  buildPoiDotLayer,
  buildPoiLayer,
  buildPoiSource,
  buildPoiStalenessLayer,
  POI_PIN_MIN_ZOOM,
  POI_SOURCE_ID,
} from './poiLayers'
import { buildWarningLayer, buildWarningSource, WARNING_SOURCE_ID } from './warningLayers'
import { buildWorkdayLayer, buildWorkdaySource, WORKDAY_SOURCE_ID } from './workdayLayers'
import { buildDisputeLayer, buildDisputeSource, DISPUTE_SOURCE_ID } from './disputeLayers'
import { nearbyTrailOpacityExpression } from './nearbyTrails'
import {
  buildTrailLabelLayer,
  NEARBY_TRAIL_LABEL_LAYER_ID,
  TRAIL_LABEL_LAYER_ID,
  TRAIL_LABEL_MIN_ZOOM,
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
import { OSM_CREDIT, USGS_TOPO_CREDIT } from './credits'
import { whenStyleReady } from './styleReady'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
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
 * layers. They are separated because they are separately LICENSED: neither
 * NYS OPRHP nor NYNJTC has stated reuse terms, so the pipeline publishes them
 * as their own artifact and publish.py holds that artifact back entirely
 * while either steward is outstanding (lib/config.ts's NEARBY_TRAILS_KEY).
 * One MapLibre GeoJSON source takes one `data`, so two artifacts is two
 * sources.
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

export const BACKDROP_LAYER_ID = 'backdrop'
export const TOPO_LAYER_ID = 'topo'
export const TRAIL_CASING_LAYER_ID = 'trail-casing'
export const BLAZE_LAYER_ID = 'trail-blaze'
export const TRAIL_OVERVIEW_LAYER_ID = 'trail-overview-line'
export const NEARBY_TRAIL_CASING_LAYER_ID = 'nearby-trail-casing'
export const NEARBY_BLAZE_LAYER_ID = 'nearby-trail-blaze'
export const NEARBY_LONG_TERM_CLOSURE_LAYER_ID = 'nearby-long-term-closure-band'
export const NEARBY_LONG_TERM_CLOSURE_CASING_LAYER_ID = 'nearby-long-term-closure-casing'

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
 * What the corridor view marks a highlight in (#858) - the app's blaze orange.
 *
 * NOT a blaze colour, and it never touches a trail line: it paints a mark
 * BESIDE the corridor, which is what keeps the two-colour rule intact while
 * still giving a hiker something to reach for. Fixed across appearances,
 * because a mark that changes hue with the sheet is a mark that has to be
 * relearned; it carries on paper and on ink alike.
 */
export const CORRIDOR_SELECTION_COLOR = '#c1611a'

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
 * The corridor-view centerline, or nothing (#869).
 *
 * Pushed and cleared through the same source, because "the sketch is gone" is
 * a state this has to be able to reach: it is drawn only until the real line
 * lands, and `null` here is what lands it. An empty collection rather than a
 * removed source, so there is one shape of style whatever a launch is doing.
 *
 * See lib/config.ts's TRAILS_OVERVIEW_KEY for what this line is worth - 100 m
 * of tolerance, which is a sketch at the corridor view and a lie at z14. The
 * layer's `maxzoom` is the other half of keeping that true.
 */
export function attachTrailOverview(
  map: MapLibreMap,
  overviewUrl: string | null,
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(TRAIL_OVERVIEW_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(TRAIL_OVERVIEW_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData((overviewUrl ?? emptyTrailOverview()) as never)
    },
    'Corridor-view centerline',
  )
}

/**
 * The casing-and-blaze pair that draws one source's trail lines.
 *
 * ONE TREATMENT, NOT TWO THAT CURRENTLY AGREE - lib/closureStyle.ts's
 * buildClosureLayers has the same shape for the same reason, and this was
 * extracted (#950) at the moment a second trail source appeared. Before that
 * there was one caller and the layers were written inline; the risk this
 * removes is not hypothetical, because the alternative on the table was
 * copying forty lines of paint expressions and hoping the next person who
 * adds a channel remembers there are two of them.
 *
 * Every argument below is an id or a source. Nothing about how a trail LOOKS
 * is a parameter, which is the property that makes the ghosting honest: a
 * nearby trail is the same line drawn dimmer, and the dimming comes from
 * nearbyTrailOpacityExpression reading the feature's own `source`, not from
 * this function being called differently.
 */
function buildTrailLineLayers(
  sourceId: string,
  casingId: string,
  blazeId: string,
  appearance: SheetAppearance,
): LayerSpecification[] {
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
        // The casing's own 0.7, MULTIPLIED by the line's ghosting rather
        // than replaced by it. Both facts are true at once and they compose:
        // a casing is always slightly softer than the blaze it carries, and
        // a nearby trail's whole stack - blaze and casing together - sits
        // back from the chosen trail's. Replacing the 0.7 would give a
        // ghosted line a FIRMER edge than the chosen trail's, which is the
        // opposite of what this channel is for.
        'line-opacity': ['*', 0.7, nearbyTrailOpacityExpression()] as unknown as number,
      },
    },
    {
      id: blazeId,
      type: 'line',
      source: sourceId,
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
        // The third channel (#783). Hue still says which blaze and width
        // still says which line the map is about; opacity says which SYSTEM,
        // which is the distinction an A.T.-only map never had to draw. See
        // map/nearbyTrails.ts for why it is opacity and not a halo or a hue.
        'line-opacity': nearbyTrailOpacityExpression() as unknown as number,
      },
    },
  ]
}

/**
 * The other organizations' trail lines, or nothing (#950).
 *
 * attachTrailOverview's shape, and one difference that matters: the overview
 * is pushed and then CLEARED, because it exists only until the real
 * centerline lands. These lines are not a stand-in for anything. Once they
 * are on the map they stay, so `null` here means "there are none" - a bucket
 * that holds no such artifact, which is what publish.py produces while either
 * steward's licence is unstated - rather than "they are finished".
 */
export function attachNearbyTrails(
  map: MapLibreMap,
  nearbyTrailsUrl: string | null,
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(NEARBY_TRAILS_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(NEARBY_TRAILS_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData((nearbyTrailsUrl ?? emptyTrailOverview()) as never)
    },
    'Nearby trails',
  )
}

/** What the overview source holds before there is one and after it is done.
 *  A function rather than a shared constant: MapLibre's typings want a
 *  mutable feature list, and one object handed to both the style and every
 *  later `setData` is one object two of them could write to. */
function emptyTrailOverview(): GeoJSON.FeatureCollection {
  return { type: 'FeatureCollection', features: [] }
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
  /**
   * Whether the trails data behind `trailsUrl` has the merged-chain shape
   * (#161, lib/trailShape.ts) - which decides the trails source's
   * `tolerance`. False by default and false whenever the caller cannot
   * tell, because the conservative direction (`tolerance: 0`) only ever
   * costs worker time, while the optimistic one over pre-merge data
   * reopens #160's miles-long gaps.
   */
  trailsMerged?: boolean
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
      // either steward's licence is unstated. An empty source rather than an
      // absent one so there is one shape of style whatever the bucket holds,
      // which is the same reason the overview above is declared empty.
      //
      // ATTRIBUTED LIKE THE TRAILS, and that is a placeholder rather than an
      // answer. The basemap credit below is honest about the BASEMAP; what
      // features/NEARBY_TRAILS.md §6 asks for is a per-steward line ("Trail
      // data: NYS OPRHP") in a voice that does not outrun a steward who
      // disclaims accuracy, read from the pipeline's own attribution fields.
      // That needs the sources screen to learn about held-back sources
      // (#927's screen, #932's registry question) and is not built. Nothing
      // ships uncredited in the meantime, because nothing ships.
      [NEARBY_TRAILS_SOURCE_ID]: {
        type: 'geojson',
        data: emptyTrailOverview(),
        attribution: OSM_CREDIT,
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
      [CORRIDOR_SOURCE_ID]: buildCorridorSource(),
      // The route being built (#755). Empty until the hiker drops points, and
      // no `attribution`: what it draws is the hiker's own intent, and there
      // is no third party to credit for a line they chose themselves.
      [ROUTE_SOURCE_ID]: buildRouteSource(),
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
          'line-color': blazeLineColor(appearance) as unknown as string,
          'line-width': TRAIL_WIDTH_EXPRESSION as unknown as number,
          // Ghosted here too, for the reason the two lines above are shared:
          // the sketch is the same appearance arriving early, so a nearby
          // trail that fades when the real line loads would read as the map
          // changing its mind about which trail it is about.
          'line-opacity': nearbyTrailOpacityExpression() as unknown as number,
        },
      },
      // The other organizations' trails (#950), UNDER the chosen trail's own
      // pair below. Order is the half of this that opacity cannot do: ghosting
      // says which system a line belongs to, but where a nearby trail runs
      // coincident with the chosen one - and in Harriman half the A.T.'s
      // length is within 150 m of another marked trail (#771) - the one drawn
      // last still owns the pixels. Drawn first, a nearby trail can never
      // cover the trail the map is about, whatever its opacity.
      ...buildTrailLineLayers(
        NEARBY_TRAILS_SOURCE_ID,
        NEARBY_TRAIL_CASING_LAYER_ID,
        NEARBY_BLAZE_LAYER_ID,
        appearance,
      ),
      // A nearby trail marked closed long-term gets the same barred band the
      // A.T.'s closures get (features/NEARBY_TRAILS.md §3: a hiker learns ONE
      // mark for "do not walk this"). Over its own blaze for the reason the
      // chosen trail's band is over its own - a barrier under the line is a
      // picture of an open trail - and still under everything about the
      // chosen trail, per the ordering argument above.
      ...buildClosureLayers(NEARBY_TRAILS_SOURCE_ID, {
        bandId: NEARBY_LONG_TERM_CLOSURE_LAYER_ID,
        casingId: NEARBY_LONG_TERM_CLOSURE_CASING_LAYER_ID,
        filter: LONG_TERM_CLOSED_FILTER,
      }),
      ...buildTrailLineLayers(
        TRAILS_SOURCE_ID,
        TRAIL_CASING_LAYER_ID,
        BLAZE_LAYER_ID,
        appearance,
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
      buildTrailLabelLayer(
        NEARBY_TRAILS_SOURCE_ID,
        trailCasingColor(appearance),
        mapBackdrop(appearance),
        TRAIL_LABEL_MIN_ZOOM,
        NEARBY_TRAIL_LABEL_LAYER_ID,
      ),
      buildTrailLabelLayer(
        TRAILS_SOURCE_ID,
        trailCasingColor(appearance),
        mapBackdrop(appearance),
        TRAIL_LABEL_MIN_ZOOM,
      ),
      // The corridor view's attribution, over the blaze and under everything
      // else (#598). Over, because the grey on an unattributed run has to
      // COVER the white blaze rather than sit beside it; under the route and
      // the closures, because a barrier or a hiker's own line crossing this
      // stretch matters more than who maintains it. Every layer here stops at
      // the seam - see corridorLayers.ts's CORRIDOR_MAX_ZOOM.
      ...buildCorridorLayers({
        casingColor: trailCasingColor(appearance),
        selectionColor: CORRIDOR_SELECTION_COLOR,
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
      // Over the blaze, and that ordering is the closure's entire job. A
      // barred red band UNDER the trail line would be a closure the trail is
      // drawn straight through - which is a picture of an open trail. See
      // lib/closureStyle.ts for why the band differs from a blaze in width,
      // rhythm and casing weight rather than only in colour.
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
      // identical either way.
      ...buildClosureLayers(CLOSURE_SOURCE_ID),
      ...buildClosureLayers(TRAILS_SOURCE_ID, {
        bandId: LONG_TERM_CLOSURE_LAYER_ID,
        casingId: LONG_TERM_CLOSURE_CASING_LAYER_ID,
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
