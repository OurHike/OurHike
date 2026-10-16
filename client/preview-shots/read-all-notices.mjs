// The "Read all" door beside the planned-hike row (the
// maintainer's poll of 2026-10-15, "Keep a 'Read all' door (Recommended)").
//
// WHAT A REVIEWER SHOULD CHECK IN THE FRAME: the legend with no hike planned,
// its notices rows under the serious-warning row -
//
//  1. "Notices for your planned hikes", as before: with nothing planned it
//     opens the panel that says so (planned-hike-notices.mjs is that panel);
//  2. directly under it, the new door, "Read all club notices not on the
//     map", in the old "Read all N trail notices" row's own style. With no
//     hike planned the phone has not downloaded conditions/notices.json,
// so the door names no count until it has; a tap downloads
//     it and lists every club's notice that no map draws.
//
// THE NOTICES ARE INVENTED (fixtures/plannedNotices.mjs's, each title saying
// "(example)"), answered on the wire before the app loads (`before`), so the
// bucket's HEAD for notices.json says it serves the file, which is what puts
// the legend in the planned-hike mode at all. No hike is seeded.
//
// Nothing here reaches an account, a hiker's own report, a dispersed campsite
// or a real location fix (.claude/skills/pr-screenshot/SKILL.md).
import { plannedNoticeStewards, routePlannedNotices } from './fixtures/plannedNotices.mjs'
import { seedStewards } from './fixtures/stewards.mjs'

export const caption =
  'The legend with no hike planned: under “Notices for your planned hikes”, the new “Read all club notices not on the map” door (the maintainer’s poll of 2026-10-15), in the old “Read all N trail notices” row’s style.'

export const alt =
  'The map legend open on a phone. Below the key’s serious-warning row are two link rows: "Notices for your planned hikes", and directly under it "Read all club notices not on the map".'

export const before = routePlannedNotices

export default async function drive(page) {
  await seedStewards(page, plannedNoticeStewards())
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Legend' }).click()
  // The door appears once the bucket's answer has put the legend in the
  // planned-hike mode: waiting on it proves that answer arrived.
  const door = page.getByRole('button', {
    name: /^Read (all|the 1) .*club notices? not on the map$/,
  })
  await door.waitFor()
  await door.scrollIntoViewIfNeeded()
}
