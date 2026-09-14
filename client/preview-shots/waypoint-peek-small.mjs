// A shelter's peek on the smallest phone this app is designed for (#1374, the
// room audit of 2026-09-10).
//
// THE SAME DRIVE AS waypoint-quick-answers.mjs, AT 375x667. That recipe's
// frame at 390x844 was never the problem: the peek fit beside its pin. At
// 375x667 the map between the header and the tab bar is about 470px, a
// shelter's peek with its answer row (#1122) about 410px, and the placement's
// old rule - above the pin whenever neither side fits, "because the top edge
// only hides the head" - put the name and the close button 25px above the
// screen (mobile-audit, waypoint-quick-answers at 375x667). The rule now takes
// the roomier side and caps the card to it, and the peek scrolls inside
// (chrome/poiCardPlacement.ts, chrome.css's .poi-card__peek). This frame is
// the proof: the name and the × on screen, the card ending short of its pin.
//
// `small` is the recipe contract's third viewport (scripts/screenshot.mjs's
// PHONE_SMALL), added for this frame and for any other screen whose claim is
// "fits on an SE". The caption names both outcomes the way the drive it
// reuses does: without the POI artifacts the picture is the search panel
// saying nothing is here, which is a true screen rather than a broken one.

import drive, { wait } from './waypoint-quick-answers.mjs'

export const small = true
export const caption =
  'The same shelter peek at 375×667 — the name and the close button on screen and the card capped short of its pin, scrolling inside, where the old placement ran it off the top (#1374, room audit 2026-09-10)'
export const alt =
  'Either a waypoint card on a small phone, its top edge just under the map header with the shelter’s name and a × close button visible, the answer buttons below and the card ending above the pin it describes; or, where this build has no waypoint data, the search panel reading “Nothing here by that name.”'
export { wait }
export default drive
