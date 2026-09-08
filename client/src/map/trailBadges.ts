// The through-route badge: the trail's registry mark plus its name, drawn
// once per line in view (#1283).
//
// WHAT IT ANSWERS. The opening camera drew every published trail as a solid
// thread in its blaze hue and named none of them - map/trailLabels.ts's
// floor was the pins' z9, and its filter deliberately never names a
// through-route, because the header already does. That is right for a map
// whose one line the header names, and wrong the moment the map holds a
// country's worth of lines: the A.T. is then one thread among hundreds and
// nothing on the sheet says which. The maintainer's design handoff
// (2026-09-08, chosen from six drawn directions) gives a through-route ONE
// badge in view - mark, plate, name - and gives everything else a name set
// along its own line. A trail carries a badge or an along-line name, never
// both; TRAIL_LABEL_FILTER over there is the other half of that sentence.
//
// WHY THE BADGE IS NOT `symbol-placement: line-center` ON THE TRAIL LAYER.
// That is the layer specification the handoff writes, and it does not do
// what the handoff wants it for: MapLibre places a line-center symbol at the
// centre of each feature IN EACH TILE (symbol_layout.ts, "No clipping,
// multiple lines per feature"), and a GeoJSON source is tiled internally.
// The A.T. across a z12 screen is three or four tile-clipped pieces, so it
// would wear three or four badges - the repetition down the corridor that
// the along-line layer already refuses for this very trail. So the badge is
// a symbol on a POINT SOURCE, and map/trailsInView.ts computes the points:
// one per named through-route on screen, on a vertex of its longest visible
// piece, recomputed as the camera settles. One badge per line, because the
// data says so rather than because the placer happened to.
//
// WHAT THE DATA CANNOT DO YET, written down the way map/labelLadder.ts
// writes down its junction rung. `trail_id` is not published on a trail
// feature - features/SOURCE_REGISTRY.md's field map is what would introduce
// it - so the mark is keyed off `source` instead: `centerline` is the A.T.
// and takes the ATC mark; every other source falls through to the OurHike
// blaze chip in the trail's own blaze hue. When a `trail_id` arrives,
// BADGE_MARK_BY_SOURCE becomes a lookup against the registry and nothing
// else here changes.
//
// The pill. MapLibre cannot draw a rounded rectangle behind an icon-and-text
// pair from a style spec alone, and the handoff's preferred answer is the one
// built here: one stretchable plate image (a 9-slice pill) fitted to the text
// with `icon-text-fit`, and the mark carried INSIDE the text as an image
// section of a `format` expression - so mark, plate and name are one symbol,
// one collision box, one placement decision. The alternative (compositing a
// raster per trail) would re-rasterise the name whenever the sheet's ink
// changed; here the ink is a paint property and the plate is two images, one
// per sheet family, swapped in attachMapAppearance like every other colour.

import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { BLAZE_PALETTE_MEMBERS, NEUTRAL_BLAZE_COLOR, blazePaintColor } from '../lib/blaze'
import { TRAILS } from '../lib/trails'
import { LABEL_TIER } from './labelLadder'
import { sheetVariant, type SheetAppearance } from './liveTopo'
import { nearbyTrailOpacityExpression } from './nearbyTrails'
import { parseHex, POI_PIN_PIXEL_RATIO, type PoiIconImage } from './poiIcons'
import { whenStyleReady } from './styleReady'
import { TRAIL_LABEL_MIN_ZOOM } from './trailLabels'

export const TRAIL_BADGE_SOURCE_ID = 'trail-badges'
export const TRAIL_BADGE_LAYER_ID = 'trail-badge'

/**
 * Who earns a badge: the through-routes. map/style.ts's PRIMARY_TRAIL_SOURCES,
 * restated for the reason map/trailLabels.ts restates THROUGH_ROUTE_SOURCES -
 * style.ts imports this module, so importing it back is a cycle.
 * trailBadges.test.ts imports both and fails if they drift.
 *
 * A badge is a claim that the line is a destination, so exactly the tier the
 * map already keys width and sort order off wears one. That is what keeps the
 * badge count roughly constant as networks are added: a state park's forty
 * trails add forty dotted lines and forty along-line names, and no badges.
 */
