// The serious-warning pin image (WIREFRAMES.md §8, HIKER_SAFETY.md §1).
//
// lib/seriousWarnings.ts has specified this pin since long before anything
// drew it - 44px, red, `triangle-alert`, haloed - and says why it is a VARIANT
// inside the waypoint icon spec rather than a visual language of its own: "a
// warning that looks like nothing else on the map is a warning nobody has
// learned to read." So the body is the same disc, the same halo, the same dark
// hairline edge, drawn by the same rasteriser (map/poiIcons.ts). What differs
// is the three things that are allowed to: size, colour, and the glyph.
//
// The glyph is the part that needed care, because the map already has a
// triangle. `campsite` is a solid tent, and a solid hazard triangle beside it
// would be the same silhouette in a different hue - which is exactly the
// failure poiIcons.ts's "shape is the primary channel" rule exists to prevent,
// and which colour cannot rescue in glare or in greyscale. So this one is
// HOLLOW: a triangular band with the exclamation standing in the empty middle.
// Solid-versus-outline survives being reduced to a black shape, and
// warningPin.test.ts measures that against every waypoint glyph rather than
// asserting it in prose.

import {
  buildPinImage,
  POI_PIN_PIXEL_RATIO,
  type Glyph,
  type PoiIconImage,
} from './poiIcons'
import { WARNING_PIN } from '../lib/seriousWarnings'

/** Stable image id, and the string the warning layer's `icon-image` resolves
 *  to. Namespaced away from `poi-*` because this is not a waypoint. */
export const WARNING_ICON_ID = 'serious-warning'

/**
 * The hazard triangle, in the same 0-1 box with y running down as every
 * waypoint glyph, and filled even-odd by the same rasteriser.
 *
 * Four rings, and the even-odd rule is what makes them one shape: the outer
 * triangle fills, the inner one cuts the hole that makes it an outline, and
 * the bar and the dot inside that hole cross a third boundary and so fill
 * again. Drawn any other way the exclamation would be a hole in a hole.
 */
export const WARNING_GLYPH: Glyph = [
  // Outer edge, taken right out to the corners of the box - deliberately a
  // little larger than the tent's, so the band is not merely a subset of it.
  [
    [0.5, 0.03],
    [0.99, 0.95],
    [0.01, 0.95],
  ],
  // Inner edge. The gap between the two is the band, and it is thick enough
  // to survive the pin being drawn small on a distant zoom.
  [
    [0.5, 0.26],
    [0.845, 0.83],
    [0.155, 0.83],
  ],
  // The exclamation: a slightly tapered bar over a square dot, both centred
  // and both comfortably inside the inner triangle at their own heights.
  [
    [0.455, 0.4],
    [0.545, 0.4],
    [0.535, 0.66],
    [0.465, 0.66],
  ],
  [
    [0.455, 0.71],
    [0.545, 0.71],
    [0.545, 0.8],
    [0.455, 0.8],
  ],
]

/**
 * The pin, as raw RGBA pixels.
 *
 * `confidence: 'high'` - a solid rim - and that is a statement rather than a
 * default. `severity: serious` is set by a moderator and never self-declared
 * (lib/seriousWarnings.ts), so a warning that reaches this pin has been
 * looked at by a person. The broken rim means "nobody has verified this",
 * which would be the wrong thing to say about the one report on this map that
 * someone had to escalate by hand.
 */
export function buildWarningIcon(): PoiIconImage {
  return buildPinImage({
    sizePx: WARNING_PIN.sizePx,
    pixelRatio: POI_PIN_PIXEL_RATIO,
    glyph: WARNING_GLYPH,
    color: WARNING_PIN.color,
    confidence: 'high',
  })
}
