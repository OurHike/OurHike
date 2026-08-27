// The live topographic background: OpenStreetMap vector tiles, drawn as a
// hiking sheet rather than a road map.
//
// WHY VECTOR, WHEN THE DOWNLOADED BACKGROUND IS RASTER
//
// The corridor archive is a picture of a map. US Topo quads are pre-rendered
// at 1:24,000, in per-quad UTM zones, with their labels baked into the pixels -
// so mosaicking them means reprojecting and resampling ink that was drawn for
// one scale, and reading them at any other zoom means looking at that ink
// stretched or crushed. Seams between quads of different vintages, type that
// cannot reflow, contours that cannot be recoloured, and nothing at all
// outside the 30-mile strip are not bugs in that pipeline; they are what a
// raster mosaic IS. features/MAP_OPTIONS.md's own framing - a live background
// is additive, most useful where there is signal - still holds, which is why
// this stacks over the archive rather than deleting it.
//
// Vector tiles carry the features instead of a picture of them, so the same
// bytes render sharp at every zoom, and every colour, weight and threshold
// below is ours to set. That is what makes "stylized for hiking" a real thing
// rather than a filter: what a hiker needs foregrounded (water, woodland,
// terrain shape, tracks and paths, named summits) is foregrounded, and what a
// road map would foreground is turned down or left out.
//
// THE SOURCE
//
// Local bytes first, the network where they do not reach (#189). The sheet's
// tiles come through the `basemap://` scheme below: map/basemap.ts answers
// each request from the downloaded basemap package when the phone holds one,
// and falls through - per tile, not per session - to OpenFreeMap's public
// instance where the package does not answer. Both serve the same unmodified
// OpenMapTiles schema (the package is built by our own Planetiler job,
// pipeline/BASEMAP.md), which is what lets every layer below stay one
// definition with no offline variant.
//
// OpenFreeMap is the network half for the same reasons it was the whole
// source: OpenStreetMap data, no API key, no registration, no request cap,
// explicitly free for commercial use with attribution. That last part is why
// it is here and raw tile.openstreetmap.org is not - the OSMF tile policy
// warns that access to that server may be withdrawn from exactly this kind
// of app, and MAP_OPTIONS.md already ruled it out on those grounds.
//
// Attribution is a licence condition on both counts - ODbL for the data,
// OpenFreeMap's own terms for the hosting - so LIVE_TOPO_ATTRIBUTION is
// carried into the style and is not behind a prop.
//
// If the public instance ever becomes a problem (it is donation-funded and
// carries no SLA), OPENFREEMAP_TILEJSON is the single line to repoint: the
// schema is standard OpenMapTiles, so a self-hosted extract on the R2 bucket
// the pipeline already publishes to serves the same layer names, and nothing
// below this constant changes.

import type {
  LayerSpecification,
  SourceSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { whenStyleReady } from './styleReady'
import { OPENFREEMAP_CREDIT, OSM_CREDIT } from './credits'
import type { ResolvedTheme } from '../lib/theme'
import type { MapStyle, Theme } from '../lib/userPreferences'
import {
  CONTOUR_ELEVATION_KEY,
  CONTOUR_LAYER,
  CONTOUR_LEVEL_KEY,
  CONTOUR_MAX_ZOOM,
  CONTOUR_SOURCE_ID,
  DEM_MAX_ZOOM,
  DEM_SOURCE_ID,
  ELEVATION_ATTRIBUTION,
  type ContourUnits,
  type TerrainUrls,
} from './terrain'

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
 * What the vector source declares: OpenFreeMap's terms for the hosting and
 * ODbL for the data underneath it, both of which this one source brings.
 *
 * Composed from credits.ts's atoms rather than spelled out, because the corner
 * shows those atoms one per line and a second spelling of either would be a
 * credit the deduping could not see - which is how "© OpenStreetMap
 * contributors" came to be printed twice in the first place.
 */
export const LIVE_TOPO_ATTRIBUTION = `${OPENFREEMAP_CREDIT} · ${OSM_CREDIT}`

/**
 * One font, varied by size, colour and halo rather than by weight.
 *
 * A fontstack the glyph endpoint does not have is a label layer that silently
 * renders nothing, and "Noto Sans Regular" is the one stack every OpenMapTiles
 * glyph source ships - including the bundled one, which is why BUNDLED_GLYPHS
 * carries exactly this stack and no other. Reaching for a second weight would
 * double the app's 6.24 MB of glyph assets to buy a distinction that halo and
 * size already make.
 */
const FONT = ['Noto Sans Regular']

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
  place: 'topo-place',
} as const

/**
 * Every paint property on the sheet whose value is a colour, and which colour
 * it is - in one table.
 *
 * It is read twice, which is the whole reason it is a table rather than
 * literals at each layer. liveTopoLayers() builds the style out of it, and
 * attachSheetAppearance() replays it onto a LIVE map when the appearance changes.
 * Written out in both places instead, the two would drift, and what drift
 * looks like here is one layer that did not follow the theme - a road still
 * drawn in paper-brown over an ink sheet, which reads as a rendering bug
 * rather than as a missing line in a list.
 *
 * Colours only. Widths, dash patterns and opacities stay at their layers,
 * because they do not change with the theme and hoisting them here would put
 * half of each layer's paint in a different part of the file for no gain.
 */
export const SHEET_COLOURS: ReadonlyArray<
  readonly [layer: string, property: string, colour: keyof TopoPalette]
