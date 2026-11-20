// The share poster's sheet (#1965, frame features/design/blaze-card/
// Poster.dc.html): "Share your summer", opened from the Where view.
//
// WHAT THIS SHOT IS EVIDENCE FOR. The poster drawn on the phone and shown as
// the image that would be shared: the list's name and year, "My summer on the
// A.T.", the count of trail karma, the card's tiles with the earned ones gold,
// the fourteen states, and the club's name. Under it the two choices. The
// sheet opens on the map poster when the phone holds the map (the
// maintainer's poll, 2026-11-04); CI's preview has no challenge_map.json until
// a publish after #1965's merge, so this shot is the states poster with the
// map card saying "No map on this phone yet." - the honest fallback. Waits
// for the image, so the shot is of a finished poster rather than "Making your
// poster…".
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs; the clock inside the window.
import { EVENING, openChallenges, seedChallenges } from './fixtures/challenges.mjs'

export async function before(page) {
  await page.clock.setFixedTime(EVENING)
}

export const caption =
  'Share your summer: the poster made on the phone - the map version when the phone holds the map, the states version otherwise (#1965, seeded hiker)'
export const alt =
  'A sheet headed Share your summer showing a dark green poster with the list name, My summer on the A.T., a large count, a card of tiles with gold earned ones and a strip of state columns, then two option cards, The map and The states, and a Share or Save the image button'

export default async function drive(page) {
  await seedChallenges(page)
  await openChallenges(page)
  await page.getByRole('button', { name: /A\.T\. Summer Bucket List/ }).click()
  await page.getByRole('button', { name: 'Where', exact: true }).click()
  await page.getByRole('button', { name: /Share your/ }).click()
  await page.locator('.poster-sheet__image').waitFor({ timeout: 20_000 })
}
