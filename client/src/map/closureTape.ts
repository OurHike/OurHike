// The barrier tape itself: the pixels every "do not walk this" line on this
// map is painted with.
//
// Split from lib/closureStyle.ts on the same line poiLayers.ts draws against
// poiIcons.ts - the spec is a lib/ module that knows nothing about MapLibre,
// and the image and its registration are here.
//
// COMPUTED, NOT SHIPPED AS AN ASSET, and not drawn on a canvas either. Both
// halves of that are poiIcons.ts's decision, taken again for the same reasons:
// an offline-first app should not spend a build step or a network round trip
// on one small tile, and jsdom - which the whole client suite runs in - can
// neither rasterise an SVG nor give you a 2d context. A pure function over a
// byte array is testable; `document.createElement('canvas')` is not.
//
// WHAT TILES AND WHAT DOES NOT. MapLibre scales a `line-pattern` so the image
// HEIGHT becomes the line width, then repeats it along the line. So the height
// here is the tape's full width and never repeats, and only the x axis has to
// tile seamlessly - which it does when the image is exactly one pitch wide,
// because translating a stripe family by one pitch maps it onto itself.
//
// ONE IMAGE PER PAPER (#1575, option E). The tape lies on an opaque band of
// the paper map/style.ts's closureTapeGround picks for the sheet - its own by
// day, the field day sheet's white on a dark sheet since 2026-09-18 -
// lib/closureStyle.ts's header has the maintainer's choice and what it costs -
// and a `line-pattern` layer has no colour of its own, so the paper is in
// the pixels. `tapeGrounds` lists every backdrop the
// sheet table can produce, `attachClosureTape` registers a closure tape and
// an ATC tape on each, and map/style.ts's attachMapAppearance points the tape
// layers at the current paper's pair. Registering them all up front rather
// than the current one on demand is the trail badge's rule for its day and
// night plates: a layer whose `line-pattern` names an image the map has not
// been given draws nothing, and a sheet change must never open that window.

import {
  CLOSURE_CASING_COLOR,
  CLOSURE_LAYER_ID,
  CLOSURE_COLOR,
  CLOSURE_STRIPE_ANGLE_DEG,
  CLOSURE_STRIPE_EDGE,
  CLOSURE_TAPE_CADENCE,
  CLOSURE_TAPE_PIXEL_RATIO,
  CLOSURE_TAPE_WIDTH,
  closureTapeImageId,
  type TapeCadence,
} from '../lib/closureStyle'
import { ATC_UPDATE_TAPE_CADENCE, atcTapeImageId } from '../lib/atcUpdateStyle'
import { MAP_STYLE_VALUES, THEME_VALUES } from '../lib/userPreferences'
import { closureTapeGround } from './style'
import { whenStyleReady } from './styleReady'
import type { Map as MapLibreMap } from 'maplibre-gl'

/** What `map.addImage` wants, and what a test can read a pixel out of. Shaped
 *  like poiIcons.ts's PoiIconImage rather than importing it, because a tape is
 *  not a pin and the two will not stay the same shape by accident. */
export interface TapeImage {
  width: number
  height: number
  data: Uint8ClampedArray
}

/** `#rrggbb` to three channels. poiIcons.ts has its own copy and does not
 *  export it; three lines is a cheaper dependency than reaching across two
 *  modules for them. */
function parseHex(hex: string): readonly [number, number, number] {
  const value = Number.parseInt(hex.slice(1), 16)
  return [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff]
}

/**
 * How much of a pixel a band of half-thickness `half` covers, at `distance`
 * from its centre.
 *
 * A one-pixel linear ramp rather than real coverage integration: at this size
 * the difference is invisible and the alternative is a supersampler nobody
 * needs. The 0.5 is what puts the ramp ACROSS the boundary rather than inside
 * one side of it, so a stripe drawn at 3.5px measures 3.5px.
 */
function coverage(distance: number, half: number): number {
  return Math.min(Math.max(half + 0.5 - distance, 0), 1)
}

/**
 * One tile of barrier tape on `ground` - the sheet's paper, `#rrggbb` -
 * ready for `map.addImage`.
 *
 * Every pixel is classified by ONE number: how far it sits from the nearest
 * stripe's centre line, measured along the stripes' shared normal. That is
 * what makes this a dozen lines rather than a polygon rasteriser - a family of
 * parallel stripes is a periodic function of exactly that distance, so the
 * whole image is `distance -> colour` evaluated per pixel. Bottom to top at
 * each one: the ground, opaque everywhere; the stripe's dark edge; the red.
 */
