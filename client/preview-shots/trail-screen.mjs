// The other standing shot (see README.md, and STANDING in
// scripts/photograph-preview.mjs): the map screen, photographed on every
// pull request.
//
// This had no drive until #1054 - the app used to open here on its own. The
// redesign made Today the opening tab (today.mjs is that shot now), so the
// map is one tap away and this recipe takes it. What the shot shows since
// the same change: the floating identity plate over the canvas and the
// next-up band along the foot, in place of the old full-width header bands.
//
// Re-pointed 2026-08-27 (#1071) rather than copied, per README.md: the screen
// this pull request changes is THIS one - the ATC point notice is drawn on
// this canvas - and a second recipe reaching the same screen would be the
// gallery .claude/skills/pr-screenshot/SKILL.md warns against.
//
// Re-pointed again 2026-08-27 (#1097), and for the third time rather than
// copied, per README.md's "reuse one by touching it": that change puts NYS
// DEC's and NYS OPRHP's 8,480 waypoints onto THIS canvas, through the same
// single symbol layer ATC's already draw through (map/poiLayers.ts draws one
// layer because MapLibre can only declutter symbols it places together). So it
// is the same screen again, and a fourth recipe reaching it would be the
// gallery SKILL.md warns against.
//
// Re-pointed a fourth time, 2026-08-27 (#1135), and this one both changes
// what the frame SHOWS and retires a stale claim two paragraphs used to
// stand on. The claim first: they said the preview build carries an empty
// `VITE_DATA_BASE_URL` (#1024) and so no release artifacts arrive. That
// stopped being true - the preview is built against the live bucket and this
// very frame draws the trail from it - so the two walls those paragraphs
// described have narrowed to one: an artifact no publish has carried yet
// (nearby_poi.geojson then, network_overview.geojson now) still cannot
// appear, and which map this shot shows is itself evidence of whether the
// publish has run.
//
// What #1135 changes in this frame: the opening camera is now the trails and
// not the waypoints. The dot stipple #603 put on the whole-corridor view is
// gone (both ranks stop at the pin seam), the "N of M waypoints fit" chip
// stands down below the seam, and - once network_overview.geojson is in the
// bucket - every other organization's trails draw ghosted around the A.T.'s
// New York miles, tapering thinner the further out the camera sits. The
// A.T.'s line, the corridor highlight marks and the closure tape were
// already here and stay.
//
// A separate recipe reached this change's screen for two CI runs and was
// retired back into this one, per README.md's "reuse one by touching it" -
// it opened the legend to photograph the new below-seam sentence, and
// learned that an open legend blanks the canvas behind it under this
// camera (#1138), which costs the shot the map half of the change. The
// sentence's evidence is Legend.test.tsx's below-seam cases; the map half
// is this frame's.
// Re-pointed a fifth time, 2026-09-08 (#1291, #1292), and this one changes
// what the frame shows twice over. The A.T.'s line is IN it now: the sketch
// that stands in for the real line used to be withdrawn the moment the shell
// held trails.geojson, seconds before the map had parsed it, and this shot -
// taken 3.5 s after the Map tap - photographed that gap on every pull
// request while the caption claimed a line. And the corridor's highlight
// marks and boundary ticks, which the alt text used to name, are gone with
// every other point mark below the seam: the opening camera is trail lines
// only, by the maintainer's call.
// NOTHING TAKEN (#1306). First run takes no trail, so this frame - first
// run skipped, nothing taken - has the A.T. as a dotted dark line like every
// other, at the same 1.5 px the network's dots take at this camera: the
// tenth build drew the network as a haze at 0.8 px, and the eleventh drew
// the A.T.'s dots at its 4.5 px tier, which on a 51,068-vertex line at z4
// is a black rope (style.ts's sketchWidthExpression).
export const caption =
  'The opening map — trail lines only below the seam (#1292), nothing taken (#1306): every trail a dot rhythm at one fine weight, the A.T. in dark ink from its corridor-view sketch until the real line lands (#1291), the other organizations’ trails dotted in their own hues around its New York miles — the Long Path in aqua — no waypoints, and the A.T.’s one badge naming it, placed at this camera since the review of #1374'
export const alt =
  'The whole-corridor opening view: the A.T. as a single fine dotted dark line from Georgia to Maine over the basemap, with no pins on it and one paper badge reading “Appalachian National Scenic Trail” with the ATC mark, and the other organizations’ trails as dotted threads of the same weight in their own colours around its New York miles'

/** The network overview is one 10.8 MB GeoJSON (lib/config.ts's
 *  NETWORK_OVERVIEW_KEY) that the map cuts into tiles in a worker after it
 *  lands, and that cut is what the photographer's 3.5 s default missed on
 *  ten builds: in the agent sandbox its dots appeared between 6 and 10 s
 *  after the Map tap (frames at 3.5, 6, 10 and 20 s, 2026-09-09), with the
 *  file itself fetched 1.8 s after load. A runner is not a sandbox, so
 *  this is the sandbox's upper bound rather than a measurement of CI. */
export const wait = 10000

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Map' }).click()
}
