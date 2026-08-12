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
//  - A closure is not a pin at all. It is a barred red band along closed
//    geometry (lib/closureStyle.ts), and drawing it here as a pin would invent
//    a symbol the map never shows.

import {
  glyphPath,
  pinGeometry,
  poiColor,
  poiGlyphPath,
  PIN_EDGE_COLOR,
  PIN_HALO_COLOR,
  RIM_DASHES,
  type PoiConfidence,
} from './poiIcons'
import { WARNING_GLYPH, WARNING_ICON_ID } from './warningPin'
import { WARNING_PIN } from '../lib/seriousWarnings'
import {
  CLOSURE_BAR_RHYTHM,
  CLOSURE_CASING_COLOR,
  CLOSURE_CASING_WIDTH,
  CLOSURE_COLOR,
  CLOSURE_LINE_WIDTH,
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

/** Height of the closure swatch in its own viewBox: the band plus its casing
 *  either side, in the same line-width units lib/closureStyle.ts uses. */
const CLOSURE_HEIGHT = CLOSURE_LINE_WIDTH + CLOSURE_CASING_WIDTH * 2
/** Twice as wide as it is tall, which is three and a bit bars - enough for
 *  "barred" to be a rhythm rather than a single stripe. */
const CLOSURE_WIDTH = CLOSURE_HEIGHT * 2

function ClosureBand({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox={`0 0 ${CLOSURE_WIDTH} ${CLOSURE_HEIGHT}`}
      aria-hidden="true"
      focusable="false"
    >
      {/* Continuous, exactly as on the map: the casing runs the whole length
          and the band's gaps are where it shows through. */}
      <rect
        className="map-icon__closure-casing"
        x={0}
        y={0}
        width={CLOSURE_WIDTH}
        height={CLOSURE_HEIGHT}
        fill={CLOSURE_CASING_COLOR}
      />
      <line
        className="map-icon__closure-band"
        x1={0}
        y1={CLOSURE_HEIGHT / 2}
        x2={CLOSURE_WIDTH}
        y2={CLOSURE_HEIGHT / 2}
        stroke={CLOSURE_COLOR}
        strokeWidth={CLOSURE_LINE_WIDTH}
        // MapLibre's dasharray is in line-width units and SVG's is in user
        // units, which is why the viewBox above is drawn in line-width units
        // too - the multiplication happens once, here.
        strokeDasharray={CLOSURE_BAR_RHYTHM.map((part) => part * CLOSURE_LINE_WIDTH).join(
          ' ',
        )}
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
}

export function MapIcon({ type, confidence = 'high', className }: MapIconProps) {
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

  return (
    <Pin
      className={className}
      color={poiColor(type)}
      path={poiGlyphPath(type)}
      confidence={confidence}
    />
  )
}
