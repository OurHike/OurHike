// The inks the map and the chrome share: what a sheet paints its paper,
// its trail casing, a closure's tape and the hiker's mark in, and the two
// widths a trail line is drawn at (#1591).
//
// A LEAF, ON PURPOSE. The legend's swatches (map/MapIcon.tsx, through
// chrome/PoiRow.tsx on Today's next-turn card) draw a trail line and a
// closure exactly as the map does, and for that they need the sheet's casing
// ink, the red-light rule, the tape's paper and the width tiers - eight
// values, and until this file they came from map/style.ts, which brought its
// eighty-odd layer builders with it. Measured 2026-09-30 by attributing the
// built chunks to their sources: the style module was 18,925 gzip bytes of
// the eager closure, in front of a first frame that draws no map. Everything
// here is a function of the sheet variant (map/sheets.ts) or a constant;
// map/style.ts re-exports all of it and reads it back for its own layers,
// so nothing is defined twice. The comments travelled with the values.

import type { ResolvedTheme } from '../lib/theme'
import { CLOSURE_INK } from '../lib/closureStyle'
import type { PositionInk } from './positionMark'
import { sheetVariant, type SheetAppearance } from './sheets'

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
 * Which ink family the hiker's mark is drawn in (#1581, map/positionMark.ts):
 * red light's one hue where it is in force, bone on every other dark sheet,
 * the pins' own hairline on the day sheets. Defined off the two predicates
 * above so it cannot drift from what "dark" and "red light" mean here.
 */
export function positionInkFor(appearance: SheetAppearance): PositionInk {
  if (redLightActive(appearance)) return 'red'
  return sheetIsDark(appearance) ? 'night' : 'day'
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
 * The paper the barrier tape lies on, per appearance (#1575, option E, and
 * the maintainer's dark-mode reading of 2026-09-18).
 *
 * The sheet's own backdrop by day, so the band is parchment on parchment
 * and white on the field sheet. On a dark sheet it is the field day sheet's
 * white paper (MAP_BACKDROP.light) rather than the sheet's ink: option E was
 * chosen off five treatments rendered on the day sheet, and built as "the
 * sheet's paper" it put red stripes on near-black ink over a near-black map
 * - "it's really hard to tell it's a closure when the background is black,
 * with black & red alternating for the closure. Maybe that should be red &
 * white just for dark mode." The night sheets' whole point is a dark ground
 * (features/MAP_STYLE_SPEC.md), and the tape is the one thing on them that
 * must not be, because it says "do not walk this".
 *
 * RED LIGHT KEEPS ITS OWN PAPER, and that is the open question rather than
 * a decision: under red light every hue collapses to one to spare night
 * vision, and a white band would be the brightest thing on the screen. The
 * maintainer asked for dark mode; red light is the dark sheet with a rule
 * of its own, so it is left as option E built it - stripes on its ink -
 * until somebody says what a closure should look like under it.
 * @unvalidated on a phone at night, both halves.
 */
export function closureTapeGround(appearance: SheetAppearance): string {
  if (sheetIsDark(appearance) && !redLightActive(appearance)) return MAP_BACKDROP.light
  return mapBackdrop(appearance)
}

/**
 * The ink a closure's trace and crosses are drawn in, per appearance (#1677).
 *
 * lib/closureStyle.ts's CLOSURE_INK on every sheet whose closure paper is
 * light - which, through closureTapeGround above, is every sheet but red
 * light. Under red light the paper is the sheet's own near-black ink, so the
 * mark takes the one hue the mode permits (RED_LIGHT_BLAZE_COLOR), as every
 * trail line does there. What separates a closure from a trail under red
 * light is then entirely structural - the crosses and the dotted trace -
 * which is the same claim the mark makes on every other sheet.
 * @unvalidated on a phone under red light at night.
 */
export function closureInk(appearance: SheetAppearance): string {
  return redLightActive(appearance) ? RED_LIGHT_BLAZE_COLOR : CLOSURE_INK
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

/** The two width tiers, in CSS pixels. */
export const PRIMARY_TRAIL_WIDTH = 4.5
export const SIDE_TRAIL_WIDTH = 2.5

/** How far the dark casing shows past each side of the line it sits under. */
export const CASING_OVERHANG = 1
