// The challenge-place pin (#1780 — Let a club publish a challenge — places on
// its own trails that hikers opt into and tag at camp — starting with the
// ATC's A.T. Summer Bucket List; features/CHALLENGES.md, frame #1 "Map layer").
//
// workdayPin.ts's call, for workdayPin.ts's reason: drawn by the same
// rasteriser as every waypoint (map/poiIcons.ts's buildSlimPinImage), with
// the same paper hairline and the same shadow, so it reads as one more pin
// rather than as a second visual language.
//
// THE SHAPE IS THE BODY, NOT THE GLYPH
//
// The design is "a yellow diamond, hollow until tagged". Drawn as a diamond
// GLYPH inside the usual disc, it would be the unknown-type fallback pin
// (poiIcons.ts's UNKNOWN_POI_TYPE is exactly a diamond in a disc) in a
// different colour - and that fallback's stone-700 sits at hue 39.0, 0.3
// degrees from this yellow's 38.7, so the two would differ by saturation
// alone. So the diamond is the whole pin (`body: 'diamond'`): the only mark
// on the map that is not round, which is the channel poiIcons.ts says comes
// first ("shape is the primary channel, colour the second").
//
// THE COLOUR, AND THE BAR IT DOES NOT CLEAR
//
// CHALLENGE_COLOR is `--blaze-yellow` (`--accent-blaze-yellow`,
// design-system/tokens/colors.css), the handoff's colour, not a hex picked
// here. Measured against every other pin's accent (challengePin.test.ts
// recomputes all of it):
//
//   - HUE: 38.7 degrees. 12.8 from resupply (25.9), 29.7 from the workday
//     olive (68.4), 30.9 from the warning/closure red (7.8). That MISSES the
//     30-degree clearance workdayPin.test.ts and poiIcons.test.ts hold every
//     other accent to, against two neighbours. And no yellow could pass it:
//     clearing resupply needs a hue above 55.9 and clearing the workday
//     needs one below 38.4, so the band is empty.
//   - LIGHTNESS: 2.10:1 or more lighter than every accent (campsite is the
//     closest), where poiIcons.ts records the accents themselves sitting
//     between 1.06:1 and 2.19:1 of each other. Against resupply, the hue
//     neighbour, 2.47:1.
//
// So what separates this pin from a resupply pin is its outline and its
// lightness, never its hue. @unvalidated as a glance-read: what would settle
// it is a hiker in sun telling a diamond from the pale resupply pin at z12,
// which nobody has tried.
//
// WHY THE CHECK IS DARK AND THE EDGE IS DERIVED
//
// Paper on blaze-yellow is 2.42:1, so the paper glyph every other filled pin
// carries would fail WCAG AA's 4.5:1 here. The tagged pin's check is drawn in
// `--stone-900` (PIN_EDGE_COLOR) instead, 6.08:1 on the yellow.
//
// The same 2.42:1 is what the yellow alone would give the pin's EDGE against
// the paper round it - under WCAG 1.4.11's 3:1 for a graphic, and the
// untagged pin's edge is the only ink it has. So the ring in both states is
// CHALLENGE_EDGE_COLOR: derived rather than picked, as colors.css derives
// `--stone-600` - the first 1% step from the yellow toward `--stone-900` whose
// contrast on the pin's paper reaches 3:1. That is 14% (#be8a2b, 3.01:1; 13%
// gives 2.96:1), still hue 38.8, so the ring reads as the same yellow a
// shade deeper - the darker edge the handoff's own frame draws on its
// filled diamond.
//
// HOLLOW MEANS "NOT TAGGED YET", NOT "NOT VERIFIED"
//
// A hollow waypoint disc means nobody has confirmed the place exists
// (poiIcons.ts, #1682). A hollow diamond means this hiker has not tagged it.
// Two meanings for one fill, kept apart by the body: no waypoint is a
// diamond, and no challenge place is a disc.

import {
  buildSlimPinImage,
  mixHex,
  PIN_EDGE_COLOR,
  PIN_HALO_COLOR,
  POI_PIN_INK_SIZE,
  POI_PIN_PIXEL_RATIO,
  POI_PIN_SIZE,
  type Glyph,
  type PoiIconImage,
} from './poiIcons'

