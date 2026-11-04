// The blaze card made bigger (#1962): the one state in which a tile is a
// button - 56 px, named by its item - and the state the brief's open thumb
// question (pinch or a button) is polled with.
import { EVENING, openChallenges, seedChallenges } from './fixtures/challenges.mjs'

export async function before(page) {
  await page.clock.setFixedTime(EVENING)
}

export const caption =
  'The blaze card at 56 px: every tile a button, Smaller tiles under it (#1962, seeded hiker)'
export const alt =
  'The same challenge header with the card’s tiles drawn large enough to tap, each showing its glyph, the earned ones white, and a Smaller tiles button'

export default async function drive(page) {
  await seedChallenges(page)
  await openChallenges(page)
  await page.getByRole('button', { name: /A\.T\. Summer Bucket List/ }).click()
  await page.getByRole('button', { name: 'Bigger tiles' }).click()
  await page.locator('.blaze-card--expanded').waitFor()
}
