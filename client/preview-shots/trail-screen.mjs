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
export const caption =
  'The opening map — every mapped trail and no waypoints below the seam (#1135); the network appears once network_overview.geojson is in the bucket this preview reads'
export const alt =
  'The whole-corridor opening view: the A.T. as a cased white line from Georgia to Maine with orange highlight marks along it, no waypoint dots anywhere, and — once the artifact publishes — the other organizations’ trails ghosted around its New York miles'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Map' }).click()
}
