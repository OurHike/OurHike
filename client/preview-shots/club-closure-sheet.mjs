// A club closure's sheet, opened by a tap on its crossed-out line (the
// maintainer's S6, poll of 2026-10-11: "same sheet as its list row"), over the
// map club-closures-on-the-map.mjs photographs.
//
// WHAT A REVIEWER SHOULD CHECK IN THE FRAME, against
// chrome/ClubClosureSheet.tsx and planned-hike-notices-not-current.mjs's
// "Section 12 closed" row:
//
//  1. The heading "Closure notice" and its close button.
//  2. One row, the planned-hike list's own (chrome/PlannedNoticeList.tsx's
//     NoticeRow): the Closure tag and the title "Example Canyon Trail closed
//     (example)" in the secondary grey, "Example County Parks" under it, and
//     the grey box "Its source gives no date. It may no longer apply." -
//     the line the list prints for it. No link: its source gives none.
//  3. The note in the closing organization's voice: "This is Example County
//     Parks’ notice, not OurHike’s. OurHike has not checked the trail
//     itself, and does not work out detours - follow their notice, or the
//     signage on the ground."
//  4. "Gathered by OurHike on" and the file's date.
//
// The line it closes is under the sheet on a phone, where the other three
// closures stay crossed out above it; club-closures-on-the-map.mjs shows that
// line at the same full strength as the rest (the maintainer's "B: same
// mark"), so only the sheet says it may no longer apply.
//
// EVERY CLOSURE AND ORGANIZATION IS INVENTED (fixtures/clubClosures.mjs), as
// on the map recipe; the organizations' names come from a seeded stewards.json
// (fixtures/stewards.mjs's seedStewards). Nothing here reaches an account, a
// hiker's own report, a dispersed campsite or a real location fix
// (.claude/skills/pr-screenshot/SKILL.md).
import {
  clubClosureStewards,
  openClosureSheet,
  routeTrailClosures,
  trailClosureRows,
} from './fixtures/clubClosures.mjs'
import { seedStewards } from './fixtures/stewards.mjs'

export const caption =
  'A club closure’s sheet, opened by a tap on its crossed-out line (the maintainer’s S6, 2026-10-11): the row the planned-hike list shows for the notice, greyed with “Its source gives no date. It may no longer apply.”, and the note that it is the organization’s notice and that OurHike works out no detour. The closure and its organization are invented examples.'

export const alt =
  'The map screen with a sheet over its lower part headed "Closure notice". Under the heading one row: a Closure tag and the title "Example Canyon Trail closed (example)" in grey, "Example County Parks" beneath, and a grey box reading "Its source gives no date. It may no longer apply." Below it a note: "This is Example County Parks’ notice, not OurHike’s. OurHike has not checked the trail itself, and does not work out detours — follow their notice, or the signage on the ground." Then "Gathered by OurHike on" and a date. Above the sheet the map shows the invented closures crossed out.'

/** As club-closures-on-the-map.mjs: vector basemap tiles at z13. */
export const wait = 22000

export const before = routeTrailClosures

export default async function drive(page) {
  await seedStewards(page, clubClosureStewards())
  // A vertex of the greyed line, which the sheet then opens on.
  const { greyed } = trailClosureRows()
  const sheet = await openClosureSheet(
    page,
    greyed.place.geometry.coordinates[1],
    greyed.title,
  )
  // The organization's name, which only the seeded stewards.json gives, and
  // the greyed line, which only the phone's own day gives.
  await sheet
    .getByText(/^Example County Parks/)
    .first()
    .waitFor()
  await sheet.getByText('Its source gives no date. It may no longer apply.').waitFor()
}
