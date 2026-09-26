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
//  - A waypoint is the slim pin (poiIcons.ts, #1682) - a disc inside a paper
//    hairline, its glyph, full colour or quiet by tier, hollow when nobody has
//    verified it, and a site's members as colour pips on its rim.
//  - A serious warning is the older coin - disc, glyph, cream halo, dark edge
//    (map/warningPin.ts) - in its own red with a hollow hazard triangle, and on
//    the map at its own size. Size is the one this does NOT carry - see below.
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
  glyphPath,
  pinGeometry,
  badgeCenters,
  poiColor,
  poiGlyphPath,
  waypointPinGeometry,
  waypointPinInks,
  PIN_EDGE_COLOR,
  PIN_HALO_COLOR,
  PIN_SHADOW_ALPHA,
  PIN_SHADOW_COLOR,
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
  closureTapeGround,
} from './style'
import { WARNING_PIN } from '../lib/seriousWarnings'
import {
  CLOSURE_CASING_COLOR,
  CLOSURE_COLOR,
  CLOSURE_DASH,
  CLOSURE_OUTLINE_WIDTH,
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
}

/**
 * The coin: the serious warning's pin (map/warningPin.ts), and every
 * waypoint's until #1682 drew those slimmer. Drawn from pinGeometry(), as
 * buildPinImage rasterises it.
 */
function Pin({ className, color, path, confidence }: PinProps) {
  // Verified pins have no dasharray attribute at all rather than a solid-
  // looking one, so "this rim is unbroken" is visible in the DOM.
  const broken = confidence === 'low'

  return (
    <svg
      className={className}
      viewBox="0 0 1 1"
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
    </svg>
  )
}

/**
 * The waypoint pin's proportions in a unit box whose side is the DRAWN pin,
 * not its 38 px footprint: a legend slot is a key read a row at a time, and
 * spending a third of it on the footprint's transparent margin would draw the
 * pin smaller than the row's other icons for no reason a legend has.
 */
const WAYPOINT = waypointPinGeometry(1, 1)

/** How far past the drawn pin its badges reach, in unit terms - the
 *  arithmetic sitePinPadding does in pixels, so the box grows exactly as the
 *  raster's does and the pin stays on the row's centre line. Not the shadow:
 *  its sliver below the pin is 0.7 px in a 24 px legend slot, and a plain pin
 *  whose box is not the unit square would sit off every other row's line. */
function waypointReach(count: number): number {
  let reach = WAYPOINT.rInk
  for (const { x, y } of badgeCenters(count, WAYPOINT.badge)) {
    reach = Math.max(
      reach,
      Math.abs(x) + WAYPOINT.badge.radius,
      Math.abs(y) + WAYPOINT.badge.radius,
    )
  }
  return reach - WAYPOINT.rInk
}

interface WaypointPinProps {
  className?: string
  type: string
  confidence: PoiConfidence
  /** The categories riding this pin as badges (#524, #1682), in
   *  SITE_MEMBER_TYPES' order. Empty draws the plain pin. */
  members?: readonly string[]
}

/**
 * The slim pin, as buildWaypointPinImage rasterises it (#1682): a faint
 * shadow, a paper hairline, the disc in the ink waypointPinInks picks for
 * this tier and confidence, a ring inside the hairline when there is one, the
 * glyph, and a site's members as small badges against the rim.
 */
