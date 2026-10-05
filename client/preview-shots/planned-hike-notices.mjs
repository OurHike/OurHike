// The notices panel as decision 66 chose it (#1805): the notices that touch
// a hike the hiker has planned for the next 7 days, and nothing else - with
// decision 76's state-wide agency notice, placed by its state, and decision
// 78's category line under a row's title.
//
// WHAT A REVIEWER SHOULD CHECK IN THE FRAME, against
// decisions-64-67-mock.html §3, statewide_notice_mock.html's frame A,
// gatc_tiger_questions.html's card N2 frame A and the rule in
// client/src/lib/plannedNotices.ts:
//
//  0. First, the invented Canyon rim loop on BLM's trails in Utah, today.
//     On its route, an invented Forest Service campground tagged Notice,
//     with "Closed" under its title in the caution tint and its forest
//     under that (decision 78, card N2's frame A): the row's category is
//     USFS's own `openstatus`, "closed", with its first letter raised by the
//     panel. Then BLM's invented Utah fire restrictions tagged Notice (never
//     Advisory: nothing in the data says what the page restricts), its where
//     line "All of Utah", credited to the Bureau of Land Management with its
//     link (decision 76, frame A). The hike's taps are joined by a straight
//     line, which its section says, because the preview's phone holds no
//     trail network in Utah.
//  1. One section per planned hike, each named and dated: the long hike's
//     stretch for the next 7 days (Neels Gap to Dicks Creek Gap), and the day
//     hike (Pine Meadow loop, in two days).
//  2. ATC's closure at mile 50.3 under the long hike, tagged Closure, because
//     the miles planned for today and tomorrow run past it. Its category is
//     "Closure" too, and the panel does not say it twice.
//  3. The hunting area the day hike's route crosses, tagged Advisory with
//     its own category "Hunting area" under the title and "Hunting allowed"
//     (decision 67) under that, never as a closure.
//  4. NYNJTC's unplaced notice under the day hike's "From the clubs" line,
//     because the loop walks the Long Path, which NYNJTC maintains.
//  5. No far club's notice and no distant shooting site: they are in the
//     file and touch no planned hike, so they are not in the panel.
//
// THE NOTICES ARE INVENTED and each title says "(example)"
// (fixtures/plannedNotices.mjs): conditions/notices.json is written only by
// the dbt path, so the bucket a preview reads may not hold it, and a recipe
// must never photograph a real club's notice as if it said something it did
// not. The file is answered on the wire before the app loads (`before`).
//
// Nothing here reaches an account, a hiker's own report, a dispersed campsite
// or a real location fix (.claude/skills/pr-screenshot/SKILL.md): the hikes
// are the existing fixtures' invented ones, and the panel draws no map.
import { seedDayHikes } from './fixtures/dayHike.mjs'
import { seedLongHike } from './fixtures/longHike.mjs'
import {
  plannedDayHikes,
  plannedNoticeStewards,
  routePlannedNotices,
} from './fixtures/plannedNotices.mjs'
import { seedStewards } from './fixtures/stewards.mjs'

export const caption =
  'Notices for your planned hikes — what touches a hike in the next 7 days, an agency’s state-wide notice for a hike in its state, and each row’s own category under its title (decisions 66, 76 and 78, #1805). Every notice is an invented example.'

export const alt =
  'The notices panel headed "Notices for your hikes", with a note that it shows notices touching a hike planned to start in the next 7 days. First a section for the day hike "Canyon rim loop (example)" today, with a Notice row for an example campground in Manti-La Sal National Forest whose category line under the title reads "Closed", and a Notice row for example Stage 1 fire restrictions on BLM land in Utah, reading "All of Utah" and credited to the Bureau of Land Management. Then a section for the long hike "Neels Gap → Dicks Creek Gap" with its dates and a Closure row for an example footbridge out, credited to the Appalachian Trail Conservancy; a section for the day hike "Pine Meadow loop" with an Advisory row for an example hunting area, its category "Hunting area" under the title, reading "Hunting allowed", credited to New York State Parks, and, under a line saying they come from the clubs that look after these trails, an example notice from the New York-New Jersey Trail Conference. Every notice is an invented example.'

export const before = routePlannedNotices

export default async function drive(page) {
  // The steward list first (no reload), then the long hike (reloads into
  // long-hike mode and waits for it), then the day hike (reloads again):
  // each seed lands before the reload that makes the app read it.
  await seedStewards(page, plannedNoticeStewards())
  await seedLongHike(page)
  await seedDayHikes(page, plannedDayHikes())

  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Legend' }).click()
  // The row's stable half, not its count: the count is the fixture's today
  // and a reworded fixture should not break the drive.
  await page.getByRole('button', { name: /Notices for your planned hikes/ }).click()
  const panel = page.getByRole('dialog', { name: 'Notices for your planned hikes' })
  await panel.waitFor()
  // Decision 76's row, which needs conditions/notice_states.json read beside
  // the notices: waiting on it proves both files arrived and the rule placed
  // the notice by its state.
  await panel.getByText('All of Utah').waitFor()
  // Decision 78's line: the invented campground's category, "closed" in the
  // file, shown as "Closed" under its title.
  await panel.getByText('Closed', { exact: true }).waitFor()
  // Then put the legend away: the panel opens in the sheet slot under it,
  // and the legend's own rows would cover all but its first hike (the same
  // clipping trail-notices.mjs records). The panel stays open; waiting on it
  // again is what proves the close did not take it too.
  await page.getByRole('button', { name: 'Close legend' }).click()
  await panel.waitFor()
}
