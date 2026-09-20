// Reporting a problem, as a window over the screen you were already on (#1133).
//
// THE SCREEN THIS CHANGE IS ABOUT. What it replaces is `ReportTypePicker`, a
// full-screen route that swapped the whole shell, tab bar included - which is
// why it needed a `Cancel` at all. The single most important thing in this
// frame is therefore not the tiles: it is that Today is still there, dimmed,
// behind the scrim, with the tab bar still on it. A reviewer can check the
// claim "you never lose your place" by looking at the edges of the picture.
//
// What else the frame carries, and what to look at:
//
//   - six tiles, two per row, LEFT-ALIGNED with a description under every
//     label. Six of the eight had no description before, which read as though
//     those six were self-evident. "Trash" is the one that gives it away.
//   - "Shelter or campsite", where the shipped picker said "Shelter repair" -
//     the constant is unchanged, only the words.
//   - the two HEAVY ROWS below the grid, full width with a chevron, because
//     neither files on a tap: a closure needs two miles, and something unsafe
//     is private to moderators.
//
// WHAT #1480 CHANGED IN THIS FRAME, which is why the recipe was touched:
//
//   - the 911 line is the band DIRECTLY UNDER THE HEADER now, not the last
//     thing in the body. It used to be 39 px below the fold here and 190 px
//     below it on a 360x640 phone, which is a notice about calling for help
//     that a hiker met only by scrolling past six categories first.
//   - the whole window fits with no scroll at all - 605 px of window in
//     820 px of scrim, where it needed 656 of 812 and scrolled by 53.
//   - each tile's icon sits BESIDE its label rather than above it, which is
//     where the height came from: tiles 75 px against 98, and the grid 268 px
//     against 328. Nothing a hiker reads got smaller - no font size, no
//     padding, no touch target.
//   - the closure row is the height of its own text again. It declares
//     `min-height: 44px`, so it was the one thing the flex squeeze could take
//     room from, and it rendered its description 15 px outside its own
//     border - visible in the photograph that opened #1480.
//
// WHAT #1563 CHANGED IN THIS FRAME, which is why the recipe was touched: the
// camera has no GPS fix, so this is the "No location yet" state, and the
// header says so with a "Change" beside it where it used to say "here". The
// tiles are unchanged and will not file until the report has a place - the
// tap opens the location sheet, which report-window-refused.mjs photographs,
// and a fix's version of the same sheet is report-window-place.mjs. The
// sheet is a window of its own (the maintainer's steer of 2026-09-17), so
// this frame is the tile frame #1480 measured and nothing in it has moved:
// its first #1563 version drew the picker inside the body, above the tiles,
// and put the body back under a scroll on the smallest phone.
//
// THIS ONE NEEDS NO TRAIL DATA, which is worth saying because the other
// recipes in this directory spend most of their comments on it. The window
// opens from Today's own button and renders entirely from the app's own
// vocabulary, so the frame is the same whether or not the bucket answered -
// with one honest difference: with the release's waypoints on the phone the
// find-by-name box has something to find, and without them it says so.
//
// Nobody's data is in it: no account, no reports seeded, no location fix, and
// the report window itself is a list of categories rather than of anything
// anyone has filed.

export const caption =
  'Report a problem with no GPS fix — the header says “No location yet” with a Change beside it (#1563), and the tiles will not file until the report has a place. The 911 line stays pinned under the header (#1480).'
export const alt =
  'A centred dialog over a dimmed Today screen, its header on dark pine reading “Report a problem / What did you find?” with the place line “No location yet” and a “Change” control, and immediately under it a full-width pale band in red type reading “Call 911 if you are in danger now. This reaches volunteers, sometimes days later.” Below the band, six left-aligned category tiles two per row, each with a small line icon beside its label and a description under it, then the “The trail is closed” and “Something unsafe happened” rows. The tab bar is still visible at the foot of the screen behind the scrim.'

export default async function drive(page) {
  // Today is where the app opens (#1054), and where the report entry now
  // lives as one half of a pair.
  await page.getByRole('tab', { name: 'Today' }).click()

  // By its accessible name rather than a test id: this is the control a hiker
  // reads, and if its label ever stops saying what it does, a recipe that
  // could not find it is the right kind of failure.
  // A PREFIX since #1438: the door is a row now, and its accessible name
  // carries the line under the title ("A dry spring, a blowdown, a trail that
  // is shut. Works with no signal.") the way More's rows do.
  await page.getByRole('button', { name: /^Report a problem/ }).click()

  // Waited on rather than assumed - the window is an overlay in the same
  // fragment as the downloads window, and "is it up" is a real question the
  // shot depends on.
  await page.getByRole('dialog', { name: 'What did you find?' }).waitFor()

  // NOTHING IS SCROLLED INTO FRAME, and that is the assertion this drive
  // makes by omission (#1480). It used to end with
  // `getByRole('note').scrollIntoViewIfNeeded()`, because the 911 line was
  // the last thing in a body that overflowed - a recipe scrolling to reach
  // the notice was the defect, photographed every time and read as framing.
  //
  // SETTLED ON THE LAST THING DRAWN, which since this change is no longer the
  // notice: pinning it put it directly under the header, so waiting on it now
  // proves only that the TOP of the window exists. The unsafe row is the foot
  // of the body and the thing a short window would cut off, so it is what
  // "the whole window is up" actually means here - and it is the element this
  // frame is for a reviewer to look at.
  await page.getByRole('button', { name: /^Something unsafe happened/ }).waitFor()
  // And the header's place line in its fixless state, which is what #1563
  // changed in this frame.
  await page.getByTestId('report-anchor').filter({ hasText: 'No location yet' }).waitFor()
}
