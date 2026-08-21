// The mark on a place the field says is not there (#876,
// features/FIELD_NOTES.md §4).
//
// WHY A MARK BESIDE THE PIN RATHER THAN A THIRD PIN
//
// §4's table asks for "dashed pin, distinct marker", and the dashed half
// cannot be delivered the obvious way. The dash is driven by the feature's
// `confidence` property, and that property is also what the legend's
// "Verified?" toggle filters on (WIREFRAMES.md §2) - so drawing a disputed
// waypoint as `confidence: low` would let a hiker with that filter on lose
// the pin entirely. §4's own rule is that **the pin is never suppressed**:
// "a POI that vanishes is indistinguishable from one that never existed".
//
// So the dispute rides its own layer instead, and the pin keeps its own rim.
// That turns out to say MORE rather than less, and it is the distinction the
// card's two sentences already make: a solid pin with this mark is a place
// ATC surveyed that hikers say is gone, and a dashed pin with this mark is a
// place nobody ever confirmed that hikers also say is gone. Collapsing both
// into one dashed pin would have thrown that away.
//
// THE SHAPE
//
// A ring with a bar through it - the "not here" sign, and the one silhouette
// on this map that reads as a negation rather than as a thing. Drawn hollow
// like map/warningPin.ts's triangle and for the same reason: solid-versus-
// outline survives being reduced to a black shape, where colour does not.
//
// Small, and deliberately so. It is a footnote on a pin, not a second pin:
// this feature's whole posture is that a dispute is *a thing to say*, not a
// claim that the place is gone.

import { PIN_EDGE_COLOR, PIN_HALO_COLOR, type PoiIconImage } from './poiIcons'

/** Stable image id. Namespaced away from `poi-*`: this is not a waypoint. */
export const DISPUTE_MARK_ID = 'poi-disputed-mark'

/** Drawn size in CSS pixels - about half a waypoint pin. */
export const DISPUTE_MARK_SIZE = 18

/** The ink. `--stone-900`, the same hairline colour every pin is edged in, so
 *  the mark reads as part of the pin's own drawing rather than as a sticker
 *  from another map. */
export const DISPUTE_MARK_COLOR = PIN_EDGE_COLOR

function parseHex(hex: string): [number, number, number] {
  const int = Number.parseInt(hex.replace('#', ''), 16)
  return [(int >> 16) & 255, (int >> 8) & 255, int & 255]
}

/**
 * The mark, as raw RGBA pixels.
 *
 * Its own tiny rasteriser rather than `buildPinImage`: that function draws a
 * PIN - a filled disc, a halo, a rim, a glyph inside it - and every one of
 * those is a thing this deliberately is not. Borrowing it would have meant
 * passing four flags to switch the pin off.
 */
export function buildDisputeMark(
  sizePx: number = DISPUTE_MARK_SIZE,
  pixelRatio = 2,
): PoiIconImage {
  const pixels = Math.round(sizePx * pixelRatio)
  const data = new Uint8ClampedArray(pixels * pixels * 4)

  const centre = pixels / 2
  const outer = centre - pixelRatio // room for the halo to sit outside the ink
  const inner = outer - 2.2 * pixelRatio // ring thickness
  const halo = parseHex(PIN_HALO_COLOR)
  const ink = parseHex(DISPUTE_MARK_COLOR)
  // The bar, at 45 degrees through the middle - the negation. Half-width in
  // pixels rather than a fraction, so it thickens with the mark instead of
  // vanishing when somebody draws it small.
  const barHalf = 1.1 * pixelRatio

  for (let y = 0; y < pixels; y += 1) {
    for (let x = 0; x < pixels; x += 1) {
      const dx = x + 0.5 - centre
      const dy = y + 0.5 - centre
      const distance = Math.hypot(dx, dy)
      if (distance > outer) continue

      // Distance from the 45-degree line through the centre.
      const onBar = Math.abs(dx + dy) / Math.SQRT2 <= barHalf
      const onRing = distance >= inner
      const at = (y * pixels + x) * 4
      const [r, g, b] = onRing || onBar ? ink : halo

      data[at] = r
      data[at + 1] = g
      data[at + 2] = b
      data[at + 3] = 255
    }
  }

  return { width: pixels, height: pixels, data }
}
