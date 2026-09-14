// Your photos and notes (#1373, D5): the hiker's own work on this phone,
// under More → You, and the summonable door to a place that has left the
// map.
//
// WHAT THIS SHOT IS EVIDENCE FOR. The door under You and the screen's own
// rule, printed on every state: notes leave with the send and are not kept
// here once they have gone; photos stay on this phone whether or not they
// were shared, and a retired place keeps them too. The preview's phone holds
// no photos and no notes - a photo is somebody's data, and the skill's
// never-photograph list keeps it that way - so the frame is the empty
// sentence over that rule. YourWork.test.tsx holds the rows, including the
// one for a place no longer on the map.
export const caption =
  'Your photos and notes, under You — the door, and the rule it lists by, on a phone holding neither (#1373, D5)'
export const alt =
  'The More tab’s You page opened to a "Your photos and notes" heading with the sentence "Nothing here yet. A photo or a note starts from a waypoint’s card on the map." and, under it, the note that notes leave with the send and photos stay on this phone; a back link reads "‹ You"'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /^You/ }).click()
  await page.getByRole('button', { name: 'Your photos and notes' }).click()
  await page.getByText(/Nothing here yet/).waitFor()
}