> = [
  [LIVE_TOPO_LAYER_IDS.wood, 'fill-color', 'wood'],
  [LIVE_TOPO_LAYER_IDS.scrub, 'fill-color', 'scrub'],
  [LIVE_TOPO_LAYER_IDS.wetland, 'fill-color', 'wetland'],
  [LIVE_TOPO_LAYER_IDS.rock, 'fill-color', 'rock'],
  [LIVE_TOPO_LAYER_IDS.parkFill, 'fill-color', 'park'],
  [LIVE_TOPO_LAYER_IDS.hillshade, 'hillshade-shadow-color', 'hillshadeShadow'],
  [LIVE_TOPO_LAYER_IDS.hillshade, 'hillshade-highlight-color', 'hillshadeHighlight'],
  [LIVE_TOPO_LAYER_IDS.hillshade, 'hillshade-accent-color', 'hillshadeAccent'],
  [LIVE_TOPO_LAYER_IDS.water, 'fill-color', 'water'],
  [LIVE_TOPO_LAYER_IDS.water, 'fill-outline-color', 'waterEdge'],
  [LIVE_TOPO_LAYER_IDS.waterway, 'line-color', 'waterway'],
  [LIVE_TOPO_LAYER_IDS.contour, 'line-color', 'contour'],
  [LIVE_TOPO_LAYER_IDS.contourIndex, 'line-color', 'contourIndex'],
  [LIVE_TOPO_LAYER_IDS.contourLabel, 'text-color', 'contourLabel'],
  [LIVE_TOPO_LAYER_IDS.contourLabel, 'text-halo-color', 'labelHalo'],
  [LIVE_TOPO_LAYER_IDS.roadMinor, 'line-color', 'roadMinor'],
  [LIVE_TOPO_LAYER_IDS.roadMajor, 'line-color', 'roadMajor'],
  [LIVE_TOPO_LAYER_IDS.track, 'line-color', 'track'],
  [LIVE_TOPO_LAYER_IDS.path, 'line-color', 'path'],
  [LIVE_TOPO_LAYER_IDS.boundary, 'line-color', 'boundary'],
  [LIVE_TOPO_LAYER_IDS.peak, 'text-color', 'label'],
  [LIVE_TOPO_LAYER_IDS.peak, 'text-halo-color', 'labelHalo'],
  [LIVE_TOPO_LAYER_IDS.waterLabel, 'text-color', 'waterLabel'],
  [LIVE_TOPO_LAYER_IDS.waterLabel, 'text-halo-color', 'labelHalo'],
  [LIVE_TOPO_LAYER_IDS.place, 'text-color', 'label'],
  [LIVE_TOPO_LAYER_IDS.place, 'text-halo-color', 'labelHalo'],
]

/** One layer's colour paint properties, resolved against a palette. Spread
 *  into the layer's own `paint` alongside whatever is not a colour. */
function sheetColours(layer: string, palette: TopoPalette): Record<string, string> {
  return Object.fromEntries(
    SHEET_COLOURS.filter(([id]) => id === layer).map(([, property, colour]) => [
      property,
      palette[colour],
    ]),
  )
}

/** Shorthand for the OpenMapTiles `class` attribute test, used a dozen times. */
function isClass(...values: string[]): unknown[] {
  return values.length === 1
    ? ['==', ['get', 'class'], values[0]]
    : ['in', ['get', 'class'], ['literal', values]]
}

/**
 * The zoom each place class starts labelling at (#159).
 *
 * Distance decides what deserves ink, the way it does on a paper sheet. The
 * corridor-wide view crosses the whole Boston-Washington seaboard, and with
 * every class labelling at every zoom, that view was a wall of type the
 * centerline had to be picked out from under. So each class waits for the
 * zoom where its name starts meaning something to a hiker: a city anchors
 * the map from any distance, a town matters once a section is being planned,
 * a village once it is about to be walked past.
 *
 * Cities carry no threshold - orientation is their whole job, and the
 * corridor view without them is a line through unnamed country.
 */
export const PLACE_TOWN_MIN_ZOOM = 8
export const PLACE_VILLAGE_MIN_ZOOM = 11

export const PLACE_FILTER = [
  'step',
  ['zoom'],
  isClass('city'),
  PLACE_TOWN_MIN_ZOOM,
  isClass('city', 'town'),
  PLACE_VILLAGE_MIN_ZOOM,
  isClass('city', 'town', 'village'),
]

/**
 * Which label survives when two places collide: the bigger one.
 *
 * Lower sorts place first, and earlier placement wins the space - so without
 * this, whether Boston or a suburb's town label survives their collision is
 * decided by feature order inside the tile, which is nobody's decision. Same
 * reasoning as poiLayers.ts's POI_PRIORITY, one layer over.
 */
export const PLACE_SORT_KEY_EXPRESSION = [
  'match',
  ['get', 'class'],
  'city',
  0,
  'town',
  1,
  2,
]