export const BADGE_SOURCES: readonly string[] = ['centerline']

/**
 * Which registry mark a source wears - the gap named in the header. Keyed
 * off `source` because nothing publishes a `trail_id`; `centerline` is ATC's
 * centerline feed, which is the A.T. (lib/trails.ts). A source with no entry
 * takes the blaze chip.
 */
export const BADGE_MARK_BY_SOURCE: Readonly<Record<string, string>> = {
  centerline: TRAILS.AT.id,
}

/** The mark's image id, or null where the source wears the blaze chip. */
export function trailMarkImageId(source: string | null | undefined): string | null {
  const trail =
    source === null || source === undefined ? undefined : BADGE_MARK_BY_SOURCE[source]
  return trail === undefined ? null : `trail-mark-${trail}`
}

/** The chip a blaze falls through to. Every palette member has one, derived
 *  from BLAZE_PALETTE_MEMBERS so lib/blaze.ts's closed-palette rule (#782)
 *  reaches the badges without anybody listing them here; the three neutral
 *  values share one grey chip, as they share one line colour. */
export function blazeChipImageId(blazeColor: string | null | undefined): string {
  if (
    blazeColor !== null &&
    blazeColor !== undefined &&
    BLAZE_PALETTE_MEMBERS.includes(blazeColor)
  ) {
    return `blaze-chip-${blazeColor}`
  }
  return 'blaze-chip-neutral'
}

/*
 * THE GEOMETRY - the only invented numbers in the handoff, listed there under
 * "Design tokens". Every colour is an existing token; these sizes are the
 * badge's own.
 */

/** Mark and chip side, CSS px. */
export const TRAIL_BADGE_MARK_SIZE = 18
/** The chip's corner radius and the blaze bar's width, as fractions of the
 *  side - lifted from design-system/assets/logo-icon.svg, the app icon,
 *  which is where the chip's geometry comes from. */
export const BLAZE_CHIP_CORNER = 0.21
export const BLAZE_CHIP_BAR_WIDTH = 0.21
export const BLAZE_CHIP_BAR_HEIGHT = 0.62
/** Between the mark and the name. Baked into the mark image as transparent
 *  columns rather than typed as spaces in the text, so it is the same width
 *  in every font and at every letter-spacing. */
export const TRAIL_BADGE_MARK_GAP = 10
/** The plate is the mark plus four px of paper above and below it. */
export const TRAIL_BADGE_PLATE_HEIGHT = TRAIL_BADGE_MARK_SIZE + 8
export const TRAIL_BADGE_PLATE_BORDER = 1
/** [top, right, bottom, left]: how far the plate's CONTENT extends past the
 *  text block. The border sits outside the content, so the visible paper is
 *  one px more on every side - 4 left of the mark, 10 right of the name, and
 *  a plate exactly TRAIL_BADGE_PLATE_HEIGHT tall. */
export const TRAIL_BADGE_TEXT_FIT_PADDING: readonly [number, number, number, number] = [
  3, 9, 3, 3,
]
export const TRAIL_BADGE_TEXT_SIZE = 12

/**
 * A White-blazed trail's chip takes `--stone-700` as its ground, or the
 * white blaze bar disappears into it. The one place a blaze is not painted
 * in its own hex, and it is the chip's ground rather than the bar - the bar
 * IS the white blaze.
 */
export const WHITE_CHIP_GROUND = '#5a5346'
/** `--paper-0`: the blaze bar on every chip. */
export const BLAZE_CHIP_BAR_COLOR = '#fffdf7'

