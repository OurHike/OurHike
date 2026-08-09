// The pins themselves: one generated image per POI category, per confidence.
//
// Three decisions here are load-bearing rather than cosmetic.
//
//  1. SHAPE is the primary channel, colour is the second one. This is the same
//     rule the blaze line widths follow (style.ts), and for the same reason:
//     these six accent colours sit between 1.06:1 and 2.19:1 of each other, so
//     in the greyscale pass (WIREFRAMES.md `9d`) or in direct sun they are one
//     colour. A droplet is still a droplet. Every category therefore gets a
//     silhouette that survives being reduced to a black shape, and no category
//     is distinguished from another by hue alone.
//
//  2. The images are COMPUTED, not shipped as assets. An offline-first app
//     should not spend a network round trip or a build step on a handful of
//     30px badges, and a pure function is testable in jsdom - which can
//     neither rasterise an SVG nor run a canvas. So the glyphs are polygons
//     and this module contains a small scanline rasteriser, which is the
//     price of both properties.
//
//  3. RED IS NOT AVAILABLE to a POI. Red is spoken for by closures
//     (lib/closureStyle.ts) and by the serious-warning pin, and a spring that
//     reads at a glance as "do not walk down there" is a worse failure than an
//     ugly palette. The test suite holds this.
//
// Confidence rides on the rim, not on the colour or the glyph: a solid rim is
// a POI somebody has verified exists, a broken one is a POI nobody has
// (WIREFRAMES.md §11 - "a dashed pin means never verified to exist"). That is
// deliberately a different channel from staleness, which is about when a human
// last looked at a POI that is known to be real.

import { POI_TYPES, type PoiType } from '../lib/config'

/**
 * Rendered size in CSS pixels.
 *
 * `--space-9` / the header-button size, which is a token this design system
 * already has rather than a number invented for the map. Comfortably inside
 * WIREFRAMES.md's serious-warning pin, which should stay the biggest thing on
 * the map, and which moved up to one full touch target (44px) when this did -
 * a warning pin that a water pin has caught up with has stopped outranking
 * anything.
 *
 * The cost of drawing pins bigger is that fewer of them survive
 * `icon-allow-overlap: false` at a given zoom. That is a trade the collision
 * ordering was built to absorb: POI_PRIORITY in poiLayers.ts decides who
 * survives, and water is first in it.
 */
export const POI_PIN_SIZE = 38

/** Drawn at 2x so the pins stay crisp on a phone. */
export const POI_PIN_PIXEL_RATIO = 2

/**
 * One accent per category, each at least 4.5:1 against the glyph on top of it
 * (FEATURES.md's waypoint icon spec asks for WCAG AA, and poiIcons.test.ts
 * computes the ratios rather than trusting this comment).
 *
 * Values are the design system's own tokens: blaze-blue, pine-700, forest-500,
 * blaze-orange-dark and the Purple blaze. Nothing here is a fresh hex invented
 * for the map.
 */
export const POI_COLORS: Record<PoiType, string> = {
  water: '#1c6ea4',
  shelter: '#284029',
  campsite: '#47784b',
  resupply: '#994e15',
  crossing: '#6a4a8f',
  // The three added with ATC's vista/parking/privy layers, and the first
  // accents here that are not lifted verbatim from tokens/colors.css. Not for
  // want of looking: a pin's disc has to clear 4.5:1 against the near-white
  // halo drawn on it, which rules out every remaining light token
  // (blaze-yellow is 2.5:1, moss-400 3.5:1), and the dark ones that do clear
  // it are either already spoken for (pine-700 is shelter, stone-700 is the
  // fallback pin) or a second orange within a degree of resupply's hue -
  // which is exactly the "one colour in glare" failure this palette is built
  // to avoid.
  //
  // So these fill the three gaps left on the wheel - teal, indigo, plum -
  // each measured against the same bars the tokens were: AA on the halo, a
  // hue of its own, and well clear of the closure red. poiIcons.test.ts
  // computes all three rather than taking this comment's word for it.
  viewpoint: '#12615c',
  parking: '#3f4d8a',
  privy: '#7a2f66',
}