/**
 * How hard the relief is shaded - a zoom ramp rather than one number, and the
 * reason is what the rest of this sheet does NOT draw.
 *
 * The hillshade is the only layer here with something to say at every zoom.
 * Everything else that describes terrain is keyed to hiking zooms: the
 * contours fade in over 9-12 and are at flat zero below that, their labels
 * start at 12, the peaks at 10, and OpenMapTiles carries no woodland to fill
 * below roughly z7. The opening view is the whole trail - App.tsx frames
 * CORRIDOR_BOUNDS, which on a phone lands near z4 - so on that view relief is
 * the only thing between the hiker and blank paper.
 *
 * At 0.35, stretched across a thousand kilometres of DEM, it was not enough to
 * be one: the first thing anyone saw on opening the app was an empty sheet
 * with a scale bar on it. So the shading is carried at full strength exactly
 * where it works alone, and hands back to its old weight as the contours
 * arrive - over the same 9-to-12 window they fade in across, read off the same
 * numbers rather than a second set that could drift from them.
 *
 * Past the handover nothing changes: at hiking zooms this is one flat weight,
 * which is what keeps the shading from competing with the contours for the
 * same job and from making the trail line harder to follow across a slope.
 * `interpolate` holds its end values outside the stops, so both ends are flat
 * rather than extrapolating into a black hillside.
 *
 * The hiking-zoom weight is the variant's own (SheetVariant.hillshadeBase):
 * 0.30 on field and night_hike, whose darker contour ink does some of the
 * work the shading was doing; 0.35 on quiet_pine and parchment, the weight
 * the sheet launched at; 0.55 on ridgeline, whose whole idea is relief
 * carried strong. The constant below is the default sheet's value, kept for
 * the callers and tests that reason about the ramp without a variant in
 * hand.
 *
 * It also costs nothing. The DEM tiles behind this layer are fetched at every
 * zoom already; the ramp only decides how much of what they contain reaches
 * the screen.
 */
export const HILLSHADE_EXAGGERATION = 0.3
export const HILLSHADE_RELIEF_ONLY_EXAGGERATION = 1
/** The first zoom at which any contour ink is drawn, and the zoom by which
 *  both contour layers are at full strength - see contourFadeZooms below,
 *  which these have to keep agreeing with. */
export const HILLSHADE_HANDOVER_START_ZOOM = 9
export const HILLSHADE_HANDOVER_END_ZOOM = 12

/** The relief ramp for one variant's hiking-zoom weight. One builder, used
 *  by the style build and the live repaint alike, so the two cannot drift. */
export function hillshadeExaggerationExpression(base: number): unknown[] {
  return [
    'interpolate',
    ['linear'],
    ['zoom'],
    HILLSHADE_HANDOVER_START_ZOOM,
    HILLSHADE_RELIEF_ONLY_EXAGGERATION,
    HILLSHADE_HANDOVER_END_ZOOM,
    base,
  ]
}

export const HILLSHADE_EXAGGERATION_EXPRESSION =
  hillshadeExaggerationExpression(HILLSHADE_EXAGGERATION)

/**
 * Where each contour layer fades in, per variant.
 *
 * The default window is the handover the hillshade comment above describes:
 * index lines over 9-11, minor lines over 10-12. `contoursEarly` (ridgeline)
 * moves both one zoom earlier - the card's "contour opacity ramps arrive one
 * zoom earlier" - because a terrain-first sheet wants the land's shape before
 * a general sheet needs it.
 */
export function contourFadeZooms(variant: SheetVariant): {
  minor: [start: number, full: number]
  index: [start: number, full: number]
} {
  return variant.contoursEarly
    ? { minor: [9, 11], index: [8, 10] }
    : { minor: [10, 12], index: [9, 11] }
}

/**
 * The type treatment one variant carries - field's sunlight brief against the
 * baseline everything else uses (MAP_STYLE_SPEC.md's "field extras": labels
 * one size up, halos 1.8). One builder for the style build and the live
 * repaint, like the palette table and for the same reason.
 */
export function sheetTypeSizes(variant: SheetVariant): {
  contourLabelSize: number
  peakSizeExpression: unknown[]
  contourLabelHalo: number
  peakHalo: number
  waterLabelHalo: number
  placeHalo: number
} {
  return variant.boldType
    ? {
        contourLabelSize: 11,
        peakSizeExpression: ['interpolate', ['linear'], ['zoom'], 10, 12, 14, 14],
        contourLabelHalo: 1.8,
        peakHalo: 1.8,
        waterLabelHalo: 1.8,
        placeHalo: 1.8,
      }
    : {
        contourLabelSize: 10,
        peakSizeExpression: ['interpolate', ['linear'], ['zoom'], 10, 10, 14, 13],
        contourLabelHalo: 1.4,
        peakHalo: 1.6,
        waterLabelHalo: 1.4,
        placeHalo: 1.6,
      }
}

export interface LiveTopoOptions {
  /**
   * DEM and contour tile URLs, or `undefined` when they could not be built.
   *
   * Optional because elevation is one INPUT to this sheet rather than the
   * sheet itself: of the layers below, exactly one reads the DEM (the
   * hillshade) and three read the contour tiles. The other sixteen are OSM
   * vector - landcover, parks, water, the path and road network, summits and
   * place names - and none of them needs an elevation model to draw.
   *
   * So a DEM that will not build costs relief and contour lines, and leaves
   * the rest of the sheet alone. That is what terrain.ts promises ("every
   * failure path here is a missing layer, never a broken map") and until this
   * was optional the promise was not kept: style.ts folded "asked for the live
   * sheet" and "got terrain URLs" into one boolean, so a missing DEM dropped
   * every layer of the sheet and left bare paper.
   */
  terrain?: TerrainUrls
  units: ContourUnits
  /**
   * Which palette the sheet is drawn in - see sheetPalette().
   *
   * All optional, defaulting to field/day, so that every caller who does not
   * care about appearance, tests included, keeps building the sheet it always
   * built. Only the shell resolves a theme (lib/useTheme.ts), and only
   * because it is the one place that knows the hiker's preference.
   *
   * The style is built with the right palette AND the map can be repainted in
   * place afterwards (attachSheetAppearance), which is not redundant: the
   * first is so a cold start under a dark appearance never paints a white
   * frame, the second is so a hiker changing a preference does not cost the
   * WebGL context, its GPS watcher and every tile in flight.
   */
  theme?: ResolvedTheme
  themeChoice?: Theme
  mapStyle?: MapStyle
  redLight?: boolean
}

