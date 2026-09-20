// The same closed trails as long-term-closures.mjs, from the opening camera:
// Bear Mountain and Doodletown at z8, below the seam, where a closure is a
// handful of pixels long and the band has to say "do not walk this" anyway.
//
// WHY THIS FRAME EXISTS (#1598). The maintainer, 2026-09-20: "The trail
// closures are not easily visible. Adjust the settings so that the closures
// are readily apparent at all the zoom levels." The z13 frame beside this one
// was the only photographed closure, and it is the easy zoom - a 1.5 km
// closure is 104 px long there. Here the same closure is between three and
// seven pixels (461 m per pixel at latitude 41), which is the zoom the
// complaint is actually about and the one no shot reached.
//
// WHAT TO LOOK FOR, AND WHAT THIS FRAME IS EVIDENCE OF. Along the closed
// runs west and south of Bear Mountain: short dark-edged red blocks. Two
// things put them there, both new on 2026-09-20 and both visible only at
// this camera. The band carries a hard outline (CLOSURE_OUTLINE_WIDTH), so
// what is left to recognise at four pixels is a shape rather than a texture;
// and below the seam the tape steps to a half-scale cadence
// (CLOSURE_TAPE_OVERVIEW_CADENCE), so a closure shorter than the navigation
// tape's 12 px pitch still crosses a stripe instead of landing between two
// and drawing as a blank slab of the sheet's paper. Against the previous
// build, where the same closures drew as 14 px white bands with, on most of
// them, no red in them at all.
//
// The lines under them are the default's, and one of those is new too
// (#1597): every trail here is the A.T.'s own red, where until 2026-09-20 a
// trail without a pill was 45% of that red over the paper. At this camera
// the A.T. and the Long Path are their own sketch lines and everything else
// is the generic haze, so what the change shows here is the haze's hue.
//
// The same seeding as long-term-closures.mjs - a remembered camera and a
// reload - and the same rule: no location fix, no account, nobody's reports.
export const caption =
  'Bear Mountain and the lower Hudson from the opening camera, z8, Blaze colors off (the default): the same OPRHP closed trails long-term-closures.mjs photographs at z13, each three to seven pixels long here. Since #1598 a closure at this camera is a dark-edged red block rather than a blank white band — the outline is what survives being four pixels long, and the tape steps to a half-scale cadence below the seam so a short closure still crosses a stripe. Every trail line in the frame is #1597’s one red rather than the 45% tint it was until 2026-09-20'
export const alt =
  'The map screen over the lower Hudson valley at zoom 8: a dense web of thin red trail lines across New York with the Appalachian Trail heavier among them, and around Bear Mountain several very short wide marks laid across individual trails, each a red block inside a dark outline, marking closed trails at a zoom where a whole closure is only a few pixels long'

/** Vector tiles from the bucket plus generated contours across a whole
 *  valley: the overview camera loads the network overview rather than the
 *  full tiles, so the same allowance the z13 frame makes is generous here. */
export const wait = 22000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract, as long-term-closures.mjs seeds it, at
  // the zoom this frame is about: the centre of the densest cell of closed
  // lines the release carries, from two thousand feet further back.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.005, 41.308], zoom: 8 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: the runner installs that
  // through an init script on the context (scripts/screenshot.mjs's
  // skipFirstRun), which re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
