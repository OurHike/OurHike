// The Hudson at Dutchess Junction on a laptop, z13 - the frame the maintainer
// photographed brown rings in (2026-09-10): contour lines at and below sea
// level from the Terrarium DEM over tidal water, drawn as index lines
// because 0 ft is a multiple of every index interval, with `0'` labels along
// the shore. map/liveTopo.ts floors every contour above zero now, and this
// is the camera that shows it - the same one the maintainer's own screenshot
// was taken from, so the before and the after are the same frame.
//
// The same frame answers two more of that day's reads: every trail line
// solid, the A.T. white with its dark casing across Breakneck Ridge and
// the park's trails in their own hues around it (map/style.ts's header,
// rule 2), and the persistent legend beside the map opening on the pin key,
// with "Read all N trail notices" under the Serious warning row and the
// switches under that (chrome/Legend.tsx). "Trails in view" is at the
// panel's foot, below this frame's fold; legend-trails-in-view.mjs is the
// phone frame that scrolls to it.
//
// A REMEMBERED CAMERA, THEN A RELOAD: lib/cameraMemory.ts's contract, as
// network-above-the-seam.mjs seeds it, so the map is built at this camera
// rather than moved there - and no location fix, no account, nobody's
// reports: the plate reads "Location is off", which is the truth about the
// runner's phone.
export const caption =
  'The Hudson at Dutchess Junction on a laptop, z13 (the maintainer’s own frame of 2026-09-10): no contour at or below sea level along the shore — the brown 0 ft rings are gone (map/liveTopo.ts) — every trail a solid line, the A.T. white inside its dark casing over Breakneck Ridge, and the legend beside the map opening on the pin key with "Read all N trail notices" directly under the Serious warning row'
export const alt =
  'A wide browser window with the OurHike sidebar down the left, the map filling the middle over the Hudson River at Dutchess Junction with contour lines on the hills and none along the water, trails as solid coloured lines with the Appalachian Trail a white line inside a thin dark casing, and the legend panel down the right: the waypoint category grid, the Closure and Serious warning rows, the "Read all trail notices" link directly under them, and the Showing, Verified, Alerts and Drought switches'

// The wide layout is the subject; the legend is the panel beside the map.
export const desktop = true

/** Contours are generated from DEM tiles in a worker and the vector tiles
 *  come from the bucket; both take longer than chrome at z13 over a river
 *  valley - the local rig needed close to 20 s for the last contour, so the
 *  window is the widest any recipe takes. */
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
}