/**
 * The two text-fields that bake the unit choice into the style, extracted so
 * the live unit switch can re-point them with `setLayoutProperty` - see
 * attachElevationLabelUnits. One home each: an expression built here and
 * rebuilt slightly differently there would show its drift as a wrong-unit
 * elevation on the map.
 */

/** An index contour's label: the tile's value plus the unit's mark. The tiles
 *  themselves are already per-unit (registerTerrain), so the value needs no
 *  conversion - only the suffix says which system the number is in. */
export function contourLabelTextField(units: ContourUnits): unknown {
  return [
    'concat',
    ['to-string', ['get', CONTOUR_ELEVATION_KEY]],
    units === 'imperial' ? "'" : 'm',
  ]
}

/** A peak's label: name over surveyed height. OpenFreeMap publishes the
 *  height in both units as separate properties, so the unit choice is which
 *  property to read, not a conversion. */
export function peakLabelTextField(units: ContourUnits): unknown {
  const elevationKey = units === 'imperial' ? 'ele_ft' : 'ele'
  // `concat` errors on a null argument and drops the feature, so the
  // name is coalesced rather than read straight: an unnamed summit with
  // a surveyed height is still worth putting on the map, and losing it
  // to an expression error would be a silent hole in exactly the layer
  // this style added terrain for.
  return [
    'case',
    ['has', elevationKey],
    [
      'concat',
      ['coalesce', ['get', 'name'], ''],
      '\n',
      ['to-string', ['get', elevationKey]],
      units === 'imperial' ? "'" : 'm',
    ],
    ['coalesce', ['get', 'name'], ''],
  ]
}

/**
 * The elevation half of the sheet's sources, or nothing when no DEM was built.
 *
 * Split out rather than spread inline so the two `raster-dem`/`vector` literals
 * keep their own declared return type. Widened into a conditional spread they
 * lose it - `type: 'raster-dem'` infers as `string`, which is not assignable to
 * SourceSpecification, and tsc fails at the call site rather than here.
 */
function terrainSources(terrain: TerrainUrls): Record<string, SourceSpecification> {
  return {
    [DEM_SOURCE_ID]: {
      type: 'raster-dem',
      tiles: [terrain.demUrl],
      encoding: 'terrarium',
      tileSize: 256,
      maxzoom: DEM_MAX_ZOOM,
      attribution: ELEVATION_ATTRIBUTION,
    },
    [CONTOUR_SOURCE_ID]: {
      type: 'vector',
      tiles: [terrain.contourTilesUrl],
      maxzoom: CONTOUR_MAX_ZOOM,
      attribution: ELEVATION_ATTRIBUTION,
    },
  }
}

export function liveTopoSources({
  terrain,
}: LiveTopoOptions): Record<string, SourceSpecification> {
  return {
    // Unconditional, and the reason `terrain` is optional at all: this one
    // needs a URL and a tile schema - none of the worker/blob-URL machinery
    // a DEM needs and therefore none of the ways that machinery can fail.
    // (basemap.ts's protocol registration is machinery, but of the same
    // idempotent addProtocol kind as the pmtiles scheme - MapView registers
    // it before any style is applied.)
    //
    // A `tiles` template through the basemap:// scheme rather than the
    // OpenFreeMap TileJSON URL, and the difference is the offline story
    // (#189): a TileJSON is a network round trip before the first tile can
    // even be asked for, so a style built around it needs signal to learn
    // where its own tiles live. The template needs nothing, and each tile
    // request is then resolved locally-first by basemap.ts. The style stays
    // a pure function - which archive answers is decided per tile at fetch
    // time, never observed here.
    [OSM_SOURCE_ID]: {
      type: 'vector',
      tiles: [BASEMAP_TILES_URL],
      maxzoom: BASEMAP_MAX_ZOOM,
      attribution: LIVE_TOPO_ATTRIBUTION,
    },
    ...(terrain === undefined ? {} : terrainSources(terrain)),
  }
}

/**
 * The layer stack, bottom to top.
 *
 * The order is the cartography. Ground cover goes down first, then relief
 * shading over it so hillsides darken the green rather than sitting beside it,
 * then water flat on top so lakes read as level surfaces rather than shaded
 * ones, then contours over everything areal, then the linear network, then
 * type last so nothing is drawn through a label.
 *
 * There is deliberately no land-coloured fill at the bottom. The style's paper
 * backdrop already is the sheet, exactly as on a printed quad where open
 * ground is simply unprinted paper - and adding a source-free fill here would
 * paint over that paper (style.ts's BACKDROP_LAYER_ID) even when no tile had
 * loaded, turning "nothing arrived" back into a confident picture of empty
 * ground.
 *
 * With no `terrain`, the layers reading the DEM and the contour tiles are
 * dropped and the rest of the stack is returned untouched. That is a filter at
 * the end rather than a conditional at each of the four sites on purpose: the
 * order above IS the cartography, a filter cannot reorder it, and it asks the
 * same question the style validator asks - does this layer's source exist -
 * so a fifth elevation layer added later is covered without joining a list
 * someone has to remember to update. A layer left pointing at a source that
 * was never added is not a missing contour; it is an invalid style.
 */