/**
 * The plate's two faces - one per sheet family - and the ink on each.
 *
 * Day: `--paper-0` at 95% with a border between `--border-1` and
 * `--border-2`, text `--fg-1`; the handoff's tokens, matching the phone's
 * own plate over the map. Night: the dark theme's raised surface (`--ink-850`)
 * at the same 95%, its `--border-1`, and `--fg-1` as the dark theme resolves
 * it (`--bone-100`). A paper pill on a night sheet would be the brightest
 * thing on the screen, which is the one property a badge must not have.
 */
export const TRAIL_BADGE_PLATE_DAY = {
  id: 'trail-badge-plate-day',
  fill: '#fffdf7',
  fillAlpha: 0.95,
  border: '#d8d1bd',
  text: '#2b2620',
} as const
export const TRAIL_BADGE_PLATE_NIGHT = {
  id: 'trail-badge-plate-night',
  fill: '#1c1a15',
  fillAlpha: 0.95,
  border: '#332f26',
  text: '#ece7db',
} as const

function plateFor(appearance: SheetAppearance) {
  return sheetVariant(appearance).dark ? TRAIL_BADGE_PLATE_NIGHT : TRAIL_BADGE_PLATE_DAY
}

/** Which plate image the layer draws under an appearance. */
export function badgePlateImageId(appearance: SheetAppearance): string {
  return plateFor(appearance).id
}

/** The name's ink under an appearance. */
export function badgeTextColor(appearance: SheetAppearance): string {
  return plateFor(appearance).text
}

/** The halo behind the name: the plate's own paper, so it disappears into
 *  the plate and only ever shows where a glyph would otherwise touch the
 *  border. */
export function badgeHaloColor(appearance: SheetAppearance): string {
  return plateFor(appearance).fill
}

/*
 * THE RASTERISER. A rounded rectangle is all either image is, so this is the
 * smallest thing that draws one: a predicate per shape, sampled 3x3 per
 * pixel and averaged in premultiplied alpha - the same standard as
 * map/poiIcons.ts and map/atcNoticeMark.ts, so a chip beside a pin reads as
 * the same weight of ink.
 */

const SUPERSAMPLE = 3

type Rgba = readonly [number, number, number, number]

/** Is (x, y) inside the rounded rectangle at (x0, y0) of size w x h with
 *  corner radius r? The nearest point of the inset rectangle is at most r
 *  away exactly when the point is inside. */
function insideRoundedRect(
  x: number,
  y: number,
  x0: number,
  y0: number,
  w: number,
  h: number,
  r: number,
): boolean {
  const radius = Math.min(r, w / 2, h / 2)
  const cx = Math.min(Math.max(x, x0 + radius), x0 + w - radius)
  const cy = Math.min(Math.max(y, y0 + radius), y0 + h - radius)
  const dx = x - cx
  const dy = y - cy
  return dx * dx + dy * dy <= radius * radius
}

function rasterise(
  width: number,
  height: number,
  colorAt: (x: number, y: number) => Rgba | null,
): PoiIconImage {
  const data = new Uint8ClampedArray(width * height * 4)
  const samples = SUPERSAMPLE * SUPERSAMPLE
  for (let py = 0; py < height; py += 1) {
    for (let px = 0; px < width; px += 1) {
      let r = 0
      let g = 0
      let b = 0
      let a = 0
      for (let sy = 0; sy < SUPERSAMPLE; sy += 1) {
        for (let sx = 0; sx < SUPERSAMPLE; sx += 1) {
          const x = px + (sx + 0.5) / SUPERSAMPLE
          const y = py + (sy + 0.5) / SUPERSAMPLE
          const sample = colorAt(x, y)
          if (sample === null) continue
          // Premultiplied, so the transparent samples outside a shape carry
          // no colour of their own into the edge - see buildPinImage.
          r += sample[0] * sample[3]
          g += sample[1] * sample[3]
          b += sample[2] * sample[3]
          a += sample[3]
        }
      }
      const offset = (py * width + px) * 4
      if (a > 0) {
        data[offset] = Math.round(r / a)
        data[offset + 1] = Math.round(g / a)
        data[offset + 2] = Math.round(b / a)
        data[offset + 3] = Math.round((a / samples) * 255)
      }
    }
  }
  return { width, height, data }
}

