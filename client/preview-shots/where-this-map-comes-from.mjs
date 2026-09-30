// "Where this map comes from", with an organization's own two buttons on its
// card (#1574 - A hiker on NYNJTC ground has nowhere to buy the paper map for
// where they are).
//
// WHAT THIS SHOT IS EVIDENCE FOR. Since #932 the registry has recorded, in
// each organization's own words, how to support it - and nothing rendered
// it, which FEATURES.md said in as many words ("No surface in the app links
// out to them yet"). This frame is that sentence going false: the NYNJTC
// card carries "Donate Today ›" (theirs, nynjtc.org/support) and "Trail
// Maps ›" (theirs, the store's map collection), the ATC card carries "Become
// a Member ›", and the framing line under the heading has gained the half
// that was held back until a link existed - "OurHike takes no cut and holds
// no money".
//
// WHAT IT IS NOT EVIDENCE FOR. Which organizations are really on a phone:
// fixtures/stewards.mjs seeds two, because the preview's phone has
// downloaded nothing and the section renders nothing for nobody. The real
// list is whatever the pinned release publishes.
//
// Nothing here reaches an account, a hiker's own report, a dispersed
// campsite or a real location fix (.claude/skills/pr-screenshot/SKILL.md).

import { seedStewards } from './fixtures/stewards.mjs'

export const caption =
  'Where this map comes from — the organization’s own buttons (#1574)'
export const alt =
  'The "Where this map comes from" section of the More tab: a framing line saying each organization sets its own licence and that every link opens the organization’s own site, OurHike taking no cut; then a card for the Appalachian Trail Conservancy with its licence and a "Become a Member ›" link, and a card for the New York-New Jersey Trail Conference with two layers, an authoritative tier, its recorded terms, and two links, "Donate Today ›" and "Trail Maps ›"'

export default async function drive(page) {
  await seedStewards(page)
  await page.reload({ waitUntil: 'load' })

  // Two taps, by the tab's name and the row's - the route about-this-build.mjs
  // takes, for the same two reasons it records.
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /Where this map comes from/ }).click()

  // Settle on the thing the shot is about rather than on a delay: the NYNJTC
  // card's store link is the last thing rendered from the seeded list, so it
  // being in the DOM is the whole of "the cards are up".
  const storeLink = page.getByRole('link', { name: 'Trail Maps ›' })
  await storeLink.waitFor()
  await storeLink.scrollIntoViewIfNeeded()
}
