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

  // A MEMBER BADGE (#524, and #611 which moved it here from a footer band).
  //
  // Big enough to carry a silhouette rather than a colour - 14 CSS px at the
  // standard pin, which puts its glyph at 7.1 CSS px, over the 7 px floor
  // poiIcons.test.ts holds and well clear of the 5.7 px that was reported as
  // unreadable on a real screen. Small enough that a hiker reads it as extra
  // information about a shelter rather than as a fourth pin.
  const badgeRadius = rOuter * 0.37
  // Far enough out that a badge crosses only the halo ring and NEVER the disc,
  // which is what leaves the anchor's own glyph at full size - the whole point
  // of moving off the band. The clearance is thin (0.4 CSS px at the standard
  // pin) and it is an invariant rather than a look, so the test suite holds it.
  const badgeRing = rOuter * 1.16
  // Thinner rings than the pin's own 1/6 and 1/15. At this size the pin's
  // proportions would spend a fifth of the badge on a halo whose only job here
  // is separating it from the disc beneath it - the dark hairline outside is
  // what does that work, and the extra room goes to the glyph.
  const badgeDisc = badgeRadius * 0.8

  return {
    // No `pixels` here any more, and its absence is the point: a site pin's
    // IMAGE is bigger than its pin, so a field on this object named for the size
    // that was passed in would be read as the image's the first time somebody
    // needed one. {@link sitePinPadding} is where the difference lives.
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
    /**
     * A member badge, for a SITE pin (#524, #611).
     *
     * The same pin at badge scale rather than a second visual language: an
     * accent disc, the category's own silhouette on it in halo white, a white
     * ring and the dark hairline outside that. The ring is what keeps a badge
     * legible where it crosses the parent's halo.
     *
     * NOT SIZED FOR THE CURRENT DISTRIBUTION, and that is deliberate - a badge
     * is the same size whatever a pin carries, so the case worth holding room
     * for is three. Of the 295 sites the 2026-08-13 publish produced, 169 carry
     * one member category (57%), 123 carry two (42%) and three carry three (1%),
     * and that 1% is measuring a DATA GAP rather than the trail: 153 of those
     * sites are privy-only and only 11 water POIs are members of anything, while
     * #529 measured that 97% of shelters have no mapped water source within
     * 250 m and observed that nearly every A.T. shelter has water in reality.
     * Close that gap and privy+water becomes ordinary and privy+campsite+water
     * common.
     *
     * WHERE THIS RUNS OUT. Three badges already fan from twelve o'clock to
     * three. A fourth member category would either tighten the pitch below what
     * the badges can take or wrap past three o'clock into the lower right, which
     * is a different look and wants the same real screen this one got rather
     * than a fraction adjusted in advance.
     */
    badge: {
      radius: badgeRadius,
      /** How far a badge's centre sits from the pin's own. */
      ring: badgeRing,
      /** The dark hairline, and the disc inside the white ring inside it. */
      edgeWidth: badgeRadius * 0.06,
      rDisc: badgeDisc,
      /** Slightly fuller than the pin's 0.86, which it can afford: these are
       *  single silhouettes on a small disc, and the corners still clear it. */
      glyphBox: badgeDisc * Math.SQRT2 * 0.9,
      /**
       * Angle between two badges, so neighbours clear each other by a
       * fourteenth of a badge rather than merely touching.
       *
       * Derived rather than typed out, because it is a consequence of the two
       * sizes above: change either and the fan re-spaces itself instead of
       * quietly overlapping.
       */
      pitch: 2 * Math.asin((badgeRadius * 1.07) / badgeRing),
    },
  }
}

export type PinGeometry = ReturnType<typeof pinGeometry>

/**
 * Where each member badge sits, as an offset from the pin's centre.
 *
 * Centred on the 45-degree axis with the first member at the top running
 * clockwise, so a pin carrying one member has it square in the corner and a pin
 * carrying three fans them from twelve o'clock to three. The order is
 * SITE_MEMBER_TYPES', which is fixed - so a hiker who learns where the privy
 * badge sits on one pin finds it in the same place on the next.
 */
export function badgeCenters(
  count: number,
  badge: PinGeometry['badge'],
): readonly { x: number; y: number }[] {
  const start = -Math.PI / 4 - (badge.pitch * (count - 1)) / 2

  return Array.from({ length: count }, (_, index) => {
    const angle = start + badge.pitch * index
    return { x: Math.cos(angle) * badge.ring, y: Math.sin(angle) * badge.ring }
  })
}

