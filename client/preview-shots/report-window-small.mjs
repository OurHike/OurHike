// The report window on the smallest phone this app is designed for (#1480).
//
// THE SAME DRIVE AS report-window.mjs, AT 375x667, and the reason for a second
// frame is that the two shots answer different questions. At 390x844 the
// window has 213px of headroom and fitting is not in doubt; the small phone is
// where the claim is actually at risk, and it is where the defect was worst -
// the 911 line sat 170px below the fold there against 39px at 390x844, so the
// notice a hiker in trouble needs was the thing furthest out of reach on the
// screen with the least room.
//
// WHAT TO LOOK AT, in one sentence: the bottom edge of the window, and whether
// the "Something unsafe happened" row is whole inside it. Measured against the
// dev server on 2026-09-15 in Chromium, the window needs 605px here and the
// scrim has 643px to give it - 38px of headroom, where before this change it
// needed 656 of 635 and scrolled by 184.
//
// `small` is the recipe contract's third viewport (scripts/screenshot.mjs's
// PHONE_SMALL), and waypoint-peek-small.mjs is the precedent: a screen whose
// claim is "fits on an SE" gets photographed on one.
//
// 375x667 IS THE FLOOR AND NOT THE WHOLE RANGE, which this frame cannot show
// and the pull request says instead: 320x568 still scrolls by 139px, and so
// does any phone whose owner has turned the system text size up. What holds at
// every size is the thing this pair is really about - the 911 line is pinned
// outside the scrolling region, so a scroll can hide a category and never the
// notice.
//
// It needs no trail data and carries nobody's data, for report-window.mjs's
// reasons - the same drive, the same vocabulary, the same empty map behind it.

import drive from './report-window.mjs'

export const small = true
// TOUCHED BY #1563 TWICE. Its first version drew the location picker inside
// the body, above the tiles, and this frame recorded the cost: the body
// scrolled again at 375x667. The picker is a sheet of its own now
// (reporting/LocationSheet.tsx), opened by Change or by a refused tap, so
// this is the tile frame #1480 measured once more - 605 px in 643 - with one
// line of the header changed. e2e/reportingDoors.spec.ts holds the 911 band
// whole in the viewport in both states.
export const caption =
  'The same window at 375×667 with no fix — the tile frame still fits with no scroll, because the location picker is a sheet over the window rather than a drawer inside it (#1480, #1563)'
export const alt =
  'The report window on a small phone, over a dimmed Today screen. Its dark header reads “Report a problem / What did you find?” with the place line “No location yet” and a “Change” control, a full-width pale band in red type directly beneath it reads “Call 911 if you are in danger now. This reaches volunteers, sometimes days later.”, and below that the six category tiles two per row, the “The trail is closed” row and the “Something unsafe happened” row, whole inside the window’s bottom edge.'
export default drive
