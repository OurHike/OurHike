// The Hudson at Dutchess Junction on a laptop, z13 - the frame the maintainer
// photographed brown rings in (2026-09-10): contour lines at and below sea
// level from the Terrarium DEM over tidal water, drawn as index lines
// because 0 ft is a multiple of every index interval, with `0'` labels along
// the shore. map/liveTopo.ts floors every contour above zero now, and this
// is the camera that shows it - the same one the maintainer's own screenshot
// was taken from, so the before and the after are the same frame.
//
// The same frame answers two more of that day's reads: every trail line
// solid, the white-blazed line over Breakneck Ridge inside its dark casing and
// the park's trails in their own hues around it (map/style.ts's header,
// rule 2), and the persistent legend beside the map opening on the pin key,
// with "Read all N trail notices" under the Serious warning row and the
// switches under that (chrome/Legend.tsx). "Trails in view" is at the
// panel's foot, below this frame's fold; legend-trails-in-view.mjs is the
// phone frame that scrolls to it.
//
// Re-pointed 2026-09-17 (#1575) rather than copied, per README.md: the
// screen this pull request changes is THIS one, and the reads above of
// "every trail line solid, the white line over Breakneck inside its casing ... the
// park's trails in their own hues" are exactly what changed. Every trail is
// now ONE RED LINE by default - the maintainer: "Showing the blaze color can
// be distracting and feel like I'm living in a rainbow ... Maybe the default
// color should be a red line, like the nynjtc has on their maps" - and the
// legend beside the map carries the toggle that brings the hues back, "Blaze
// colors", first under the Legend / In view pills and off. So the difference
// to look for is
// an ABSENCE: no white line inside its casing over Breakneck, no blue or yellow park trails,
// one red at two weights instead. hudson-highlands-blaze-colors.mjs is this
// same frame with the switch on, which is the other half of the evidence.
//
// A REMEMBERED CAMERA, THEN A RELOAD: lib/cameraMemory.ts's contract, as
// network-above-the-seam.mjs seeds it, so the map is built at this camera
// rather than moved there - and no location fix, no account, nobody's
// reports: the plate reads "Location is off", which is the truth about the
// runner's phone.
// AMENDED 2026-09-18 (#1588): the same frame, and what changed in it is the
// default's whole vocabulary. "Ok Im not so convinced about these strong
// redlines. could you show what these would look like as light dashed?" -
// so the park's trails are dashed and thinner now and a badged trail a
// plain solid red with no casing (map/style.ts's header, rule 2) - none runs
// through this frame, so it shows the dash alone. AMENDED 2026-09-20
// (#1597): those dashes were 45% of the red over the paper until then, and
// this frame is where the maintainer read them as pink, so they are the
// A.T.'s own red here now. The switch still restores the previous look,
// which hudson-highlands-blaze-colors.mjs shows.
export const caption =
  'The Hudson at Dutchess Junction on a laptop, z13, with blaze colours OFF — the shipped default: since #1588 every trail without a pill is thinner and dashed (2 px, 3 on and 2.5 off), and since #1597 it is the palette’s Red at full strength rather than the 45% tint over paper this frame was where the maintainer read as pink; no badged trail runs through this frame — the nearest A.T. point is 9 km east of the camera, measured off the release’s centerline — so every line in it is that dash; the maintainer’s pick from two sheets of mock-ups, replacing #1575’s first cut in which every trail was a solid red line inside a dark casing. The legend beside the map opens on its "Blaze colors" toggle, first under the Legend / In view pills and off, reading "Every trail as one red line. Tap a line for its blaze." hudson-highlands-blaze-colors.mjs is this frame with the switch on, where the previous vocabulary — solid, cased, in the blazes’ hues — still draws'
export const alt =
  'A wide browser window with the OurHike sidebar down the left, the map filling the middle over the Hudson River at Dutchess Junction with contour lines on the hills and none along the water, every trail a thin red dashed line with no solid line among them, and the legend panel down the right: a Blaze colors row with a toggle switch, off, first under the Legend and In view pills, then the waypoint category grid, the Closure and Serious warning rows, the "Read all trail notices" link directly under them, and the Showing, Verified, Alerts and Drought switches'

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
