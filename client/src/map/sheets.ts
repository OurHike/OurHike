// The sheets the live map can be drawn in - every palette, the variant table
// that composes them, the appearance a caller names one by - and the ids and
// URLs the shell reads about the live sheet without building it (#1591).
//
// A LEAF, ON PURPOSE. Everything here is data: hex tables, a lookup over
// them, and strings. Nothing imports a layer builder, MapLibre, or the terrain
// and credits modules. That is what lets map/MapIcon.tsx draw a legend swatch
// in the sheet's casing ink, map/trailBadges.ts pick a badge plate for a dark
// sheet, and lib/mapLabelLayers.ts name a live layer, without any of them
// pulling map/liveTopo.ts - the sheet's twenty-one layers and their repaint -
// into the bundle a launch parses before its first frame. Measured 2026-09-30
// (features/LAUNCH_BUDGET.md §4.4's attribution over the built chunks): the
// live-topo module was 14,421 raw bytes of the eager closure, reached from
// App.tsx through five modules that wanted only what is now in this file.
//
// map/liveTopo.ts re-exports all of it, so every reader that imported these
// from there still does; the split changes which chunk they land in, not
// where they are read from. Each block below keeps the comment it was written
// with in liveTopo.ts - the provenance of a palette is the palette's.

import type { ResolvedTheme } from '../lib/theme'
import type { MapStyle, Theme } from '../lib/userPreferences'

export const OPENFREEMAP_TILEJSON = 'https://tiles.openfreemap.org/planet'

/**
 * The scheme the sheet's tile requests go through, and the template the osm
 * source declares. Config only - the handler that answers it lives in
 * basemap.ts (local package first, network fallthrough), the same
 * config/runtime split terrain.ts and contours.ts draw, and for the same
 * reason: building a style must cost arithmetic, not a protocol registration.
 */
export const BASEMAP_SCHEME = 'basemap'
export const BASEMAP_TILES_URL = `${BASEMAP_SCHEME}://{z}/{x}/{y}`

/**
 * Declared on the source because a `tiles:` template carries no TileJSON to
 * say it. 14 is the OpenMapTiles standard ceiling - true of OpenFreeMap's
 * planet and of our own Planetiler build alike (pipeline/BASEMAP.md), so the
 * local and network halves of the fallthrough agree on where overzooming
 * starts and one constant serves both.
 */
export const BASEMAP_MAX_ZOOM = 14

/**
 * Glyphs ship with the app, not from a font host (#188).
 *
 * Symbol layers fetch glyph PBFs per 256-codepoint range, and no offline
 * plumbing intercepts those requests - the pmtiles protocol only handles tile
 * sources. Served from a host, every label on the sheet - place names, peak
 * elevations, contour labels - silently rendered nothing without signal. So
 * the one fontstack the style uses is bundled under public/glyphs/ (6.24 MB,
 * all 256 ranges of Noto Sans Regular, OFL-licensed - provenance and licence
 * note sit next to the files) and the style points at its own origin. Being
 * real build assets is also what gets the ranges into the service worker's
 * precache, so a fresh install labels its map in airplane mode - the same
 * reasoning mapWorker.ts documents for the emitted worker asset.
 *
 * BASE_URL rather than a bare `/`: GitHub Pages serves the app under
 * /OurHike/app/, and a root-anchored path would resolve to the project site
 * instead - see vite.config.ts's note on BASE.
 */
export const BUNDLED_GLYPHS = `${import.meta.env.BASE_URL}glyphs/{fontstack}/{range}.pbf`

export const OSM_SOURCE_ID = 'osm'

/**
 * The `field` day sheet - MAP_STYLE_SPEC.md's reviewed favorite (card 1b in
 * the spec's mockups), and the palette every hiker on the defaults sees.
 *
 * A topographic sheet's palette, not a screen palette: white paper, ink that
 * is brown rather than black, woodland as a flat overprint rather than a
 * photograph of trees, and nothing competing with the blaze colours the trail
 * lines are drawn in. That last constraint is the real one, and it got
 * stricter in review: roads and tracks are NEUTRAL GRAY on purpose, because
 * nothing on the ground may share a hue with a blaze colour (review finding,
 * 2026-08-06) - the old sheet's tan roads sat too close to the Yellow and
 * Orange blazes for a glance to separate.
 */
