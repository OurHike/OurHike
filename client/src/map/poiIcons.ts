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
// Confidence rides on the fill, not on the colour or the glyph: a filled pin
// is a POI somebody has verified exists, a HOLLOW one - paper inside an accent
// ring - is a POI nobody has (#1682, which replaced WIREFRAMES.md §11's broken
// rim; a 1.5 px hairline has no room for dashes). That is deliberately a
// different channel from staleness, which is about when a human last looked
// at a POI that is known to be real. The coin below - the serious warning and
// the workday pin - keeps the broken rim, and neither ever draws one.

import { POI_TYPES, type PoiType } from '../lib/config'
import { LOUD_POI_TYPES } from './poiPriority'
import { SITE_ANCHOR_TYPES, SITE_MEMBER_TYPES } from './poiSites'

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
 * ordering was built to absorb: POI_PRIORITY (map/poiPriority.ts) decides
 * who is drawn as a pin and who falls back to a dot.
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
  // The ninth (#1197), and there was no comfortable room left.
  //
  // THE FIRST ATTEMPT WAS AN OLIVE AT HUE 58, AND IT WAS WRONG in a way worth
  // leaving on the record: it was checked against every hue in THIS table and
  // against the closure red, found the 97-degree gap between resupply (26)
  // and shelter (123), and sat in the middle of it. What that search left out
  // is that this table is not the whole palette - map/workdayPin.ts's
  // WORKDAY_COLOR is hue 68, its own test requires 30 degrees of clearance
  // from every accent here, and 58 is 10 away. A measurement against the
  // wrong denominator reads exactly like a measurement.
  //
  // With that band excluded (38-98) the wheel has four openings wide enough to
  // matter - the rest leave under 20 degrees either side - and three are
  // rejected for reasons no test states:
  //
  //   privy 316 -> resupply 26, through the top of the wheel. The widest
  //     separation on offer (35 degrees at hue 351), and 17 degrees off the
  //     closure red. That CLEARS the 15-degree bar. It fails the sentence the
  //     bar was written for - "a pin that reads at a glance as do not walk
  //     down there is a worse failure than a dull palette" - which is not a
  //     threshold to squeak past by two degrees.
  //   98 -> shelter 123. Exactly 30.1 degrees off the workday pin, against a
  //     bar of 30. One rounding away from the failure this whole note is
  //     about.
  //   campsite 125 -> viewpoint 176. A third green, on a green basemap, for
  //     the class map/labelLadder.ts ranks FIRST. Passing every bar and being
  //     the hardest pin on the map to find is the wrong trade.
  //
  //   crossing 268 -> privy 316. Taken, at 292.
  //
  // Measured, and poiIcons.test.ts and workdayPin.test.ts compute all of it
  // rather than taking this comment's word: 5.52:1 on the halo (bar 4.5),
  // 23.7 degrees off its nearest neighbour crossing, 76 off the closure red,
  // 137 off the workday pin.
  //
  // ITS 24 DEGREES ARE THE TIGHTEST PAIR IN THIS TABLE BAR ONE, and saying so
  // is more use than the number alone. Hue is not the only channel: crossing
  // was a muted grey-violet (saturation 0.32, contrast 6.91) and this is a
  // clearer magenta-violet (0.42, 5.52), which is the same two-channel
  // separation shelter and campsite already ship on 2.4 degrees of hue. The
  // family is deliberate too - parking (229) and this are the two gateway
  // classes and the two ways in, both cool, both off the terrain's own
  // greens and browns. But a ninth accent leans harder on the glyph than the
  // first did, and "shape as the primary channel" is doing real work here.
  //
  // CROSSING HAS SINCE GONE (#1674), so the 268 above is a hue nothing draws
  // any more and the tight pair it made with this one no longer exists. The
  // nearest neighbour now is privy, 24.5 degrees round the other side
  // (316.0 against 291.5, computed from the two hexes), which is the gap the
  // choice of 292 always left there. Left where it was rather than re-centred:
  // moving an accent every hiker has already learned buys nothing a test asks
  // for.
  trailhead: '#9944a7',
}

