// The notices list for a planned hike whose conditions/notices.json is not on
// this phone: option A of the maintainer's poll of 2026-10-09, on #1805.
//
// WHY THIS SCREEN NEEDED A CAMERA. A planned hike's notices come only from
// conditions/notices.json (decision 77 downloads it once a hike is planned).
// A phone holding no copy of it - a first run with no signal, a file over
// lib/conditionsCache.ts's 32 MiB ceiling relaunched offline, or a download
// that failed - showed ATC's and NYNJTC's list under "Read all N trail
// notices", and nothing said that a club's closure on the planned hike could
// not be in it. planned-hike-notices.mjs photographs the panel with the file;
// this photographs the phone without it.
//
// WHAT A REVIEWER SHOULD CHECK IN THE FRAME, against the poll's wireframe
// (three phones: today, A and B; the maintainer chose A):
//
//  1. The list opens with the warning, in the caution tint: "This phone has
//     no notices for your planned hikes yet. Connect once to get them. Until
//     then, a closure on your hike will not show here."
//  2. Under it the heading "Trail notices this phone has", where today's
//     list is headed "N trail notices".
//  3. Then ATC's and NYNJTC's rows, exactly as today's list draws them.
//
// The legend row that opens it reads "Notices for your planned hikes: not on
// this phone yet". It is not in the frame (the legend is closed so it does
// not cover the list, as planned-hike-notices.mjs does), but the drive taps
// the row by those words, so there is a shot only if the row said them.
//
// HOW THE STATE IS REACHED. conditions/notices.json fails on the wire
// (`before`), as it does in a dead spot, and the phone kept no copy, so the
// planned hike's read settles as missing. The hikes are the planned-hike
// fixtures' invented ones (fixtures/plannedNotices.mjs). On a bucket that
// answers 404 for the file the panel stays today's, so the failure is made
// here rather than left to whichever bucket CI reads.
//
// THE NOTICES ARE INVENTED and each title says "(example)". ATC's and
// NYNJTC's files are answered on the wire too, so the frame is the same in
// CI and in an agent sandbox, and no real notice is photographed. The
// organizations are real registry entries, named from the steward list as
// the app names them (features/ORG_NOTICES.md §6). Every row is dated ten
// days back, outside lib/notices.ts's 72-hour "new" window, so the legend
// row carries no " · N new".
//
// Nothing here reaches an account, a hiker's own report, a dispersed campsite
// or a real location fix (.claude/skills/pr-screenshot/SKILL.md): no account
// is seeded, the hikes and notices are invented, the list draws no map, and a
// CI browser has no location fix.
import { seedDayHikes } from './fixtures/dayHike.mjs'
import { plannedDayHikes, plannedNoticeStewards } from './fixtures/plannedNotices.mjs'
import { seedStewards } from './fixtures/stewards.mjs'

export const caption =
  'A planned hike whose notices are not on this phone — the list opens with the warning “This phone has no notices for your planned hikes yet. Connect once to get them. Until then, a closure on your hike will not show here.”, then “Trail notices this phone has” over ATC’s and NYNJTC’s list as it is today (option A of the maintainer’s poll of 2026-10-09). Every notice is an invented example.'

export const alt =
  'The trail-notices sheet. At the top, in a caution-tinted box with an orange rule down its left edge: "This phone has no notices for your planned hikes yet. Connect once to get them. Until then, a closure on your hike will not show here." Under it the heading "Trail notices this phone has" with a Close button, the note that OurHike carries each notice’s facts and a link, and the rows: example notices credited to the Appalachian Trail Conservancy and the New York-New Jersey Trail Conference. Every notice is an invented example.'

/** Ten days ago, as ATC's and NYNJTC's files write a time. */
function tenDaysAgo() {
  return new Date(Date.now() - 10 * 86_400_000).toISOString().slice(0, 19) + 'Z'
}

/**
 * conditions/atc_updates.json, in the shape export_atc_updates.py writes.
 *
 * At mile 5, on the 40-mile centerline seedStewards puts on the phone
 * (fixtures/stewards.mjs), so the map draws its dot and NoticeList keeps the
 * row whatever stretch is on screen. At a mile off that line the list scoped
 * it behind "Show 1 more, elsewhere on the trail" (the first frame of this
 * recipe, 2026-10-09), which is today's list doing its job and hid the row.
 */
function atcUpdatesDocument() {
  return {
    generated_at: tenDaysAgo(),
    reviewed_at: tenDaysAgo(),
    atc_updates: [
      {
        atc_id: 'example-footbridge-out',
        title: 'Footbridge out on the A.T. (example)',
        category: 'Detour',
        states: ['GA'],
        start_mile_marker: 5,
        end_mile_marker: 5,
        obstructs_trail: true,
        updated_at: tenDaysAgo(),
        source_url: 'https://appalachiantrail.org/trail-updates/',
      },
    ],
  }
}

/** conditions/nynjtc_alerts.json, in the shape export_nynjtc_alerts.py
 *  writes: unplaced and unreviewed, as every row of theirs is. */
function nynjtcAlertsDocument() {
  return {
    generated_at: tenDaysAgo(),
    nynjtc_alerts: [
      {
        notice_id: 'nynjtc_trail_alerts:example-long-path-trail-work',
        source_key: 'nynjtc_trail_alerts',
        title: 'Trail work on the Long Path this weekend (example)',
        category: null,
        locality: 'Harriman-Bear Mountain',
        place: { kind: 'unplaced' },
        obstructs_trail: false,
        updated_at: tenDaysAgo(),
        source_url: 'https://www.nynjtc.org/trail-alerts/',
        review_state: 'unreviewed',
      },
    ],
  }
}

/** A pattern on the key and not the whole URL, because the bucket and the
 *  environment folder in front of it are the build's business. */
function answer(page, pattern, document) {
  return page.route(pattern, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(document),
    }),
  )
}

export async function before(page) {
  // The dead spot: the planned hike's download of conditions/notices.json
  // fails, as fetch does when the network drops (lib/publishedConditions.ts's
  // readPublished reads that as "could not get it", never as "not served").
  await page.route(/\/conditions\/notices\.json(\?|$)/, (route) => route.abort('failed'))
  await answer(page, /\/conditions\/atc_updates\.json(\?|$)/, atcUpdatesDocument())
  await answer(page, /\/conditions\/nynjtc_alerts\.json(\?|$)/, nynjtcAlertsDocument())
}

export default async function drive(page) {
  // The steward list first (no reload), then the day hikes (reloads): each
  // seed lands before the reload that makes the app read it.
  await seedStewards(page, plannedNoticeStewards())
  await seedDayHikes(page, plannedDayHikes())

  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Legend' }).click()
  // The legend row, by the maintainer's words: the drive fails here, and the
  // comment says the camera could not take this shot, unless the row says
  // them.
  await page
    .getByRole('button', {
      name: 'Notices for your planned hikes: not on this phone yet',
    })
    .click()
  const list = page.getByRole('dialog', { name: 'Trail notices this phone has' })
  await list.waitFor()
  await list.getByText('Connect once to get them.', { exact: false }).waitFor()
  // Then put the legend away, which would cover the list (the same clipping
  // planned-hike-notices.mjs records). The list stays open; waiting on it
  // again proves the close did not take it too.
  await page.getByRole('button', { name: 'Close legend' }).click()
  await list.waitFor()
}