export const TOPO_PALETTE = {
  /** Woodland overprint, the same green family as the app's sage tokens. */
  wood: '#dcebd2',
  scrub: '#e8f0dd',
  wetland: '#cfe3d8',
  rock: '#eae6da',
  /** Protected land. The wash is the WHOLE treatment - no outline (#347) -
   *  so it is mixed green enough to still read over woodland, which is what
   *  most protected land along the corridor is. */
  park: '#c2ddb1',
  water: '#8fc0dc',
  waterEdge: '#2e79a6',
  waterway: '#2e79a6',
  /** Contours in USGS brown. Index lines are the same hue, darker and wider. */
  contour: '#8a6c42',
  contourIndex: '#5f4527',
  contourLabel: '#4a3620',
  /** Roads and tracks: hue-free (see above), and since #1074 drawn as single
   *  strokes rather than cased ribbons - so `roadMajor` is now the INK of a
   *  1.8px line rather than the fill of a 7px one, and is correspondingly
   *  dark. It is the value `path` used to carry, which is where it came from:
   *  already hue-free, already tuned per sheet, and already the right darkness
   *  for a line of that weight. `path` moves 45% of the way to `wood` in
   *  exchange. */
  roadMajor: '#55503f',
  roadMinor: '#848672',
  track: '#8e8e80',
  path: '#929681',
  boundary: '#6f6753',
  label: '#14130f',
  labelHalo: '#ffffff',
  waterLabel: '#1c5c86',
  /** Relief shading. Here rather than inline at the layer for the same reason
   *  as everything else in this object: it is a colour, so it is a colour the
   *  appearance can change. */
  hillshadeShadow: '#4a4234',
  hillshadeHighlight: '#ffffff',
  hillshadeAccent: '#6f6753',
} as const

/** The shape both palettes share, so a key added to one has to be added to the
 *  other rather than silently keeping the light value under the dark theme. */
export type TopoPalette = Record<keyof typeof TOPO_PALETTE, string>

/**
 * The `night_hike` sheet - the dark style in its own right, and what `field`
 * turns into when the theme resolves dark (MAP_STYLE_SPEC.md: "night_hike is
 * the auto-dark for field").
 *
 * Not the light palette inverted. An inverted topo sheet puts white contours
 * and pale roads over dark ground, which is the wrong way round twice over:
 * contours and roads are the quiet layers here (see above - everything is
 * chosen to sit BEHIND the trail), and inversion makes them the loudest thing
 * on the screen while turning the blaze colours, which are not inverted
 * because they mean something, into the quietest.
 *
 * So it is re-drawn to the same brief instead. Ground goes to ink; woodland
 * stays a slightly-greener overprint of it, a few percent lighter rather than
 * a dark green block; contours keep their USGS brown at a lightness that reads
 * on ink without shouting; and the only things allowed to be genuinely bright
 * are the labels, because a place name you cannot read is a place name that is
 * not there.
 *
 * Kept dark on purpose, and darker than a desktop dark theme would be. The
 * reason this is in MVP at all is a phone out on a trail after sunset
 * (features/UX_CUSTOMIZATION.md), where the screen is the brightest object for
 * a mile and a "dark" map that settles at mid-grey still costs the night
 * vision it was meant to protect.
 */
export const TOPO_PALETTE_DARK: TopoPalette = {
  wood: '#101b14',
  scrub: '#0f1913',
  wetland: '#0e1c19',
  rock: '#141a13',
  /* Lifted off the card's own #122016 to clear the over-woodland margin the
     outline's removal made load-bearing (#347): the card drew this wash with
     a dashed edge to lean on, and with the edge gone the tint has to carry
     protected land by itself. Same hue, same night-vision brief - only far
     enough from `wood` for the fact to survive on a phone panel. */
  park: '#163218',
  water: '#0e2430',
  waterEdge: '#1f4456',
  waterway: '#2c5a72',
  contour: '#2c3a2e',
  contourIndex: '#465844',
  contourLabel: '#6b8465',
  roadMajor: '#565b46',
  roadMinor: '#3e4535',
  track: '#3e4532',
  path: '#373e30',
  boundary: '#444a3a',
  /* Moss, not white - card 1c's whole trick: the brightest ink on this sheet
     is the White blaze itself, which is the point of it. */
  label: '#96b98c',
  labelHalo: '#0c1410',
  waterLabel: '#5f8ea6',
  /* Relief inverts more honestly than ink does: a shadow on dark ground is
     near-black, and a lit slope is a dim green-grey rather than paper. */
  hillshadeShadow: '#040705',
  hillshadeHighlight: '#1d2a1e',
  hillshadeAccent: '#0f1a12',
}

