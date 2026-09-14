// The map's own icons, drawn in the DOM instead of onto the map.
//
// The legend (chrome/Legend.tsx) names what is on screen, and until now named
// it in words alone - so the one panel whose whole job is to teach "this shape
// means water" never showed the shape. This is that shape, and the rule it is
// built on is that there is no second copy of it: every proportion comes from
// pinGeometry(), every colour from POI_COLORS, every silhouette from GLYPHS,
// and the broken rim from RIM_DASHES. A legend pin whose rim thickness was
// typed out again in a stylesheet would drift from the map's the first time
// either moved, and drift is the one failure a legend cannot survive.
//
// SVG rather than the rasteriser the map uses (buildPoiIcon), even though that
// is the literal same-pixels answer. Its output is a Uint8ClampedArray, and
// putting one on screen needs a canvas to turn it into a data URL - which
// jsdom cannot do, so every test of this would be untestable, and which would
// spend a canvas and a blob per row for a 24px badge. pinGeometry(1) hands
// back the same proportions as fractions of a unit box, so the SVG below is
// the same pin expressed in the units a DOM can draw.
//
// Three kinds of thing end up in a legend row, and they are not all pins:
//
//  - A waypoint is a pin - disc, glyph, halo, rim (poiIcons.ts).
//  - A serious warning is the same pin with the three things allowed to differ
//    (map/warningPin.ts): its colour, its hollow hazard triangle, and on the
//    map its size. Size is the one this does NOT carry - see below.
//  - A closure is not a pin at all. It is barrier tape along closed geometry
//    (lib/closureStyle.ts), and drawing it here as a pin would invent a symbol
//    the map never shows.
//
// And since #1283 a fourth, which is a line and not a pin: the trail swatch
// beside each row of the legend's "Trails in view" block, drawn as the map
// draws that line - solid, at its own tier's width, in its own ink over its
// casing, ghosted if it is not the chosen system's. Every number in it
// comes from map/style.ts and map/nearbyTrails.ts, for the reason the pins'
// come from poiIcons.ts: a second table of blaze hexes in this file is the
// drift the header above exists to prevent.

import {
  badgeCenters,
  glyphPath,
  pinGeometry,
  poiColor,
  poiGlyphPath,
  PIN_EDGE_COLOR,
  PIN_HALO_COLOR,
  RIM_DASHES,
  type PoiConfidence,
} from './poiIcons'
import './mapIcon.css'
import { WARNING_GLYPH, WARNING_ICON_ID } from './warningPin'
import { blazePaintColor } from '../lib/blaze'
import type { SheetAppearance } from './liveTopo'
import { NEARBY_TRAIL_OPACITY, CHOSEN_TRAIL_OPACITY } from './nearbyTrails'
import {
  CASING_OVERHANG,
  PRIMARY_TRAIL_WIDTH,
  RED_LIGHT_BLAZE_COLOR,
  SIDE_TRAIL_WIDTH,
  redLightActive,
  trailCasingColor,
} from './style'
import { WARNING_PIN } from '../lib/seriousWarnings'
import {
  CLOSURE_CASING_COLOR,
  CLOSURE_COLOR,
  CLOSURE_STRIPE_ANGLE_DEG,
  CLOSURE_STRIPE_EDGE,
  CLOSURE_TAPE_CADENCE,
  CLOSURE_TAPE_WIDTH,
} from '../lib/closureStyle'

/** The one type here that is a line rather than a pin. Paired with
 *  {@link WARNING_ICON_ID}, these are exactly legendContents.ts's two
 *  never-hideable rows - which is not a coincidence: the safety layers are the
 *  two the map draws in a language of their own.
 *
 *  Not exported: nothing outside this file needs it, and a module that exports
 *  a constant beside a component is the thing React Fast Refresh gives up on
 *  (see the warnings oxlint already carries for screens/DetailPicker.tsx). */
const CLOSURE_TYPE = 'closure'

