// A shelter's peek naming its parts, on the smallest phone this app is
// designed for (#1706, and #1374's room audit for the size).
//
// THE SAME DRIVE AS waypoint-site-parts.mjs, AT 375x667, because this is the
// size where the change could fail without anybody seeing it at 390x844. The
// peek is capped to the room beside its pin and scrolls inside
// (chrome/poiCardPlacement.ts), and the strip's `overflow-x: auto` makes its
// automatic minimum height zero - so, photographed 2026-09-28 against the UA
// bucket before chrome.css's `flex-shrink: 0`, Limestone Spring Shelter's peek
// drew its name and conditions and no chip row at all. The frame this recipe
// is for shows the row held and "Notes & details" scrolled just under the
// cap, which is #1374's answer for a card taller than its room.

import drive, { wait } from './waypoint-site-parts.mjs'

export const small = true
export const caption =
  'The same shelter peek at 375×667 — the parts row held under the name, and the peek scrolling inside its cap where the room above the pin runs out (#1706, #1374)'
export const alt =
  'Either a waypoint card on a small phone for Limestone Spring Shelter, with a row of four round icons under its name - a house, a privy, a water droplet and a tent - above the condition line, the card ending short of its pin; or, where this build has no waypoint data, the search panel reading “Nothing here by that name.”'
export { wait }
export default drive
