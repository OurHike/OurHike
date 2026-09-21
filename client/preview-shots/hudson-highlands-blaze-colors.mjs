// The same laptop frame as hudson-highlands-desktop.mjs - the Hudson at
// Dutchess Junction, z13 - with the legend's "Blaze colors" switch ON
// (#1575). That recipe is the shipped default, every trail one red line;
// this one is the other state, and the two together are the change: the
// white-blazed line over Breakneck Ridge inside its casing again, the park's trails
// in their own hues, and the toggle on at the head of the legend beside the
// map, reading "Each trail in the color of its blazes."
//
// A second recipe reaching the same screen is what README.md's "reuse one by
// touching it" allows when the two shots carry different evidence - one
// state each - and it retires back into hudson-highlands-desktop.mjs the day
// the switch is not the change under review. The desktop frame rather than
// the phone's, because on the phone an open legend blanks the canvas behind
// it (#1138) and the whole point here is the switch and the lines in one
// picture.
//
// RE-PHOTOGRAPHED ON 2026-09-20, and for three reasons rather than one.
//
// The first is required rather than optional: that day's change moved
// CONTEXT_TRAIL_TINT from 0.45 to 0.8, which is exactly the ink this frame is
// about - the park's other trails. A recipe whose subject a pull request
// repaints has to be re-run, or the comment shows a picture of the build
// before it.
//
// The second is a report this frame is the standing check for. The
// maintainer, same day: "When I turn on the Blaze Color, it displays as grey
// and hides some trails. Until I zoom out/in, then it displays correctly."
// That was investigated and NOT reproduced - map/appearanceRestore.test.ts
// now diffs every appearance-dependent paint property on every line layer
// against what buildMapStyle would have produced, and the switch writes all
// of them back correctly, so it is not a missing write. What is left is a
// render-timing question that only a real map can answer, and this is the
// only recipe that taps that switch on one.
//
// WHAT TO LOOK FOR in this frame, therefore: coloured lines, not grey ones,
// and the same number of trails as the recipe beside it. Note what this
// frame CANNOT settle - it sits at z13 on a desktop, above the waypoint
// seam, so the below-seam sketches (map/style.ts's TRAIL_OVERVIEW_LAYER_ID
// and the network's, the two that draw dark-inked because they have no
// casing) are not on it. If the report turns out to be about those, it will
// take a camera below z7 that nothing points yet.
//
// WHAT THE TAP PROVES. The drive taps the toggle and nothing else; the
// runner's second settle is what lets the repaint land before the shutter.
// The lines change colour in place - attachMapAppearance repaints
// `line-color` on every blaze layer rather than rebuilding the map
// (map/style.ts) - so a frame that still showed red lines with the switch
// checked would be that repaint failing, which is the regression this
// recipe exists to catch on a real map rather than the mock.
//
// THE THIRD REASON IS THE LEGEND'S PICKER, which this frame has open beside
// the map and no other committed recipe does on a laptop.
//
// The waypoint master gate spent one day (2026-09-20) as a "Show points" pill
// floating over the map's bottom-left, and the maintainer moved it into the
// Showing picker: *"Maybe the show points should be part of the legend. Can
// this be integrated into the showing dropdown?"* So the panel down the right
// carries it now, as the last entry in that control's list. What has to be in
// the frame: a "Showing" row reading "All types", and NOTHING floating over
// the map's bottom-left corner but MapLibre's own scale bar.
//
// A pill over the map in this frame means the switch came back. A picker
// reading "None" over a map drawing waypoints means Legend.tsx's readout has
// stopped following lib/showPoints.ts.
//
// The same corner also carries the dropped-waypoint chip when there is one
// (.map-screen__dropped), and both it and the scale bar clear the credit
// strip by chrome.css's --over-map-floor. A chip or a bar drawn across the
// credit line is that figure not being raised above 900px, where the strip
// becomes an in-flow row of the canvas.
//
// The same seeding as hudson-highlands-desktop.mjs, for its reasons: a
// remembered camera and a reload, no location fix, no account, nobody's
// reports.
export const caption =
  'The same frame with "Blaze colors" switched ON (#1575): the white-blazed park trail over Breakneck Ridge white inside its dark casing again (not the A.T., whose nearest point is 9 km east of this camera), the park’s other trails in their own blaze hues around it, and the legend’s Blaze colors toggle on, first under the Legend / In view pills, reading "Each trail in the color of its blazes." This is what every hiker saw before this change; it is now one tap away and remembered. The panel also carries a second change: the "Showing" picker runs from "All types" down to a new "None", which is where the waypoint master gate lives — it was a "Show points" pill floating over the map’s bottom-left for one day, and that corner is empty of our chrome again'
export const alt =
  'The same wide browser window over the Hudson at Dutchess Junction, the trails now solid coloured lines with the one over Breakneck Ridge a white line inside a thin dark casing and the others in blue, yellow and other blaze colours, and in the legend panel down the right the Blaze colors toggle switched on, first under the Legend and In view pills, and below the pin grid a row labelled Showing with a dropdown reading All types; the map’s bottom-left corner holds only a scale bar reading 1000 ft, above the OpenStreetMap credit line'

// The wide layout is the subject; the legend is the panel beside the map.
export const desktop = true

/** As hudson-highlands-desktop.mjs: contours from the DEM in a worker and
 *  vector tiles from the bucket, both slower than chrome at z13 over a river
 *  valley. */
export const wait = 22000

export default async function drive(page) {
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-73.96, 41.47], zoom: 13 }),
    )
  })
  await page.reload({ waitUntil: 'load' })
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()

  // The persistent panel beside the map is a region, not a dialog
  // (chrome/Legend.tsx's `persistent`), and the toggle is a `role="switch"`
  // button whose accessible name is the row's name plus the sentence under
  // it, so the anchor is the name at the start of it. A click rather than
  // `check()`, which Playwright reserves for checkboxes and radios.
  const legend = page.getByRole('region', { name: 'Legend' })
  await legend.getByRole('switch', { name: /^Blaze colors/ }).click()
}
