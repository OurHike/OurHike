// The live sheet's road and other-trail network, at a zoom where it draws
// (#1074).
//
// The standing trail-screen shot cannot be the evidence for this change. It
// photographs the map as the app opens it - App.tsx's CORRIDOR_BOUNDS, which
// lands near z4.9 - and at that zoom none of the layers #1074 touches is on
// screen at all: minor roads and paths start at z12, tracks at z11. A picture
// of the whole corridor says nothing about how a road is drawn.
//
// So this recipe puts the camera somewhere the network is dense before taking
// the shot. Harpers Ferry is the A.T.'s own road crossing - US-340 over the
// Potomac, the town's street grid, the railway - and it is entirely public
// ground: no campsite, nobody's report, nobody's fix (the four things
// .claude/skills/pr-screenshot/SKILL.md says must never appear in one).
//
// The camera is seeded through lib/cameraMemory.ts's own session-storage key
// rather than by clicking zoom in eight times: the app already restores a
// remembered view on load, the shape is validated field by field on the way
// back in, and a reload is what that memory exists for. Driving the map by
// double-click would zoom around a pixel, and which piece of Virginia that
// pixel is over depends on the viewport.
//
// WHAT THIS SHOT SHOWS, AND WHERE IT WILL BE THIN. The basemap tiles in CI
// are real - the style fetches OpenFreeMap, so the roads, tracks and OSM
// footpaths this change re-draws are all genuinely on the canvas. The A.T.
// itself is NOT: the preview build carries an empty VITE_DATA_BASE_URL
// (#1024), so the blaze line that the ground network is supposed to sit
// behind is missing from the comparison. Read this shot for the road weight
// and the ink; the trail-against-road half is in the PR body's renders, which
// were shot against a build that has both.
export const caption =
  'The live sheet at Harpers Ferry — roads as single strokes, other trails quieted (#1074)'
export const alt =
  'The map screen over Harpers Ferry at zoom 14: roads drawn as thin single strokes rather than cased ribbons, dotted side trails in a pale ink, contours and woodland behind them'

/** Tiles and generated contours over a town both take longer than chrome. */
export const wait = 6000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, read back
  // with every field validated, and null on anything that does not convince.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-77.7305, 39.3255], zoom: 14 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across this: the runner installs that through an
  // init script on the CONTEXT (scripts/screenshot.mjs's skipFirstRun), which
  // re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()
}