function solid(hex: string, alpha = 1): Rgba {
  const [r, g, b] = parseHex(hex)
  return [r, g, b, alpha]
}

/** What `map.addImage` takes for a stretchable image, alongside the pixels. */
export interface StretchableImageOptions {
  pixelRatio: number
  stretchX: Array<[number, number]>
  stretchY: Array<[number, number]>
  content: [number, number, number, number]
}

/**
 * The plate, as a 9-slice pill: two fully rounded ends around a one-pixel
 * stretchable column, and a stretchable band across its waist so a name that
 * wraps still gets a plate (text-max-width keeps that from happening for any
 * name the data holds, but a plate that could not grow would clip the day it
 * does). `content` is everything inside the border, which is what
 * `icon-text-fit` fits the padded text into; the border is then drawn outside
 * that, one px all round.
 */
export function buildBadgePlate(
  face: typeof TRAIL_BADGE_PLATE_DAY | typeof TRAIL_BADGE_PLATE_NIGHT,
  pixelRatio: number = POI_PIN_PIXEL_RATIO,
): { image: PoiIconImage; options: StretchableImageOptions } {
  const height = TRAIL_BADGE_PLATE_HEIGHT
  const radius = height / 2
  // Two caps and one stretchable column between them.
  const width = radius * 2 + 1
  const border = TRAIL_BADGE_PLATE_BORDER
  const fill = solid(face.fill, face.fillAlpha)
  const edge = solid(face.border)

  const pw = Math.round(width * pixelRatio)
  const ph = Math.round(height * pixelRatio)
  const image = rasterise(pw, ph, (x, y) => {
    const cx = x / pixelRatio
    const cy = y / pixelRatio
    if (
      insideRoundedRect(
        cx,
        cy,
        border,
        border,
        width - border * 2,
        height - border * 2,
        radius - border,
      )
    ) {
      return fill
    }
    if (insideRoundedRect(cx, cy, 0, 0, width, height, radius)) return edge
    return null
  })

  const px = (css: number) => Math.round(css * pixelRatio)
  return {
    image,
    options: {
      pixelRatio,
      stretchX: [[px(radius), px(radius + 1)]],
      stretchY: [[px(radius - 1), px(radius + 1)]],
      content: [px(border), px(border), px(width - border), px(height - border)],
    },
  }
}

/**
 * The OurHike blaze chip: a rounded square in the blaze's own hue carrying
 * the white blaze bar from the app icon. Baked into an image
 * TRAIL_BADGE_MARK_GAP wider than the chip, transparent on the right, so the
 * gap to the name is the image's and not the font's.
 */
export function buildBlazeChip(
  blazeColor: string | null,
  pixelRatio: number = POI_PIN_PIXEL_RATIO,
): PoiIconImage {
  const side = TRAIL_BADGE_MARK_SIZE
  const ground =
    blazeColor === null
      ? NEUTRAL_BLAZE_COLOR
      : blazeColor === 'White'
        ? WHITE_CHIP_GROUND
        : blazePaintColor(blazeColor)
  const groundRgba = solid(ground)
  const bar = solid(BLAZE_CHIP_BAR_COLOR)
  const barWidth = side * BLAZE_CHIP_BAR_WIDTH
  const barHeight = side * BLAZE_CHIP_BAR_HEIGHT

  const width = Math.round((side + TRAIL_BADGE_MARK_GAP) * pixelRatio)
  const height = Math.round(side * pixelRatio)
  return rasterise(width, height, (x, y) => {
    const cx = x / pixelRatio
    const cy = y / pixelRatio
    if (
      insideRoundedRect(
        cx,
        cy,
        (side - barWidth) / 2,
        (side - barHeight) / 2,
        barWidth,
        barHeight,
        barWidth / 2,
      )
    ) {
      return bar
    }
    if (insideRoundedRect(cx, cy, 0, 0, side, side, side * BLAZE_CHIP_CORNER)) {
      return groundRgba
    }
    return null
  })
}

