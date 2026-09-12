// The other organizations' trails above the pin seam, drawn from vector tiles
// (#1257).
//
// The standing trail-screen shot cannot be the evidence for this change. It
// photographs the map as the app opens it - the whole corridor near z4.9 -
// and below the seam the network is the corridor-view sketch, one GeoJSON
// that #1257 leaves exactly as it was. What changed is everything from z9 up:
// those lines used to arrive as one 228,820,578-byte GeoJSON handed to
// MapLibre whole, which crashed every phone on 2026-09-07 (#1254), and they
// now arrive as tiles read by byte range out of `nearby_trails.pmtiles`
// (map/networkTiles.ts), a few kilobytes under the camera and nothing else.
// A frame at z12 over a park where several organizations' trails cross the
// A.T. is the one picture that shows the change: the same ghosted lines,
// same widths, same tape, drawn from a source the old build could not hold.
//
// Harriman State Park is that ground. The A.T. runs through it, and within
// 150 m of another marked trail for half its length there (#771): OPRHP's
// blazed park trails, the NYNJTC-maintained ones, the Long Path a ridge over.
// Public ground throughout - no campsite readable at this zoom, nobody's
// report, nobody's fix (the four things SKILL.md says must never appear).
//
// The camera is seeded through lib/cameraMemory.ts's session-storage key, as
// basemap-ground-network.mjs does and for its reasons: the app restores a
// remembered view on load, validates the shape field by field, and a reload
// is what that memory is for.
//
// WHAT THIS FRAME SHOWS, AND WHEN IT SHOWS NOTHING. The tiles come from the
// bucket this preview reads, so the network appears here once a publish has
// carried `nearby_trails.pmtiles` - until then map/networkTiles.ts reads
// latest.json, finds no archive named, and draws nothing above the seam
// rather than erroring, which is exactly the honest state a phone on an older
// release is in. So a frame with the A.T. alone over Harriman is not a
// broken recipe: it is the answer to "has publish-vector-data.yml run since
// the merge", which is the handoff the PR body's Data pipelines section
// exists to track.
//
// Re-pointed 2026-09-08 (#1283) rather than copied, per README.md: this is
// the frame where the design handoff's park camera lands, and what changes
// in it is everything a hiker sees on the lines. The A.T. is no longer a
// cased white line but a single dark one - a near-white blaze on paper is
// inked in the casing colour with no casing - and it is the ONLY solid line:
// every other trail in the park is a dot rhythm in its own blaze hue,
// ghosted as before, with its name set along it. (Both of those are gone
// since 2026-09-10: every line is solid, and the A.T. is its white blaze
// with its dark casing whether or not it is taken - map/style.ts's header,
// rule 2. What separates the taken A.T. from the park's trails in this
// frame is its width, its full strength against their ghosting, and its
// badge.) Somewhere on the A.T.'s
// longest visible stretch sits its badge, a paper pill carrying the ATC mark
// and the full name. Amended (#1307): the Long Path can wear one too now,
// wherever its own longest visible stretch has room - it joined
// PRIMARY_TRAIL_SOURCES/BADGE_SOURCES the same way the A.T. holds them,
// still ghosted rather than taken, since neither list is the takeable one. Whether the Long Path's line is prominent enough in THIS
// frame to earn one is unverified from a sandbox with no rendered tiles, so
// the caption claims only what can wear a badge now, not what does in this
// crop. What the caption has to name is which line is solid and which
// carries a plate, because the old frame had neither distinction to point
// at.
//
// TWO THINGS THIS FRAME CANNOT PROMISE ABOUT THE BADGE. The mark decodes
// from at-logo.png on a canvas; where that fails the badge falls through to
// the White blaze chip - a stone rounded square with the white bar - and is
// still a badge. And the NAME is on the plate only where the plate has room:
// this stretch of the A.T. is lined with shelters, campsites and springs a
// thumb's width apart, and four preview rounds established that no 230 px
// strip along it is free of pins (map/trailsInView.ts's header). So here the
// badge is most likely the mark alone on its small plate, the fallback
// map/trailBadges.ts's header argues for, and the full plate with the name
// is what a less crowded stretch gets. The caption claims the plate and the
// mark; whether the name is beside them is what the frame answers.
// TAKEN BY THE HIKE, NOT BY A TAP (#1352). Nothing is taken on first launch,
// and the drive used to open the legend and take the A.T. from its row; since
// the state merge that tap opens the "Which long hike?" sheet instead, so the
// wait for "Close legend" hung for its full timeout and the frame was never
// shot (caught on the local rig, 2026-09-10, when this recipe was touched
// for the solid lines). What replaces it is what legend-trails-in-view.mjs
// already does: seed an active A.T. hike (fixtures/longHike.mjs, nobody's
// data) before the reload, so the A.T. is taken BECAUSE the hiker is on it -
// one state, read in two places - and the legend never opens. What the
// caption claims about full strength against ghosting is a claim about the
// taken state, and this is how the recipe reaches it.
import { seedLongHike } from './fixtures/longHike.mjs'

export const caption =
  'Harriman at zoom 12, the A.T. taken from its legend row in the drive (#1306) — the A.T. a solid white blaze with its dark casing at full strength, wearing its badge (the ATC mark on a paper plate, with the name beside it wherever the pins leave room for one); every other trail a solid line too since 2026-09-10 (the dot rhythm of #1283 is gone), in its own blaze hue, ghosted, with its name set along it; the park’s trails appear once nearby_trails.pmtiles is in the bucket this preview reads'
export const alt =
  'The map screen over Harriman State Park at zoom 12: the A.T. as a single solid white line inside a thin dark casing, with a small paper plate on it carrying the round ATC trail mark, and the name Appalachian National Scenic Trail beside the mark where the surrounding pins leave room; the park’s other blazed trails as fainter solid lines in their own colours around and across it, each with its name running along it'

/** Vector tiles from the bucket plus generated contours over a park both take
 *  longer than chrome. */
export const wait = 6000

export default async function drive(page) {
  // The hike first: it is what makes the A.T. taken at all (the header's
  // last paragraph). Its reload lands on the entry screen; the camera write
  // below survives it in sessionStorage either way.
  await seedLongHike(page)

  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, read back
  // with every field validated, and null on anything that does not convince.
  // Lake Tiorati, where the A.T., the Ramapo-Dunderberg and the Long Path's
  // feeder trails all sit inside one z12 frame.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.09, 41.25], zoom: 12 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: the runner installs that
  // through an init script on the CONTEXT (scripts/screenshot.mjs's
  // skipFirstRun), which re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()
}
