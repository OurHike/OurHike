// The Mountains-to-Sea Trail wearing its badge, on a phone at z6 over the
// Pisgah and Nantahala national forests, North Carolina.
//
// WHAT CHANGED. pipeline/reference/trail_name_aliases.json gained the Forest
// Service's section spellings of three trails on 2026-09-30 - `FNST - …
// SECTION`, `ICE AGE NST-A/B/C` and `MST - … RD` - and map/longTrailNames.ts
// with them. Before that, every one of those lines drew as an anonymous
// thread. This recipe and its two siblings, florida-trail-badge.mjs and
// ice-age-trail-badge.mjs, photograph one trail each.
//
// WHY z6, AND WHY THE FIRST VERSION OF THIS RECIPE WAS WRONG. It sat at z8,
// on the belief that the badge draws below a pin seam at z9. The seam moved
// to POI_PIN_MIN_ZOOM = 7 (map/poiLayers.ts, #1585), and map/trailBadges.ts
// gives the badge layer `maxzoom: POI_PIN_MIN_ZOOM`, which MapLibre reads as
// exclusive - so at z8 no trail wears a badge at all, and the preview frame
// of 58e09609 showed exactly that: pins, the full network, and no badge, not
// even the A.T.'s. From NETWORK_SKETCH_MAX_ZOOM (z5, map/style.ts) the lines
// come from the nearby-trails vector tiles, which carry every line's name, so
// z5 to z7 is the band where a section spelling can badge. z6 is its middle,
// and the zoom pacific-crest-badge.mjs already uses.
//
// WHERE THE CAMERA POINTS, MEASURED against UA release 2026-09-30: the four
// `MST - … RD` spellings span lon -83.04..-81.78 and lat 35.30..36.08. The
// centre is that extent's midpoint. At z6 a 390 px phone spans 4.28 degrees of
// longitude, so all four are in frame, with the A.T., Benton MacKaye and
// Bartram badges likely beside them.
//
// WHAT THE BADGE SHOULD LOOK LIKE: the plate and the name "Mountains-to-Sea
// Trail" with NO marker. `mst` has no trail_marks row, so longTrailHasMarker
// is false and the badge is the plate and the name, the same as the Great
// Western Trail's. A marker here would be the defect
// longTrailNames.test.ts's "draws NOTHING" case guards against. A crowded
// frame can drop a badge whose every position collides; if this one is
// missing, that is the first thing to rule out.
//
// Nothing here reaches an account, anybody's reports or photos, a dispersed
// campsite at a readable zoom, or a real location fix - the four things
// .claude/skills/pr-screenshot/SKILL.md says must never appear in a shot. At
// z6 nothing is readable but public ground and place names.
export const caption =
  'The Mountains-to-Sea Trail on a phone at z6 over western North Carolina, wearing a badge that reads "Mountains-to-Sea Trail". The Forest Service publishes this trail as four lines named for the ranger districts they cross, such as "MST - GRANDFATHER RD". Before this change none of them had a badge. The plate carries no marker, because no marker for this trail ships.'
export const alt =
  'The map screen over the Blue Ridge of western North Carolina at zoom 6: trail lines across the Pisgah and Nantahala national forests, one carrying a small paper badge that reads "Mountains-to-Sea Trail" with no emblem, near other badged trails such as the Appalachian Trail.'

/** The same figure pacific-crest-badge.mjs and long-distance-trails.mjs
 *  settled on for a frame this wide. */
export const wait = 8000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, seeded the
  // way pacific-crest-badge.mjs does rather than by zooming out and landing on
  // whichever pixel the double-click zoomed around.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-82.41, 35.69], zoom: 6 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: scripts/screenshot.mjs's
  // skipFirstRun installs it through an init script on the context.
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
