// The same closed trails as long-term-closures.mjs, from an overview camera:
// Bear Mountain and Doodletown at z10, below the zoom where the band's near
// rhythm draws, where a closure is a few pixels long and the mark has to say
// "do not walk this" anyway.
//
// WHY THIS FRAME EXISTS (#1598). The maintainer, 2026-09-20: "The trail
// closures are not easily visible. Adjust the settings so that the closures
// are readily apparent at all the zoom levels." The z13 frame beside this one
// was the only photographed closure, and it is the easy zoom - a 1.5 km
// closure is 104 px long there. Here the same closure is nine to sixteen
// pixels (115 m per pixel at latitude 41), which is short enough to be the
// case the second rhythm exists for and long enough to photograph.
//
// WHY IT IS z10 AND NOT z8, WHICH IS WHERE IT STARTED. At z8 this recipe
// showed a closure two to four pixels long - the zoom the complaint is
// really about - and what it actually photographed was 6,677 waypoint pins
// with the closures somewhere in the middle of them. The pins do not COVER
// the marks (every closure and warning draws above them, #1599), but at that
// density a four-pixel mark is lost in the noise rather than under anything,
// and a frame that claims to show a closure and shows a pin carpet is worse
// than no frame - .claude/skills/pr-screenshot/SKILL.md's own rule. The z8
// density is a real open question about the opening camera and it is raised
// in the pull request rather than answered by a screenshot that cannot see
// it.
//
// WHAT TO LOOK FOR. Along the closed runs west and south of Bear Mountain:
// short red-and-white blocks inside a hard dark edge. Two things put them
// there, both new on 2026-09-20 and both visible only at a camera like this
// one. The band carries an outline (CLOSURE_OUTLINE_WIDTH), so what is left
// to recognise at ten pixels is a shape rather than a texture; and below z11
// the band steps to a half-scale rhythm (CLOSURE_OVERVIEW_DASH), so a closure
// shorter than the navigation band's pitch still carries a tick instead of
// landing between two and drawing as a blank slab of the sheet's paper. z11
// is where the shortest closed run on this map first clears one near pitch.
// Against the previous build, where the same closures drew as 14 px white
// bands with, on most of them, no red in them at all.
//
// The lines under them are the default's, and one of those is new too
// (#1597): every trail here is the A.T.'s own red, where until 2026-09-20 a
// trail without a pill was 45% of that red over the paper.
//
// The same seeding as long-term-closures.mjs - a remembered camera and a
// reload - and the same rule: no location fix, no account, nobody's reports.
export const caption =
  'Bear Mountain and the lower Hudson at z10, below the zoom the band’s near rhythm draws at, Blaze colors off (the default): the same OPRHP closed trails long-term-closures.mjs photographs at z13, nine to sixteen pixels long here. Since #1598 a closure at this camera is a dark-edged red block rather than a blank white band — the outline is what survives at that length, and the band steps to a half-scale rhythm below z11 so a short closure still carries a tick. This frame was z8 until 2026-09-21, where it photographed 6,677 waypoint pins with the closures lost among them; that density is a real question about the opening camera and it is raised in the pull request rather than answered here'
export const alt =
  'The map screen over Bear Mountain State Park and the lower Hudson at zoom 10: a web of thin red trail lines with the Appalachian Trail heavier among them, and along several trails around Bear Mountain short wide marks laid across the line, each a red and white block inside a dark outline, marking closed trails at a zoom where a whole closure is only a few pixels long'

/** Vector tiles from the bucket plus generated contours across a park and
 *  its valley, the same allowance the z13 frame makes. */
export const wait = 22000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract, as long-term-closures.mjs seeds it, at
  // the zoom this frame is about: the centre of the densest cell of closed
  // lines the release carries, from three zooms further back.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.005, 41.308], zoom: 10 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: the runner installs that
  // through an init script on the context (scripts/screenshot.mjs's
  // skipFirstRun), which re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