/** Stable image ids, and what the challenge layer's `icon-image` resolves to.
 *  Namespaced away from `poi-*`, because a challenge place is drawn over a
 *  waypoint rather than being one. */
export const CHALLENGE_ICON_ID = 'challenge-place'
export const CHALLENGE_TAGGED_ICON_ID = 'challenge-place-tagged'

/** `--blaze-yellow`, the tagged pin's fill. See the header for what it does
 *  and does not clear. */
export const CHALLENGE_COLOR = '#d69a2d'

/** How far toward `--stone-900` the edge is mixed: the first 1% step at which
 *  it reaches 3:1 on the pin's paper. challengePin.test.ts derives it again. */
export const CHALLENGE_EDGE_MIX = 0.14

/** The ring both states wear - `#be8a2b`, 3.01:1 on paper. */
export const CHALLENGE_EDGE_COLOR = mixHex(
  CHALLENGE_COLOR,
  PIN_EDGE_COLOR,
  CHALLENGE_EDGE_MIX,
)

/**
 * A tick, as ONE closed outline (the rasteriser fills even-odd, so two
 * strokes drawn as two rings would cancel where they meet): the short arm
 * down to the elbow, the long arm up to the right, a 0.17-wide stroke.
 *
 * The handoff's frame draws exactly this on the filled diamond. It is the
 * pin's second channel for "tagged" after the fill, and the one that
 * survives a greyscale pass: a filled diamond and a hollow one are two greys,
 * a tick is a shape.
 */
export const CHALLENGE_CHECK_GLYPH: Glyph = [
  [
    [0.22, 0.46],
    [0.4, 0.64],
    [0.8, 0.2],
    [0.92, 0.32],
    [0.4, 0.88],
    [0.1, 0.58],
  ],
]

/** Nothing drawn inside an untagged pin - the hollow is the whole message. */
const NO_GLYPH: Glyph = []

/**
 * The pin image, ready for `map.addImage`.
 *
 * THE SIZE IS THE WAYPOINT'S, CIRCUMSCRIBED. The diamond's apothem is the
 * waypoint pin's radius (POI_PIN_INK_SIZE / 2), so the diamond exactly covers
 * the round pin of the place it stands for when the two are drawn concentric
 * (map/challengeLayers.ts puts them there) - no sliver of the waypoint's
 * accent pokes out past an edge. Tip to tip that is 36.8 px, inside the same
 * 38 px footprint a waypoint claims; the shadow below the bottom tip loses
 * 0.2 px to the image edge, which nobody can see. Those are icon-size 1
 * figures; the layer scales the image with the waypoint's own size
 * expression, so the match holds at every zoom (map/challengeLayers.ts).
 *
 * Not larger than that: a challenge is something the hiker opted into, and
 * a pin drawn bigger than the waypoints around it would be claiming a
 * priority over the walking view that features/CHALLENGES.md's principle 2
 * ("the walking view does not change") withholds.
 */
export function buildChallengeIcon(
  tagged: boolean,
  sizePx: number = POI_PIN_SIZE,
  pixelRatio: number = POI_PIN_PIXEL_RATIO,
): PoiIconImage {
  return buildSlimPinImage({
    sizePx,
    // The waypoint's proportion of the footprint, as workdayPin.ts does it,
    // so a caller asking for another footprint gets the same pin scaled.
    inkPx: POI_PIN_INK_SIZE * (sizePx / POI_PIN_SIZE),
    pixelRatio,
    body: 'diamond',
    glyph: tagged ? CHALLENGE_CHECK_GLYPH : NO_GLYPH,
    inks: tagged
      ? {
          fill: CHALLENGE_COLOR,
          ring: CHALLENGE_EDGE_COLOR,
          ringWidth: 'hollow',
          glyph: PIN_EDGE_COLOR,
        }
      : {
          // Paper inside the ring - hollow, as the handoff draws it.
          fill: PIN_HALO_COLOR,
          ring: CHALLENGE_EDGE_COLOR,
          ringWidth: 'hollow',
          glyph: PIN_EDGE_COLOR,
        },
  })
}
