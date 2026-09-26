// The staleness ring's artwork, as raw RGBA pixels, and the pin it is drawn
// onto.
//
// PART OF THE PIN SINCE 2026-09-26 (#1676), not a layer of its own. With the
// collision engine back on the pin layer, a pin that loses its place falls
// back to a dot - and a ring on a separate layer cannot know that happened,
// because MapLibre exposes no per-feature placement result to another layer.
// Photographed on the restored build that day, against the UA bucket: the
// Manhattan frame at z11 placed 44 pins out of 1,570 waypoints, and pale rings
// stood round empty air right across it. So {@link composeRingedPin} paints
// the ring into the pin's own image, and whatever the collision engine does to
// the pin it does to the ring. The maintainer chose this from drawn frames
// (poll, 2026-09-26): "ring rides the pin".
//
// The history below is why the ring is shaped and sized the way it is, and
// still holds. What it says about `icon-offset` lifting the ring is now done
// by painting both into one image round one centre.
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
import { parseHex, POI_PIN_INK_SIZE, type PoiIconImage } from './poiIcons'

/**
 * The ring's radius in CSS px at icon-size 1, to the middle of its ink: half
 * the drawn pin plus 3 px of air. Scaled by the pin's own `icon-size`, so a
 * secondary pin gets a proportionally smaller ring.
 *
 * 16 since the pin was drawn 26 px across inside its 38 px footprint (#1682);
 * it was 22 round the 38 px coin. Derived from the drawn size rather than
 * typed, so the 3 px of air is what survives a resize - the circle layer's
 * original choice, kept.
 */
export const STALENESS_RING_RADIUS = POI_PIN_INK_SIZE / 2 + 3

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

/**
 * Half the ring image's side, in CSS px at icon-size 1: how far the ring's
 * artwork reaches from its centre, antialiasing included. The pin image is
 * smaller than this unless a site pin's badge padding makes it larger, and the
 * difference is what {@link ringOverhang} measures.
 */
export const STALENESS_RING_HALF_PX = Math.ceil(STALENESS_RING_RADIUS + RING_INK / 2 + 1)

/**
 * How far a ringed pin's image reaches BELOW the pin's own bottom edge, in CSS
 * px at icon-size 1, for a pin whose disc centre sits `lift` px above that
 * edge (map/poiLayers.ts's `ringLift`).
 *
 * The pin layer anchors the image's bottom on the coordinate (the jigger), so
 * a ringed image would stand its pin this much higher than an unringed one.
 * The layer's `icon-offset` gives it back, and the place stays exactly where
 * the pin touches down. Zero for a site pin whose badge padding already makes
 * its image taller than the ring.
 */
export function ringOverhang(lift: number): number {
  return Math.max(0, STALENESS_RING_HALF_PX - lift)
}

/**
 * A pin with its staleness ring painted round it, as one image.
 *
 * The ring goes UNDER the pin, as the ring layer went under the pin layer: a
 * site pin's badges reach past the ring and have to stay on top of it. Both
 * images share one centre, which is the pin disc's centre - the pin image is
 * square and symmetrically padded, and so is the ring's.
 *
 * `ringAlpha` scales the ring's own coverage. It is baked in rather than left
 * to the layer's `icon-opacity`, which would fade the pin with it.
 *
 * Both images are straight (not premultiplied) RGBA at the same pixel ratio,
 * which is what poiIcons.ts's rasteriser and {@link buildStalenessRingImage}
 * both write; composited with the ordinary "over" operator.
 */
export function composeRingedPin(
  pin: PoiIconImage,
  ring: PoiIconImage,
  ringAlpha: number,
): PoiIconImage {
  const width = Math.max(pin.width, ring.width)
  const height = Math.max(pin.height, ring.height)
  const data = new Uint8ClampedArray(width * height * 4)

  const ringX = (width - ring.width) / 2
  const ringY = (height - ring.height) / 2
  for (let y = 0; y < ring.height; y += 1) {
    for (let x = 0; x < ring.width; x += 1) {
      const from = (y * ring.width + x) * 4
      const alpha = ring.data[from + 3] * ringAlpha
      if (alpha === 0) continue
      const to = ((y + ringY) * width + (x + ringX)) * 4
      data[to] = ring.data[from]
      data[to + 1] = ring.data[from + 1]
      data[to + 2] = ring.data[from + 2]
      data[to + 3] = alpha
    }
  }

  const pinX = (width - pin.width) / 2
  const pinY = (height - pin.height) / 2
  for (let y = 0; y < pin.height; y += 1) {
    for (let x = 0; x < pin.width; x += 1) {
      const from = (y * pin.width + x) * 4
      const top = pin.data[from + 3] / 255
      if (top === 0) continue
      const to = ((y + pinY) * width + (x + pinX)) * 4
      const under = data[to + 3] / 255
      const out = top + under * (1 - top)
      for (let channel = 0; channel < 3; channel += 1) {
        data[to + channel] =
          (pin.data[from + channel] * top + data[to + channel] * under * (1 - top)) / out
      }
      data[to + 3] = out * 255
    }
  }

  return { width, height, data }
}