/**
 * For a POI type this build has never heard of.
 *
 * A later import adding a category should put a neutral pin on the map rather
 * than nothing at all. The same call the waypoint lanes USED to make when they
 * dropped an unrecognised type into the ELSE lane - `lib/waypointLanes.ts` was
 * deleted by #1054 when the lanes became chrome/NextUpRail.tsx's cards, and the
 * rail keeps the behaviour (an unknown type falls back to its own label rather
 * than vanishing). The reasoning is what carried over; the file did not.
 * Silently not drawing it would hide real data behind a client release.
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
export function poiIconId(
  type: string,
  confidence: PoiConfidence,
  members: readonly string[] = [],
): string {
  const base = `poi-${type}-${confidence === 'high' ? 'verified' : 'unverified'}`
  // A site pin's id carries what it is carrying, so the style resolves straight
  // from the feature's `site_members` property to an image without a lookup
  // table in between (#524). Empty members give exactly the old id, so every
  // plain pin keeps the name it already had - nothing re-registers.
  return members.length === 0 ? base : `${base}-${members.join('+')}`
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
 *
 * Exported for the third caller, which wants no pixels at all: map/MapIcon.tsx
 * draws these same pins as SVG for the legend, and asks for `pinGeometry(1)` to
 * get every proportion as a fraction of a unit viewBox. That is the whole
 * reason the numbers below are ratios - a legend pin whose rim thickness was
 * typed out a second time in a stylesheet would drift from the map's the first
 * time either moved.
 */