/**
 * Every proportion, as a fraction of a unit viewBox.
 *
 * Module scope because it is a pure function of a constant - recomputing nine
 * divisions per row per render would be work nobody asked for.
 */
const PIN = pinGeometry(1)

/**
 * How far the halo is painted under its neighbours, so no seam shows.
 *
 * The rasteriser has no such problem: it decides one colour per pixel, so the
 * disc and the halo simply abut. SVG antialiases each shape against what is
 * behind it, and two shapes that merely touch leave a hairline of page showing
 * between them. So the halo is drawn FIRST and drawn wide - from just inside
 * the disc all the way out to the rim's outer edge - and the disc and the dark
 * edge are painted over it. Every boundary is then an overlap, and what is
 * left visible is exactly the band buildPinImage would have inked.
 */
const HALO_BLEED = PIN.edgeWidth / 2

const HALO_INNER = PIN.rDisc - HALO_BLEED
const HALO_RADIUS = (PIN.rOuter + HALO_INNER) / 2
const HALO_WIDTH = PIN.rOuter - HALO_INNER

/** The dark hairline, exactly where buildPinImage puts it: the outermost
 *  `edgeWidth` of the rim. */
const EDGE_RADIUS = PIN.rOuter - PIN.edgeWidth / 2

/** The glyph is drawn in a centred box of side `glyphBox`, in a 0-1 space with
 *  y running down - the same box buildPinImage samples it in. */
const GLYPH_TRANSFORM = `translate(${PIN.center - PIN.glyphBox / 2} ${
  PIN.center - PIN.glyphBox / 2
}) scale(${PIN.glyphBox})`

/**
 * The broken rim, as a dash pattern rather than as an angle test.
 *
 * buildPinImage inks the rim where `floor(turns * RIM_DASHES * 2)` is even -
 * sixteen equal arcs, alternating, starting at three o'clock. An SVG circle
 * also starts at three o'clock and runs clockwise, so a dash and a gap of one
 * sixteenth of the circumference each is the same pattern, not a lookalike.
 */
function rimDashes(radius: number): string {
  const arc = (2 * Math.PI * radius) / (RIM_DASHES * 2)
  return `${arc} ${arc}`
}

interface PinProps {
  className?: string
  color: string
  path: string
  confidence: PoiConfidence
  /** The categories riding this pin as badges (#524), in SITE_MEMBER_TYPES'
   *  order - a shelter carrying a privy and water wears them rather than
   *  three pins fighting for one spot. Empty draws the plain pin. */
  members?: readonly string[]
}

/**
 * How far past the pin's own edge its badges reach, in unit terms - the same
 * arithmetic sitePinPadding does in pixels, so a badged SVG grows exactly as
 * the badged image does and the disc stays at the centre of both.
 */
function badgeReach(count: number): number {
  let reach = 0
  for (const { x, y } of badgeCenters(count, PIN.badge)) {
    reach = Math.max(
      reach,
      Math.abs(x) + PIN.badge.radius,
      Math.abs(y) + PIN.badge.radius,
    )
  }
  return Math.max(0, reach - PIN.rOuter)
}