/**
 * For a POI type this build has never heard of.
 *
 * A later import adding a category should put a neutral pin on the map rather
 * than nothing at all - the same call lib/waypointLanes.ts makes when it drops
 * an unrecognised type into the ELSE lane. Silently not drawing it would hide
 * real data behind a client release.
 */
export const POI_FALLBACK_COLOR = '#5a5346'

/** `--paper-0`. The halo and the glyph. It sat lighter than the map's old
 *  cream paper; on the field sheet's white (`MAP_BACKGROUND_COLOR`) the edge
 *  hairline below is what keeps a pin reading as sitting on top. */
export const PIN_HALO_COLOR = '#fffdf7'

/** `--stone-900`, a hairline outside the halo. Without it a pale halo on pale
 *  paper has no edge at all where the topo happens to be blank. */
export const PIN_EDGE_COLOR = '#2b2620'

/** The name the fallback pin is registered under. Not a `PoiType` - that is
 *  the point of it. */
export const UNKNOWN_POI_TYPE = 'unknown'

export type PoiConfidence = 'high' | 'low'

/** Stable image id, and the string the style's `match` expression resolves to. */
export function poiIconId(type: string, confidence: PoiConfidence): string {
  return `poi-${type}-${confidence === 'high' ? 'verified' : 'unverified'}`
}

/**
 * Geometry, in image pixels from the centre outwards.
 *
 * Every one of these is a FRACTION of the pin rather than a fixed pixel count,
 * which is what makes the size a single knob. Written as constants they held
 * their look at exactly one size: drawn bigger, the rim thinned out and the
 * glyph shrank inside a disc that grew around it, so a pin asked to be larger
 * came back not just larger but differently proportioned.
 *
 * A function of the size rather than a set of module constants,
 * because there is now a second pin at a second size - the serious-warning pin
 * at 44px (map/warningPin.ts). Sharing this is the whole reason that pin is a
 * variant of the waypoint spec rather than a visual language of its own.
 */
function pinGeometry(pixels: number) {
  const center = pixels / 2
  const rOuter = center
  const edgeWidth = rOuter / 15
  const haloWidth = rOuter / 6
  const rDisc = rOuter - edgeWidth - haloWidth

  return {
    pixels,
    center,
    rOuter,
    edgeWidth,
    rDisc,
    /**
     * Side of the centred box the glyph is drawn in.
     *
     * Its half-diagonal must stay inside `rDisc` or the corners of a glyph
     * would spill onto the halo - so it is derived from that bound rather than
     * checked against it. The largest box that fits has side `rDisc * √2`; 86%
     * of it leaves the corners some air.
     */
    glyphBox: rDisc * Math.SQRT2 * 0.86,
  }
}

/** Dash count around the rim of an unverified pin. Even, so the pattern closes
 *  cleanly where the last gap meets the first dash. */
const RIM_DASHES = 8

/** Sub-samples per axis. 3x3 is enough to take the stair-stepping off a 60px
 *  circle without making icon generation something to think about. */
const SUPERSAMPLE = 3

export type Point = readonly [number, number]
/** Rings in a normalised glyph box, filled even-odd so a ring inside another
 *  ring - the tent's doorway - cuts a hole instead of filling it. */
export type Glyph = readonly (readonly Point[])[]

function arc(
  cx: number,
  cy: number,
  r: number,
  fromDeg: number,
  toDeg: number,
  steps = 14,
): Point[] {
  const points: Point[] = []
  for (let i = 0; i <= steps; i += 1) {
    const rad = ((fromDeg + ((toDeg - fromDeg) * i) / steps) * Math.PI) / 180
    points.push([cx + r * Math.cos(rad), cy + r * Math.sin(rad)])
  }
  return points
}