export function liveTopoLayers({
  terrain,
  units,
  theme = 'light',
  themeChoice = 'auto',
  mapStyle = 'field',
  redLight = false,
}: LiveTopoOptions): LayerSpecification[] {
  const variant = sheetVariant({ theme, themeChoice, mapStyle, redLight })
  const palette = variant.palette
  const fade = contourFadeZooms(variant)
  const type = sheetTypeSizes(variant)

  const layers: LayerSpecification[] = [
    {
      id: LIVE_TOPO_LAYER_IDS.wood,
      type: 'fill',
      source: OSM_SOURCE_ID,
      'source-layer': 'landcover',
      filter: isClass('wood') as never,
      paint: sheetColours(LIVE_TOPO_LAYER_IDS.wood, palette),
    },
    {
      id: LIVE_TOPO_LAYER_IDS.scrub,
      type: 'fill',
      source: OSM_SOURCE_ID,
      'source-layer': 'landcover',
      filter: isClass('grass') as never,
      paint: sheetColours(LIVE_TOPO_LAYER_IDS.scrub, palette),
    },
    {
      id: LIVE_TOPO_LAYER_IDS.wetland,
      type: 'fill',
      source: OSM_SOURCE_ID,
      'source-layer': 'landcover',
      filter: isClass('wetland') as never,
      paint: sheetColours(LIVE_TOPO_LAYER_IDS.wetland, palette),
    },
    {
      id: LIVE_TOPO_LAYER_IDS.rock,
      type: 'fill',
      source: OSM_SOURCE_ID,
      'source-layer': 'landcover',
      filter: isClass('rock', 'sand') as never,
      paint: sheetColours(LIVE_TOPO_LAYER_IDS.rock, palette),
    },
    // Protected land is context a hiker plans with (where camping is allowed,
    // whose rules apply), and the wash is the WHOLE treatment: an area, drawn
    // as an area. It used to get an outline too, and the outline was the bug
    // (#347) - along the corridor the protected land is a narrow sliver whose
    // edges run beside the trail for miles, and a broken line wandering
    // through woodland gets read as a walkable one whatever its rhythm. So
    // every palette's tint is calibrated to carry the fact alone instead:
    // mixed far enough from its wood fill to read over the woodland most
    // protected land here is, and still a ground that sits behind every line
    // the sheet draws. The test file holds that over-woodland margin on all
    // three palettes, so a palette tweak cannot quietly fade the fact back
    // out of the map.
    {
      id: LIVE_TOPO_LAYER_IDS.parkFill,
      type: 'fill',
      source: OSM_SOURCE_ID,
      'source-layer': 'park',
      paint: {
        ...sheetColours(LIVE_TOPO_LAYER_IDS.parkFill, palette),
        'fill-opacity': 0.55,
      },
    },
    // Relief shading, and the sheet's only terrain channel until the contours
    // arrive - which is why its strength follows the zoom rather than sitting
    // at one number. See HILLSHADE_EXAGGERATION_EXPRESSION.
    {
      id: LIVE_TOPO_LAYER_IDS.hillshade,
      type: 'hillshade',
      source: DEM_SOURCE_ID,
      paint: {
        'hillshade-exaggeration': hillshadeExaggerationExpression(
          variant.hillshadeBase,
        ) as never,
        ...sheetColours(LIVE_TOPO_LAYER_IDS.hillshade, palette),
      },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.water,
      type: 'fill',
      source: OSM_SOURCE_ID,
      'source-layer': 'water',
      // Swimming pools are in this layer too and are not a water source.
      filter: ['!=', ['get', 'class'], 'swimming_pool'] as never,
      paint: sheetColours(LIVE_TOPO_LAYER_IDS.water, palette),
    },
    // Streams matter more to a hiker than lakes do - they are the refill
    // points - so they are drawn wide enough to follow, and intermittent ones
    // are dashed rather than hidden, because "sometimes dry" is information,
    // not an absence.
    {
      id: LIVE_TOPO_LAYER_IDS.waterway,
      type: 'line',
      source: OSM_SOURCE_ID,
      'source-layer': 'waterway',
      paint: {
        ...sheetColours(LIVE_TOPO_LAYER_IDS.waterway, palette),
        'line-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          9,
          ['case', isClass('river') as never, 1, 0.4],
          14,
          ['case', isClass('river') as never, 2.6, 1.2],
        ] as never,
        'line-opacity': ['case', ['==', ['get', 'intermittent'], 1], 0.6, 1] as never,
      },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.contour,
      type: 'line',
      source: CONTOUR_SOURCE_ID,
      'source-layer': CONTOUR_LAYER,
      filter: ['==', ['get', CONTOUR_LEVEL_KEY], 0] as never,
      paint: {
        ...sheetColours(LIVE_TOPO_LAYER_IDS.contour, palette),
        'line-width': 0.6,
        // Faded out where they would otherwise mat together into a solid
        // hillside, rather than switched off at a hard zoom threshold. The
        // window is the variant's (contourFadeZooms) - ridgeline pulls it a
        // zoom earlier.
        'line-opacity': [
          'interpolate',
          ['linear'],
          ['zoom'],
          fade.minor[0],
          0,
          fade.minor[1],
          0.7,
        ] as never,
      },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.contourIndex,
      type: 'line',
      source: CONTOUR_SOURCE_ID,
      'source-layer': CONTOUR_LAYER,
      filter: ['>', ['get', CONTOUR_LEVEL_KEY], 0] as never,
      paint: {
        ...sheetColours(LIVE_TOPO_LAYER_IDS.contourIndex, palette),
        'line-width': 1.2,
        'line-opacity': [
          'interpolate',
          ['linear'],
          ['zoom'],
          fade.index[0],
          0,
          fade.index[1],
          0.9,
        ] as never,
      },
    },
    // Only index lines are labelled. Labelling every contour is what makes a
    // digital topo map unreadable - the number belongs on the line you count
    // from, not on the ones you count.
    {
      id: LIVE_TOPO_LAYER_IDS.contourLabel,
      type: 'symbol',
      source: CONTOUR_SOURCE_ID,
      'source-layer': CONTOUR_LAYER,
      filter: ['>', ['get', CONTOUR_LEVEL_KEY], 0] as never,
      minzoom: 12,
      layout: {
        'symbol-placement': 'line',
        'text-field': contourLabelTextField(units) as never,
        'text-font': FONT,
        // Size and halo are the variant's (sheetTypeSizes): field's sunlight
        // brief takes both up a step, the other sheets keep the baseline.
        'text-size': type.contourLabelSize,
        'text-max-angle': 25,
        'text-padding': 6,
        // Set into the line the way a printed contour label is, rather than
        // floating beside it.
        'symbol-spacing': 320,
      },
      paint: {
        ...sheetColours(LIVE_TOPO_LAYER_IDS.contourLabel, palette),
        'text-halo-width': type.contourLabelHalo,
      },
    },
    // THE GROUND NETWORK IS DRAWN IN STROKES, NOT RIBBONS (#1074).
    //
    // Every road here used to be a casing plus a fill - a filled ribbon, the
    // way a road basemap draws one - and the ribbon grew with zoom until it
    // reached 7.00px at z16, against the 6.50px the A.T. occupies with its own
    // casing. The road was, measurably, the widest line on a map whose whole
    // subject is the trail. From z13 up it also out-drew a side trail's entire
    // 4.50px footprint.
    //
    // So the casing is gone and each of these is ONE stroke, capped below
    // style.ts's SIDE_TRAIL_WIDTH - the narrowest trail line on the sheet -
    // at every zoom. `roadsStayUnderTheTrail` in the tests is that ceiling
    // written down, because the old widths were nobody's decision: they were a
    // road-basemap default that no test disagreed with.
    //
    // Losing the ribbon costs the untitled "this is a paved highway" cue, and
    // road class is now carried by width alone (1.8 / 1.3 / 1.1px). That was
    // the accepted trade; the alternative that kept the ribbon (a plain width
    // cut) left the roads no easier to find on the sheets that are already
    // hardest to read.
    {
      id: LIVE_TOPO_LAYER_IDS.roadMinor,
      type: 'line',
      source: OSM_SOURCE_ID,
      'source-layer': 'transportation',
      filter: isClass('minor', 'service') as never,
      minzoom: 12,
      paint: {
        ...sheetColours(LIVE_TOPO_LAYER_IDS.roadMinor, palette),
        'line-width': ['interpolate', ['linear'], ['zoom'], 12, 0.5, 16, 1.3] as never,
      },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.roadMajor,
      type: 'line',
      source: OSM_SOURCE_ID,
      'source-layer': 'transportation',
      filter: isClass('motorway', 'trunk', 'primary', 'secondary', 'tertiary') as never,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        ...sheetColours(LIVE_TOPO_LAYER_IDS.roadMajor, palette),
        'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.6, 16, 1.8] as never,
      },
    },
    // Tracks are how you reach most trailheads, and forest roads are a real
    // bail-out option, so they are drawn at their own weight rather than
    // lumped in with service roads.
    {
      id: LIVE_TOPO_LAYER_IDS.track,
      type: 'line',
      source: OSM_SOURCE_ID,
      'source-layer': 'transportation',
      filter: isClass('track') as never,
      minzoom: 11,
      paint: {
        ...sheetColours(LIVE_TOPO_LAYER_IDS.track, palette),
        'line-width': ['interpolate', ['linear'], ['zoom'], 11, 0.4, 16, 1.1] as never,
        'line-dasharray': [6, 3],
      },
    },
    // OSM paths, NOT the A.T. The trail comes from ATC data and is drawn by
    // style.ts in its blaze colours on top of this; these are the other
    // footpaths around it, which are exactly what the downloaded raster cannot
    // show and what a hiker looking for a side trail or a shortcut wants.
    // Dotted and quiet so they never read as a blazed route.
    //
    // "Quiet" is now true of the ink as well as the rhythm. Measured against
    // each sheet's own wood fill, `path` used to be the 2nd highest-contrast
    // of the eight ground inks on eight of the ten sheets (1st on night_hike,
    // 3rd on field/night) - louder than the minor contour lines on all ten. A
    // 1px dotted line inked at near-label darkness is loud whatever its width,
    // which is why this one was fixed with colour while the roads above were
    // fixed with weight: they were opposite defects (#1074).
    {
      id: LIVE_TOPO_LAYER_IDS.path,
      type: 'line',
      source: OSM_SOURCE_ID,
      'source-layer': 'transportation',
      filter: isClass('path') as never,
      minzoom: 12,
      paint: {
        ...sheetColours(LIVE_TOPO_LAYER_IDS.path, palette),
        'line-width': 0.8,
        'line-dasharray': [2, 2],
        'line-opacity': 0.75,
      },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.boundary,
      type: 'line',
      source: OSM_SOURCE_ID,
      'source-layer': 'boundary',
      filter: ['<=', ['get', 'admin_level'], 4] as never,
      paint: {
        ...sheetColours(LIVE_TOPO_LAYER_IDS.boundary, palette),
        'line-width': 1,
        'line-dasharray': [3, 2, 1, 2],
        'line-opacity': 0.7,
      },
    },
    // Named summits with their height. This is the single most hiking-specific
    // thing OSM carries that a road basemap throws away, and on a ridge it is
    // how you confirm which bump you are standing on.
    {
      id: LIVE_TOPO_LAYER_IDS.peak,
      type: 'symbol',
      source: OSM_SOURCE_ID,
      'source-layer': 'mountain_peak',
      filter: isClass('peak', 'volcano') as never,
      minzoom: 10,
      layout: {
        'text-field': peakLabelTextField(units) as never,
        'text-font': FONT,
        // The ramp is the variant's (sheetTypeSizes): field carries summits
        // a size up - they are the most hiking-specific type on the sheet -
        // and the other sheets keep the launch weights.
        'text-size': type.peakSizeExpression as never,
        'text-anchor': 'top',
        'text-offset': [0, 0.4],
        'text-max-width': 8,
      },
      paint: {
        ...sheetColours(LIVE_TOPO_LAYER_IDS.peak, palette),
        'text-halo-width': type.peakHalo,
      },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.waterLabel,
      type: 'symbol',
      source: OSM_SOURCE_ID,
      'source-layer': 'water_name',
      minzoom: 11,
      layout: {
        'text-field': ['get', 'name'] as never,
        'text-font': FONT,
        'text-size': 11,
        'text-max-width': 8,
      },
      paint: {
        ...sheetColours(LIVE_TOPO_LAYER_IDS.waterLabel, palette),
        'text-halo-width': type.waterLabelHalo,
      },
    },
    // Towns only, and only the ones big enough to matter for resupply - a
    // hamlet label every half mile is noise on a trail map. The same rule
    // continues up the ladder by zoom (PLACE_FILTER): zoomed out far enough,
    // even a town is a hamlet.
    {
      id: LIVE_TOPO_LAYER_IDS.place,
      type: 'symbol',
      source: OSM_SOURCE_ID,
      'source-layer': 'place',
      filter: PLACE_FILTER as never,
      layout: {
        'text-field': ['get', 'name'] as never,
        'text-font': FONT,
        // The low stop matters most: at the corridor-wide view a city is an
        // orientation anchor, not a destination, and it is set smaller there
        // so the type never outweighs the line the view is about.
        'text-size': [
          'interpolate',
          ['linear'],
          ['zoom'],
          5,
          ['case', isClass('city') as never, 11, 9],
          8,
          ['case', isClass('city') as never, 13, 10],
          14,
          ['case', isClass('city') as never, 18, 13],
        ] as never,
        'text-max-width': 8,
        'symbol-sort-key': PLACE_SORT_KEY_EXPRESSION as unknown as number,
      },
      paint: {
        ...sheetColours(LIVE_TOPO_LAYER_IDS.place, palette),
        'text-halo-width': type.placeHalo,
      },
    },
  ]

  if (terrain !== undefined) return layers

  // Keyed off the source each layer declares rather than off a list of layer
  // ids, so this cannot drift from terrainSources() above: whatever that
  // function does not add, this removes. A `background` layer has no `source`
  // at all, hence the `in` check - there is none in this stack today, and a
  // filter that would silently drop one if there were is the kind of thing
  // that only shows up much later.
  return layers.filter(
    (layer) =>
      !('source' in layer) ||
      (layer.source !== DEM_SOURCE_ID && layer.source !== CONTOUR_SOURCE_ID),
  )
}