/**
 * night_hike's red-light sub-mode: the dark sheet re-inked in one hue.
 *
 * Rod cells are nearly blind to deep red, which is why headlamps carry a red
 * mode - a red screen can be READ without spending the half hour of dark
 * adaptation a white one costs. So this is TOPO_PALETTE_DARK's lightness
 * ladder with every hue pulled to the same red-amber family: ground fills
 * stay near-black, lines sit in dim rust, and only the labels are allowed
 * brightness, exactly as on the dark sheet. Blue is the first casualty on
 * purpose - water keeps its lightness step and loses its hue, because a blue
 * that reads as blue is a wavelength the eye pays for.
 *
 * The reviewed values from the mockups' card 1c (Red light), which are dimmer
 * throughout than a first derivation of them was - "astronomy-grade darkness"
 * is the card's own bar, and every step of brightness spent here is spent
 * against it.
 */
export const TOPO_PALETTE_RED: TopoPalette = {
  wood: '#1c0906',
  scrub: '#190805',
  wetland: '#1a0a07',
  rock: '#1e0b07',
  /* The wash stays in the red family - a green would be a wavelength the eye
     pays for - and clears the same over-woodland margin the other sheets
     hold, because protected land is still information at night. Lifted off
     the card's #200c08 for the reason the dark sheet's was: the outline it
     was drawn beside is gone (#347), so the tint carries the fact alone. */
  park: '#3a1409',
  water: '#260e08',
  waterEdge: '#45180d',
  waterway: '#571f10',
  contour: '#481a0e',
  contourIndex: '#6b2a16',
  contourLabel: '#963f20',
  roadMajor: '#6b2a15',
  roadMinor: '#4f1e10',
  track: '#521f10',
  path: '#471b0e',
  boundary: '#521f10',
  label: '#c1611a',
  labelHalo: '#140503',
  waterLabel: '#a34c1c',
  hillshadeShadow: '#000000',
  hillshadeHighlight: '#2b0f07',
  hillshadeAccent: '#1c0906',
}

/**
 * `field` after an EXPLICIT dark - card 1b's Night: maximum-contrast dark,
 * white type on near-black, water still saturated. Deliberately distinct from
 * night_hike, which is dim on purpose: this one is for a bright screen in the
 * dark - driving to a trailhead - not for eyes that are adapting. Which is
 * why it is only reachable by CHOOSING dark (see sheetVariant): a phone that
 * flips itself dark at sunset on the trail gets night_hike instead.
 */
export const TOPO_PALETTE_FIELD_NIGHT: TopoPalette = {
  wood: '#17231a',
  scrub: '#141d15',
  wetland: '#12211d',
  rock: '#1c1e17',
  /* Every sheet below carries its park wash lifted off its card value, for
     the reason the two above do: the cards drew this tint with a dashed
     outline beside it, #347 removed the outline as a false trail line, and
     the wash now has to carry protected land alone - far enough from the
     sheet's own `wood` for the fact to survive over the woodland most
     protected land here is. The test file pins that margin per palette. */
  park: '#1b3d1c',
  water: '#123349',
  waterEdge: '#3d84ad',
  waterway: '#3d84ad',
  contour: '#5f5236',
  contourIndex: '#8a7649',
  contourLabel: '#b39b60',
  roadMajor: '#7a745c',
  roadMinor: '#575845',
  track: '#5d5e54',
  path: '#4d503e',
  boundary: '#5f5c4a',
  label: '#ffffff',
  labelHalo: '#0d0e0b',
  waterLabel: '#7cbade',
  hillshadeShadow: '#000000',
  hillshadeHighlight: '#2e3128',
  hillshadeAccent: '#141610',
}

