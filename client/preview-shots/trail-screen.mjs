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
// run skipped, nothing taken - has the A.T. as a fine dark line like every
// other, at the same 1.5 px the network takes at this camera: the tenth
// build drew the network as a haze at 0.8 px, and the eleventh drew the
// A.T. at its 4.5 px tier, which on a 51,068-vertex line at z4 is a black
// rope (style.ts's sketchWidthExpression). SOLID since 2026-09-10: the dot
// rhythm #1283 gave every untaken line is gone (map/style.ts's header, rule
// 2). The dark ink stays at this camera only, because the sketch has no
// casing to edge a white line with; the real line above the seam is white.
// RE-TAKEN 2026-09-10 for the room audit (#1374): the bottom bar is one row -
// the mode chip at its left, then the four tabs, no brand mark - where it was
// three rows with the mark alone on the first, and the plate is the OPEN
// state this frame has always shown; map-plate-folded.mjs is the same screen
// one pan later.
// AMENDED 2026-09-18 (#1588): under the default the lines here are the A.T.
// and the Long Path solid and every other trail thinner and dashed - the
// maintainer's pick from mock-ups after #1577's first frames drew every
// trail solid. AMENDED AGAIN 2026-09-20 (#1597): the dashed lines were a
// light red until then, 45% of the A.T.'s over the paper, and the
// maintainer read that as pink - so every line in this frame is now the
// one red and only the width and the dash separate them. This recipe is
// the standing opening frame, so it is photographed on every pull request;
// the caption below is what to check it against now.
//
// RE-FRAMED 2026-09-30, AND THIS ONE CHANGES THE WHOLE PICTURE: "We should
// start showing the entire US, not just the at corridor" - the maintainer.
// App.tsx's opening camera is UNITED_STATES_BOUNDS now rather than
// CORRIDOR_BOUNDS, so this shot is the lower 48 at roughly z2.2 where it was
// Georgia-to-Maine at z4.9. This recipe seeds no camera of its own - it
// photographs whatever the app opens on - so it re-framed without being
// touched, which is why the caption and alt below had to be rewritten rather
// than amended: they described the A.T.'s New York miles, which are now a
// couple of hundred pixels of a continent.
//
// WHAT SHOULD BE IN THE NEW FRAME, so a reviewer can tell a working shot from
// a broken one. The published overview (network_overview.geojson, release
// 2026-09-16-4) carries 201 lines and 127 of them are `usfs_trails`, drawn
// across the whole country - so the frame is NOT the A.T. alone on an empty
// continent. Measured 2026-09-30: all 201 lines are centred inside these
// bounds. If this frame comes back with trails only in the northeast, the
// overview did not load and the shot is evidence of that rather than of the
// camera.
export const caption =
  'The opening map, now the entire lower 48 rather than the A.T. corridor (the maintainer, 2026-09-30) — near z2.2 where this frame was z4.9 over Georgia-to-Maine. Trail lines only below the seam (#1292), nothing taken (#1306), blaze colours off (#1575, the shipped default): the badged trails each a plain solid red line at one fine weight since #1588, every other organization’s trail thinner and dashed in the same red since #1597, so width and dash are the whole difference. 127 of the release’s 201 overview lines are USFS and nationwide, so the west should carry lines too — a frame with trails only in the northeast means the overview did not load.'
export const alt =
  'The opening map view of the entire continental United States: a pale basemap from the Pacific to the Atlantic with fine red trail lines threaded across it — the Appalachian Trail down the eastern mountains, the Pacific Crest Trail through the far west, the Continental Divide Trail through the Rockies, and many fainter dashed red threads of other organizations’ trails between them, each long trail carrying a small paper badge naming it, with no waypoint pins at this zoom'

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
