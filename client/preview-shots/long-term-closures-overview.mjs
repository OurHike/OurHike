// CROSSED OUT SINCE 2026-09-26 (#1677), and at this camera that means
// something new: below z11 a closure is one large dark x per closed run,
// placed at the run's middle, rather than any mark along the line. A closure
// here is nine to sixteen pixels long, too short to carry a chain. The runs
// themselves are knocked out of the red to thin white bands with a dotted
// trace. The notes below describe the red blocks this frame used to show,
// and why. WHAT TO LOOK FOR NOW: a few bold x marks over Bear Mountain and
// Doodletown, not one per closed trail. Far marks thin each other out by
// collision, so a park with two dozen closed trails reads as a handful of
// crosses rather than a scribble. And against the waypoints in this frame
// - 426 in view on CI's first photograph of it, at 3453b43 - the crosses
// draw above the pins and win the pixels, and a pin under one falls back to
// its dot (#1676) rather than disappearing.
//
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
// WHAT TO LOOK FOR, AND WHAT THIS FRAME ALSO SHOWS. Along the closed runs
// west and south of Bear Mountain: red-and-white blocks inside a hard dark
// edge, plainly findable among 800 waypoints where the z8 version of this
// frame lost them among 6,677. At Doodletown itself they MERGE into one
// mass - this is the densest closure cell in the release, where OPRHP marks
// trail after trail closed, and at 11 px wide the neighbouring bands touch.
// MAGNIFIED 4x THE BLOCK STRUCTURE DOES NOT SURVIVE THERE, and the caption
// says so rather than promising blocks a reviewer will not find: the merged
// cell is a red mass carrying white wedges, because a tick splays where the
// bend is tight against an 11 px width - railway ties on a curve, which
// reads correctly at z13 and becomes a starburst at this one - and because
// each band's casing cuts across its neighbour's ticks where they overlap.
// That is a true thing about that ground rather than a rendering fault, and
// it is left in the frame rather than photographed around: a reviewer
// should see what a park with two dozen closed trails looks like at an
// overview camera. Two things put them
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
  'Bear Mountain and the lower Hudson at z10, Blaze colors off (the default), crossed out (#1677): below z11 a closure is one bold dark x per closed run, at its middle, over the run knocked out of the red to a thin white band with a dotted trace. A closure here is nine to sixteen pixels long, too short to carry the chain of small crosses the z13 frame shows. Far marks thin each other out by collision, so the two dozen closed trails around Doodletown read as a handful of crosses rather than a scribble. They draw above the waypoint pins and win the pixels; a pin under one falls back to its dot (#1676), so no waypoint is hidden. Whether they outshout the pins is the question this frame is here to answer.'
export const alt =
  'The map screen over Bear Mountain State Park and the lower Hudson at zoom 10: a web of thin red trail lines with the Appalachian Trail heavier among them, waypoint pins, and around Bear Mountain a few bold dark x marks with white edges, each over a short white dotted line where a trail is closed.'

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
