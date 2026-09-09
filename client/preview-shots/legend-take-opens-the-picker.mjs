// Taking a trail from the legend now opens the door that sets a hike (#1352).
//
// WHAT THIS SHOT IS EVIDENCE FOR, and it is the whole of Part 1 in one
// frame. Before this change the legend's `take` button wrote
// `chosen_trail_id`, a map-only preference that nothing else in the app
// read: a hiker could take the A.T. here and still have no hike in Plan, or
// have a hike in Plan and an untaken map. The button now opens the same
// "Which long hike?" sheet the Long hike mode switch opens, because the
// map's taken trail IS the active hike's trail since the merge. One state,
// one door onto it.
//
// WHY IT IS A SECOND RECIPE AND NOT A TOUCH ON long-hike-pick.mjs. That
// recipe's evidence is the sheet itself - its lede, its one door, what
// closing it costs - reached from the mode switch, and it says so. This
// one's evidence is WHERE THE SHEET CAME FROM: the same sheet arriving from
// the map's legend, which is the connection #1352 made and which no frame
// showed before. Re-pointing long-hike-pick.mjs would have traded its claim
// for this one, which is the trade legend-trails-in-view.mjs's own header
// argues against.
//
// WHAT IT IS NOT EVIDENCE FOR. That the sheet leads anywhere good from here
// - long-hike-setup.mjs is what its door opens, unchanged by this pull
// request. Nor that the map behind it is right: the sheet covers it, and
// legend-trails-in-view.mjs is the frame for what the map does once a hike
// is active.
//
// NOTHING TAKEN AND NOBODY'S DATA. A clean launch with no seeded hike, which
// is both the state this button is interesting in and the state with no
// account, no reports and no location fix in it.

// WHAT THE FRAME ACTUALLY HOLDS, checked against the photographed PNG
// rather than assumed from the drive (2026-09-09). The ground behind the
// sheet is a flat blank, not the map with the legend on it: the legend
// panel blanks the canvas under this camera (#1138) and the sheet's own
// scrim covers the panel, so nothing of either survives into the picture.
// The caption said "risen over the map screen with its legend behind it"
// until the PNG was opened and it plainly was not - the exact "display
// outruns its source" failure CLAUDE.md names, on the one artefact a
// reviewer reads instead of running the branch. What this frame is evidence
// for is the DOOR: the drive tapped the A.T.'s legend row and this is what
// the tap reached. legend-trails-in-view.mjs is the frame with the map and
// the rows in it.
export const caption =
  'What the legend’s “take” on the A.T. now opens (#1352): the same “Which long hike?” sheet the mode switch opens, reached by tapping the A.T.’s legend row. The map’s taken trail is the active hike’s trail now, so taking one from the legend goes through the door that sets a hike rather than writing a second, map-only state beside it. The ground behind is blank because the legend blanks the canvas under this camera (#1138) and the sheet covers the legend — this frame is evidence about the door, not about the map'
export const alt =
  'A bottom sheet titled "Which long hike?" over a blank field, explaining that a long hike follows one trail and that closing it returns to Day hike, with one door reading "A new long hike"'

/** The rows are measured off a settled frame, same as
 *  legend-trails-in-view.mjs: the button cannot be tapped before the map has
 *  drawn the line the row is about. */
export const wait = 6000

export default async function drive(page) {
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.09, 41.25], zoom: 12 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  await page.getByRole('tab', { name: 'Map' }).click()
  await page.waitForTimeout(wait)

  await page.getByRole('button', { name: 'Legend' }).click()
  await page.getByRole('heading', { name: 'Trails in view' }).waitFor()

  // The row's own button, which reads `take` while nothing is taken.
  await page.getByRole('button', { name: /Appalachian National Scenic Trail/ }).click()

  await page.getByRole('dialog', { name: 'Which long hike?' }).waitFor()
}