/**
 * The elevation labels' half of the live unit switch.
 *
 * attachContourUnits (contours.ts) re-points the contour SOURCE at the other
 * unit's tiles, but the two places the unit choice is baked into the style as
 * layout - the contour label's suffix and the peak layer's choice of `ele_ft`
 * vs `ele` - do not move with it. Left alone they produce the worst kind of
 * wrong map: metric tiles under imperial punctuation, a 500 m index contour
 * reading 500'. This re-points both text-fields in place, with the same
 * expressions the style was built from, for the same reason the source
 * retune exists at all: `units` is deliberately kept out of the map-building
 * effect so a settings change never tears the map down under a hiker.
 *
 * Waits on EITHER label layer, because the two no longer arrive together. The
 * contour label comes with the DEM and the peak label comes with the OSM
 * sheet, so a live style built without terrain has summits and no contours -
 * and a probe that waited on the contour label alone would never fire there,
 * leaving every summit reading `ele_ft` after a switch to metric. A wrong
 * number on the map is the exact failure this function exists to prevent, so
 * the probe asks for the weaker condition and each write is guarded on its
 * own layer. On the offline background neither exists and there is nothing to
 * retune - the wait simply ends at detach, exactly as attachContourUnits
 * treats its absent source.
 */
export function attachElevationLabelUnits(
  map: MapLibreMap,
  units: ContourUnits,
): () => void {
  return whenStyleReady(
    map,
    () =>
      map.getLayer(LIVE_TOPO_LAYER_IDS.contourLabel) !== undefined ||
      map.getLayer(LIVE_TOPO_LAYER_IDS.peak) !== undefined,
    () => {
      // Both guarded, since the probe now proves only that ONE of them is
      // there. Neither is load-bearing for the other.
      if (map.getLayer(LIVE_TOPO_LAYER_IDS.contourLabel) !== undefined) {
        map.setLayoutProperty(
          LIVE_TOPO_LAYER_IDS.contourLabel,
          'text-field',
          contourLabelTextField(units) as never,
        )
      }
      if (map.getLayer(LIVE_TOPO_LAYER_IDS.peak) !== undefined) {
        map.setLayoutProperty(
          LIVE_TOPO_LAYER_IDS.peak,
          'text-field',
          peakLabelTextField(units) as never,
        )
      }
    },
    'Elevation label units',
  )
}

