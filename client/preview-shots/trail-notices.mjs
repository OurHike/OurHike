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
//
// THE DATA IS REAL AND THE CAMERA RUNS IN CI, which is the whole reason this
// file exists rather than a hand-run screenshot: the sandbox has neither the
// published artifacts nor anywhere to put the image.
//
// Nothing here reaches an account, a hiker's own report, a dispersed campsite
// or a real location fix - the four things a shot must never contain
// (.claude/skills/pr-screenshot/SKILL.md). Every row is an organization's own
// public notice.
export const caption =
  'Trail notices — NYNJTC’s alerts on a hiker’s screen for the first time (#1083)'
export const alt =
  'The trail-notices sheet over the map: one flat list newest first, mixing rows credited to the Appalachian Trail Conservancy with rows credited to the New York-New Jersey Trail Conference. The NYNJTC rows carry a locality such as Harriman-Bear Mountain and no category line, and each says it is not drawn on the map. The heading counts every notice rather than naming one organization.'

export default async function drive(page) {
  // The map first: the app opens on Today since #1054, and the legend's
  // button floats over the map screen.
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
}
