// The Ten Essentials page (#1689), opened from the Plan tab's "Before you
// go" row.
//
// WHAT THIS SHOT IS EVIDENCE FOR. The banner at the head of the page, which
// is the only disclosure a hiker gets before a tap takes them to REI (the
// maintainer's choice, poll 2026-09-26, frame D). Read what it says: this
// build ships no affiliate code (lib/tenEssentials.ts's REI_AFFILIATE_LINK
// is null), so the banner says the links go to REI and does NOT claim a
// commission. When a code lands, the banner gains that sentence and this
// frame should show it.
//
// Then the list: ten rows, each a checkbox with a name and a line under it,
// and an "REI ↗" link to that category's page. Two are ticked by this recipe
// so the ticked state is in the frame. The foot says the ticks stay on this
// phone and offers "Clear all ticks".
//
// Nobody's data: the fixture hike, and two ticks this recipe makes.
import { seedLongHike } from './fixtures/longHike.mjs'

export const caption =
  'The Ten Essentials page: the banner that is the only disclosure, ten rows with an REI link each, two ticked (#1689, frame D)'
export const alt =
  'A screen headed "The Ten Essentials" under a "‹ Plan" crumb. A shaded note reads "Links on this page go to REI. Each one opens in your browser." Below it a list of ten rows, Navigation to Extra clothes, each with a checkbox, a one-line note and an "REI ↗" link; Navigation and Headlamp are ticked.'

export default async function drive(page) {
  await seedLongHike(page)
  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('heading', { level: 1, name: 'Springer → Katahdin' }).waitFor()
  await page.getByRole('button', { name: /Pack the Ten Essentials/ }).click()
  await page.getByRole('heading', { name: 'The Ten Essentials' }).waitFor()
  await page.getByRole('checkbox', { name: /Navigation/ }).check()
  await page.getByRole('checkbox', { name: /Headlamp/ }).check()
  await page.getByRole('heading', { name: 'The Ten Essentials' }).scrollIntoViewIfNeeded()
}