/**
 * The sheet's half of a live appearance change - theme, map style, and red
 * light alike, since all of them resolve to one variant (sheetVariant).
 *
 * Repaints every colour in SHEET_COLOURS onto a map that is already built,
 * rather than rebuilding the style - and then the variant's tuning: relief
 * weight, contour fade windows, and the type treatment, each with the same
 * builder the style was built from so the two cannot drift. Not rebuilding is
 * not an optimisation, it is the same rule MapView.tsx keeps for the scale
 * bar's units and contours.ts keeps for the contour interval: a preference
 * change must not cost a WebGL context. Swapping the style out drops the
 * context, and with it the POI source pushed in from IndexedDB, every tile in
 * flight from the archive, and the camera - so a hiker who taps "Dark" while
 * walking would watch the map they were reading disappear and rebuild.
 *
 * Every write, colour and tuning alike, targets ALL managed properties for
 * the target variant rather than only the ones that differ: `setPaintProperty`
 * is sticky, so writing the full set is what makes leaving ridgeline for
 * quiet_pine an actual restore of the 0.35 relief and the later contours.
 *
 * Waits on the wood layer and not on any of the others, deliberately. It is
 * the first layer this module declares and it reads the plain OSM source, so
 * it is present whenever the live sheet is present at all - including on a
 * style built without terrain, where the four DEM/contour layers were filtered
 * out. Every write below is still guarded on its own layer: the probe proves
 * the style is parsed and takes writes, not that any particular layer survived
 * that filter.
 *
 * On the downloaded background none of these layers exists, and there is
 * nothing here to repaint - the wait simply ends at detach, exactly as
 * attachContourUnits treats its absent source. The archive's own dimming and
 * the backdrop are not this function's job; map/style.ts owns those, and its
 * attachMapAppearance is what calls this - the parts of the canvas that are drawn
 * whatever the background is belong to the file that declares them.
 */
