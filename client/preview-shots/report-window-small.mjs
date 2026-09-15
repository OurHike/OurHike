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
// dev server on 2026-09-15 in Chromium, the window needs 607px here and the
// scrim has 643px to give it - 36px of headroom, where before this change it
// needed 656 of 635 and scrolled by 184.
//
// `small` is the recipe contract's third viewport (scripts/screenshot.mjs's
// PHONE_SMALL), and waypoint-peek-small.mjs is the precedent: a screen whose
// claim is "fits on an SE" gets photographed on one.
//
// 375x667 IS THE FLOOR AND NOT THE WHOLE RANGE, which this frame cannot show
// and the pull request says instead: 320x568 still scrolls by 141px, and so
// does any phone whose owner has turned the system text size up. What holds at
// every size is the thing this pair is really about - the 911 line is pinned
// outside the scrolling region, so a scroll can hide a category and never the
// notice.
//
// It needs no trail data and carries nobody's data, for report-window.mjs's
// reasons - the same drive, the same vocabulary, the same empty map behind it.

import drive from './report-window.mjs'

export const small = true
export const caption =
  'The same window at 375×667 — the whole of it on screen, the 911 band under the header and the unsafe row whole at the bottom, where it scrolled by 184px and buried the 911 line 170px down (#1480)'
export const alt =
  'The report window on a small phone, over a dimmed Today screen. Its dark header reads “Report a problem / What did you find?”, a full-width pale band in red type directly beneath it reads “Call 911 if you are in danger now. This reaches volunteers, sometimes days later.”, and below that six category tiles two per row, a “The trail is closed” row and a “Something unsafe happened” row — the last of them complete, with its full description, above the window’s bottom edge and with no scrollbar anywhere.'
export default drive