/**
 * How far past its own edge a site pin has to be padded, in CSS pixels.
 *
 * Badges hang outside the rim, so the image has to grow to hold them - and it
 * grows SYMMETRICALLY, which is the whole reason map/poiLayers.ts needs no
 * `icon-offset`: the disc stays at the centre of the image, so it stays on the
 * hiker's coordinate at every zoom.
 *
 * Per member count rather than one padding for every site pin, because the
 * padding is what MapLibre's collision box is made of. A pin carrying one member
 * needs 4 px and a pin carrying three needs 10; giving the first the second's
 * box would evict neighbours for room it is not using, on 57% of sites.
 *
 * Whole pixels, so the image is an integer number of pixels wide at any integer
 * pixel ratio.
 */
export function sitePinPadding(memberCount: number, sizePx = POI_PIN_SIZE): number {
  if (memberCount <= 0) return 0

  const { rOuter, badge } = pinGeometry(sizePx)
  let reach = 0
  for (const { x, y } of badgeCenters(memberCount, badge)) {
    reach = Math.max(reach, Math.abs(x) + badge.radius, Math.abs(y) + badge.radius)
  }

  return Math.max(0, Math.ceil(reach - rOuter))
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
  /**
   * The categories riding this pin, in the order they are drawn (#524).
   *
   * Empty or omitted draws the plain pin, unchanged - which is what every pin
   * that is not a site anchor gets, and what a phone that downloaded before #523
   * gets for everything.
   */
  members?: readonly string[]
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
  members = [],
}: PinSpec): PoiIconImage {
  const geometry = pinGeometry(sizePx * pixelRatio)
  const disc = parseHex(color)
  const halo = parseHex(PIN_HALO_COLOR)
  const edge = parseHex(PIN_EDGE_COLOR)

  const { rOuter, rDisc, edgeWidth, glyphBox, badge } = geometry
  // The image is the pin plus whatever the badges hang past it, and the pin sits
  // in the middle of it. A pin carrying nothing pads by nothing and is therefore
  // the exact image it always was, byte for byte.
  const pad = sitePinPadding(members.length, sizePx) * pixelRatio
  const pixels = sizePx * pixelRatio + pad * 2
  const center = pixels / 2
  // Each badge, with its own accent and silhouette. The colour pair is the SAME
  // one the contrast assertion in poiIcons.test.ts already proves for every type
  // - a type's colour against PIN_HALO_COLOR - so a badge clears WCAG AA by
  // numbers that were already measured rather than by new ones.
  const badges = badgeCenters(members.length, badge).map((spot, index) => ({
    ...spot,
    glyph: GLYPHS[members[index]] ?? GLYPHS[UNKNOWN_POI_TYPE],
    ink: parseHex(poiColor(members[index])),
  }))

  /** The badge covering this offset from the centre, if any covers it. */
  function badgeInkAt(dx: number, dy: number): readonly [number, number, number] | null {
    for (const spot of badges) {
      const bx = dx - spot.x
      const by = dy - spot.y
      const distance = Math.hypot(bx, by)
      if (distance > badge.radius) continue

      if (distance > badge.radius - badge.edgeWidth) return edge
      if (distance > badge.rDisc) return halo

      const gx = (bx + badge.glyphBox / 2) / badge.glyphBox
      const gy = (by + badge.glyphBox / 2) / badge.glyphBox
      return insideGlyph(spot.glyph, gx, gy) ? halo : spot.ink
    }

    return null
  }

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

          // Badges are drawn OVER the pin, so they are asked first. They never
          // reach the disc - see `badge.ring` - so what one can cover is the halo
          // ring, the rim and the paper outside it, never the anchor's own glyph.
          let ink = badgeInkAt(dx, dy)

          if (ink === null) {
            if (distance <= rDisc) {
              const gx = (dx + glyphBox / 2) / glyphBox
              const gy = (dy + glyphBox / 2) / glyphBox
              ink = insideGlyph(glyph, gx, gy) ? halo : disc
            } else if (distance <= rOuter && rimHasInk(dx, dy, confidence)) {
              ink = distance <= rOuter - edgeWidth ? halo : edge
            }
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
export function buildPoiIcon(
  type: string,
  confidence: PoiConfidence,
  members: readonly string[] = [],
): PoiIconImage {
  return buildPinImage({
    sizePx: POI_PIN_SIZE,
    pixelRatio: POI_PIN_PIXEL_RATIO,
    glyph: GLYPHS[type] ?? GLYPHS[UNKNOWN_POI_TYPE],
    color: poiColor(type),
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

  return [...plain, ...sited]
}
