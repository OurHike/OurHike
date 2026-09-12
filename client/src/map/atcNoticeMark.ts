// The ATC point-notice mark, as raw RGBA pixels: the hazard triangle, bare.
//
// lib/atcUpdateStyle.ts decides WHAT this looks like - the size, the colour,
// the hairline - and why; this file only turns those numbers into an image,
// which is the division map/warningPin.ts already keeps with
// lib/seriousWarnings.ts.
//
// THE SHAPE IS THE SERIOUS-WARNING PIN'S GLYPH, on the maintainer's call of
// 2026-09-10 ("adopt the warning icon we made" - asked which mark was meant,
// the answer was the hazard triangle, for the ATC notice marks too). It was
// an eight-spoke burst from #1071 until then, and the burst's reasons are
// kept here because the triangle keeps them:
//
//  1. THE GROUND READS THROUGH. A point notice is placed ON the centerline
//     (map/atcUpdateLayers.ts), so a solid mark hid the trail the notice is
//     about plus the shelter or ford the notice is about; #1071 made the mark
//     mostly hole. The hazard triangle is a BAND with an exclamation standing
//     in the empty middle (map/warningPin.ts), so the hole is still most of
//     the mark: 688.7 px² of ink at 40 px against the disc's 1,256.6 px²
//     (54.8%; the burst put 760.1 px²), measured 2026-09-10 off the rendered
//     alpha, which atcNoticeMark.test.ts re-measures.
//  2. IT IS NOT THE SERIOUS-WARNING PIN. That pin is the same glyph on a
//     44 px disc with a halo; this is the glyph alone, in the closure red, at
//     40 px. A hiker who has learned the disc learns that the triangle means
//     "look" and the disc means "a person confirmed something serious here"
//     - one vocabulary, two weights - where a second disc four pixels smaller
//     would have been the same mark with the difference hidden in the size.
//
// WHY IT IS NOT map/poiIcons.ts's `buildPinImage`: that draws a disc, a halo
// and an edge and then the glyph inside them, and the disc is the thing this
// mark must not have. What IS shared is the fill rule - `insideGlyph`, the
// even-odd crossing count every pin's glyph is cut with - the output type, the
// 2x pixel ratio, the hex parse and the 3x3 supersample.
//
// THE CASING is the shape grown by the hairline: a sample is dark when it is
// not inside the glyph but within `casing` pixels of any edge of any ring.
// That is the Minkowski sum of the glyph with a disc of the casing's radius,
// so the outline is one width everywhere - down the outside of the band, up
// the inside of the hole, and round the exclamation - without insetting or
// scaling any ring by hand, which is the trap the burst's polar spelling
// existed to avoid for a shape with eight tapered spokes.

import {
  ATC_NOTICE_CASING_WIDTH,
  ATC_NOTICE_GLYPH_BOX,
  ATC_UPDATE_CASING_COLOR,
  ATC_UPDATE_COLOR,
  ATC_UPDATE_POINT_DRAWN_WIDTH,
} from '../lib/atcUpdateStyle'
import {
  insideGlyph,
  parseHex,
  POI_PIN_PIXEL_RATIO,
  type Glyph,
  type PoiIconImage,
} from './poiIcons'
import { WARNING_GLYPH } from './warningPin'

/** Sub-samples per axis. Three, because map/poiIcons.ts uses three and a mark
 *  anti-aliased to a different standard from the pins beside it would read as
 *  a different weight of ink rather than as a different shape. */
const SUPERSAMPLE = 3

/** The glyph this mark draws: the hazard triangle, shared with the
 *  serious-warning pin so the two cannot drift into two triangles. */
export const ATC_NOTICE_GLYPH: Glyph = WARNING_GLYPH

/** Distance from a point to the nearest edge of any ring, in the glyph's own
 *  0-1 box. */