/** A zigzag band: a wave that still reads as a wave in silhouette. */
function chevron(top: number, amplitude: number, thickness: number): Point[] {
  const xs = [0.04, 0.27, 0.5, 0.73, 0.96]
  const ys = xs.map((_, i) => top + (i % 2 === 0 ? amplitude : 0))
  return [
    ...xs.map((x, i): Point => [x, ys[i]]),
    ...xs.map((x, i): Point => [x, ys[i] + thickness]).reverse(),
  ]
}

/**
 * The silhouettes, in a 0-1 box with y running down the screen.
 *
 * Bold and geometric on purpose. At 30px in sunlight a faithful line-art icon
 * is a smudge, so each of these is a filled shape that survives being small,
 * being desaturated, and being looked at for a quarter of a second.
 */
const GLYPHS: Record<string, Glyph> = {
  // Droplet: apex over a round bowl.
  water: [[[0.5, 0.02], ...arc(0.5, 0.63, 0.33, -50, 230)]],
  // House: gable roof over a square body, with a doorway cut out of it.
  //
  // The doorway is not decoration. Without it the house is a solid blob that
  // completely CONTAINS the droplet - every pixel of water's glyph sits inside
  // shelter's - and a shape that is a strict subset of another can read as a
  // half-rendered version of it. The cutout breaks the containment, and is why
  // poiIcons.test.ts asserts against subsets rather than only against overlap.
  shelter: [
    [
      [0.5, 0.04],
      [0.97, 0.45],
      [0.84, 0.45],
      [0.84, 0.96],
      [0.16, 0.96],
      [0.16, 0.45],
      [0.03, 0.45],
    ],
    [
      [0.39, 0.62],
      [0.61, 0.62],
      [0.61, 0.96],
      [0.39, 0.96],
    ],
  ],
  // Tent: a triangle with a doorway cut out, so it is never just a triangle.
  // The doorway is small on purpose - drawn any bigger it eats the walls and
  // what is left reads as a bare chevron rather than a tent.
  campsite: [
    [
      [0.5, 0.05],
      [0.95, 0.93],
      [0.05, 0.93],
    ],
    [
      [0.5, 0.62],
      [0.59, 0.93],
      [0.41, 0.93],
    ],
  ],
  // Carried bag: body plus a handle standing clear above it.
  resupply: [
    [
      [0.14, 0.38],
      [0.86, 0.38],
      [0.93, 0.97],
      [0.07, 0.97],
    ],
    [...arc(0.5, 0.38, 0.23, 180, 360), ...arc(0.5, 0.38, 0.15, 360, 180)],
  ],
  // Running water, as two bands - a stream to be crossed, not a stream to drink
  // from, which is what the droplet says.
  crossing: [chevron(0.1, 0.14, 0.15), chevron(0.52, 0.14, 0.15)],
  // Two peaks with a valley between them, and a sun clear of the left one.
  //
  // The peaks alone are the obvious drawing and were not enough: a solid
  // range sits almost entirely inside the resupply bag's body, which the
  // subset check caught at 6% outside it. The sun is what breaks the
  // containment - it is the one part of this glyph in a corner nothing else
  // reaches - and it happens to be the difference between a mountain and a
  // view of one, which is what this category actually means.
  viewpoint: [
    [
      [0.02, 0.93],
      [0.31, 0.3],
      [0.5, 0.62],
      [0.7, 0.15],
      [0.98, 0.93],
    ],
    arc(0.19, 0.17, 0.13, 0, 360),
  ],
  // The letter P, the one waypoint here that is a letter rather than a
  // picture - and it earns the exception, because it is the sign a driver
  // has been reading at every car park for sixty years. A drawn car would be
  // less legible at 38px and less recognised at any size.
  parking: [
    [
      [0.22, 0.04],
      [0.55, 0.04],
      ...arc(0.55, 0.3, 0.26, -90, 90),
      [0.42, 0.56],
      [0.42, 0.96],
      [0.22, 0.96],
    ],
    // The counter, cut out even-odd exactly as the shelter's doorway is -
    // without it the P is a lollipop.
    arc(0.55, 0.3, 0.11, 0, 360),
  ],
  // An outhouse: a wide roof over a narrow box, with the crescent cut into
  // the door. The crescent is the whole reason this is not read as a small
  // shelter at a glance, which at 38px in sun is a real confusion and an
  // embarrassing one - it is also the mark actually carved into privy doors.
  //
  // Drawn as A-minus-B rather than as two rings, because two overlapping
  // circles under an even-odd fill would leave a second, unwanted hole where
  // B sits outside A. The arc endpoints are the two circles' real
  // intersection points, so the ring closes on itself exactly.
  privy: [
    [
      [0.14, 0.16],
      [0.86, 0.16],
      [0.86, 0.3],
      [0.72, 0.3],
      [0.72, 0.96],
      [0.28, 0.96],
      [0.28, 0.3],
      [0.14, 0.3],
    ],
    [...arc(0.485, 0.56, 0.12, 51.6, 308.4), ...arc(0.545, 0.56, 0.093, 278.8, 81.2)],
  ],
  // Diamond: deliberately not any of the above, and obviously a placeholder.
  [UNKNOWN_POI_TYPE]: [
    [
      [0.5, 0.13],
      [0.95, 0.5],
      [0.5, 0.87],
      [0.05, 0.5],
    ],
  ],
}