function Pin({ className, color, path, confidence, members = [] }: PinProps) {
  // Verified pins have no dasharray attribute at all rather than a solid-
  // looking one, so "this rim is unbroken" is visible in the DOM.
  const broken = confidence === 'low'
  const pad = badgeReach(members.length)
  const badges = badgeCenters(members.length, PIN.badge).map((spot, index) => ({
    cx: PIN.center + spot.x,
    cy: PIN.center + spot.y,
    path: poiGlyphPath(members[index]),
    ink: poiColor(members[index]),
  }))

  return (
    <svg
      className={className}
      // The box grows symmetrically for the badges, as the raster's image
      // does (sitePinPadding), so the disc stays on the row's centre line.
      viewBox={`${-pad} ${-pad} ${1 + 2 * pad} ${1 + 2 * pad}`}
      // Decorative here: every row that carries one of these already names its
      // category in text beside it, and a screen reader announcing "Water,
      // Water" is worse than one announcing it once.
      aria-hidden="true"
      focusable="false"
    >
      <circle
        className="map-icon__halo"
        cx={PIN.center}
        cy={PIN.center}
        r={HALO_RADIUS}
        fill="none"
        stroke={PIN_HALO_COLOR}
        strokeWidth={HALO_WIDTH}
        strokeDasharray={broken ? rimDashes(HALO_RADIUS) : undefined}
      />
      <circle
        className="map-icon__disc"
        cx={PIN.center}
        cy={PIN.center}
        r={PIN.rDisc}
        fill={color}
      />
      <g transform={GLYPH_TRANSFORM}>
        <path
          className="map-icon__glyph"
          d={path}
          fill={PIN_HALO_COLOR}
          // The rule that keeps the shelter's doorway and the privy's crescent
          // open - the same even-odd count buildPinImage does by hand.
          fillRule="evenodd"
        />
      </g>
      <circle
        className="map-icon__edge"
        cx={PIN.center}
        cy={PIN.center}
        r={EDGE_RADIUS}
        fill="none"
        stroke={PIN_EDGE_COLOR}
        strokeWidth={PIN.edgeWidth}
        strokeDasharray={broken ? rimDashes(EDGE_RADIUS) : undefined}
      />
      {/* A member badge is the same pin at badge scale (poiIcons.ts): the
          category's own accent disc, its silhouette in halo white, a white
          ring and the dark hairline outside. Drawn after the pin so it sits
          over the halo where the two cross, as buildPinImage inks it. */}
      {badges.map((badge, index) => (
        <g key={members[index]} className="map-icon__badge" data-member={members[index]}>
          <circle
            cx={badge.cx}
            cy={badge.cy}
            r={PIN.badge.radius}
            fill={PIN_HALO_COLOR}
          />
          <circle cx={badge.cx} cy={badge.cy} r={PIN.badge.rDisc} fill={badge.ink} />
          <g
            transform={`translate(${badge.cx - PIN.badge.glyphBox / 2} ${
              badge.cy - PIN.badge.glyphBox / 2
            }) scale(${PIN.badge.glyphBox})`}
          >
            <path d={badge.path} fill={PIN_HALO_COLOR} fillRule="evenodd" />
          </g>
          <circle
            cx={badge.cx}
            cy={badge.cy}
            r={PIN.badge.radius - PIN.badge.edgeWidth / 2}
            fill="none"
            stroke={PIN_EDGE_COLOR}
            strokeWidth={PIN.badge.edgeWidth}
          />
        </g>
      ))}
    </svg>
  )
}

/**
 * The bare silhouette on a tinted square - the review's PoiGlyph in its
 * default mode, and Today's own category chip (today.css) given one home: the
 * type's accent at ~22% over the card, the glyph in the accent. For lists
 * where the pin's halo and rim would be noise, and where "which kind of
 * place" is the only thing the glyph has to say.
 */
function Tile({
  className,
  color,
  path,
}: {
  className?: string
  color: string
  path: string
}) {
  return (
    <span
      className={['map-icon-tile', className].filter(Boolean).join(' ')}
      style={{ '--chip-accent': color } as React.CSSProperties}
      aria-hidden="true"
    >
      <svg viewBox="0 0 1 1" focusable="false">
        <path
          className="map-icon__glyph"
          d={path}
          fill="currentColor"
          fillRule="evenodd"
        />
      </svg>
    </span>
  )
}

/** The swatch's viewBox is drawn in CSS pixels, at the tape's own width - so
 *  every number below is the number map/closureTape.ts rasterises, and the
 *  legend cannot drift from the map by someone editing one of them. */
const CLOSURE_HEIGHT = CLOSURE_TAPE_WIDTH
/**
 * How many pitches of tape the swatch shows.
 *
 * Four, and the number was chosen by looking rather than by arithmetic: the
 * legend's slot is 24px square (chrome.css's .legend__icon) and the viewBox
 * letterboxes into it, so this trades the strip's height against how much
 * cadence it shows. At two the swatch is a pair of fat slashes with no rhythm
 * to read; at four it is a run of parallel diagonals, which is the thing a
 * hiker has to recognise again on the map.
 *
 * The stripes stay at the map's own proportions throughout - this crops the
 * tape, it does not redraw it - so the last one runs off the right edge, the
 * way a crop of something continuous should.
 */
