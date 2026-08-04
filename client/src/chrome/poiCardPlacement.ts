// Where the waypoint card sits, relative to the pin it describes.
//
// The card floats NEXT TO the tapped pin rather than docking at the bottom of
// the screen, so the answer to "which of these three shelters did I just tap"
// is carried by position instead of asking the hiker to match a name against
// the map. That only works if the card visibly belongs to its pin, which is
// what these rules protect: the card may slide along its own edge to stay
// readable, but it never lets go of the pin, and when the pin pans off screen
// the card goes with it instead of squatting on the edge pointing at nothing.
//
// Pure geometry, in canvas pixels, so the flip-and-clamp behaviour is testable
// without a DOM that can measure anything - jsdom reports every size as zero,
// and a test against a component could only ever exercise the degenerate case.

import { POI_PIN_SIZE } from '../map/poiIcons'

export interface Size {
  width: number
  height: number
}

export interface ScreenPoint {
  x: number
  y: number
}

/** Canvas-pixel offset of the card's top-left corner. */
export interface CardPlacement {
  left: number
  top: number
}

/** Air between the pin's drawn edge and the card. */
export const CARD_GAP_PX = 12

/** How close to the canvas edge the card is allowed to sit while its pin is
 *  on screen. Small on purpose: the margin buys legibility, not layout. */
export const CARD_EDGE_MARGIN_PX = 8

/** The pins are anchored at their centre (poiLayers.ts adds no icon-anchor),
 *  so the card clears half a pin, not a whole one. */
const PIN_HALF_PX = POI_PIN_SIZE / 2

/**
 * Places the card above the pin, centred - flipped below when there is no
 * room, slid sideways when the pin is near an edge.
 *
 * The same decision MapLibre's own Popup makes on every camera move, rather
 * than a placement chosen once when the card opens: a pin tapped near the top
 * of the screen and then panned to the middle should have a card above it,
 * not a below-card frozen in its opening pose.
 */
export function placePoiCard(pin: ScreenPoint, card: Size, canvas: Size): CardPlacement {
  // Above unless above does not fit and below does. When NEITHER fits - a
  // short viewport, or jsdom's zero-height one - above wins, because a card
  // over the top edge still shows its lower lines and a card past the bottom
  // edge shows nothing.
  const above = pin.y - PIN_HALF_PX - CARD_GAP_PX - card.height
  const below = pin.y + PIN_HALF_PX + CARD_GAP_PX
  const fitsAbove = above >= CARD_EDGE_MARGIN_PX
  const fitsBelow = below + card.height <= canvas.height - CARD_EDGE_MARGIN_PX
  const top = fitsAbove || !fitsBelow ? above : below

  let left = pin.x - card.width / 2

  // A canvas too narrow to hold the card at all - which includes jsdom's
  // zero-width one - gets the centred position and no clamping: there is no
  // readable place to slide to, and shoving the card against x=0 would just
  // pick a different unreadable one.
  if (canvas.width >= card.width + 2 * CARD_EDGE_MARGIN_PX) {
    // Slide inside the canvas edges first...
    left = Math.min(left, canvas.width - CARD_EDGE_MARGIN_PX - card.width)
    left = Math.max(left, CARD_EDGE_MARGIN_PX)
    // ...then let the pin win: the card's span always contains the pin's x,
    // so a pin panned off screen drags its card off with it instead of
    // leaving it pinned to the margin. Applied second, deliberately - this
    // bound outranks the edge margin.
    left = Math.max(Math.min(left, pin.x), pin.x - card.width)
  }

  return { left, top }
}
