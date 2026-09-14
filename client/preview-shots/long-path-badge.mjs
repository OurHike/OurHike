// Two through-routes below the seam, each wearing its own mark (2026-09-11).
//
// THE MAINTAINER'S OWN FRAME. Opening the app over the Hudson at z7 showed
// the A.T. wearing its pill and the Long Path, in aqua beside it, wearing
// nothing: "All long distance trails should have that Pill and a logo." The
// cause was not a collision and not the badge layer. Below POI_PIN_MIN_ZOOM
// the other organizations' trails draw from one coarse sketch
// (lib/config.ts's NETWORK_OVERVIEW_KEY), and the copy in the bucket carries
// source, blaze and status and no name at all - 38 features, none named,
// read live that day - so map/trailsInView.ts skipped every one of them and
// the Long Path was neither badged nor listed. The A.T. was unaffected
// because it draws from its own file, which is named at every zoom.
//
// The exporter has named the sketch's qualifying trails since #1307 and its
// test pins that; the artifact is simply older than the exporter, because
// the publish that would refresh it is held back with the network file it
// sketches (#1293's two New Jersey sources). So the client now takes the
// name from lib/trails.ts for a source the badge already marks
// (map/trailBadges.ts's registryNameForSource) - which is the same claim the
// mark makes, and fires for those two sources alone.
//
// WHY THIS CAMERA AND NOT trail-screen.mjs's. The opening view fits the
// whole corridor, where the Long Path is a thumbnail squiggle over New York
// and its badge says little. z7 over the Hudson is the frame the maintainer
// was actually reading, and it holds both marks at a size that shows which
// is which.
//
// WHAT MAY DIFFER BY BUILD, said rather than promised: the badge falls back
// to the mark alone where the full pill has no free position, so either
// trail may show its roundel without its name. Both are the badge; the
// layer's own fallback is map/trailsInView.ts's, not a fault in this frame.
//
// Nobody's data is in the frame: no account, no notes, no location fix, and
// no waypoints at all - this is below the pin seam (#1292).

export const caption =
  'Two through-routes over the Hudson at z7, below the seam — the A.T. on its pill and the Long Path on NYNJTC’s mark beside it, where the published sketch carries no names and the Long Path wore nothing (2026-09-11)'
export const alt =
  'A phone map over the Hudson valley from New York City to Albany: the Appalachian Trail as a white cased line running north-east with a paper pill naming it and the round ATC mark, and the Long Path as an aqua line to its west carrying the round green-and-white NYNJTC Long Path mark on its own plate'

/** The corridor sketch and the generated contours both land well after the
 *  chrome; trail-screen.mjs's own note sizes this, and this frame needs the
 *  same 10.8 MB network overview cut into tiles in a worker before any of
 *  these lines exist to badge. Two seconds over that recipe's 10 s because
 *  the badge is the SUBJECT here: on the rig a 13 s settle photographed a
 *  hillshade with no trail on it at all, and 20 s photographed both pills. */
export const wait = 12000

export default async function drive(page) {
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-73.7, 42.0], zoom: 7 }),
    )
  })
  await page.reload({ waitUntil: 'load' })
  await page.getByRole('tab', { name: 'Map' }).click()
}