/** Every chip the style can ask for, with the id each is registered under. */
export function buildBlazeChips(): Array<{ id: string; image: PoiIconImage }> {
  return [
    ...BLAZE_PALETTE_MEMBERS.map((blaze) => ({
      id: blazeChipImageId(blaze),
      image: buildBlazeChip(blaze),
    })),
    { id: blazeChipImageId(null), image: buildBlazeChip(null) },
  ]
}

/**
 * A registry mark, drawn from its asset onto the same mark-plus-gap canvas
 * the chips use, at the device pixel ratio.
 *
 * Needs a 2D canvas, which is the one thing this file asks of the browser:
 * the A.T. mark is a PNG and the placeholders are SVGs, and nothing but a
 * canvas turns either into pixels. Where there is none - jsdom, a browser
 * that refuses one - this resolves to null and the badge falls through to the
 * blaze chip, which the layer's `coalesce` already does without being told.
 * A missing mark costs the badge its logo, never the badge.
 */
export function rasteriseTrailMark(
  url: string,
  pixelRatio: number = POI_PIN_PIXEL_RATIO,
): Promise<PoiIconImage | null> {
  if (typeof document === 'undefined' || typeof Image === 'undefined') {
    return Promise.resolve(null)
  }
  const canvas = document.createElement('canvas')
  const width = Math.round((TRAIL_BADGE_MARK_SIZE + TRAIL_BADGE_MARK_GAP) * pixelRatio)
  const height = Math.round(TRAIL_BADGE_MARK_SIZE * pixelRatio)
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (context === null) return Promise.resolve(null)

  return new Promise((resolve) => {
    const image = new Image()
    image.decoding = 'async'
    image.onload = () => {
      try {
        const side = Math.round(TRAIL_BADGE_MARK_SIZE * pixelRatio)
        context.clearRect(0, 0, width, height)
        context.drawImage(image, 0, 0, side, side)
        const pixels = context.getImageData(0, 0, width, height)
        resolve({ width, height, data: pixels.data })
      } catch {
        // A tainted canvas or a decode that failed after load: no mark,
        // and the chip stands in.
        resolve(null)
      }
    }
    image.onerror = () => resolve(null)
    image.src = url
  })
}

/**
 * Registers every image the badge layer can name, on a map that is already
 * built, and returns a detach.
 *
 * Two clocks. The plates and the chips are arithmetic and land the moment the
 * layer is in the style. The registry marks decode from their assets, so they
 * land when they land - and a badge drawn before its mark arrives shows the
 * blaze chip for a frame, then the mark, because adding an image re-lays the
 * symbols that name it. Never re-added: images outlive a style reload and
 * re-adding one throws, the same rule every other registrar in map/ keeps.
 */
export function attachTrailBadgeImages(map: MapLibreMap): () => void {
  let detached = false

  const stopWaiting = whenStyleReady(
    map,
    () => map.getLayer(TRAIL_BADGE_LAYER_ID) !== undefined,
    () => {
      for (const face of [TRAIL_BADGE_PLATE_DAY, TRAIL_BADGE_PLATE_NIGHT]) {
        if (map.hasImage(face.id)) continue
        const { image, options } = buildBadgePlate(face)
        map.addImage(face.id, image, options)
      }
      for (const { id, image } of buildBlazeChips()) {
        if (!map.hasImage(id))
          map.addImage(id, image, { pixelRatio: POI_PIN_PIXEL_RATIO })
      }
      for (const trail of Object.values(TRAILS)) {
        const id = `trail-mark-${trail.id}`
        if (map.hasImage(id)) continue
        void rasteriseTrailMark(trail.logo).then((image) => {
          if (detached || image === null || map.hasImage(id)) return
          if (map.getLayer(TRAIL_BADGE_LAYER_ID) === undefined) return
          map.addImage(id, image, { pixelRatio: POI_PIN_PIXEL_RATIO })
        })
      }
    },
    'Trail badge images',
  )

  return () => {
    detached = true
    stopWaiting()
  }
}

