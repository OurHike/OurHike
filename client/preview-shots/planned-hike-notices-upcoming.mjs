// Notices for your planned hikes, with closures that have not started yet
// (the maintainer's frame B, poll of 2026-10-11: "Shown now, marked with
// its start. It closes the trail only from its start day.").
//
// WHAT A REVIEWER SHOULD CHECK IN THE FRAME, against frame B of the
// maintainer's "show it now, as upcoming" wireframe (2026-10-11) and client/src/lib/noticeCurrency.ts's `startsAhead` and
// `obstructsOn`:
//
//  1. One section, the invented "Example Creek loop (example)", planned four
//     days from today, its four notices all on its route.
//  2. First, "Bridge out at Mill Creek (example)" from Example County Parks,
//     tagged Closure: in force, no start.
//  3. "Rim Trail closed for footbridge repair (example)" from Example Trail
//     Club, tagged "Starts <tomorrow, Mon D>" in the closure's caution tint,
//     its "from ... until ..." dates under it: today is the day before its
//     start, so it already closes the trail and sorts with the closures.
//  4. "Trail crew on the Example Creek Trail this week (example)", tagged
//     Notice, in the plain tint.
//  5. Last, frame B's row: "Emergency closure, Example Creek Trail (example)"
//     tagged "Starts <in three days, Mon D>" in the caution tint, then "from
//     <Month D, YYYY>", then Example State Parks. It does not close the trail
//     until the day before its start, so it sorts after the ordinary notice
//     above it. It is not greyed, though it gives only a start, which on its
//     own would grey it once begun.
//
// The frame drew the "Starts" tag blue; the design system has no blue
// register for a tag (chrome/chrome.css's `.planned-notices__tag`), so a
// closure's takes the closure's caution tint. A reviewer who wants the frame's
// blue should say so.
//
// EVERY ORGANIZATION AND NOTICE IS INVENTED (fixtures/upcomingNotices.mjs),
// as on the frame the maintainer chose from: a shot on every future pull
// request must never put a closure in a real club's mouth. The file is
// answered on the wire before the app loads (`before`), dated around the
// browser's own today, so the upcoming rows stay upcoming.
//
// Nothing here reaches an account, a hiker's own report, a dispersed campsite
// or a real location fix (.claude/skills/pr-screenshot/SKILL.md): the hike is
// two invented taps, nothing is signed in, and the panel draws no map.
import { seedDayHikes } from './fixtures/dayHike.mjs'
import {
  routeUpcomingNotices,
  upcomingDayHikes,
  upcomingStewards,
} from './fixtures/upcomingNotices.mjs'
import { seedStewards } from './fixtures/stewards.mjs'

export const caption =
  'Notices for your planned hikes with closures that have not started yet — shown now, tagged with the day each starts, and sorted with the closures only from the day before it (the maintainer’s frame B). Every organization and notice is an invented example.'

export const alt =
  'The notices panel headed "Notices for your planned hikes", with one section for the day hike "Example Creek loop (example)" in four days. First a Closure row, "Bridge out at Mill Creek (example)", from Example County Parks. Then "Rim Trail closed for footbridge repair (example)" from Example Trail Club, tagged "Starts" and tomorrow’s date, with its from and until dates. Then a Notice row, "Trail crew on the Example Creek Trail this week (example)". Last, "Emergency closure, Example Creek Trail (example)", tagged "Starts" and the date three days from now, with "from" and that date, and Example State Parks under it. Every organization and notice is an invented example.'

export const before = routeUpcomingNotices

export default async function drive(page) {
  // The steward list first (no reload), then the day hike (reloads), so the
  // app reads both at its next mount.
  await seedStewards(page, upcomingStewards())
  await seedDayHikes(page, upcomingDayHikes())

  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Legend' }).click()
  await page.getByRole('button', { name: /Notices for your planned hikes/ }).click()
  const panel = page.getByRole('dialog', { name: 'Notices for your planned hikes' })
  await panel.waitFor()
  // Both "Starts" tags, which only a file carrying `starts_on` still ahead of
  // the phone's own day can produce, and the ordinary notice the upcoming
  // closure sorts after.
  await panel
    .getByText(/^Starts [A-Z][a-z]{2} \d{1,2}$/)
    .first()
    .waitFor()
  await panel
    .getByText('Emergency closure, Example Creek Trail (example)', { exact: true })
    .waitFor()
  // Put the legend away, as planned-hike-notices.mjs does: the panel opens in
  // the sheet slot under it. Waiting on the panel again proves the close did
  // not take it too.
  await page.getByRole('button', { name: 'Close legend' }).click()
  await panel.waitFor()
}