export function attachSheetAppearance(
  map: MapLibreMap,
  appearance: SheetAppearance,
): () => void {
  const variant = sheetVariant(appearance)
  const palette = variant.palette
  const fade = contourFadeZooms(variant)
  const type = sheetTypeSizes(variant)

  const paint = (layer: string, property: string, value: unknown) => {
    if (map.getLayer(layer) === undefined) return
    map.setPaintProperty(layer, property as never, value as never)
  }
  const layout = (layer: string, property: string, value: unknown) => {
    if (map.getLayer(layer) === undefined) return
    map.setLayoutProperty(layer, property as never, value as never)
  }

  return whenStyleReady(
    map,
    () => map.getLayer(LIVE_TOPO_LAYER_IDS.wood) !== undefined,
    () => {
      for (const [layer, property, colour] of SHEET_COLOURS) {
        paint(layer, property, palette[colour])
      }

      paint(
        LIVE_TOPO_LAYER_IDS.hillshade,
        'hillshade-exaggeration',
        hillshadeExaggerationExpression(variant.hillshadeBase),
      )
      paint(LIVE_TOPO_LAYER_IDS.contour, 'line-opacity', [
        'interpolate',
        ['linear'],
        ['zoom'],
        fade.minor[0],
        0,
        fade.minor[1],
        0.7,
      ])
      paint(LIVE_TOPO_LAYER_IDS.contourIndex, 'line-opacity', [
        'interpolate',
        ['linear'],
        ['zoom'],
        fade.index[0],
        0,
        fade.index[1],
        0.9,
      ])

      layout(LIVE_TOPO_LAYER_IDS.contourLabel, 'text-size', type.contourLabelSize)
      layout(LIVE_TOPO_LAYER_IDS.peak, 'text-size', type.peakSizeExpression)
      paint(LIVE_TOPO_LAYER_IDS.contourLabel, 'text-halo-width', type.contourLabelHalo)
      paint(LIVE_TOPO_LAYER_IDS.peak, 'text-halo-width', type.peakHalo)
      paint(LIVE_TOPO_LAYER_IDS.waterLabel, 'text-halo-width', type.waterLabelHalo)
      paint(LIVE_TOPO_LAYER_IDS.place, 'text-halo-width', type.placeHalo)
    },
    'Sheet appearance',
  )
}
