// The workday pin image (features/VOLUNTEERING.md Phase B, #760).
//
// The same call warningPin.ts made, for the same reason: a pin that looks like
// nothing else on the map is a pin nobody has learned to read. So the body is
// the waypoint disc, the same halo, the same dark hairline edge, drawn by the
// same rasteriser (map/poiIcons.ts). Only the three things that are allowed to
// differ do: size, colour, and the glyph.
//
// THE GLYPH IS A SHOVEL (#1373, the inventory's P38), AND THE SHAPE IS
// DOING THE WORK
//
// poiIcons.ts's rule is that shape is the primary channel and colour the
// second - a pin has to survive glare, greyscale, and a hiker who is
// colour-blind. The eight waypoint glyphs are a drop, a house, a tent, a bag,
// two chevrons, a summit, a P and a privy door; warningPin.ts adds a hollow
// triangle. A shovel is a T over a stem over a blade, which is none of those
// in silhouette: the only glyph here with a narrow waist between two wider
// ends.
//
// It used to be a hard hat, and chrome/ModeIcon.tsx claimed - since #1373's
// phase 0 - that "the switch, the read-out above the tab bar and the
// volunteer pin on the map all draw the same shape". The switch and the
// read-out did; the pin did not, and the review's argument for making it
// so is exactly that "the mark on the map and the word in the switch are
// the same thing". So the geometry here is ModeIcon's shovel, upright rather
// than tilted (a tilt reads as motion at 19px and as a smudge at 12px),
// traced as ONE closed outline because the rasteriser fills even-odd: a
// handle, a stem and a blade as three shapes would cancel where they overlap.
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

/** One side of the blade's curve - a quadratic from the blade's corner down
 *  to its point, sampled so the rasteriser gets a curve rather than a
 *  chamfer. `sign` picks the side; the two halves meet at the point. */
function bladeSide(sign: 1 | -1, steps = 6): Array<[number, number]> {
  const [x0, y0] = [0.5 + sign * 0.26, 0.5]
  const [cx, cy] = [0.5 + sign * 0.26, 0.84]
  const [x1, y1] = [0.5, 0.92]
  const points: Array<[number, number]> = []
  for (let i = 1; i < steps; i += 1) {
    const t = i / steps
    const x = (1 - t) * (1 - t) * x0 + 2 * (1 - t) * t * cx + t * t * x1
    const y = (1 - t) * (1 - t) * y0 + 2 * (1 - t) * t * cy + t * t * y1
    points.push([Number(x.toFixed(4)), Number(y.toFixed(4))])
  }
  return points
}

/**
 * The shovel, as one closed outline: across the handle's top, down its
 * right end, in to the stem, down the stem to the blade's shoulder, out to
 * the blade's corner, round to the point, and back up the mirror side.
 *
 * Every figure is ModeIcon.tsx's SHOVEL geometry (handle 0.34-0.66 at the
 * top, stem 0.44-0.56, blade 0.26-0.74 curving to a point) shifted so the
 * whole tool sits in the disc's inner box, the way the waypoint glyphs do.
 */
export const WORKDAY_GLYPH: Glyph = [
  [
    [0.34, 0.08],
    [0.66, 0.08],
    [0.66, 0.2],
    [0.56, 0.2],
    [0.56, 0.5],
    [0.76, 0.5],
    ...bladeSide(1),
    [0.5, 0.92],
    ...bladeSide(-1).reverse(),
    [0.24, 0.5],
    [0.44, 0.5],
    [0.44, 0.2],
    [0.34, 0.2],
  ],
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