/**
 * `quiet_pine` - card 1a: modern muted outdoor. The brown ink cools to
 * gray-green so the sheet reads as one calm surface and the blaze colours
 * become the loudest thing on it. The closest sheet to the app chrome's own
 * palette, and the mockups' own suggested default before review settled on
 * field.
 */
export const TOPO_PALETTE_QUIET_PINE: TopoPalette = {
  wood: '#dfe8d6',
  scrub: '#e7ecdc',
  wetland: '#d6e2da',
  rock: '#e9e7dd',
  park: '#cbe0be',
  water: '#b7d4de',
  waterEdge: '#84aec2',
  waterway: '#6f9fb8',
  contour: '#a3a08c',
  contourIndex: '#7c7a64',
  contourLabel: '#6d6b55',
  roadMajor: '#97907a',
  roadMinor: '#b0af9a',
  track: '#b4ae94',
  path: '#b7b8a3',
  boundary: '#9a9483',
  label: '#3f4237',
  labelHalo: '#f4f4ec',
  waterLabel: '#41708a',
  hillshadeShadow: '#5f6350',
  hillshadeHighlight: '#ffffff',
  hillshadeAccent: '#8b8f7c',
}

/** quiet_pine's dark companion - evening use at normal screen brightness;
 *  blazes keep their day hexes. For headlamp hours, night_hike goes further. */
export const TOPO_PALETTE_QUIET_PINE_NIGHT: TopoPalette = {
  wood: '#1c2b21',
  scrub: '#192720',
  wetland: '#182a26',
  rock: '#20261f',
  park: '#1e3e22',
  water: '#14303c',
  waterEdge: '#2b5468',
  waterway: '#3a6b84',
  contour: '#46503f',
  contourIndex: '#66705a',
  contourLabel: '#8b9678',
  roadMajor: '#6a6f58',
  roadMinor: '#4f5745',
  track: '#4e5540',
  path: '#47503f',
  boundary: '#55584a',
  label: '#cfd8c2',
  labelHalo: '#121a14',
  waterLabel: '#7fb3cc',
  hillshadeShadow: '#060b08',
  hillshadeHighlight: '#2c3a2e',
  hillshadeAccent: '#1a231c',
}

/**
 * `parchment` - card 1d: the current sheet leaned harder into the USGS quad
 * it quotes. Warmer paper, contours saturated toward true USGS brown, the
 * classic green woodland overprint, water edges at engraving weight. The
 * style for anything a hiker prints or reads like a document.
 */
export const TOPO_PALETTE_PARCHMENT: TopoPalette = {
  wood: '#d9e4c0',
  scrub: '#e5ebcf',
  wetland: '#cfdfc9',
  rock: '#e9e2cd',
  park: '#c4dea0',
  water: '#aed3e4',
  waterEdge: '#5b9cbd',
  waterway: '#4f92b4',
  contour: '#b06e35',
  contourIndex: '#7e4a1e',
  contourLabel: '#6b3d16',
  roadMajor: '#7d6a45',
  roadMinor: '#9d9570',
  track: '#9e8659',
  path: '#a6a17c',
  boundary: '#8a6f4a',
  label: '#3d3222',
  labelHalo: '#f6efdd',
  waterLabel: '#2f6b8a',
  hillshadeShadow: '#6b5535',
  hillshadeHighlight: '#fff8e6',
  hillshadeAccent: '#93825f',
}

/** parchment's Lantern mode - the same engraved linework on umber, warm
 *  candle-dark. For reading in the tent, not navigating on the move;
 *  night_hike owns that job. */
export const TOPO_PALETTE_LANTERN: TopoPalette = {
  wood: '#1f2010',
  scrub: '#1c1d0e',
  wetland: '#1a2013',
  rock: '#241c0e',
  park: '#2c3a14',
  water: '#142834',
  waterEdge: '#2b4c5e',
  waterway: '#396379',
  contour: '#6b4a24',
  contourIndex: '#966c38',
  contourLabel: '#c19453',
  roadMajor: '#77644a',
  roadMinor: '#584c36',
  track: '#5c4c30',
  path: '#4f4530',
  boundary: '#5f4f36',
  label: '#e0d0a6',
  labelHalo: '#191108',
  waterLabel: '#7aa8bf',
  hillshadeShadow: '#000000',
  hillshadeHighlight: '#2e2410',
  hillshadeAccent: '#4a3d24',
}

