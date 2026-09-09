// The ATC point-notice mark, as raw RGBA pixels (#1071).
//
// lib/atcUpdateStyle.ts decides WHAT this looks like - the spoke count, the
// taper, how much of the middle stays open, and why the glow that used to sit
// behind it is gone. This file only turns those numbers into an image, which is
// the division map/warningPin.ts already keeps with lib/seriousWarnings.ts.
//
// WHY IT IS NOT map/poiIcons.ts's RASTERISER. That one fills POLYGONS by
// even-odd crossing count, and a burst spelled as a polygon has two problems
// this shape cannot afford:
//
//  1. The casing. A dark edge gets drawn there by insetting a ring inside the
//     shape's own outline, which works for a disc because a disc's outline is
//     one circle. A burst's outline is eight tapered wedges plus a dot, and
//     insetting each of them by hand is nine chances to get a hairline wrong -
//     and a scaled-up copy, the obvious shortcut, gives an edge that is thin at
//     the hub and fat at the tip.
//  2. The tips. Every spoke ends on an arc of the mark's rim, so a polygon
//     spelling needs a fan of vertices per tip and the smoothness of the mark
//     becomes a step count.
//
// In POLAR terms both problems disappear. A spoke's lateral half-width at
// radius r is an ANGLE, so `casing / r` radians of extra width is exactly
// `casing` PIXELS of outline at every radius; and "inside the rim" is a
// comparison against r rather than a polygon at all. {@link insideBurst} is the
// entire shape, and the casing is that same predicate sampled a second time
// with everything grown by the hairline.
//
// WHAT IS SHARED WITH THE PINS, deliberately, so this mark cannot drift away
// from the map it sits on: the output type, the 2x pixel ratio, the hex parse
// and the 3x3 supersample. Only the shape is its own.

import {
  ATC_NOTICE_BURST,
  ATC_NOTICE_CASING_WIDTH,
  ATC_NOTICE_FILL_RADIUS,
  ATC_UPDATE_CASING_COLOR,
  ATC_UPDATE_COLOR,
  ATC_UPDATE_POINT_DRAWN_WIDTH,
  type AtcNoticeBurst,
} from '../lib/atcUpdateStyle'
import { parseHex, POI_PIN_PIXEL_RATIO, type PoiIconImage } from './poiIcons'

const TAU = Math.PI * 2

/** Sub-samples per axis. Three, because map/poiIcons.ts uses three and a mark
 *  anti-aliased to a different standard from the pins beside it would read as
 *  a different weight of ink rather than as a different shape. */
const SUPERSAMPLE = 3

/** The smallest signed angle between two bearings, as a magnitude. */
function bearingGap(a: number, b: number): number {
  return Math.abs(((((a - b) % TAU) + TAU + Math.PI) % TAU) - Math.PI)
}

/**
 * Is this offset from the mark's centre inside the burst?
 *
 * `grow`, in the same pixels as everything else here, dilates the whole shape
 * uniformly - the hub, the rim, the inner ends of the spokes and their sides.
 * That is what draws the casing: sample once with `grow` set to the hairline
 * for the dark edge, once with it at zero for the red, and the difference
 * between the two answers is an outline of constant width.
 *
 * Exported for map/atcNoticeMark.test.ts, which asserts the property the whole
 * change turns on - that the ring between the hub and the spokes, and the gaps
 * between the spokes, are OUTSIDE the grown shape too and therefore carry no
 * ink at all.
 */
export function insideBurst(
  burst: AtcNoticeBurst,
  fillRadius: number,
  dx: number,
  dy: number,
  grow: number,
): boolean {
  const radius = Math.hypot(dx, dy)

  // The dot on the coordinate, first, so it is drawn whatever the spokes do.
  if (radius <= burst.hubRadius * fillRadius + grow) return true
  if (radius > fillRadius + grow) return false

  const inner = burst.innerRadius * fillRadius
  // The open ring. This one line is the feature: between the hub and the inner
  // end of the spokes there is nothing, so whatever the notice is drawn on
  // reads straight through the middle of it.
  if (radius < inner - grow) return false

  const pitch = TAU / burst.spokes
  const bearing = Math.atan2(dy, dx)
  const nearest = Math.round((bearing - burst.phase) / pitch) * pitch + burst.phase
  const offAxis = bearingGap(bearing, nearest)

  const along =
    (Math.min(Math.max(radius, inner), fillRadius) - inner) / (fillRadius - inner)
  const halfWidth =
    burst.innerHalfWidth + (burst.tipHalfWidth - burst.innerHalfWidth) * along

  // `grow / radius` is the angle that adds `grow` pixels of width at this
  // radius. The floor stops it exploding near the centre - unreachable in
  // practice, since the hub returns above, but a predicate that can divide by
  // zero is one edit away from doing it.
  return offAxis <= halfWidth + grow / Math.max(radius, 0.5)
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
 * alpha alone. Averaging over all nine instead would fringe every spoke with
 * half-transparent dark pixels, because the transparent samples beside it carry
 * a colour of their own into the mean - and on a mark that is mostly edge, that
 * fringe is most of the mark.
 */
export function buildAtcNoticeIcon(): PoiIconImage {
  const pixels = ATC_UPDATE_POINT_DRAWN_WIDTH * POI_PIN_PIXEL_RATIO
  const center = pixels / 2
  const fillRadius = ATC_NOTICE_FILL_RADIUS * POI_PIN_PIXEL_RATIO
  const casing = ATC_NOTICE_CASING_WIDTH * POI_PIN_PIXEL_RATIO

  const red = parseHex(ATC_UPDATE_COLOR)
  const dark = parseHex(ATC_UPDATE_CASING_COLOR)

  const data = new Uint8ClampedArray(pixels * pixels * 4)
  const step = 1 / SUPERSAMPLE
  const samples = SUPERSAMPLE * SUPERSAMPLE
  // The furthest a pixel's own samples can sit from its centre, so the skip
  // below is exact rather than approximate - the same derivation `buildPinImage`
  // spells out for its own corner skip.
  const reach = Math.SQRT2 * (0.5 - step / 2)

  for (let py = 0; py < pixels; py += 1) {
    for (let px = 0; px < pixels; px += 1) {
      const cx = px + 0.5 - center
      const cy = py + 0.5 - center
      if (Math.hypot(cx, cy) > fillRadius + casing + reach) continue

      let r = 0
      let g = 0
      let b = 0
      let hits = 0

      for (let sy = 0; sy < SUPERSAMPLE; sy += 1) {
        for (let sx = 0; sx < SUPERSAMPLE; sx += 1) {
          const dx = px + (sx + 0.5) * step - center
          const dy = py + (sy + 0.5) * step - center

          let ink: readonly [number, number, number] | null = null
          if (insideBurst(ATC_NOTICE_BURST, fillRadius, dx, dy, 0)) ink = red
          else if (insideBurst(ATC_NOTICE_BURST, fillRadius, dx, dy, casing)) ink = dark

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