/**
 * The category silhouette as SVG path data in a unit box (`viewBox="0 0 1 1"`),
 * for chrome that wants the same shape language as the pins - the waypoint
 * card's photo placeholder is the customer. One subpath per ring, so an
 * `evenodd` fill keeps the shelter's doorway open exactly as the rasteriser's
 * crossing count below does.
 *
 * Same fallback as {@link buildPoiIcon}: a type this build has never heard of
 * gets the diamond, not an empty path - the placeholder should show SOMETHING
 * for a POI the map is already drawing as a neutral pin.
 */
export function poiGlyphPath(type: string): string {
  const glyph = GLYPHS[type] ?? GLYPHS[UNKNOWN_POI_TYPE]
  return glyph
    .map(
      (ring) =>
        `M${ring
          // The arcs carry full float precision, which nobody rendering a
          // 56px glyph can see and every DOM snapshot has to carry.
          .map(([x, y]) => `${Number(x.toFixed(4))} ${Number(y.toFixed(4))}`)
          .join('L')}Z`,
    )
    .join('')
}

/** Even-odd crossing count, which is what gives the tent its doorway. */
function insideGlyph(glyph: Glyph, x: number, y: number): boolean {
  let inside = false

  for (const ring of glyph) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
      const [xi, yi] = ring[i]
      const [xj, yj] = ring[j]
      if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
        inside = !inside
      }
    }
  }

  return inside
}

/** True where the rim has ink: everywhere on a verified pin, on the dashes
 *  only when nobody has verified the POI exists. */
function rimHasInk(dx: number, dy: number, confidence: PoiConfidence): boolean {
  if (confidence === 'high') return true

  const turns = (Math.atan2(dy, dx) / (Math.PI * 2) + 1) % 1
  return Math.floor(turns * RIM_DASHES * 2) % 2 === 0
}

function parseHex(hex: string): readonly [number, number, number] {
  const value = Number.parseInt(hex.slice(1), 16)
  return [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff]
}

export interface PoiIconImage {
  width: number
  height: number
  data: Uint8ClampedArray
}

export interface PinSpec {
  /** Rendered size in CSS pixels - {@link POI_PIN_SIZE} for a waypoint. */
  sizePx: number
  /** Drawn at this multiple of `sizePx`, and declared to MapLibre alongside
   *  the image so it lands at the right size on a phone. */
  pixelRatio: number
  /** The silhouette, in a 0-1 box with y running down the screen. */
  glyph: Glyph
  /** Fill behind the glyph. */
  color: string
  /** Solid rim, or the broken one that means "nobody has verified this". */
  confidence: PoiConfidence
}