/**
 * `ridgeline` - card 1e: terrain does the talking. Hillshade carried at 0.55
 * through hiking zooms, contours promoted to gray ink, landcover flattened
 * near-monochrome; colour is reserved for water, park edges and the blazes.
 * For judging a climb before committing to it.
 */
export const TOPO_PALETTE_RIDGELINE: TopoPalette = {
  wood: '#e2e4d8',
  scrub: '#e9eadf',
  wetland: '#dde4dd',
  rock: '#e7e5da',
  park: '#cee0ba',
  water: '#a5c8d6',
  waterEdge: '#6ba2bb',
  waterway: '#5e97b2',
  contour: '#97948a',
  contourIndex: '#6e6b60',
  contourLabel: '#5c594e',
  roadMajor: '#8c8574',
  roadMinor: '#aaa697',
  track: '#aba492',
  path: '#b3b0a1',
  boundary: '#969082',
  label: '#3a382f',
  labelHalo: '#efeee8',
  waterLabel: '#40708a',
  hillshadeShadow: '#3f3d33',
  hillshadeHighlight: '#ffffff',
  hillshadeAccent: '#6e6b60',
}

/** ridgeline's Moonlit relief - the highlight lifts instead of the shadow
 *  deepening, so ridges glow and valleys sink; contours one step brighter
 *  than quiet_pine's night so terrain still reads. */
export const TOPO_PALETTE_RIDGELINE_NIGHT: TopoPalette = {
  wood: '#1b201a',
  scrub: '#191d17',
  wetland: '#182019',
  rock: '#1f211c',
  park: '#1e381c',
  water: '#122833',
  waterEdge: '#295062',
  waterway: '#356882',
  contour: '#4c4e45',
  contourIndex: '#6e7165',
  contourLabel: '#909485',
  roadMajor: '#626555',
  roadMinor: '#494d40',
  track: '#4a4e40',
  path: '#42463a',
  boundary: '#4e5145',
  label: '#d5d8c9',
  labelHalo: '#141613',
  waterLabel: '#79aac2',
  hillshadeShadow: '#000000',
  hillshadeHighlight: '#34372e',
  hillshadeAccent: '#101210',
}

/**
 * One sheet as drawn: its palette plus the handful of values that vary with
 * it but do not live in the palette's 24 colour keys. Exactly what one mockup
 * card mode carries, and the cards are the source of every row below.
 *
 * - `backdrop`/`casing` are style.ts's layers (the paper under everything,
 *   the hairline under every blaze) - carried here because each sheet inks
 *   them itself, and read through style.ts's mapBackdrop/trailCasingColor.
 * - `hillshadeBase` is the relief weight at hiking zooms - ridgeline's whole
 *   idea is carrying it at 0.55 where the others sit at 0.30-0.35.
 * - `contoursEarly` moves the contour fade-ins one zoom earlier (ridgeline:
 *   terrain first means terrain sooner).
 * - `boldType` is field's sunlight brief: labels one size up, halos 1.8 -
 *   per the card, not sheet-wide.
 * - `dark` is what the archive dimming and the chrome-facing predicates key
 *   off; `redLight` marks the one variant that overrides the blazes.
 */
export interface SheetVariant {
  palette: TopoPalette
  backdrop: string
  casing: string
  hillshadeBase: number
  contoursEarly: boolean
  boldType: boolean
  dark: boolean
  redLight: boolean
}

const QUIET_PINE_DAY: SheetVariant = {
  palette: TOPO_PALETTE_QUIET_PINE,
  backdrop: '#f4f4ec',
  casing: '#2b2f26',
  hillshadeBase: 0.35,
  contoursEarly: false,
  boldType: false,
  dark: false,
  redLight: false,
}

