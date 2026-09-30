// The Mountains-to-Sea Trail wearing its badge, on a phone at z8 over the
// Grandfather Ranger District of Pisgah National Forest, North Carolina.
//
// WHAT CHANGED. pipeline/reference/trail_name_aliases.json gained the Forest
// Service's section spellings of three trails on 2026-09-30 - `FNST - …
// SECTION`, `ICE AGE NST-A/B/C` and `MST - … RD` - and map/longTrailNames.ts
// with them. Before that, every one of those lines drew as an anonymous
// thread.
//
// WHY THE MST AND NOT THE OTHER TWO, MEASURED. Below the pin seam (z9) the
// map draws the sketch, network_overview.geojson, and a badge is only ever
// drawn below that seam - the badge layer's `maxzoom` is POI_PIN_MIN_ZOOM and
// MapLibre reads it as exclusive (pacific-crest-badge.mjs has the longer
// account). Of the twelve new spellings, the sketch carries exactly one:
// `MST - GRANDFATHER RD`, `through_route: true`, in both production's release
// 2026-09-24-2 and UA's 2026-09-30 (fetched 2026-09-30). The Florida and Ice
// Age sections are not in either sketch, so no camera can photograph their
// badge on the map. Above the seam they should reach a hiker as a
// trails-in-view row in the legend reading "Florida Trail" or "Ice Age
// Trail". That is reasoned from map/trailsInView.ts feeding chrome/Legend.tsx
// with the same printed name; it has not been photographed.
//
// WHERE THE CAMERA POINTS. The one feature spans -82.17..-81.78 by
// 35.75..36.08 (70.7 miles). The centre is that extent's midpoint. At z8 a
// 390 px phone spans 1.07 degrees of longitude, so the whole feature is in
// frame with room either side.
//
// WHAT THE BADGE SHOULD LOOK LIKE: the plate and the name "Mountains-to-Sea
// Trail" with NO marker. `mst` has no trail_marks row, so longTrailHasMarker
// is false and the badge is the plate and the name, the same as the Great
// Western Trail's. A marker here would be the defect
// longTrailNames.test.ts's "draws NOTHING" case guards against.
//
// Nothing here reaches an account, anybody's reports or photos, a dispersed
// campsite at a readable zoom, or a real location fix - the four things
// .claude/skills/pr-screenshot/SKILL.md says must never appear in a shot. At
// z8 nothing is readable but public ground and place names.
export const caption =
  'The Mountains-to-Sea Trail on a phone at z8 over the Grandfather Ranger District, North Carolina, wearing a badge that reads "Mountains-to-Sea Trail". The Forest Service publishes this line as "MST - GRANDFATHER RD", where RD is the ranger district. Before this change the line had no badge. The plate carries no marker, because no marker for this trail ships.'
export const alt =
  'The map screen over the Blue Ridge of western North Carolina at zoom 8: a trail line running roughly north-east past Linville Gorge toward Grandfather Mountain, carrying a small paper badge that reads "Mountains-to-Sea Trail" with no emblem, among fainter threads for other trails.'

/** The sketch is one GeoJSON the app loads with the map. The same figure
 *  pacific-crest-badge.mjs and long-distance-trails.mjs settled on for a
 *  frame this wide. */
export const wait = 8000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, seeded the
  // way pacific-crest-badge.mjs does rather than by zooming out and landing on
  // whichever pixel the double-click zoomed around.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-81.975, 35.915], zoom: 8 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: scripts/screenshot.mjs's
  // skipFirstRun installs it through an init script on the context.
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
