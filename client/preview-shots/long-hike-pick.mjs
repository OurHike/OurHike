// "Which long hike?" (#1317) - the sheet tapping Long hike opens when no
// hike is picked yet.
//
// WHAT THIS SHOT IS EVIDENCE FOR. That the mode switch is now a door: the
// segment reads chosen-but-pending at .55 behind the sheet, and the lede
// says out loud what closing it does ("Close this and you're back on Day
// hike") - the one place in the app where tapping a mode segment is not
// instantaneous, said on screen rather than only in a comment.
//
// WHAT IT IS EVIDENCE FOR SINCE #1329: that the PHONE did not move. The
// sheet is one `.hike-window--sheet` now, shared with every other long-hike
// surface, and every difference between a phone and a laptop lives in
// desktop.css - so this frame has to be the same frame it was before that
// change, and long-hike-window-desktop.mjs is what the laptop looks like.
//
// WHAT IT IS NOT EVIDENCE FOR. The list of existing hikes. This phone has
// none, which is deliberately the frame a first-time hiker gets: one door,
// "A new long hike", with nothing above it. long-hike-setup.mjs is what that
// door opens.
export const caption = 'Which long hike? — the sheet behind the mode switch (#1317)'
export const alt =
  'A bottom sheet titled "Which long hike?" over the Today screen, explaining that a long hike follows one trail and that closing the sheet returns to Day hike, with one door reading "A new long hike"'

export default async function drive(page) {
  await page.getByRole('radio', { name: 'Long hike' }).click()
  await page.getByRole('dialog', { name: 'Which long hike?' }).waitFor()
}
