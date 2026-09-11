// The Today journal (#1054): the screen the app opens on since the redesign.
//
// No drive - Today is the new default tab, so the runner's ordinary
// skip-first-run landing IS this screen. That is also why trail-screen.mjs
// gained a drive the same day: the map stopped being where the app opens,
// and this file is the shot of what replaced it.
//
// What the preview can and cannot show. Nothing grants the camera a
// location, so there is no GPS fix and no mile readout, and the shot is the
// chrome being honest about that ("Location is off", the mode switch, the
// volunteer card saying the workday list needs signal, the no-signal footer).
// This used to add "the preview build has no data source (#1024)" as a
// second absence; that was the camera's own origin, fixed in #1096, and the
// release arrives now - what stays absent here is only what a fix would
// bring, and the dated journal appears the day a recipe can supply one.
// Re-pointed 2026-09-10 (#1373, F2): with nothing planned, the column now
// leads with a setup head rather than an empty list - "Nothing planned
// today" and the sentence saying what to do about it - and the Find / Plan
// bar is pinned under the paper on every state of the screen (rule R4).
// Same landing, no drive: the head is what a phone with nothing planned
// sees first.
// RE-TAKEN 2026-09-10 for the room audit (#1374): the bottom bar under the
// pinned Find / Plan bar is one row - the mode chip, then the tabs - and the
// header's status strip wraps its sync chip instead of running off a 375px
// screen (chrome.css's .status-strip).
export const caption =
  'Today with nothing planned — the setup head that replaces an empty list, and the pinned Find / Plan bar (#1373, F2)'
export const alt =
  'The Today screen: a pine header with the date and a mode switch reading Day hike, Long hike and Volunteer; below it a paper column opening with the heading Nothing planned today and a sentence about published walks and a builder, then the volunteer card and the no-signal footer; pinned under the column, a two-button bar reading Find a hike and Plan a hike, Plan emphasised, above the four tabs'
