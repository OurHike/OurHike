// The Pacific Crest Trail wearing the Forest Service's emblem, on a phone at
// z6 over northern California and southern Oregon.
//
// WHY A NEW RECIPE RATHER THAN TOUCHING long-distance-trails.mjs. That one is
// the right frame for the badged set and the wrong frame for this change: its
// camera sits at [-74.6, 42.4], the Hudson valley, and the PCT is three
// thousand miles west of it. The standing trail-screen shot is the corridor
// view the app opens on, which is the A.T.'s. Neither could photograph the
// mark this pull request adds, so neither is evidence for it.
//
// WHERE THE CAMERA POINTS, MEASURED. The pinned release's
// network_overview.geojson (2026-09-16-4, fetched 2026-09-30) publishes the
// PCT as two features whose names both resolve to the `pct` slug through
// map/longTrailNames.ts - `PACIFIC CREST TRAIL` at -123.258..-119.915 by
// 38.625..42.619, and `PACIFIC CREST NATIONAL SCENIC` at -121.785..-121.295
// by 40.027..41.060, which sits inside it. One badge, not two: the dedupe
// keys on the resolved trail rather than the published spelling, and this
// frame is where that is visible on the one trail that publishes a spelling
// wholly contained in another.
//
// THE TWO FEATURES BECOME ONE AT THE NEXT PUBLISH (#1776), and until it runs
// this frame is the BEFORE. The sketch now qualifies a run of shared tread
// rather than a spelling, and folds USFS's 81 spellings of this trail into
// one identity first - so the export writes a single feature called
// `Pacific Crest Trail` where the pinned release has two, and it reaches
// further: the largest continuous run of the PCT in that layer is 424 miles
// through the Oregon and Washington Cascades, which carried NO spelling the
// alias table listed and so drew as anonymous haze. What this frame should
// show afterwards is the same single badge in the same place, with more
// cased line running north out of the top of it. If it shows TWO badges, the
// client dedupe is carrying a case the pipeline was supposed to have stopped
// creating.
//
// WHY z6 AND NOT z7. MapLibre's world is 512 px times two to the zoom, so a
// 390 by 844 px phone at z6 spans 4.28 degrees of longitude and, at this
// latitude, about 7.0 of latitude - against the 3.34 by 3.99 the trail needs.
// z7 halves both and would hold the badge (one vertex on screen is enough)
// while running the line off the top and the bottom. The trail whole is the
// better picture for a mark that says which trail the line is.
//
// WHAT WOULD MAKE THIS FRAME A FAILURE, worth writing down because the last
// badge recipe this branch added photographed no badge at all and was
// withdrawn: the badge layer's `maxzoom` is POI_PIN_MIN_ZOOM (9) and MapLibre
// reads it as EXCLUSIVE, so a recipe at or above the pin seam shows nothing
// whatever it is pointed at. z6 is below it. There is no `minzoom` on the
// layer, so nothing cuts it off from underneath.
//
// Nothing here reaches an account, anybody's reports or photos, a dispersed
// campsite at a readable zoom, or a real location fix - the four things
// .claude/skills/pr-screenshot/SKILL.md says must never appear in a shot. At
// z6 nothing is readable but public ground and place names.
export const caption =
  'The Pacific Crest Trail on a phone at z6 over northern California, wearing the US Forest Service’s own trail emblem in place of the blue "PCT" hexagon OurHike had drawn — the emblem is public domain under 17 U.S.C. 105 and is not PCTA’s file, whose stated permission requirement is untouched. One badge although the release publishes two spellings of this trail, because the dedupe keys on the resolved trail rather than the published name.'
export const alt =
  'The map screen over northern California and southern Oregon at zoom 6: a solid red line running north to south through the Cascades and the northern Sierra, carrying a small paper badge that reads "Pacific Crest Trail" beside a rounded-triangle emblem — a dark conifer over white peaks on a teal field — with fainter dashed red threads for other trails around it.'

/** The sketch is one GeoJSON the app loads with the map, and the basemap
 *  tiles for a frame this wide take a moment more than a park's. The same
 *  figure long-distance-trails.mjs settled on for its state-wide frame. */
export const wait = 8000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, validated
  // field by field on load - the same seeding long-distance-trails.mjs and
  // network-above-the-seam.mjs use, rather than clicking zoom out six times
  // and landing on whichever pixel the double-click zoomed around.
  //
  // The centre is the midpoint of the measured extent above, so the trail
  // sits in the frame rather than against an edge.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-121.6, 40.6], zoom: 6 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: the runner installs that
  // through an init script on the context (scripts/screenshot.mjs's
  // skipFirstRun), which re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
