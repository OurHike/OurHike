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
  'Trail notices, scrolled to the foot of the list — the “Show N more” control, which had no styles at all until now'

/** Short, and the drive says why: the default 3500 leaves the shutter open
 *  through a re-render that scrolls this list back to the top. Every step of
 *  the drive auto-waits, so the settle this replaces was already redundant. */
export const wait = 700
export const alt =
  'The foot of the trail-notices sheet, scrolled down: the last of the notices, each credited to the organization that posted it — the Appalachian Trail Conservancy or the New York-New Jersey Trail Conference — with the NYNJTC rows carrying a locality such as Harriman-Bear Mountain, no category line, and a note that they are not drawn on the map. Beneath the last row, a plain text control in the link colour offers to show the remaining notices elsewhere on the trail, where it previously drew as the browser’s default grey push button.'

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

  // THEN SCROLL TO THE CONTROL, because waiting for the dialog is not enough
  // and the first run of this recipe proved both halves of that.
  //
  // The frame it produced (pr-1159, 2026-08-28) was wrong twice over: the
  // sheet was caught mid-transition with the legend's own rows showing
  // through beneath it, and the thing this recipe exists to photograph was
  // nowhere in it. "Show N more, elsewhere on the trail" sits at the FOOT of
  // the list, and the list that day was 49 notices long - the scoping hid 4
  // of 53, which is enough for the control to exist and nowhere near enough
  // to bring it on screen. A shot of the top of a long list is a shot of the
  // list, not of the change.
  //
  // `scrollIntoViewIfNeeded` fixes both: it puts the control in frame, and
  // getting there requires the dialog to have finished laying out, which is
  // the settle the `waitFor` above only looked like.
  //
  // IT THROWS WHEN THE CONTROL IS ABSENT, and that is the right failure. The
  // button renders only when the viewport scopes something out; if a future
  // change to the scoping means nothing is ever hidden here, this recipe
  // should say "the camera could not take trail-notices" in the comment
  // rather than quietly photograph a list with no control at the bottom and
  // let a caption claim otherwise. That is exactly the mistake this paragraph
  // is a correction of.
  const showAll = page.getByRole('button', {
    name: /Show \d+ more, elsewhere on the trail/,
  })
  await showAll.scrollIntoViewIfNeeded()

  // AND HOLD IT THERE, because one scroll was not enough either - the second
  // frame proved that too. `scripts/screenshot.mjs` runs `drive(page)`, then
  // `waitForTimeout(wait)`, THEN shoots, so there is a settle between the
  // scroll and the shutter; the shell's `now` ticks during it, `scopedNotices`
  // recomputes, the list re-renders and the scroller goes back to the top. The
  // second frame landed deep in the list - NYNJTC's June 2025 alerts, which
  // sort near the bottom - and still had no control in it, which is what a
  // scroll that happened and was then undone looks like.
  //
  // Re-scrolling for two seconds outlasts a tick, and `wait` below is dropped
  // to just enough for the paint so the shutter is not sitting open through
  // another one. The drive's own steps do the settling that the long default
  // wait used to: every locator here auto-waits, and the dialog `waitFor`
  // above is a real assertion rather than a timer.
  for (let i = 0; i < 8; i += 1) {
    await page.waitForTimeout(250)
    await showAll.scrollIntoViewIfNeeded()
  }
}
