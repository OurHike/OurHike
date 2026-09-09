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
//   - the 911 line, above the fold of that decision rather than after it.
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
  'Report a problem — a window over Today, not a page instead of it (#1133)'
export const alt =
  'A centred dialog over a dimmed Today screen, its header on dark pine reading “Report a problem / What did you find?”: six left-aligned category tiles two per row with a line icon, a label and a description each, then two full-width rows below them — “The trail is closed” and “Something unsafe happened” — and a tinted notice reading “Call 911 if you are in danger now.” The tab bar is still visible at the foot of the screen behind the scrim.'

export default async function drive(page) {
  // Today is where the app opens (#1054), and where the report entry now
  // lives as one half of a pair.
  await page.getByRole('tab', { name: 'Today' }).click()

  // By its accessible name rather than a test id: this is the control a hiker
  // reads, and if its label ever stops saying what it does, a recipe that
  // could not find it is the right kind of failure.
  await page.getByRole('button', { name: 'Report a problem' }).click()

  // Waited on rather than assumed - the window is an overlay in the same
  // fragment as the downloads window, and "is it up" is a real question the
  // shot depends on.
  await page.getByRole('dialog', { name: 'What did you find?' }).waitFor()

  // The 911 notice is the last thing in the body and the reason the two heavy
  // rows are rows. Scrolled into frame by the thing that IS the change rather
  // than by a pixel offset: how far down it sits moves whenever the category
  // list does. `scrollIntoViewIfNeeded` also waits, so this is the settle as
  // well as the scroll.
  await page
    .getByRole('note')
    .scrollIntoViewIfNeeded()
    .catch(() => {})
}