/** Every badge feature carries these, copied from the line it names. */
export const BADGE_NAME_PROPERTY = 'name'
export const BADGE_SOURCE_PROPERTY = 'source'
export const BADGE_MARK_PROPERTY = 'mark'
export const BADGE_CHIP_PROPERTY = 'chip'

/** The point source the badges draw from: empty in the style, filled by
 *  map/trailsInView.ts as the camera settles. A function rather than a
 *  shared constant, for the reason style.ts's emptyTrailOverview gives. */
export function buildTrailBadgeSource(): {
  type: 'geojson'
  data: GeoJSON.FeatureCollection
} {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

/**
 * The badge layer.
 *
 * One symbol per point: the plate is the icon, fitted to the text; the mark
 * is the first section of the text, the name the second, both centred on
 * the line. `text-anchor: left` with the offset below puts the MARK's centre
 * on the trail rather than the middle of the pill - the prototype's rule,
 * because a long name would otherwise carry its own mark seventy pixels off
 * the line it claims.
 *
 * Required, both halves: a plate with no name is a pill that says nothing,
 * and a name with no plate is the along-line label this layer exists to be
 * distinct from. `symbol-sort-key` is map/labelLadder.ts's routeTrail rung,
 * and where the layer sits in the stack (style.ts) is what decides it beats
 * an along-line name and loses to every pin.
 */
export function buildTrailBadgeLayer(appearance: SheetAppearance): LayerSpecification {
  return {
    id: TRAIL_BADGE_LAYER_ID,
    type: 'symbol',
    source: TRAIL_BADGE_SOURCE_ID,
    minzoom: TRAIL_LABEL_MIN_ZOOM,
    filter: ['!=', ['to-string', ['get', BADGE_NAME_PROPERTY]], ''] as never,
    layout: {
      'symbol-placement': 'point',
      'icon-image': badgePlateImageId(appearance),
      'icon-text-fit': 'both',
      'icon-text-fit-padding': [...TRAIL_BADGE_TEXT_FIT_PADDING],
      'icon-optional': false,
      'text-optional': false,
      'text-field': [
        'format',
        [
          'coalesce',
          ['image', ['get', BADGE_MARK_PROPERTY]],
          ['image', ['get', BADGE_CHIP_PROPERTY]],
        ],
        { 'vertical-align': 'center' },
        ['get', BADGE_NAME_PROPERTY],
        { 'vertical-align': 'center' },
      ] as never,
      'text-font': ['Noto Sans Regular'],
      'text-size': TRAIL_BADGE_TEXT_SIZE,
      'text-anchor': 'left',
      // Ems of text-size: the mark's half-width, so its centre lands on the
      // anchor vertex.
      'text-offset': [-(TRAIL_BADGE_MARK_SIZE / 2) / TRAIL_BADGE_TEXT_SIZE, 0],
      // No wrapping for any name the data holds: the longest published
      // through-route name is 33 characters (trailLabels.ts's measurement),
      // and a badge that wrapped would be two lines of pill.
      'text-max-width': 40,
      'text-letter-spacing': 0.02,
      'symbol-sort-key': LABEL_TIER.routeTrail,
    },
    paint: {
      'text-color': badgeTextColor(appearance),
      'text-halo-color': badgeHaloColor(appearance),
      'text-halo-width': 2,
      // The ghosting rule, on both halves of the symbol, so a badge for a
      // through-route outside the chosen system dims with its line.
      'icon-opacity': nearbyTrailOpacityExpression() as never,
      'text-opacity': nearbyTrailOpacityExpression() as never,
    },
  }
}
