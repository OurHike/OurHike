// The staleness ring's artwork, as raw RGBA pixels - one image per ring
// colour, drawn by map/poiLayers.ts's ring layer as an ICON rather than the
// circle it used to be.
//
// WHY AN ICON NOW (v1.3.2 release review, 2026-09-23). The ring was a circle
// layer centred on the waypoint's coordinate, "sized to sit just outside the
// pin". Then the jigger (2026-09-20, map/poiLayers.ts's `icon-anchor:
// 'bottom'`) lifted every pin so its bottom edge touches the coordinate, and
// the ring stayed where it was: centred on the pin's bottom edge, cutting
// through the lower half of the disc. A circle layer cannot follow, because
// how far the pin moved depends on the feature - a secondary pin is drawn at
// SECONDARY_POI_SCALE, and a site pin's image is padded for its badges - and
// `circle-translate` takes no per-feature value. An icon's `icon-size` and
// `icon-offset` both do, so the ring now rides the pin's own size expression
// and is lifted by the pin's own half-height.
//
// Its own tiny rasteriser rather than `buildPinImage`, for the reason
// map/positionMark.ts gives: that function draws a pin, and this is not one.
import { parseHex, type PoiIconImage } from './poiIcons'

/**
 * The ring's radius in CSS px at icon-size 1, to the middle of its ink: half
 * the 38 px pin plus 3 px of air, the same 22 px the circle layer drew at
 * full size. Scaled by the pin's own `icon-size` now, so a secondary pin gets
 * a proportionally smaller ring rather than the full-size one it used to.
 */
export const STALENESS_RING_RADIUS = 22

/** The ink width in CSS px - the circle layer's `circle-stroke-width: 2`. */
const RING_INK = 2

/** Drawn at 2x, like the pins, so the rim stays crisp on a phone. */
export const STALENESS_RING_PIXEL_RATIO = 2

const SUPERSAMPLE = 3

/** One ring in `color`, opaque; the layer's `icon-opacity` does the fading. */
export function buildStalenessRingImage(
  color: string,
  pixelRatio = STALENESS_RING_PIXEL_RATIO,
): PoiIconImage {
  // The box the ink reaches, plus a pixel of air so antialiasing is not
  // clipped at the edge. Even, so the ring's centre is the image's centre.
  const half = Math.ceil(STALENESS_RING_RADIUS + RING_INK / 2 + 1) * pixelRatio
  const size = half * 2
  const radius = STALENESS_RING_RADIUS * pixelRatio
  const inkHalf = (RING_INK / 2) * pixelRatio
  const [r, g, b] = parseHex(color)
  const data = new Uint8ClampedArray(size * size * 4)
  const step = 1 / SUPERSAMPLE
  const samples = SUPERSAMPLE * SUPERSAMPLE

  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      let hits = 0
      for (let sy = 0; sy < SUPERSAMPLE; sy += 1) {
        for (let sx = 0; sx < SUPERSAMPLE; sx += 1) {
          const dx = x + (sx + 0.5) * step - half
          const dy = y + (sy + 0.5) * step - half
          if (Math.abs(Math.hypot(dx, dy) - radius) <= inkHalf) hits += 1
        }
      }
      if (hits === 0) continue
      const offset = (y * size + x) * 4
      data[offset] = r
      data[offset + 1] = g
      data[offset + 2] = b
      data[offset + 3] = Math.round((255 * hits) / samples)
    }
  }

  return { width: size, height: size, data }
}