export function pinGeometry(pixels: number) {
  const center = pixels / 2
  const rOuter = center
  const edgeWidth = rOuter / 15
  const haloWidth = rOuter / 6
  const rDisc = rOuter - edgeWidth - haloWidth

  return {
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

export type PinGeometry = ReturnType<typeof pinGeometry>

/**
 * How far past its footprint a site pin has to be padded, in CSS pixels.
 *
 * Badges hang outside the drawn pin, so the image grows to hold them - by
 * less than it did round the coin (#1682): a three-member site is 58 px
 * against 72, because the 17 px badges sit against a 26 px pin inside the
 * 38 px footprint rather than against the footprint's own edge. A plain pin
 * pads by nothing.
 *
 * Per member count rather than one padding for every site pin, because the
 * padding is what MapLibre's collision box is made of: 57% of sites carry one
 * member, and giving them three members' box would evict neighbours for room
 * they are not using.
 *
 * Symmetric, so the pin stays at the centre of its image. Whole pixels, so
 * the image is an integer number of pixels wide at any integer pixel ratio.
 */
export function sitePinPadding(
  memberCount: number,
  sizePx = POI_PIN_SIZE,
  inkPx = POI_PIN_INK_SIZE,
): number {
  if (memberCount <= 0) return 0

  const { badge } = waypointPinGeometry(sizePx, inkPx)
  let reach = 0
  for (const { x, y } of badgeCenters(memberCount, badge)) {
    reach = Math.max(reach, Math.abs(x) + badge.radius, Math.abs(y) + badge.radius)
  }

  return Math.max(0, Math.ceil(reach - sizePx / 2))
}

/** Dash count around the rim of an unverified pin. Even, so the pattern closes
 *  cleanly where the last gap meets the first dash.
 *
 *  Exported for the same reason {@link pinGeometry} is: map/MapIcon.tsx spends
 *  it on an SVG `stroke-dasharray`, and a legend pin dashed to a different
 *  rhythm from the map's would be teaching the wrong rhythm. */
export const RIM_DASHES = 8

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
  // A signpost: a post with one arm pointing off it. The mark actually
  // standing at a trailhead, and the one shape here that says "the walking
  // starts, and it goes that way" (#1197).
  //
  // NOT the footprints the design handoff drew. Two boot prints are four
  // small shapes with a lot of internal detail, and at the 22.8px this pin
  // shrinks to at the seam (POI_PIN_MIN_SCALE) they silt up into one blob -
  // the failure the privy's crescent exists to avoid. A post and an arm are
  // two rectangles and a point, which survive the shrink.
  //
  // Distinct from parking's P by having no counter and an arm off one side,
  // and from the shelter's house by having no roof. poiIcons.test.ts measures
  // the overlap against every other glyph rather than trusting that.
  trailhead: [
    // The post.
    [
      [0.4, 0.06],
      [0.52, 0.06],
      [0.52, 0.96],
      [0.4, 0.96],
    ],
    // The arm, pointed at its far end like every trail sign.
    [
      [0.52, 0.2],
      [0.86, 0.2],
      [0.96, 0.31],
      [0.86, 0.42],
      [0.52, 0.42],
    ],
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
  return glyphPath(GLYPHS[type] ?? GLYPHS[UNKNOWN_POI_TYPE])
}

/**
 * Any glyph as SVG path data, for the ones that are not keyed by POI type -
 * the hazard triangle (map/warningPin.ts) is the customer, and it is spelled
 * out there rather than in {@link GLYPHS} because a serious warning is not a
 * waypoint.
 */
export function glyphPath(glyph: Glyph): string {
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

/**
 * The disc colour for a POI type, falling back for one this build has never
 * heard of - the same pairing {@link buildPoiIcon} draws with, so a pin and
 * anything drawn to match it cannot disagree about the accent.
 */
export function poiColor(type: string): string {
  return type in POI_COLORS ? POI_COLORS[type as PoiType] : POI_FALLBACK_COLOR
}

/** Even-odd crossing count, which is what gives the tent its doorway.
 *  Exported for map/atcNoticeMark.ts, which draws the hazard triangle bare
 *  (no disc) and needs the same fill rule the pins use for it. */
export function insideGlyph(glyph: Glyph, x: number, y: number): boolean {
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
 *  only when nobody has verified the POI exists.
 *
 *  Exported for map/positionMark.ts, whose ring breaks into these same eight
 *  dashes when the GPS fix is stale (#1581) - one rhythm, so a hiker who has
 *  learned what a broken rim means on a pin is not taught a second one. */
export function rimHasInk(dx: number, dy: number, confidence: PoiConfidence): boolean {
  if (confidence === 'high') return true

  const turns = (Math.atan2(dy, dx) / (Math.PI * 2) + 1) % 1
  return Math.floor(turns * RIM_DASHES * 2) % 2 === 0
}

/** `#rrggbb` to a channel triple.
 *
 *  Exported for map/atcNoticeMark.ts, which rasterises a shape this module's
 *  scanline path cannot draw (a burst is polar, not a polygon) but which has to
 *  put down exactly the same bytes for the same hex string. */
export function parseHex(hex: string): readonly [number, number, number] {
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
  const pixels = sizePx * pixelRatio
  const geometry = pinGeometry(pixels)
  const disc = parseHex(color)
  const halo = parseHex(PIN_HALO_COLOR)
  const edge = parseHex(PIN_EDGE_COLOR)

  const { center, rOuter, rDisc, edgeWidth, glyphBox } = geometry

  const data = new Uint8ClampedArray(pixels * pixels * 4)
  const step = 1 / SUPERSAMPLE
  const samples = SUPERSAMPLE * SUPERSAMPLE
  // How far a pixel's furthest SAMPLE can sit from its centre. Samples are on a
  // sub-grid inset by half a step, so this is the half-diagonal of that grid -
  // and it is what makes the skip below exact rather than approximate: a pixel
  // further than this from the pin cannot have a sample in it.
  const reach = Math.SQRT2 * (0.5 - step / 2)

  for (let py = 0; py < pixels; py += 1) {
    for (let px = 0; px < pixels; px += 1) {
      if (Math.hypot(px + 0.5 - center, py + 0.5 - center) > rOuter + reach) continue

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
            const gx = (dx + glyphBox / 2) / glyphBox
            const gy = (dy + glyphBox / 2) / glyphBox
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

// ---------------------------------------------------------------------------
// THE WAYPOINT PIN (#1682), which is no longer the coin above.
//
// The maintainer, 2026-09-26: "Having so many icons display on the map at once
// can be difficult to read." Five redrawings of the same 301 real waypoints
// (the UA release 2026-09-24-2, Harriman at z10) went to them as a poll, and
// they chose E: a slimmer pin, the categories under the top four made quiet,
// unverified drawn hollow, and a site's members as smaller badges. Measured on
// those drawings, not on the app: pin ink went from 32% of the screen to 18%,
// and the dark-or-saturated share of it from 20% to 5%.
//
// The coin stays for the pins that are NOT waypoints - the serious warning and
// the workday pin draw with buildPinImage above, unchanged, and they now
// outrank a waypoint by weight as well as by size.

/**
 * The waypoint pin's drawn diameter in CSS pixels, inside its
 * {@link POI_PIN_SIZE} footprint.
 *
 * TWO NUMBERS ON PURPOSE. The image stays 38 px square and the pin is drawn
 * 26 px across in the middle of it, so everything that is a fact about the
 * FOOTPRINT keeps the value the maintainer approved on 2026-09-26 (#1676):
 * the collision box, and so how many pins place at a zoom and how much paper
 * sits between them; the tap target (map/poiPinProbe.ts); the room a card
 * leaves. What changes is only what is inked. A pin that shrank its footprint
 * as well would let the collision engine pack a third more pins into the same
 * screen, which is the clutter this was for.
 *
 * @unvalidated 26 is the drawn option's number, chosen by eye in a browser
 * against the real Harriman waypoints. Nobody has looked at it on a phone in
 * sun. What would settle it: whether a hiker at arm's length can still name a
 * water pin's droplet at z10.
 */
export const POI_PIN_INK_SIZE = 26

/**
 * How pale a quiet pin's disc is: its accent mixed this far toward paper.
 *
 * The drawing's number, chosen by eye, and it happens to sit just inside the
 * limit that matters: the glyph is drawn in the full accent ON this tint, and
 * resupply's orange is the tightest pair at 4.61:1 against WCAG AA's 4.5.
 * Any less pale and resupply fails; poiIcons.test.ts computes every quiet
 * type rather than trusting this comment.
 *
 * @unvalidated as a paleness: the contrast is measured, the "quiet enough to
 * recede, loud enough to find" is a browser judgement. What would settle it:
 * whether a hiker looking for parking on a phone in sun finds the pale P as
 * fast as they found the solid one.
 */
export const QUIET_TINT = 0.82

/**
 * A site member's badge, across, in CSS pixels at full size (#1682).
 *
 * Chosen by the maintainer from the app built three ways and photographed on
 * Limestone Spring Shelter (poll, 2026-09-26): 14 (the coin's badge-to-pin
 * proportion, glyph 7.5 px - a size #611 had already found too quiet), 17
 * (glyph 9.1 px) and 21 (the coin's badge unchanged, glyph 11.2 px, nearly as
 * big as the pin it rides).
 *
 * @unvalidated on a phone: chosen from sandbox frames at 2x. What would settle
 * it: whether a hiker can say "there is a privy at this shelter" from the map
 * alone at z12, in sun, without tapping.
 */
export const MEMBER_BADGE_SIZE = 17

/** `--black` at this alpha, one sliver below the pin. The dark edge the coin
 *  spends r/15 on, replaced by something that only lifts. */
export const PIN_SHADOW_COLOR = '#14130f'
export const PIN_SHADOW_ALPHA = 0.28

/** Is this type drawn full colour, or quiet? The maintainer's four tiers
 *  (2026-09-26, #1676): shelters/campsites, water, trailheads, then everything
 *  else - and "everything else" is the quiet tier (#1682), unknown types
 *  included. */
export function poiTier(type: string): 'loud' | 'quiet' {
  return LOUD_POI_TYPES.includes(type) ? 'loud' : 'quiet'
}

/**
 * Every proportion of the waypoint pin, in image pixels, as fractions of its
 * drawn diameter - the same single-knob rule {@link pinGeometry} keeps, and
 * exported for the same second caller: map/MapIcon.tsx draws the legend's pin
 * from `waypointPinGeometry(1, 1)`, a unit box the size of the drawn pin.
 *
 * `pixels` is the image's side (the footprint, at its pixel ratio) and only
 * places the centre; `inkPixels` is the drawn diameter every width below is a
 * fraction of. Each is written as CSS px at {@link POI_PIN_INK_SIZE}, so the
 * numbers read as what a hiker sees at full size.
 */
export function waypointPinGeometry(pixels: number, inkPixels: number) {
  const unit = inkPixels / POI_PIN_INK_SIZE
  const rInk = inkPixels / 2
  // A 1.5 px paper hairline, where the coin spent 7.3 px on a dark edge and a
  // cream halo. It separates a pin from a darker map and from a neighbour; on
  // pale paper the disc's own colour does that.
  const hairline = 1.5 * unit
  const rDisc = rInk - hairline
  const badgeRadius = (MEMBER_BADGE_SIZE * unit) / 2
  // A paper ring, no dark edge - the slim pin's own treatment at badge scale.
  const badgeStroke = badgeRadius * 0.16
  const badgeDisc = badgeRadius - badgeStroke
  // Tangent to the pin's disc with a sliver of daylight, the rule the coin's
  // badges kept (#611): a badge never covers the anchor's own glyph.
  const badgeRing = rDisc + badgeRadius + hairline / 5
  return {
    center: pixels / 2,
    rInk,
    rDisc,
    /** The glyph box, by the same rule as the coin's: its half-diagonal kept
     *  inside the disc with 14% to spare. */
    glyphBox: rDisc * Math.SQRT2 * 0.86,
    /** An unverified pin's accent ring, just inside the hairline. */
    hollowRing: 2 * unit,
    /** A quiet pin's faint ring, the same place. */
    quietRing: 1 * unit,
    shadowOffset: 0.8 * unit,
    /**
     * A site member, as its own small pin: the member's accent disc, its glyph
     * in paper, a paper ring (#524, #611, #1682). Colour-only pips were drawn
     * first; the maintainer, shown them on the real map (poll, 2026-09-26):
     * "When you put the icon in the upper right, make it the icon, not just
     * the pin."
     *
     * Sized for three, the call the coin's badges made: of the 295 sites the
     * 2026-08-13 publish produced, 57% carried one member category, 42% two
     * and 1% three, and #529 measured that the third is mostly a data gap
     * (97% of shelters with no mapped water within 250 m) rather than rare on
     * the trail.
     */
    badge: {
      radius: badgeRadius,
      stroke: badgeStroke,
      rDisc: badgeDisc,
      glyphBox: badgeDisc * Math.SQRT2 * 0.9,
      /** How far a badge's centre sits from the pin's own. */
      ring: badgeRing,
      /** Neighbours clear each other by a fourteenth of a badge, derived from
       *  the two sizes rather than typed, so a resize re-spaces the fan. */
      pitch: 2 * Math.asin((badgeRadius * 1.07) / badgeRing),
    },
  }
}

export type WaypointPinGeometry = ReturnType<typeof waypointPinGeometry>

/**
 * Where each member badge sits, as an offset from the pin's centre: fanned
 * about the 45-degree axis, first member at the top, in SITE_MEMBER_TYPES'
 * fixed order - so a hiker who learns where the privy sits on one shelter
 * finds it in the same place on the next.
 */
export function badgeCenters(
  count: number,
  badge: WaypointPinGeometry['badge'],
): readonly { x: number; y: number }[] {
  const start = -Math.PI / 4 - (badge.pitch * (count - 1)) / 2
  return Array.from({ length: count }, (_, index) => {
    const angle = start + badge.pitch * index
    return { x: Math.cos(angle) * badge.ring, y: Math.sin(angle) * badge.ring }
  })
}

/** `#rrggbb` mixed toward `#rrggbb` by `t` (0 is `a`, 1 is `b`). */
export function mixHex(a: string, b: string, t: number): string {
  const [ar, ag, ab] = parseHex(a)
  const [br, bg, bb] = parseHex(b)
  return `#${[ar + (br - ar) * t, ag + (bg - ag) * t, ab + (bb - ab) * t]
    .map((c) => Math.round(c).toString(16).padStart(2, '0'))
    .join('')}`
}

/**
 * The four inks one waypoint pin is drawn in, by tier and confidence. One home
 * for them, so the map's raster and the legend's SVG cannot pick differently.
 *
 *  - loud, verified: the accent disc with the glyph in paper - the coin's
 *    colours at two-thirds the size.
 *  - quiet, verified: a pale tint of the accent, a faint ring in it, and the
 *    glyph in the full accent. Present, legible, a step back.
 *  - unverified, either tier: HOLLOW - paper inside, an accent ring, the glyph
 *    in the accent. It replaces the broken rim (WIREFRAMES.md §11), which a
 *    1.5 px hairline could not carry. Still the rim, still no colour of its
 *    own: a hollow pin is the same category, provisionally.
 */
export function waypointPinInks(type: string, confidence: PoiConfidence): SlimPinInks {
  const accent = poiColor(type)
  if (confidence === 'low') {
    return { fill: PIN_HALO_COLOR, ring: accent, ringWidth: 'hollow', glyph: accent }
  }
  if (poiTier(type) === 'quiet') {
    return {
      fill: mixHex(accent, PIN_HALO_COLOR, QUIET_TINT),
      ring: mixHex(accent, PIN_HALO_COLOR, 0.35),
      ringWidth: 'quiet',
      glyph: accent,
    }
  }
  return { fill: accent, ring: null, ringWidth: null, glyph: PIN_HALO_COLOR }
}

type Rgba = readonly [number, number, number, number]

/**
 * The supersampling loop, for a shape given as a function: `shade` answers one
 * sample, in image pixels from the image's centre, with straight RGBA (alpha
 * 0-1) or null for nothing. Averaged in premultiplied alpha, for the reason
 * {@link buildPinImage} gives - and unlike that loop, a sample can itself be
 * part-transparent, which is what the shadow needs.
 */
function rasterise(
  pixels: number,
  reach: number,
  shade: (dx: number, dy: number) => Rgba | null,
): Uint8ClampedArray {
  const data = new Uint8ClampedArray(pixels * pixels * 4)
  const step = 1 / SUPERSAMPLE
  const samples = SUPERSAMPLE * SUPERSAMPLE
  const center = pixels / 2
  const slack = Math.SQRT2 * (0.5 - step / 2)

  for (let py = 0; py < pixels; py += 1) {
    for (let px = 0; px < pixels; px += 1) {
      if (Math.hypot(px + 0.5 - center, py + 0.5 - center) > reach + slack) continue
      let r = 0
      let g = 0
      let b = 0
      let a = 0
      for (let sy = 0; sy < SUPERSAMPLE; sy += 1) {
        for (let sx = 0; sx < SUPERSAMPLE; sx += 1) {
          const ink = shade(
            px + (sx + 0.5) * step - center,
            py + (sy + 0.5) * step - center,
          )
          if (ink === null) continue
          r += ink[0] * ink[3]
          g += ink[1] * ink[3]
          b += ink[2] * ink[3]
          a += ink[3]
        }
      }
      if (a === 0) continue
      const at = (py * pixels + px) * 4
      data[at] = r / a
      data[at + 1] = g / a
      data[at + 2] = b / a
      data[at + 3] = (a / samples) * 255
    }
  }
  return data
}

/** The inks a slim pin is drawn in - {@link waypointPinInks} for a waypoint. */
export interface SlimPinInks {
  fill: string
  ring: string | null
  ringWidth: 'hollow' | 'quiet' | null
  glyph: string
}

export interface SlimPinSpec {
  /** The footprint - {@link POI_PIN_SIZE}. */
  sizePx: number
  /** What is drawn inside it - {@link POI_PIN_INK_SIZE}. */
  inkPx: number
  pixelRatio: number
  glyph: Glyph
  inks: SlimPinInks
  /** A site's other categories, as badges on the rim (#524, #1682). */
  members?: readonly string[]
}

/**
 * One slim pin, as raw RGBA pixels: every waypoint, and since #1682 the
 * workday pin (map/workdayPin.ts) - one rasteriser for both, for the reason
 * {@link buildPinImage} is shared with the warning pin.
 */
export function buildSlimPinImage({
  sizePx,
  inkPx,
  pixelRatio,
  glyph,
  inks,
  members = [],
}: SlimPinSpec): PoiIconImage {
  const pad = sitePinPadding(members.length, sizePx, inkPx) * pixelRatio
  const pixels = sizePx * pixelRatio + pad * 2
  const geometry = waypointPinGeometry(pixels, inkPx * pixelRatio)
  const { rInk, rDisc, glyphBox, badge } = geometry
  const opaque = (hex: string): Rgba => [...parseHex(hex), 1]
  const paper = opaque(PIN_HALO_COLOR)
  const fill = opaque(inks.fill)
  const glyphInk = opaque(inks.glyph)
  const ring = inks.ring === null ? null : opaque(inks.ring)
  const ringWidth =
    inks.ringWidth === 'hollow'
      ? geometry.hollowRing
      : inks.ringWidth === 'quiet'
        ? geometry.quietRing
        : 0
  const shadow: Rgba = [...parseHex(PIN_SHADOW_COLOR), PIN_SHADOW_ALPHA]
  const badges = badgeCenters(members.length, badge).map((spot, index) => ({
    ...spot,
    glyph: GLYPHS[members[index]] ?? GLYPHS[UNKNOWN_POI_TYPE],
    ink: opaque(poiColor(members[index])),
  }))

  const data = rasterise(pixels, pixels / 2, (dx, dy) => {
    // Badges over the pin: a member's accent disc, its glyph in paper, a
    // paper ring. They never reach the disc (`badge.ring`), so what one can
    // cover is the hairline, the shadow and the paper beyond.
    for (const spot of badges) {
      const bx = dx - spot.x
      const by = dy - spot.y
      const d = Math.hypot(bx, by)
      if (d > badge.radius) continue
      if (d > badge.rDisc) return paper
      const gx = (bx + badge.glyphBox / 2) / badge.glyphBox
      const gy = (by + badge.glyphBox / 2) / badge.glyphBox
      return insideGlyph(spot.glyph, gx, gy) ? paper : spot.ink
    }
    const distance = Math.hypot(dx, dy)
    if (distance <= rInk) {
      if (distance > rDisc) return paper
      const gx = (dx + glyphBox / 2) / glyphBox
      const gy = (dy + glyphBox / 2) / glyphBox
      if (insideGlyph(glyph, gx, gy)) return glyphInk
      if (ring !== null && distance > rDisc - ringWidth) return ring
      return fill
    }
    if (Math.hypot(dx, dy - geometry.shadowOffset) <= rInk) return shadow
    return null
  })

  return { width: pixels, height: pixels, data }
}

/** One waypoint pin, as raw RGBA pixels. */
export function buildWaypointPinImage({
  type,
  confidence,
  ...spec
}: Omit<SlimPinSpec, 'glyph' | 'inks'> & {
  type: string
  confidence: PoiConfidence
}): PoiIconImage {
  return buildSlimPinImage({
    ...spec,
    glyph: GLYPHS[type] ?? GLYPHS[UNKNOWN_POI_TYPE],
    inks: waypointPinInks(type, confidence),
  })
}

/** One waypoint pin, at the one size and palette every waypoint uses. */
export function buildPoiIcon(
  type: string,
  confidence: PoiConfidence,
  members: readonly string[] = [],
): PoiIconImage {
  return buildWaypointPinImage({
    sizePx: POI_PIN_SIZE,
    inkPx: POI_PIN_INK_SIZE,
    pixelRatio: POI_PIN_PIXEL_RATIO,
    type,
    confidence,
    members,
  })
}

/**
 * Every member combination a site pin can carry, as the style will ask for it.
 *
 * The non-empty subsets of SITE_MEMBER_TYPES in that array's own order, which is
 * seven - and the reason the glyph strip is buildable at all where a `+N` badge
 * is not. Distinct categories are bounded at three, so the whole matrix can be
 * pre-registered; N is unbounded, and a site with five campsites would want a
 * "+5" image nobody built.
 */
export function siteMemberCombinations(): readonly string[][] {
  const combinations: string[][] = []
  for (let mask = 1; mask < 2 ** SITE_MEMBER_TYPES.length; mask += 1) {
    combinations.push(SITE_MEMBER_TYPES.filter((_, index) => (mask >> index) & 1))
  }
  return combinations
}

export interface RegisteredPoiIcon {
  id: string
  image: PoiIconImage
  pixelRatio: number
}

/**
 * Built once, then handed out.
 *
 * Every trip to the More tab and back builds a new map, and every new map calls
 * {@link buildPoiIcons} - which is a few hundred milliseconds of scanline
 * rasterising on the main thread, paid again for an answer that cannot have
 * changed. The inputs are module constants, so the second call and the fiftieth
 * have the same output as the first, byte for byte.
 *
 * Safe to share rather than copy: `map.addImage` reads the pixels into its own
 * atlas texture and nothing in this app writes to them afterwards.
 */
let cachedPoiIcons: RegisteredPoiIcon[] | undefined

/**
 * Every pin the style can ask for: each published POI type plus the unknown
 * fallback, each in both confidences.
 *
 * Built from {@link POI_TYPES} rather than from a list kept here, so adding a
 * POI type to config.ts cannot leave the map with a `match` arm pointing at an
 * image that was never registered.
 */
export function buildPoiIcons(): RegisteredPoiIcon[] {
  if (cachedPoiIcons !== undefined) return cachedPoiIcons

  const types: string[] = [...POI_TYPES, UNKNOWN_POI_TYPE]
  const confidences: PoiConfidence[] = ['high', 'low']

  const plain = types.flatMap((type) =>
    confidences.map((confidence) => ({
      id: poiIconId(type, confidence),
      image: buildPoiIcon(type, confidence),
      pixelRatio: POI_PIN_PIXEL_RATIO,
    })),
  )

  // Site variants for the ANCHOR types only (#524). A viewpoint never anchors a
  // site, so building it a footer strip would be 14 images the style can never
  // ask for - and the matrix is small enough to be worth keeping honest.
  const sited = SITE_ANCHOR_TYPES.flatMap((type) =>
    confidences.flatMap((confidence) =>
      siteMemberCombinations().map((members) => ({
        id: poiIconId(type, confidence, members),
        image: buildPoiIcon(type, confidence, members),
        pixelRatio: POI_PIN_PIXEL_RATIO,
      })),
    ),
  )

  cachedPoiIcons = [...plain, ...sited]
  return cachedPoiIcons
}
