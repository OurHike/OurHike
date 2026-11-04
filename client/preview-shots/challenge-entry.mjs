// The entry, visible from day one (#1964): "Your entry" from the challenge's
// own page at 3 of 25, opening on what the ATC receives, the one-entry
// rule, the mystery drawings line and when the entry opens - with nothing
// to send yet and nothing sent.
import { EVENING, openChallenges, seedChallenges } from './fixtures/challenges.mjs'

export async function before(page) {
  await page.clock.setFixedTime(EVENING)
}

export const caption =
  'The entry at 3 of 25: what the ATC receives, one entry per person, the entry opens at 25 (#1964, seeded hiker)'
export const alt =
  'A screen headed You walked A.T. Summer Bucket List with a draft banner, a line reading 3 earned over 2 days, a list of what the ATC receives, One entry per person, and The entry opens at 25 for the drawing'

export default async function drive(page) {
  await seedChallenges(page)
  await openChallenges(page)
  await page.getByRole('button', { name: /A\.T\. Summer Bucket List/ }).click()
  await page.getByRole('button', { name: 'Your entry' }).click()
  await page.getByText(/What the ATC receives/).waitFor()
}
