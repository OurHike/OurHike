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
// WHAT THE TAP PROVES. The drive taps the toggle and nothing else; the
// runner's second settle is what lets the repaint land before the shutter.
// The lines change colour in place - attachMapAppearance repaints
// `line-color` on every blaze layer rather than rebuilding the map
// (map/style.ts) - so a frame that still showed red lines with the switch
// checked would be that repaint failing, which is the regression this
// recipe exists to catch on a real map rather than the mock.
//
// The same seeding as hudson-highlands-desktop.mjs, for its reasons: a
// remembered camera and a reload, no location fix, no account, nobody's
// reports.
export const caption =
  'The same frame with "Blaze colors" switched ON (#1575): the white-blazed park trail over Breakneck Ridge white inside its dark casing again (not the A.T., whose nearest point is 9 km east of this camera), the park’s other trails in their own blaze hues around it, and the legend’s Blaze colors toggle on, first under the Legend / In view pills, reading "Each trail in the color of its blazes." This is what every hiker saw before this change; it is now one tap away and remembered'
export const alt =
  'The same wide browser window over the Hudson at Dutchess Junction, the trails now solid coloured lines with the one over Breakneck Ridge a white line inside a thin dark casing and the others in blue, yellow and other blaze colours, and in the legend panel down the right the Blaze colors toggle switched on, first under the Legend and In view pills'

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