function edgeDistance(glyph: Glyph, x: number, y: number): number {
  let nearest = Infinity
  for (const ring of glyph) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
      const [ax, ay] = ring[j]
      const [bx, by] = ring[i]
      const vx = bx - ax
      const vy = by - ay
      const length2 = vx * vx + vy * vy
      const t =
        length2 === 0
          ? 0
          : Math.max(0, Math.min(1, ((x - ax) * vx + (y - ay) * vy) / length2))
      const dx = x - (ax + t * vx)
      const dy = y - (ay + t * vy)
      nearest = Math.min(nearest, Math.hypot(dx, dy))
    }
  }
  return nearest
}

/**
 * Is this offset from the mark's centre, in image pixels, inside the glyph
 * grown by `grow` pixels?
 *
 * `grow` at zero is the red; `grow` at the casing width is the red plus its
 * dark outline, and the difference between the two answers is the outline.
 * `box` is the glyph's 0-1 square in image pixels. Exported for
 * atcNoticeMark.test.ts, which holds the property the shape is chosen for:
 * that the hole inside the band, off the exclamation, is outside the grown
 * shape too and so carries no ink at all.
 */
export function insideNoticeMark(
  box: number,
  dx: number,
  dy: number,
  grow: number,
): boolean {
  const x = dx / box + 0.5
  const y = dy / box + 0.5
  if (insideGlyph(ATC_NOTICE_GLYPH, x, y)) return true
  if (grow <= 0) return false
  return edgeDistance(ATC_NOTICE_GLYPH, x, y) * box <= grow
}

/**
 * The mark, as raw RGBA pixels.
 *
 * Rasterised ONCE at full size and sampled down by MapLibre for every zoom
 * below z13, which is what `icon-size` means and what map/poiLayers.ts already
 * does to every waypoint pin. The alternative - one image per zoom stop - would
 * be three images to register, three to keep in step, and no crisper, because
 * the ramp is continuous between the stops and something has to interpolate.
 *
 * Sub-samples in the same shape map/poiIcons.ts's `buildPinImage` does: the
 * colour is the mean of the samples that HAD colour and coverage is carried by
 * alpha alone. Averaging over all nine instead would fringe every edge with
 * half-transparent dark pixels, because the transparent samples beside it carry
 * a colour of their own into the mean - and on a mark that is mostly edge, that
 * fringe is most of the mark.
 */
export function buildAtcNoticeIcon(): PoiIconImage {
  const pixels = ATC_UPDATE_POINT_DRAWN_WIDTH * POI_PIN_PIXEL_RATIO
  const center = pixels / 2
  const box = ATC_NOTICE_GLYPH_BOX * POI_PIN_PIXEL_RATIO
  const casing = ATC_NOTICE_CASING_WIDTH * POI_PIN_PIXEL_RATIO

  const red = parseHex(ATC_UPDATE_COLOR)
  const dark = parseHex(ATC_UPDATE_CASING_COLOR)

  const data = new Uint8ClampedArray(pixels * pixels * 4)
  const step = 1 / SUPERSAMPLE
  const samples = SUPERSAMPLE * SUPERSAMPLE

  for (let py = 0; py < pixels; py += 1) {
    for (let px = 0; px < pixels; px += 1) {
      let r = 0
      let g = 0
      let b = 0
      let hits = 0

      for (let sy = 0; sy < SUPERSAMPLE; sy += 1) {
        for (let sx = 0; sx < SUPERSAMPLE; sx += 1) {
          const dx = px + (sx + 0.5) * step - center
          const dy = py + (sy + 0.5) * step - center

          let ink: readonly [number, number, number] | null = null
          if (insideNoticeMark(box, dx, dy, 0)) ink = red
          else if (insideNoticeMark(box, dx, dy, casing)) ink = dark

          if (ink !== null) {
            r += ink[0]
            g += ink[1]
            b += ink[2]
            hits += 1
          }
        }
      }

      if (hits === 0) continue

      const at = (py * pixels + px) * 4
      data[at] = r / hits
      data[at + 1] = g / hits
      data[at + 2] = b / hits
      data[at + 3] = (hits / samples) * 255
    }
  }

  return { width: pixels, height: pixels, data }
}