const CLOSURE_TILES = 4
const CLOSURE_WIDTH = CLOSURE_TAPE_CADENCE.pitch * CLOSURE_TILES
/** How far a stripe travels along the tape while crossing it. Same angle the
 *  image uses, so the swatch leans the way the map does. */
const CLOSURE_STRIPE_RUN =
  CLOSURE_HEIGHT / Math.tan((CLOSURE_STRIPE_ANGLE_DEG * Math.PI) / 180)
/** One stripe per pitch, plus one past each end: an SVG clips to its own
 *  viewBox, so a stripe that starts off the left edge still draws the part of
 *  itself that is inside - which is what keeps the swatch from beginning and
 *  ending on a half-stripe. */
const CLOSURE_STRIPES = Array.from(
  { length: CLOSURE_TILES + 2 },
  (_, index) => (index - 1) * CLOSURE_TAPE_CADENCE.pitch,
)

function ClosureBand({ className }: { className?: string }) {
  // Every stripe drawn twice: the dark edge first, the red over it. The same
  // two passes map/closureTape.ts makes into its byte array, and the same
  // reason - the edge is what the stripe is outlined WITH, never a second
  // mark beside it.
  const stripe = (x: number, mark: string, stroke: string, width: number) => (
    <line
      key={`${mark}-${x}`}
      className={mark}
      x1={x}
      y1={CLOSURE_HEIGHT}
      x2={x + CLOSURE_STRIPE_RUN}
      y2={0}
      stroke={stroke}
      strokeWidth={width}
    />
  )

  return (
    <svg
      className={className}
      viewBox={`0 0 ${CLOSURE_WIDTH} ${CLOSURE_HEIGHT}`}
      aria-hidden="true"
      focusable="false"
    >
      {/* No background rect, which is the whole change: what shows between the
          stripes on the map is the trail and the ground under it, so what
          shows between them here has to be the legend's own paper. */}
      {CLOSURE_STRIPES.map((x) =>
        stripe(
          x,
          'map-icon__closure-casing',
          CLOSURE_CASING_COLOR,
          CLOSURE_TAPE_CADENCE.stripe + CLOSURE_STRIPE_EDGE * 2,
        ),
      )}
      {CLOSURE_STRIPES.map((x) =>
        stripe(x, 'map-icon__closure-band', CLOSURE_COLOR, CLOSURE_TAPE_CADENCE.stripe),
      )}
    </svg>
  )
}

/** The swatch's box: chrome.css's 24px slot, drawn in CSS pixels so the
 *  widths below are the map's own widths and not a proportion of them. */
const SWATCH = 24
/** The casing's own softness, the same 0.7 map/style.ts multiplies the
 *  ghosting into. */
const CASING_OPACITY = 0.7

export interface TrailLineSwatchProps {
  /** The published blaze, or null where the line carries none. */
  blazeColor: string | null
  /** Drawn at the through-route width, or the side-trail width. */
  throughRoute: boolean
  /** In the chosen system: full-strength. Otherwise ghosted, exactly as the
   *  map draws every other line. (It decided solid against dotted until
   *  2026-09-10 - map/style.ts's header, rule 2.) */
  chosen: boolean
  /** Which sheet the map is drawn in, for the casing ink and red light.
   *  Defaults to the field day sheet, which is what a legend rendered
   *  without a map behind it should assume. */
  appearance?: SheetAppearance
  className?: string
}

/**
 * One trail line, as the map draws it, in a 24px box (#1283).
 *
 * Opacity follows `chosen`, the width follows `throughRoute`, and the ink
 * follows the rules map/style.ts's blazeLineColor keeps for a CASED line:
 * red light's one hue, or the blaze's own hex over the sheet's casing - a
 * white blaze white with its dark edge, the way the real line draws it
 * since 2026-09-10 (the near-white dark ink is the uncased sketches' rule
 * only, DARK_INKED_BLAZE_LAYER_IDS, and no sketch has a legend row).
 */
