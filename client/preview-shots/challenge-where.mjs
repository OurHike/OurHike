// "Where did it happen?" with location off (#1963, frame
// features/design/blaze-card/Where.dc.html): the seeded hiker earns "Take a
// photo of a white blaze" - an at-home item the ATC's wording puts on the
// trail - from its tile, and the sheet opens on "On the trail, somewhere"
// because this phone has no fix. No Here card, and nothing asking for one.
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs, no location granted.
import { EVENING, openChallenges, seedChallenges } from './fixtures/challenges.mjs'

export async function before(page) {
  await page.clock.setFixedTime(EVENING)
}

export const caption =
  'Where did it happen? with location off: opens on On the trail, somewhere (#1963, seeded hiker)'
export const alt =
  'A sheet headed Where did it happen? over a dark green top, with cards for Pick a place, On the trail somewhere with a state menu, and Not on the trail, and an Earn it here button'

export default async function drive(page) {
  await seedChallenges(page)
  await openChallenges(page)
  await page.getByRole('button', { name: /A\.T\. Summer Bucket List/ }).click()
  await page.getByRole('button', { name: 'Experience', exact: true }).click()
  await page
    .getByRole('button', { name: /Earn it: Take a photo of a white blaze/ })
    .click()
  await page.getByRole('dialog', { name: 'Where did it happen?' }).waitFor()
}