const QUIET_PINE_NIGHT: SheetVariant = {
  palette: TOPO_PALETTE_QUIET_PINE_NIGHT,
  backdrop: '#16201a',
  casing: '#0a0f0b',
  hillshadeBase: 0.35,
  contoursEarly: false,
  boldType: false,
  dark: true,
  redLight: false,
}

const FIELD_DAY: SheetVariant = {
  palette: TOPO_PALETTE,
  backdrop: '#ffffff',
  casing: '#14130f',
  hillshadeBase: 0.3,
  contoursEarly: false,
  boldType: true,
  dark: false,
  redLight: false,
}

const FIELD_NIGHT: SheetVariant = {
  palette: TOPO_PALETTE_FIELD_NIGHT,
  backdrop: '#0d0e0b',
  casing: '#000000',
  hillshadeBase: 0.3,
  contoursEarly: false,
  boldType: true,
  dark: true,
  redLight: false,
}

/** One variant for both of night_hike's slots: it has no day form - a
 *  night-vision sheet chosen in daylight is still the night-vision sheet. */
const NIGHT_HIKE: SheetVariant = {
  palette: TOPO_PALETTE_DARK,
  backdrop: '#0c1410',
  casing: '#060907',
  hillshadeBase: 0.3,
  contoursEarly: false,
  boldType: false,
  dark: true,
  redLight: false,
}

const NIGHT_HIKE_RED: SheetVariant = {
  palette: TOPO_PALETTE_RED,
  backdrop: '#140503',
  casing: '#0a0301',
  hillshadeBase: 0.3,
  contoursEarly: false,
  boldType: false,
  dark: true,
  redLight: true,
}

const PARCHMENT_DAY: SheetVariant = {
  palette: TOPO_PALETTE_PARCHMENT,
  backdrop: '#f6efdd',
  casing: '#241d12',
  hillshadeBase: 0.35,
  contoursEarly: false,
  boldType: false,
  dark: false,
  redLight: false,
}

const PARCHMENT_LANTERN: SheetVariant = {
  palette: TOPO_PALETTE_LANTERN,
  backdrop: '#191108',
  casing: '#0e0a05',
  hillshadeBase: 0.35,
  contoursEarly: false,
  boldType: false,
  dark: true,
  redLight: false,
}

const RIDGELINE_DAY: SheetVariant = {
  palette: TOPO_PALETTE_RIDGELINE,
  backdrop: '#efeee8',
  casing: '#26251e',
  hillshadeBase: 0.55,
  contoursEarly: true,
  boldType: false,
  dark: false,
  redLight: false,
}

const RIDGELINE_NIGHT: SheetVariant = {
  palette: TOPO_PALETTE_RIDGELINE_NIGHT,
  backdrop: '#171916',
  casing: '#0b0d0a',
  hillshadeBase: 0.55,
  contoursEarly: true,
  boldType: false,
  dark: true,
  redLight: false,
}

/** Every style's day and night sheet, exactly as the mockup cards spec them.
 *  Exported for the tests that sweep all of them; resolution goes through
 *  sheetVariant below, never through this table directly. */
export const SHEET_VARIANTS: Record<
  MapStyle,
  { day: SheetVariant; night: SheetVariant }
> = {
  quiet_pine: { day: QUIET_PINE_DAY, night: QUIET_PINE_NIGHT },
  field: { day: FIELD_DAY, night: FIELD_NIGHT },
  night_hike: { day: NIGHT_HIKE, night: NIGHT_HIKE },
  parchment: { day: PARCHMENT_DAY, night: PARCHMENT_LANTERN },
  ridgeline: { day: RIDGELINE_DAY, night: RIDGELINE_NIGHT },
}

/** The red variant, reachable only through night_hike + the toggle - see
 *  sheetVariant. Exported for the same test sweep as SHEET_VARIANTS. */
export const SHEET_VARIANT_RED: SheetVariant = NIGHT_HIKE_RED

/**
 * Which sheet the map draws, per MAP_STYLE_SPEC.md's preferences. All
 * optional, defaulting to the sheet a caller with no opinion has always been
 * handed - the field day sheet.
 *
 * `theme` is the spec's `mapMode` under the name this codebase already had
 * for it: day = light, night = dark, and auto resolves through
 * lib/useTheme.ts before it gets here, exactly as it does for the chrome.
 * `themeChoice` is the preference BEFORE that resolution, and it exists for
 * exactly one distinction - see sheetVariant on field's two darks.
 */
