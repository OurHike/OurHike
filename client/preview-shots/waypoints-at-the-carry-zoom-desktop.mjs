// The carry-zoom waypoint frame, in the laptop layout (#1688).
//
// waypoints-at-the-carry-zoom.mjs photographs the phone. This is the same
// camera - the A.T. through the Hudson Highlands at z7.8 - in a 1280 x 800
// window, above lib/useDesktop.ts's 900 px breakpoint, where the app has its
// sidebar and a legend panel that never closes.
//
// WHAT THIS FRAME IS EVIDENCE FOR: that the laptop draws waypoints exactly as
// the phone does. The maintainer, 2026-09-26: "the look and feel needs to be
// aligned between the two. make a test to keep both aligned." The test is
// src/chrome/waypointsAcrossLayouts.test.tsx; this is the picture of it. Hold
// it against the phone frame: the same pins, the same small dots for the
// waypoints that lost their pin, the same rings only on pins, and the pin
// sizes the same because the zoom is the same. The laptop simply shows more
// ground, because its map is about twice as wide.
//
// Public ground throughout, as the phone frame's header says: no campsite
// readable at this zoom, nobody's report, nobody's location fix.
export const caption =
  'The same carry-zoom waypoints on a laptop (#1688): the Hudson Highlands at zoom 7.8 in the desktop layout, drawn exactly as the phone draws them — pins where there is room, shelters and campsites first, small dots for the waypoints that lost their pin, rings only on pins — with the sidebar on the left and the legend panel on the right'
export const alt =
  'A wide browser window: the OurHike sidebar down the left, the map of the Hudson Highlands at zoom 7.8 in the middle with the Appalachian Trail as a red line, a few dozen waypoint pins spaced apart and small coloured dots between them, and the legend panel down the right listing each waypoint category'

// The wide layout is the subject.
export const desktop = true

/** As waypoints-at-the-carry-zoom.mjs, and for its measured reason: at 6 s the
 *  first #1681 preview photographed that frame mid-load. 22000 is what the
 *  Hudson Highlands desktop recipes wait for the same bucket. */
export const wait = 22000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract, as in the phone recipe, and the same
  // camera, so the two frames can be held against each other.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.09, 41.25], zoom: 7.8 }),
    )
  })
  await page.reload({ waitUntil: 'load' })
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
