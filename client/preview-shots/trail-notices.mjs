// The trail-notices list, holding two organizations for the first time.
//
// A recipe exports a caption and, when the screen is not the one the app
// opens on, a default-export drive that takes a Playwright page the rest of
// the way. The runner (scripts/photograph-preview.mjs) has already loaded the
// built app, skipped first run, and let it settle; the drive does only the
// taps a hiker would.
//
// WHY THIS SCREEN NEEDED A CAMERA POINTED AT IT (#1083). Until this pull
// request the list was `AtcNoticeList`: it sorted by `start_mile_marker`, a
// field only the A.T. has, and said "Appalachian Trail Conservancy" in five
// places as a literal. NYNJTC's eighteen alerts had been published, fetched,
// parsed and rendered by nothing. No recipe reached this sheet at all - the
// nearest, legend.mjs, photographs the panel that OPENS it - so every claim
// about how a notice reads has lived in Legend.test.tsx and NoticeList.test.tsx
// and never in a picture.
//
// WHAT A REVIEWER SHOULD CHECK IN THE FRAME, in the order it matters:
//
//  1. Two organizations' names, each on its own rows, neither on the other's.
//     They are read from the published registry (`stewards.json`) rather than
//     written in the component - features/ORG_NOTICES.md §6.
//  2. NYNJTC's rows carrying NO category line, because they publish none and
//     borrowing a word from ATC's list would invent a classification.
//  3. One flat list, newest first, whoever published it.
//  4. "Not drawn on the map — read it here" under the unplaced rows, which is
//     the honest state rather than a gap.
//  5. "Show N more, elsewhere on the trail" at the foot of the list, drawn as
//     a text control rather than the platform's default grey button. It had
//     no CSS rule at all until now - `.atc-notices__show-all` was written in
//     the component and never in the stylesheet - so this sheet shipped with
//     one element in it that looked like it belonged to another app. That is
//     the thing this recipe was re-pointed to photograph.
//
// THE CAMERA IS PARKED SO THAT CONTROL EXISTS. The button only renders when
// the viewport scopes something out (`scopedNotices`'s `hidden`), so a shot
// taken wherever the app happened to open would contain it on some days and
// not others - and a picture that intermittently shows the thing under review
// is not evidence. Parking at Harriman puts most of the trail's notices off
// the stretch on screen and leaves NYNJTC's unplaced rows in the list, which
// is both halves of what this sheet has to get right.
//
// THE DATA IS REAL AND THE CAMERA RUNS IN CI, which is the whole reason this
// file exists rather than a hand-run screenshot: the sandbox has neither the
// published artifacts nor anywhere to put the image.
//
// Nothing here reaches an account, a hiker's own report, a dispersed campsite
// or a real location fix - the four things a shot must never contain
// (.claude/skills/pr-screenshot/SKILL.md). Every row is an organization's own
// public notice.
//
// The parked camera is worth checking against that list rather than waving
// at, because pins draw from z9 and this sits at z12. The campsite rule is
// kept BY CONSTRUCTION: the 2,333 user-created sites live in ATC's
// Campsite_Sustainability_Index, which is not a registered source and ships
// in no artifact (SOURCE_SURVEY.md §3b). What can draw here is ATC's
// club/agency campsites and DEC's designated primitive tent sites - places
// the agencies publish as places to camp. There is no location fix in a CI
// browser and no account, so the other three are kept the same way.
export const caption =
  'Trail notices — two organizations in one list. The sheet clips before the “Show N more” control this change restyled; see the pull request'

export const alt =
  'The trail-notices sheet over the map at Harriman, scrolled into the older half of the list: NYNJTC alerts credited to the New York-New Jersey Trail Conference, each carrying a locality such as Minnewaska State Park Preserve, no category line, a note that OurHike has not checked it, and a note that it is not drawn on the map. The sheet clips before the foot of the list, so the “Show N more” control this change restyled is not in the frame.'

