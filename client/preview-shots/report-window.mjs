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
//   - the whole window fits with no scroll at all - 607 px of window in
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
// THIS ONE NEEDS NO TRAIL DATA, which is worth saying because the other
// recipes in this directory spend most of their comments on it. The window
// opens from Today's own button and renders entirely from the app's own
// vocabulary, so the frame is the same whether or not the bucket answered.
// There is no second honest frame here and no branch in the drive.
//
// Nobody's data is in it: no account, no reports seeded, no location fix, and
// the report window itself is a list of categories rather than of anything
// anyone has filed.

export const caption =
  'Report a problem — the 911 line pinned under the header, and a window that no longer scrolls (#1480). It is still a window over Today rather than a page instead of it (#1133).'
export const alt =
  'A centred dialog over a dimmed Today screen, its header on dark pine reading “Report a problem / What did you find?” and, immediately under it, a full-width pale band in red type reading “Call 911 if you are in danger now. This reaches volunteers, sometimes days later.” Below the band, six left-aligned category tiles two per row, each with a line icon beside its label and a description underneath, then two full-width rows — “The trail is closed” and “Something unsafe happened” — both showing their full two-line descriptions inside their own borders. The whole window is on screen with nothing cut off and no scrollbar. The tab bar is still visible at the foot of the screen behind the scrim.'

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
  // Settled on the notice being present rather than on a delay: it is the
  // last thing this window renders after the header, so having it is having
  // the window. Where it sits is the frame's business and not this drive's.
  await page.getByRole('note').waitFor()
}
