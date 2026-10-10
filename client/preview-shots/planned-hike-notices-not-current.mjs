// Notices for your planned hikes, with notices that may no longer apply
// (#1805, the maintainer's frame A, poll of 2026-10-10).
//
// WHAT A REVIEWER SHOULD CHECK IN THE FRAME, against frame A of the expiry
// wireframe ("A: show, marked old") and client/src/lib/noticeCurrency.ts:
//
//  1. One section, the invented "Canyon rim loop (example)" planned for
//     today, its four notices all on its route.
//  2. First, "Bridge out at Mill Creek (example)" from Example County Parks,
//     tagged Closure, with "— updated" and its date: it reads as current.
//  3. "Lower loop closed for 3 to 6 months (example)" from Example City
//     Parks, tag and title in the secondary grey, its "from" date still
//     shown, and under its source the grey box "Last reported <its edit
//     date>. It may no longer apply." - frame A's middle row. Its source line
//     no longer repeats the date.
//  4. "Section 12 closed (example)" from Example Trail Alliance, greyed, with
//     "Its source gives no date. It may no longer apply." - frame A's last
//     row, and no link, as its source gives none.
//  5. "Campground closed (example)" from Example National Forest, tagged
//     Notice (past its own end it no longer closes the trail), greyed, its
//     "from ... until ..." dates shown, and "Its source said it would end
//     <three days ago>. It may no longer apply." - the case the frame did
//     not draw, in the wording this pull request proposes.
//
// The current closure sorts first and the greyed ones after it, closures
// before the notice (lib/plannedNotices.ts's byWeight).
//
// EVERY ORGANIZATION AND NOTICE IS INVENTED (fixtures/notCurrentNotices.mjs),
// as on the frame the maintainer chose from: a shot on every future pull
// request must never show a real club's closure as possibly stale. The file
// is answered on the wire before the app loads (`before`), dated around the
// browser's own today, so the current row stays current.
//
// Nothing here reaches an account, a hiker's own report, a dispersed campsite
// or a real location fix (.claude/skills/pr-screenshot/SKILL.md): the hike is
// two invented taps, nothing is signed in, and the panel draws no map.
import { seedDayHikes } from './fixtures/dayHike.mjs'
import {
  notCurrentDayHikes,
  notCurrentStewards,
  routeNotCurrentNotices,
} from './fixtures/notCurrentNotices.mjs'
import { seedStewards } from './fixtures/stewards.mjs'

export const caption =
  'Notices for your planned hikes with notices that may no longer apply — kept in the list, greyed, with one line under each saying why: last reported more than 90 days ago, no date at all, or past its own end date (the maintainer’s frame A, #1805). Every organization and notice is an invented example.'

export const alt =
  'The notices panel headed "Notices for your planned hikes", with one section for the day hike "Canyon rim loop (example)" today. First a Closure row, "Bridge out at Mill Creek (example)", from Example County Parks with its updated date, in full colour. Then three greyed rows, each with a grey box under its source: "Lower loop closed for 3 to 6 months (example)" from Example City Parks, "Last reported" and its date, "It may no longer apply."; "Section 12 closed (example)" from Example Trail Alliance, "Its source gives no date. It may no longer apply."; and a Notice row, "Campground closed (example)" from Example National Forest, "Its source said it would end" and its date, "It may no longer apply." Every organization and notice is an invented example.'

export const before = routeNotCurrentNotices

export default async function drive(page) {
  // The steward list first (no reload), then the day hike (reloads), so the
  // app reads both at its next mount.
  await seedStewards(page, notCurrentStewards())
  await seedDayHikes(page, notCurrentDayHikes())

  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Legend' }).click()
  await page.getByRole('button', { name: /Notices for your planned hikes/ }).click()
  const panel = page.getByRole('dialog', { name: 'Notices for your planned hikes' })
  await panel.waitFor()
  // The greyed rows' lines, which only a file carrying current_until, read
  // against the phone's own day, can produce.
  await panel.getByText('Its source gives no date. It may no longer apply.').waitFor()
  await panel.getByText(/^Last reported .+\. It may no longer apply\.$/).waitFor()
  // Put the legend away, as planned-hike-notices.mjs does: the panel opens
  // in the sheet slot under it. Waiting on the panel again proves the close
  // did not take it too.
  await page.getByRole('button', { name: 'Close legend' }).click()
  await panel.waitFor()
}