export default async function drive(page) {
  // Park the camera before anything else, so the list is scoped to a stretch
  // rather than to wherever the app opened. lib/cameraMemory.ts's contract:
  // { center: [lon, lat], zoom }, every field validated on read, null on
  // anything that does not convince - basemap-ground-network.mjs does the
  // same and says why a restore beats clicking zoom eight times.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.0207, 41.2725], zoom: 12 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // The map first: the app opens on Today since #1054, and the legend's
  // button floats over the map screen. First run stays skipped across the
  // reload - the runner installs that on the CONTEXT, so it re-runs for every
  // document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()

  // The header's icon button. Its accessible name is the visually-hidden span
  // inside it (chrome/Header.tsx), which is what a screen reader - and
  // therefore this locator - sees.
  await page.getByRole('button', { name: 'Legend' }).click()

  // The row that opens the list. Matched on the stable half of the sentence
  // rather than on the count: the number is however many notices both
  // organizations happen to be holding on the day CI runs, and a locator
  // pinned to it would break on a quiet week.
  await page.getByRole('button', { name: /Read all .* trail notices/ }).click()

  // Wait on the list itself rather than on a delay. The dialog's accessible
  // name is the component's own `aria-label`, so this both settles the shot
  // and asserts the sheet actually opened - a recipe that photographed the
  // legend because the tap missed would produce a picture that looks fine and
  // shows nothing this pull request changed.
  await page.getByRole('dialog', { name: 'Every trail notice OurHike holds' }).waitFor()

  // THEN TRY TO FRAME THE CONTROL - AND KNOW THAT IT DOES NOT WORK YET.
  //
  // "Show N more, elsewhere on the trail" sits at the FOOT of the list, and
  // the list is long: the scoping hid 4 of 53 notices on the day this was
  // written, which is enough for the control to exist and nowhere near enough
  // to bring it on screen. NYNJTC's alerts are all `unplaced` and never scoped
  // out, so this list has a floor of roughly eighteen rows however tightly the
  // camera is parked. Scrolling is the only way to reach the foot of it.
  //
  // THREE FRAMES, NONE OF THEM CONTAINING THE CONTROL, and the honest state of
  // this is that nobody knows why. What is known, measured on pr-1159:
  //
  //  - the scroll RUNS and lands deep in the list: the frames show NYNJTC's
  //    June 2025 alerts, which sort near the bottom;
  //  - `scrollIntoViewIfNeeded` does not throw, so the control is present and
  //    Playwright believes it scrolled to it;
  //  - the sheet clips at the same place every time, with the legend's own
  //    rows visible beneath it;
  //  - re-scrolling for two seconds and dropping `wait` from 3500 to 700
  //    changed the frame by 22 bytes, which killed the "a re-render resets the
  //    scroll during the settle" theory the second attempt was built on;
  //  - `.atc-notices` is a single `overflow-y: auto` box with `max-height:
  //    85%` that CONTAINS the button, so "the footer is clipped out of a
  //    non-scrollable sheet" does not explain it either.
  //
  // The scroll is kept because it is closer than not scrolling and costs
  // nothing. The pull request says plainly that the shot does not show the
  // control and points a reviewer at the preview to scroll it themselves,
  // which is what .claude/skills/pr-screenshot/SKILL.md asks for when no
  // recipe can photograph the thing. A fourth guess would be spending CI on a
  // button's CSS.
  //
  // NOT REPRODUCIBLE HERE, which is why it is three guesses and not three
  // measurements: this drive cannot run in an agent sandbox at all. The step
  // above it needs `Read all N trail notices`, which needs conditions
  // artifacts, and `--url` at the live preview fails the same way because
  // Chromium here cannot use the egress proxy (the skill's own measurement).
  // Whoever picks this up with a browser will learn more in five minutes than
  // three CI rounds taught.
  //
  // IT THROWS WHEN THE CONTROL IS ABSENT, and that stays deliberate. The
  // button renders only when the viewport scopes something out; if that stops
  // being true the comment should read "the camera could not take
  // trail-notices" rather than photograph a list with no control under a
  // caption asserting one.
  const showAll = page.getByRole('button', {
    name: /Show \d+ more, elsewhere on the trail/,
  })
  await showAll.scrollIntoViewIfNeeded()
}