/**
 * One pin, as raw RGBA pixels.
 *
 * Sub-samples each pixel and averages in PREMULTIPLIED alpha. Averaging the
 * raw channels instead would fringe the whole outer edge with a ring of
 * half-transparent dark pixels, because the transparent samples outside the
 * circle carry a colour of their own into the mean.
 *
 * Exported so the serious-warning pin (map/warningPin.ts) is drawn by THIS
 * rasteriser at a different size and colour, rather than by a second one that
 * would drift from it. Every proportion it uses comes from
 * {@link pinGeometry}, so the two are the same pin at two sizes.
 */
export function buildPinImage({
  sizePx,
  pixelRatio,
  glyph,
  color,
  confidence,
}: PinSpec): PoiIconImage {
  const geometry = pinGeometry(sizePx * pixelRatio)
  const disc = parseHex(color)
  const halo = parseHex(PIN_HALO_COLOR)
  const edge = parseHex(PIN_EDGE_COLOR)

  const { pixels, center, rOuter, rDisc, edgeWidth, glyphBox } = geometry
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
          const x = px + (sx + 0.5) * step
          const y = py + (sy + 0.5) * step
          const dx = x - center
          const dy = y - center
          const distance = Math.hypot(dx, dy)

          let ink: readonly [number, number, number] | null = null

          if (distance <= rDisc) {
            const gx = (x - (center - glyphBox / 2)) / glyphBox
            const gy = (y - (center - glyphBox / 2)) / glyphBox
            ink = insideGlyph(glyph, gx, gy) ? halo : disc
          } else if (distance <= rOuter && rimHasInk(dx, dy, confidence)) {
            ink = distance <= rOuter - edgeWidth ? halo : edge
          }

          if (ink !== null) {
            r += ink[0]
            g += ink[1]
            b += ink[2]
            hits += 1
          }
        }
      }

      const at = (py * pixels + px) * 4
      // Divided by `hits`, not by `samples`: the colour is the mean of the
      // samples that HAD colour, and coverage is carried by alpha alone.
      if (hits > 0) {
        data[at] = r / hits
        data[at + 1] = g / hits
        data[at + 2] = b / hits
        data[at + 3] = (hits / samples) * 255
      }
    }
  }

  return { width: pixels, height: pixels, data }
}

/** One waypoint pin, at the one size and palette every waypoint uses. */
export function buildPoiIcon(type: string, confidence: PoiConfidence): PoiIconImage {
  return buildPinImage({
    sizePx: POI_PIN_SIZE,
    pixelRatio: POI_PIN_PIXEL_RATIO,
    glyph: GLYPHS[type] ?? GLYPHS[UNKNOWN_POI_TYPE],
    color: type in POI_COLORS ? POI_COLORS[type as PoiType] : POI_FALLBACK_COLOR,
    confidence,
  })
}

export interface RegisteredPoiIcon {
  id: string
  image: PoiIconImage
  pixelRatio: number
}

/**
 * Every pin the style can ask for: each published POI type plus the unknown
 * fallback, each in both confidences.
 *
 * Built from {@link POI_TYPES} rather than from a list kept here, so adding a
 * POI type to config.ts cannot leave the map with a `match` arm pointing at an
 * image that was never registered.
 */
export function buildPoiIcons(): RegisteredPoiIcon[] {
  const types: string[] = [...POI_TYPES, UNKNOWN_POI_TYPE]
  const confidences: PoiConfidence[] = ['high', 'low']

  return types.flatMap((type) =>
    confidences.map((confidence) => ({
      id: poiIconId(type, confidence),
      image: buildPoiIcon(type, confidence),
      pixelRatio: POI_PIN_PIXEL_RATIO,
    })),
  )
}
