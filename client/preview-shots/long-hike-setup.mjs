// Setting up a long hike (#1317).
//
// WHAT THIS SHOT IS EVIDENCE FOR. That the whole form is the points: a pine
// SETTING UP band with Cancel, the lede saying two ends is the whole
// requirement, the points list in RouteStopsPanel's own anatomy, "Add a
// point on the way", the note about what a third point means, the
// already-walked shelf, and a primary button refused with its reason until
// there are two ends. No "whole trail or a section?" toggle and no "do you
// have dates?" step - the absences are the design, and a shot is how a
// reviewer sees they are absent.
//
// WHAT IT IS NOT EVIDENCE FOR. A filled-in points list. Dropping points
// needs the stop picker over real trail data and a drive through it, which
// is a second recipe's job; this is the empty state, where the refusal line
// and the disabled primary are the things worth photographing.
export const caption = 'Setting up a long hike — the points are the whole form (#1317)'
export const alt =
  'A full screen with a pine SETTING UP band reading "A new long hike" and a Cancel button, a lede saying two ends is the whole requirement, an empty points list with "Add a point on the way", a note about what a third point means, an "Already walked some of it?" door, and a disabled "Start this long hike" button under the reason it is refused'

export default async function drive(page) {
  await page.getByRole('radio', { name: 'Long hike' }).click()
  await page.getByRole('button', { name: /A new long hike/ }).click()
  await page.getByRole('button', { name: 'Start this long hike' }).waitFor()
}
