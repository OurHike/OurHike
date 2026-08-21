// The workday pin image (features/VOLUNTEERING.md Phase B, #760).
//
// The same call warningPin.ts made, for the same reason: a pin that looks like
// nothing else on the map is a pin nobody has learned to read. So the body is
// the waypoint disc, the same halo, the same dark hairline edge, drawn by the
// same rasteriser (map/poiIcons.ts). Only the three things that are allowed to
// differ do: size, colour, and the glyph.
//
// THE GLYPH IS A HARD HAT, AND THE SHAPE IS DOING THE WORK
//
// poiIcons.ts's rule is that shape is the primary channel and colour the
// second - a pin has to survive glare, greyscale, and a hiker who is
// colour-blind. The eight waypoint glyphs are a drop, a house, a tent, a bag,
// two chevrons, a summit, a P and a privy door; warningPin.ts adds a hollow
// triangle. A hat is a wide flat brim with a dome over it, which is none of
// those in silhouette: it is the only glyph here that is wider than it is tall
// and flat along the bottom.
//
// Drawn as ONE ring rather than a dome plus a brim, because the rasteriser
// fills even-odd: two overlapping rings would cancel where they overlap and
// punch a hole through the middle of the hat.
//
// THE COLOUR
//
// @unvalidated The olive `#556011` is picked, not measured against anybody's
// design system - it is not one of the eight accents in poiIcons.ts, and there
// was no token left to reuse. Two bars it does clear, and workdayPin.test.ts
// computes both rather than trusting this comment: 4.5:1 against the halo it
// is drawn under (the bar FEATURES.md's waypoint icon spec sets), and at least
// 30 degrees of hue from every existing accent and from the closure red, which
// is what stops "one colour in glare" (poiIcons.ts's own phrase). What would
// settle it properly is the maintainer's eye on a real screen in real
// sunlight, which is #105's field pass rather than a number this file can
// compute.
//
// WHY IT IS NOT A WAYPOINT COLOUR AT ALL
//
// A workday is not a place. It is an event with a date, drawn on a layer that
// is deliberately never baked into an offline package because it expires
// (lib/workProjects.ts). Giving it a waypoint accent would file it visually
// among the things that are still there next month.

import {
  buildPinImage,
  POI_PIN_PIXEL_RATIO,
  type Glyph,
  type PoiIconImage,
} from './poiIcons'

/** Stable image id, and what the workday layer's `icon-image` resolves to.
 *  Namespaced away from `poi-*` because this is not a waypoint. */
export const WORKDAY_ICON_ID = 'work-project'

/** The disc accent - see the header for the two bars it clears. */
export const WORKDAY_COLOR = '#556011'

/**
 * The pin's drawn size, in CSS pixels.
 *
 * `POI_PIN_SIZE` exactly, unlike the serious warning, which is larger. A
 * workday is an invitation rather than a hazard, and a pin drawn bigger than
 * a shelter would be claiming a priority over the hiker's own trail that this
 * feature explicitly does not have: VOLUNTEERING.md's whole posture is an
 * offer, and #761's four rules exist to stop the volunteering surfaces
 * pressing on anybody.
 */
export { POI_PIN_SIZE as WORKDAY_PIN_SIZE } from './poiIcons'

/** Points along a half-circle, in the 0-1 glyph box with y running down.
 *  From the right end of the diameter over the top to the left end. */
function dome(cx: number, cy: number, r: number, steps = 14): Array<[number, number]> {
  const points: Array<[number, number]> = []
  for (let i = 0; i <= steps; i += 1) {
    const angle = Math.PI * (i / steps)
    points.push([
      Number((cx + r * Math.cos(angle)).toFixed(4)),
      // Minus, because y runs down: the arc has to go UP over the brim.
      Number((cy - r * Math.sin(angle)).toFixed(4)),
    ])
  }
  return points
}

/**
 * The hard hat, as one closed outline: along the brim, up its right edge,
 * over the dome, down the left edge, closed by the rasteriser.
 *
 * The brim runs wider than the dome on both sides, which is the part that
 * makes the silhouette read as a hat rather than as a tombstone.
 */
export const WORKDAY_GLYPH: Glyph = [
  [[0.06, 0.78], [0.94, 0.78], [0.94, 0.64], ...dome(0.5, 0.64, 0.3), [0.06, 0.64]],
]

/** The pin image, ready for `map.addImage`. */
export function buildWorkdayIcon(
  sizePx: number,
  pixelRatio = POI_PIN_PIXEL_RATIO,
): PoiIconImage {
  return buildPinImage({
    sizePx,
    pixelRatio,
    glyph: WORKDAY_GLYPH,
    color: WORKDAY_COLOR,
    // A solid rim. `confidence` says whether anybody has verified the PLACE,
    // and a workday is not a place - the club that posted it is the source,
    // and the broken rim would be claiming a doubt about the wrong thing.
    confidence: 'high',
  })
}