export interface SheetAppearance {
  theme?: ResolvedTheme
  /** The stored preference ('light' | 'dark' | 'auto'), so night can tell
   *  "chosen" from "arrived with sunset". Defaults to 'auto', which keeps
   *  every caller that does not pass it on the spec's auto behaviour. */
  themeChoice?: Theme
  mapStyle?: MapStyle
  /** Only meaningful with night_hike - see TOPO_PALETTE_RED. */
  redLight?: boolean
  /**
   * Whether each trail line is inked in its own blaze hue, or every line in
   * the one red (#1575, lib/blaze.ts's PLAIN_TRAIL_COLOR). Absent means the
   * hues - what every caller drew before the switch existed, so a caller with
   * no opinion builds the style it always built - and the SHIPPED default is
   * lib/userPreferences.ts's `blaze_colors_shown: false`, which MapView always
   * passes. Read by map/style.ts's blazeLineColor alone: the sheet's own
   * palette (sheetVariant below) never looks at it, and neither does the
   * legend's line swatch, on the maintainer's instruction that the switch
   * changes the map and nothing else (map/MapIcon.tsx's TrailLineSwatch).
   */
  blazeColorsShown?: boolean
}

/**
 * The sheet's variant for an appearance. One function so nothing else has to
 * know how the preferences compose:
 *
 * - night_hike is dark under either theme (a hiker readying night vision
 *   before dusk should not have to flip the whole app), and red light
 *   refines it only - never any day sheet.
 * - Every other style follows the resolved theme to its own night form -
 *   with one deliberate exception. Field's AUTO-dark is night_hike (the
 *   spec's own line): a phone that flips itself dark at sunset is a phone on
 *   a trail at dusk, and handing it field's maximum-contrast white-on-black
 *   night sheet would light the woods up. Field/night is reachable by
 *   CHOOSING the dark theme, which is the "bright screen in the dark" case
 *   it was drawn for.
 */
export function sheetVariant({
  theme = 'light',
  themeChoice = 'auto',
  mapStyle = 'field',
  redLight = false,
}: SheetAppearance): SheetVariant {
  if (mapStyle === 'night_hike' && redLight) return NIGHT_HIKE_RED
  if (theme !== 'dark') return SHEET_VARIANTS[mapStyle].day
  if (mapStyle === 'field' && themeChoice !== 'dark') return NIGHT_HIKE
  return SHEET_VARIANTS[mapStyle].night
}

/** The palette alone, for the callers that only paint colours. */
export function sheetPalette(appearance: SheetAppearance): TopoPalette {
  return sheetVariant(appearance).palette
}

export const LIVE_TOPO_LAYER_IDS = {
  wood: 'topo-wood',
  scrub: 'topo-scrub',
  wetland: 'topo-wetland',
  rock: 'topo-rock',
  parkFill: 'topo-park-fill',
  hillshade: 'topo-hillshade',
  water: 'topo-water',
  waterway: 'topo-waterway',
  contour: 'topo-contour',
  contourIndex: 'topo-contour-index',
  contourLabel: 'topo-contour-label',
  roadMinor: 'topo-road-minor',
  roadMajor: 'topo-road-major',
  track: 'topo-track',
  path: 'topo-path',
  boundary: 'topo-boundary',
  peak: 'topo-peak',
  waterLabel: 'topo-water-label',
  /**
   * Road names (#1194).
   *
   * Tier 1 of map/labelLadder.ts, and the handoff's argument for putting it
   * there is worth keeping next to the layer: "Roads exist specifically so a
   * user can find a start point." Every other label on this sheet describes
   * ground a hiker walks; this one describes how they got there, which is the
   * question the day-hike builder is answering.
   *
   * `transportation_name` rather than `transportation` - the OpenMapTiles
   * schema keeps road geometry and road names in separate source layers, and
   * the line layers above read the geometry one, which carries no `name` at
   * all.
   */
  roadLabel: 'topo-road-label',
  place: 'topo-place',
} as const