export function buildClosureTape(
  ground: string,
  cadence: TapeCadence = CLOSURE_TAPE_CADENCE,
  pixelRatio: number = CLOSURE_TAPE_PIXEL_RATIO,
): TapeImage {
  const height = Math.round(CLOSURE_TAPE_WIDTH * pixelRatio)
  const width = Math.round(cadence.pitch * pixelRatio)
  const data = new Uint8ClampedArray(width * height * 4)

  const angle = (CLOSURE_STRIPE_ANGLE_DEG * Math.PI) / 180
  // The stripes' shared normal, a quarter turn from their direction. y runs
  // down the image, which is why this is (sin, cos) rather than (-sin, cos).
  const normalX = Math.sin(angle)
  const normalY = Math.cos(angle)
  // Sliding one stripe a whole pitch ALONG the line moves it this far along
  // its own normal, so this is the period the pattern actually repeats on.
  const period = cadence.pitch * pixelRatio * Math.sin(angle)

  const half = (cadence.stripe * pixelRatio) / 2
  const edged = half + CLOSURE_STRIPE_EDGE * pixelRatio

  const [redR, redG, redB] = parseHex(CLOSURE_COLOR)
  const [darkR, darkG, darkB] = parseHex(CLOSURE_CASING_COLOR)
  const [groundR, groundG, groundB] = parseHex(ground)

  // `top` over `bottom` by `cover`. Straight (non-premultiplied) colour, which
  // is what addImage reads - and with an opaque ground under everything, every
  // pixel's alpha is simply 255, so no division by it is needed any more.
  const over = (top: number, bottom: number, cover: number) =>
    top * cover + bottom * (1 - cover)

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const along = (x + 0.5) * normalX + (y + 0.5) * normalY
      // Folded into one period, then to the nearer of the two stripe centres
      // bounding it - so a pixel's distance is always to the stripe it is
      // actually closest to, including across the tile's own seam.
      const phase = ((along % period) + period) % period
      const distance = Math.min(phase, period - phase)

      const red = coverage(distance, half)
      const dark = coverage(distance, edged)
      // The edge over the ground, then red over both. Where red is opaque the
      // edge and the ground contribute nothing, which is why the stripe is
      // not darkened by the casing under it.
      const at = (y * width + x) * 4
      data[at] = over(redR, over(darkR, groundR, dark), red)
      data[at + 1] = over(redG, over(darkG, groundG, dark), red)
      data[at + 2] = over(redB, over(darkB, groundB, dark), red)
      data[at + 3] = 255
    }
  }

  return { width, height, data }
}

/**
 * Every paper a tape can lie on: closureTapeGround's answer for every
 * appearance the sheet table can produce, de-duplicated (#1575).
 *
 * Enumerated through map/style.ts's closureTapeGround over the whole
 * appearance space - five styles, two resolved themes, three theme choices,
 * red light on and off - rather than by reading liveTopo.ts's variant table
 * directly, so the set is exactly what the map can ask for and stays so when
 * the table gains a sheet: the function that picks a paper is the one that
 * lists them. Five distinct papers today - four day sheets' (night_hike has
 * none) and red light's ink; every other dark sheet takes the field day
 * sheet's white since 2026-09-18 - measured by running this, and held by
 * closureTape.test.ts so the number moves in the open. (Ten until then, one
 * per backdrop.)
 */
export function tapeGrounds(): readonly string[] {
  const grounds = new Set<string>()
  for (const mapStyle of MAP_STYLE_VALUES) {
    for (const theme of ['light', 'dark'] as const) {
      for (const themeChoice of THEME_VALUES) {
        for (const redLight of [false, true]) {
          grounds.add(closureTapeGround({ theme, themeChoice, mapStyle, redLight }))
        }
      }
    }
  }
  return [...grounds]
}

/**
 * Registers both tapes on every paper on a live map, and returns a detach.
 *
 * BOTH, from one call and one generator, because features/NEARBY_TRAILS.md §3
 * and lib/atcUpdateStyle.ts want the same thing from opposite directions: a
 * hiker learns ONE mark for "do not walk this", and which organisation said so
 * is the sheet's job rather than the line's. Two `addImage` calls that could
 * drift apart would be the same latent bug as two layer builders that
 * currently agree.
 *
 * EVERY PAPER, not the current one, so a sheet change never points a tape
 * layer at an image the map has not been given (this file's header). Ten
 * images of 30 by 28 pixels is about 34 KB, rasterised once per map.
 */
export function attachClosureTape(map: MapLibreMap): () => void {
  return whenStyleReady(
    map,
    // The layer that names this image existing proves the style spec has
    // parsed, which is the condition addImage actually requires - the same
    // question attachWarningIcon asks, asked the same way.
    () => map.getLayer(CLOSURE_LAYER_ID) !== undefined,
    () => {
      for (const ground of tapeGrounds()) {
        // Images outlive a style reload, and re-adding one throws.
        const closureId = closureTapeImageId(ground)
        if (!map.hasImage(closureId)) {
          map.addImage(closureId, buildClosureTape(ground, CLOSURE_TAPE_CADENCE), {
            pixelRatio: CLOSURE_TAPE_PIXEL_RATIO,
          })
        }
        const atcId = atcTapeImageId(ground)
        if (!map.hasImage(atcId)) {
          map.addImage(atcId, buildClosureTape(ground, ATC_UPDATE_TAPE_CADENCE), {
            pixelRatio: CLOSURE_TAPE_PIXEL_RATIO,
          })
        }
      }
    },
    'barrier tape images',
  )
}
