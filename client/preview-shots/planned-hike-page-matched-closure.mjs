// A closed section a person matched to an item on the trail's closures page,
// as the planned-hike notices panel shows it (#1805, decision 128: the
// maintainer's poll of 2026-10-09, shown w6-ptny-closures.html).
//
// WHAT A REVIEWER SHOULD CHECK IN THE FRAME, against that mock's frame A and
// the two lines in its dashed box:
//
//  1. One planned day hike, today: the invented "Waterfront walk (example)".
//  2. Under "On your route", a Closure row titled "Shoreline Trail (example)",
//     credited to Parks & Trails New York with no date on that line: PTNY's
//     layer dates nothing.
//  3. Under it, "On the trail’s closures page — updated <the page's day>" and
//     the link "Read the trail’s closures page": the page's day and link,
//     which is all decision 128 lets such a row say beyond "Closed".
//
// WHERE THIS SHOWS, AND WHERE IT DOES NOT. A club's or an agency's closure
// reaches a phone only in this panel, for a hike planned through it (decision
// 77: notices.json is downloaded only once a hike is planned). The mock's
// frame A also drew the section as a ✕ on the map; the map draws no
// organization's closure line today, so that half is not here and is not
// built.
//
// THE NOTICE IS INVENTED and its title says "(example)"
// (fixtures/plannedNotices.mjs's pageMatchedNoticesDocument): no section has
// been matched yet, so pipeline/dbt's notice_page_matches seed is empty and no
// real notices.json carries a `matched_page`. The organization, its registry
// key and the page's address are real; the walk, the line and the page's day
// are not.
//
// Nothing here reaches an account, a hiker's own report, a dispersed campsite
// or a real location fix (.claude/skills/pr-screenshot/SKILL.md): the hike is
// two invented taps, and the panel draws no map.
import { seedDayHikes } from './fixtures/dayHike.mjs'
import {
  pageMatchedDayHikes,
  pageMatchedNoticesDocument,
  pageMatchedStewards,
  routePlannedNotices,
} from './fixtures/plannedNotices.mjs'
import { seedStewards } from './fixtures/stewards.mjs'

export const caption =
  'A closed section matched to the trail’s closures page, in the notices for a planned hike — the page’s date and link under the organization (decision 128, #1805). The notice is an invented example.'

export const alt =
  'The notices panel headed "Notices for your hikes", with one section for the day hike "Waterfront walk (example)" today. Under "On your route" a Closure row titled "Shoreline Trail (example)", credited to Parks & Trails New York, then the line "On the trail’s closures page — updated" with the page’s date, and a link reading "Read the trail’s closures page". The notice is an invented example.'

export async function before(page) {
  await routePlannedNotices(page, pageMatchedNoticesDocument())
}

export default async function drive(page) {
  // The steward list first (no reload), then the day hike, which reloads the
  // app so it reads both.
  await seedStewards(page, pageMatchedStewards())
  await seedDayHikes(page, pageMatchedDayHikes())

  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Legend' }).click()
  await page.getByRole('button', { name: /Notices for your planned hikes/ }).click()
  const panel = page.getByRole('dialog', { name: 'Notices for your planned hikes' })
  await panel.waitFor()
  // Decision 128's line: proves the file arrived, the row met the walk's
  // route, and the panel read its matched page.
  await panel.getByText(/^On the trail’s closures page — updated /).waitFor()
  // Then put the legend away, as planned-hike-notices.mjs does: the panel
  // opens in the sheet slot under it.
  await page.getByRole('button', { name: 'Close legend' }).click()
  await panel.waitFor()
}