function WaypointPin({ className, type, confidence, members = [] }: WaypointPinProps) {
  const inks = waypointPinInks(type, confidence)
  const pad = waypointReach(members.length)
  const c = WAYPOINT.center
  const ringWidth =
    inks.ringWidth === 'hollow'
      ? WAYPOINT.hollowRing
      : inks.ringWidth === 'quiet'
        ? WAYPOINT.quietRing
        : 0
  const box = WAYPOINT.glyphBox
  const badge = WAYPOINT.badge
  const badges = badgeCenters(members.length, badge).map((spot, index) => ({
    cx: c + spot.x,
    cy: c + spot.y,
    ink: poiColor(members[index]),
    path: poiGlyphPath(members[index]),
    member: members[index],
  }))

  return (
    <svg
      className={className}
      viewBox={`${-pad} ${-pad} ${1 + 2 * pad} ${1 + 2 * pad}`}
      aria-hidden="true"
      focusable="false"
      data-confidence={confidence}
    >
      <circle
        className="map-icon__shadow"
        cx={c}
        cy={c + WAYPOINT.shadowOffset}
        r={WAYPOINT.rInk}
        fill={PIN_SHADOW_COLOR}
        fillOpacity={PIN_SHADOW_ALPHA}
      />
      <circle
        className="map-icon__halo"
        cx={c}
        cy={c}
        r={WAYPOINT.rInk}
        fill={PIN_HALO_COLOR}
      />
      <circle
        className="map-icon__disc"
        cx={c}
        cy={c}
        r={WAYPOINT.rDisc}
        fill={inks.fill}
      />
      {inks.ring !== null && (
        <circle
          className="map-icon__ring"
          cx={c}
          cy={c}
          r={WAYPOINT.rDisc - ringWidth / 2}
          fill="none"
          stroke={inks.ring}
          strokeWidth={ringWidth}
        />
      )}
      <g transform={`translate(${c - box / 2} ${c - box / 2}) scale(${box})`}>
        <path
          className="map-icon__glyph"
          d={poiGlyphPath(type)}
          fill={inks.glyph}
          fillRule="evenodd"
        />
      </g>
      {badges.map((spot) => (
        <g key={spot.member} className="map-icon__badge" data-member={spot.member}>
          <circle cx={spot.cx} cy={spot.cy} r={badge.radius} fill={PIN_HALO_COLOR} />
          <circle cx={spot.cx} cy={spot.cy} r={badge.rDisc} fill={spot.ink} />
          <g
            transform={`translate(${spot.cx - badge.glyphBox / 2} ${
              spot.cy - badge.glyphBox / 2
            }) scale(${badge.glyphBox})`}
          >
            <path d={spot.path} fill={PIN_HALO_COLOR} fillRule="evenodd" />
          </g>
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

/** The swatch's viewBox is drawn in CSS pixels, at the band's own width - so
 *  every number below is a number lib/closureStyle.ts ships, and the legend
 *  cannot drift from the map by someone editing one of them. */
const CLOSURE_HEIGHT = CLOSURE_TAPE_WIDTH
/** The swatch's full height: the band plus the outline showing past each
 *  side (#1598). The band's own width grows with the zoom on the map, and
 *  this swatch draws the top of that taper - the weight a hiker learns the
 *  mark at, which is the zoom they are reading the legend from. */
const CLOSURE_BOX_HEIGHT = CLOSURE_HEIGHT + CLOSURE_OUTLINE_WIDTH * 2

/** One tick and the paper after it, in CSS pixels: the map's rhythm, which
 *  is written in line widths, resolved at the width above. */
const CLOSURE_TICK = CLOSURE_DASH.tick * CLOSURE_HEIGHT
const CLOSURE_PITCH = (CLOSURE_DASH.tick + CLOSURE_DASH.gap) * CLOSURE_HEIGHT

/**
 * How many pitches of band the swatch shows.
 *
 * Four, and the number was chosen by looking rather than by arithmetic: the
 * legend's slot is 24px square (chrome.css's .legend__icon) and the viewBox
 * letterboxes into it, so this trades the strip's height against how much
 * rhythm it shows. At two the swatch is a pair of fat ticks with no rhythm
 * to read; at four it is a run of bars, which is the thing a hiker has to
 * recognise again on the map.
 */
const CLOSURE_TILES = 4
const CLOSURE_WIDTH = CLOSURE_PITCH * CLOSURE_TILES
/** One tick per pitch, plus one past each end: an SVG clips to its own
 *  viewBox, so a tick that starts off the left edge still draws the part of
 *  itself that is inside - which is what keeps the swatch from beginning and
 *  ending on a half tick. */
const CLOSURE_TICKS = Array.from(
  { length: CLOSURE_TILES + 2 },
  (_, index) => (index - 1) * CLOSURE_PITCH,
)

function ClosureBand({ className, ground }: { className?: string; ground: string }) {
  /** The outline, drawn as the two edges it actually is (#1598). Two rects
   *  over the ticks rather than one behind them, which is the same picture
   *  the map makes: the band is opaque, so the line under it shows only past
   *  its two sides. */
  const outline = (y: number) => (
    <rect
      key={`outline-${y}`}
      className="map-icon__closure-outline"
      x={0}
      y={y}
      width={CLOSURE_WIDTH}
      height={CLOSURE_OUTLINE_WIDTH}
      fill={CLOSURE_CASING_COLOR}
    />
  )

  return (
    <svg
      className={className}
      viewBox={`0 0 ${CLOSURE_WIDTH} ${CLOSURE_BOX_HEIGHT}`}
      aria-hidden="true"
      focusable="false"
    >
      {/* The sheet's paper under the ticks, exactly as the map draws it
          (#1575, option E). There was no rect here from 2026-08-27, when the
          band's gaps were transparent and the legend's own paper showed
          through; now the map's paper does, in the map's own colour, which on
          a dark sheet is ink - a legend that drew the panel's surface instead
          would be teaching a mark the map does not draw. */}
      <rect
        className="map-icon__closure-ground"
        x={0}
        y={CLOSURE_OUTLINE_WIDTH}
        width={CLOSURE_WIDTH}
        height={CLOSURE_HEIGHT}
        fill={ground}
      />
      {/* The ticks, SQUARE TO THE BAND since #1599, which is the whole of
          that change: a mark leaning at 55 degrees was what tore at every
          bend on the real map, so the legend leans no more than the map
          does. */}
      {CLOSURE_TICKS.map((x) => (
        <rect
          key={`tick-${x}`}
          className="map-icon__closure-band"
          x={x}
          y={CLOSURE_OUTLINE_WIDTH}
          width={CLOSURE_TICK}
          height={CLOSURE_HEIGHT}
          fill={CLOSURE_COLOR}
        />
      ))}
      {[0, CLOSURE_HEIGHT + CLOSURE_OUTLINE_WIDTH].map(outline)}
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
   *  without a map behind it should assume. Its `blazeColorsShown` is
   *  deliberately not read - the docstring below says why. */
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
 *
 * EXCEPT THE BLAZE SWITCH (#1575). blazeLineColor paints every line one red
 * while `blazeColorsShown` is off; this swatch keeps the blaze hue whatever
 * `appearance.blazeColorsShown` says, on the maintainer's instruction of
 * 2026-09-17 - "Changing the color option should only affect the map itself,
 * not the other options" - so that with the map one red, the legend's
 * "Trails in view" rows are where a named trail's blaze is read. That is why
 * the ink below comes from `blazePaintColor` and not from `blazeLineColor`:
 * the two agree everywhere but here, and here the disagreement is the point.
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
  /** Filled, or the hollow pin that means nobody has verified the POI exists
   *  (#1682). Ignored by the closure band and the warning pin, neither of which
   *  is a claim about a waypoint's existence. */
  confidence?: PoiConfidence
  className?: string
  /** The categories riding a site pin as pips - see WaypointPinProps. */
  members?: readonly string[]
  /** `pin` (the default) is the map's own pin; `tile` is the bare silhouette
   *  on a tinted square, for lists (#1373). A closure and a warning have no
   *  tile form - a warning is its pin, a closure is its tape. */
  variant?: 'pin' | 'tile'
  /** Which sheet the map is drawn in - read by the closure swatch alone, for
   *  the paper its tape lies on (#1575). Defaults to the field day sheet, as
   *  TrailLineSwatch does for the same reason; the pins ignore it. */
  appearance?: SheetAppearance
}

export function MapIcon({
  type,
  confidence = 'high',
  className,
  members,
  variant = 'pin',
  appearance = { theme: 'light' },
}: MapIconProps) {
  if (type === CLOSURE_TYPE) {
    return <ClosureBand className={className} ground={closureTapeGround(appearance)} />
  }

  if (type === WARNING_ICON_ID) {
    // Drawn at the same size as every other icon here, which is the one place
    // this deliberately parts company with the map. On the map the warning pin
    // is the biggest thing drawn (44px against a waypoint's 26 drawn inside a 38 px footprint) because it has
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
    <WaypointPin
      className={className}
      type={type}
      confidence={confidence}
      members={members}
    />
  )
}