export function TrailLineSwatch({
  blazeColor,
  throughRoute,
  chosen,
  appearance = { theme: 'light' },
  className,
}: TrailLineSwatchProps) {
  const width = throughRoute ? PRIMARY_TRAIL_WIDTH : SIDE_TRAIL_WIDTH
  const casing = trailCasingColor(appearance)
  const ink = redLightActive(appearance)
    ? RED_LIGHT_BLAZE_COLOR
    : blazePaintColor(blazeColor ?? 'Unknown')
  const opacity = chosen ? CHOSEN_TRAIL_OPACITY : NEARBY_TRAIL_OPACITY
  const path = `M ${width} ${SWATCH / 2} H ${SWATCH - width}`

  return (
    <svg
      className={className}
      viewBox={`0 0 ${SWATCH} ${SWATCH}`}
      // Decorative, like the pins: the row names the trail beside it.
      aria-hidden="true"
      focusable="false"
    >
      <path
        className="map-icon__trail-casing"
        d={path}
        fill="none"
        stroke={casing}
        strokeWidth={width + CASING_OVERHANG * 2}
        strokeLinecap="round"
        strokeOpacity={CASING_OPACITY * opacity}
      />
      <path
        className="map-icon__trail-blaze"
        d={path}
        fill="none"
        stroke={ink}
        strokeWidth={width}
        strokeLinecap="round"
        strokeOpacity={opacity}
      />
    </svg>
  )
}

export interface MapIconProps {
  /** A POI type, `closure`, or `serious-warning`. Anything this build has
   *  never heard of gets the neutral diamond pin, which is what the map draws
   *  for it too - a category added upstream should look unfamiliar here, not
   *  invisible. */
  type: string
  /** Solid rim, or the broken one that means nobody has verified the POI
   *  exists. Ignored by the closure band and the warning pin, neither of which
   *  is a claim about a waypoint's existence. */
  confidence?: PoiConfidence
  className?: string
  /** The categories riding a site pin as badges - see PinProps. */
  members?: readonly string[]
  /** `pin` (the default) is the map's own pin; `tile` is the bare silhouette
   *  on a tinted square, for lists (#1373). A closure and a warning have no
   *  tile form - a warning is its pin, a closure is its tape. */
  variant?: 'pin' | 'tile'
}

export function MapIcon({
  type,
  confidence = 'high',
  className,
  members,
  variant = 'pin',
}: MapIconProps) {
  if (type === CLOSURE_TYPE) return <ClosureBand className={className} />

  if (type === WARNING_ICON_ID) {
    // Drawn at the same size as every other icon here, which is the one place
    // this deliberately parts company with the map. On the map the warning pin
    // is the biggest thing drawn (44px against a waypoint's 38) because it has
    // to win a glance across a moving screen. A legend is a key, read a row at
    // a time, and a row 16% taller than its neighbours would buy no urgency
    // and cost the grid its alignment. What carries the recognition instead is
    // the part that carries it on the map too: a hollow red triangle, the one
    // silhouette here that is an outline rather than a solid.
    return (
      <Pin
        className={className}
        color={WARNING_PIN.color}
        path={glyphPath(WARNING_GLYPH)}
        // Never broken, for the reason buildWarningPin gives: `serious` is set
        // by a moderator and never self-declared, so a warning that reaches
        // this pin has been looked at by a person. A dashed rim would say the
        // opposite of the one true thing about it.
        confidence="high"
      />
    )
  }

  if (variant === 'tile') {
    return <Tile className={className} color={poiColor(type)} path={poiGlyphPath(type)} />
  }

  return (
    <Pin
      className={className}
      color={poiColor(type)}
      path={poiGlyphPath(type)}
      confidence={confidence}
      members={members}
    />
  )
}
