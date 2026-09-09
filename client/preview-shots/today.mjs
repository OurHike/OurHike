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
export const caption = 'Today — the journal the app now opens on (#1054)'
export const alt =
  'The Today screen: a pine header with the date, a mode switch reading Day hike, Long hike and Volunteer, and a paper column below with the volunteer card and the no-signal footer'
