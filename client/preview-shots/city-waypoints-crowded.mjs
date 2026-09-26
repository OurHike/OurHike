// The pins on the crowdedest ground OurHike carries, which is not on a trail
// at all (#1536).
//
// Neither standing shot can be the evidence for this change. `first-run.mjs`
// is a card over a photograph and `trail-screen.mjs` is the whole corridor
// near z4.9, below the pin seam, where no waypoint draws at all. What changed
// is how much room each pin claims, and it only changes where the ground is
// crowded - so the frame has to be somewhere crowded, and the crowdedest
// place this app publishes is Brooklyn.
//
// THE CAMERA IS THE MEASUREMENT, not a nice-looking view. -73.9715, 40.6932
// at z12 is the densest 390x700 window in the five boroughs, found by
// pipeline/spike_city_poi_density.py's point-anchored sweep over the
// published artifact: 638 waypoints in 3.51 x 6.30 miles of Red Hook to
// Prospect Park, 531 drinking fountains and 107 public restrooms. It is the
// screen every number on #1534's mockup describes, so a reviewer can hold
// the frame and the table against each other.
//
// WHAT THE FRAME SHOWS. Before this change the collision engine packed 63
// pins into it, covering 30% of the phone at a median 51 px apart with a pin
// 36 px wide - touching, edge to edge. map/poiCrowding.ts now counts how many
// drawn marks sit within 800 m and widens `icon-padding` where that count is
// high, so the same ground draws about half as many pins with paper between
// them and the rest stay as dots at their own coordinates. Nothing is hidden:
// features/POI_VISIBILITY.md's "a pin or a dot and never as neither" is
// untouched.
//
// AND SINCE #1682 (2026-09-26) THE FOUNTAINS ARE HOLLOW AND UNRINGED. Every
// fountain here ships at `confidence: low` (NYC's `featuresta` reads Active on
// all 3,849 rows, #1534), so each is drawn hollow - paper inside a blue ring,
// the droplet in blue - and the restrooms, in the quiet tier, are pale plum.
// The faint invite ring #1676 painted round each fountain is not drawn round a
// hollow pin, where the two read as a bullseye (the maintainer's call, poll,
// 2026-09-26). What to look for: the same pins place as before, with far less
// ink each.
//
// WHAT IT CANNOT PROMISE YET, and a thin frame here is an answer rather than
// a broken recipe - network-above-the-seam.mjs makes the same distinction for
// the same reason. Two of the three things in this picture come from the
// bucket this preview reads:
//
//   - THE FOUNTAINS THEMSELVES are `nearby_poi.geojson`. They are already
//     published, so they should draw.
//   - THE FOLD (#1536's option 2) is written by export_nearby_poi.py and
//     reaches a phone only once publish-vector-data.yml has run since the
//     merge. Until then every fountain is its own mark and the frame shows
//     option 1 alone - which is the honest state of a phone on the current
//     release, and is the answer to "has the publish happened", the handoff
//     the PR body's Data pipelines section exists to track.
//   - THE PADDING is client-side and ships with this build, so it is in the
//     frame either way.
//
// So: fewer pins than before with air around them is option 1 working; site
// pins carrying several fountains is option 2 having been published too.
//
// NOTHING HERE IS ANYBODY'S. Public drinking fountains and public restrooms
// as New York City publishes them, on city park ground, with no account
// signed in, no report, no photo and no location fix - the four things
// .claude/skills/pr-screenshot/SKILL.md says must never appear. There is no
// dispersed campsite within a hundred miles of this camera.
//
// The camera is seeded through lib/cameraMemory.ts's session-storage key, as
// network-above-the-seam.mjs and basemap-ground-network.mjs both do and for
// their reasons: the app restores a remembered view on load, validates the
// shape field by field, and a reload is what that memory is for. No hike is
// seeded, deliberately - this is a map of a place rather than of a walk, and
// nothing in the frame depends on anything being taken.

export const caption =
  'Brooklyn at zoom 12, Red Hook to Prospect Park — the densest 390×700 window in the five boroughs, 638 waypoints in it, where the collision engine used to pack 63 pins edge to edge across 30% of the phone. Each pin now claims room in proportion to how crowded its own ground is (map/poiCrowding.ts), so the pins have paper between them and everything that loses one is still a dot at its true coordinate. Since #1682 each pin is drawn 26 px inside its 38 px footprint: the unverified fountains hollow, the restrooms pale. Fountains carrying a site’s worth of parts appear once publish-vector-data.yml has run since the merge; until then every fountain is its own mark and this is the padding alone'
export const alt =
  'The map screen over Brooklyn at zoom 12, from Red Hook up to Prospect Park, with NYC Parks’ green property shapes under it: hollow blue water-drop pins for public drinking fountains and pale plum pins for public restrooms, spaced apart with map paper visible between them, and a scatter of small blue dots marking the waypoints that did not take a pin'

/** POIs arrive from IndexedDB after the map is built, and the pins are
 *  rasterised off the main thread (#857) - both land a beat after chrome.
 *
 * 22000, as the Hudson Highlands desktop recipes wait, since #1676's first
 * preview (built from 698274a7): at the old wait all three waypoint recipes
 * photographed the map mid-load - the carry frame with its dots drawn but no
 * pin and no trail line, the Brooklyn and Shenandoah frames with neither. The trail
 * line is not something #1676 touches, so the frame was early rather than
 * wrong. Measured in the agent sandbox the same day, through
 * scripts/data-proxy.mjs: at 6 s `main` and #1676's branch were both still
 * blank at the carry camera, and at 15-20 s both had drawn everything. */
export const wait = 22000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, read back
  // with every field validated, and null on anything that does not convince.
  // The window pipeline/spike_city_poi_density.py names, centre for centre.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-73.9715, 40.6932], zoom: 12 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: the runner installs that
  // through an init script on the CONTEXT (scripts/screenshot.mjs's
  // skipFirstRun), which re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()
}
