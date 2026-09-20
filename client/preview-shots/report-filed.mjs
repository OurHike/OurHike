// What a tap actually does, which is the whole of variant 1a (#1133).
//
// THE SECOND STATE, AND THE ONE THE CHANGE IS FOR. `report-window.mjs`
// photographs the question; this photographs the answer, and they are
// genuinely two screens rather than two crops of one. Everything that makes
// 1a what it is only exists here:
//
//   - "Filed — blow down at …", past tense, because the report is already in
//     the outbox. Nothing was submitted and nothing is pending.
//   - "It waits in your outbox and sends itself" — the offline promise, said
//     at the moment somebody is most likely to wonder whether it worked.
//   - the Undo button, WITH ITS COUNTDOWN RUNNING. That control is the whole
//     escape hatch: under 1a there is no form to abandon, so this is what
//     stands in for one, and a reviewer should see that it is a real button
//     with a real number on it rather than a promise in a pull request body.
//   - the optional note below a rule, and `Done` / `Note something else`.
//     There is no `Cancel`, which is the point: the report already stands.
//
// THE COUNTDOWN MAKES THIS FRAME NON-DETERMINISTIC, deliberately and
// harmlessly. It will read 8s, 7s or 6s depending on how the runner's clock
// falls between the tap and the shutter. That is a photograph of a live
// control, not an assertion about one - ReportWindow.test.tsx is where the
// exact seconds are pinned.
//
// IT FILES A REPORT, AND THAT IS FINE HERE, which is worth being explicit
// about because .claude/skills/pr-screenshot/SKILL.md forbids photographing
// "anybody's reports". The rule is about other people's submissions. This one
// is written by the camera, one second earlier, into a preview build that has
// no backend at all - the preview comment says so itself: "Sending a report
// does not [work]: a preview is built with no backend on purpose". It reaches
// nobody's moderation queue and no hiker's phone.
//
// No trail data needed, for `report-window.mjs`'s reason. No account, no
// location fix, nobody else's anything.
//
// TOUCHED BY #1480 THOUGH THE DRIVE DID NOT CHANGE, which is the whole reason
// this comment exists. That change is about the window's OTHER state - the
// tiles, and the 911 line pinned above them - and none of its copy reaches
// this frame. But four of its rules are on the window itself rather than on
// the tiles, so they land here too: the scrim's gutter went 16 to 12 and
// became inset-aware, `.report-window` took `box-sizing: border-box` against
// its 334 px cap, and `.report-window__body` went to 12 px of padding and an
// 8 px gap. The receipt is 463 px tall and every one of those moves it.
//
// `pr-preview.yml` photographs the recipes a pull request adds or CHANGES, so
// a receipt that shifted and a recipe nobody touched would have meant the
// preview comment showing the pre-change frame for the one state that still
// had a visible difference in it. CLAUDE.md's rule is that a UI change is not
// finished until a recipe reaches the screen it changed; this is that recipe,
// and this paragraph is what re-points the camera at it.

// AND SINCE #1563 THE TAP NEEDS A PLACE. The camera has no fix, so the tap
// on Blow down is refused and opens the location sheet - the state
// report-window-refused.mjs photographs. This drive answers it with the
// last-resort place, words, and closes the sheet; the tap that was refused
// files by itself the moment it has a place (the maintainer's "only ask
// once", 2026-09-17), so there is no second tap to make - the camera's
// first version made one and timed out on tiles that were already gone.
// The receipt therefore reads "where you described" rather than "here".
//
// AND THE RECEIPT ASKS TWO THINGS IT DID NOT (the maintainer's additions of
// 2026-09-17): which name the report is signed with - the trail name, or a
// real name typed here and kept for next time - and whether the hiker may be
// contacted for more. Both sit under the note, after the tap, because under
// 1a nothing may stand between a hiker and the tile; both are written to the
// queued report as they change (reporting/ReporterDetails.tsx). The camera
// has no trail name set, so the summary line says "not set" rather than
// inventing one.
//
// AND PHOTOS SIT ABOVE THE NOTE (the maintainer's "add the ability to add
// pictures above the note", 2026-09-18): the same `+` tile the long form
// draws, reporting/PhotoTiles.tsx over one state machine. The camera picks
// nothing - a photo here would be a file the runner invented - so the frame
// shows the tile with nothing claimed under it, which is the state a hiker
// reaches first.

export const caption =
  'One tap files it — and the Undo that makes that safe to do (#1133). With no fix the tap needs a place first, here the hiker’s own words; the receipt then offers a photo above the note, and asks which name signs it and whether a club may follow up (#1563).'
export const alt =
  'The report window after tapping Blow down: a green-tinted receipt reading “Filed — blow down where you described” over “It waits in your outbox and sends itself”, with an “Undo · 7s” button counting down beside it; below a rule, “Add a photo — optional” over a single “+ Add a photo” tile, then an optional note field labelled “Add detail — optional”; then a boxed “Signed as” block reading “Signed as not set (trail name) · day” with two radio rows, “Trail name — not set” selected and “Real name — not set, type it below”, a checkbox “You can contact me for more information”, and a hint that only the club moderators who read the report see the name and the answer; then a filled “Done” button and an outlined “Note something else”. No Cancel.'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Today' }).click()
  await page.getByRole('button', { name: 'Report a problem' }).click()
  await page.getByRole('dialog', { name: 'What did you find?' }).waitFor()

  // A blow-down, because it is the plainest of the six and the one the
  // receipt's own copy uses as its example. No fix, so the tap is refused
  // and opens the location sheet; the words are the place (#1563), and Done
  // is what files it. Fixture-shaped prose, nobody's actual report.
  await page.getByTestId('report-tile-blowdown').click()
  await page.getByTestId('location-words').fill('The ford below the gap')
  await page.getByTestId('location-sheet-done').click()

  // The receipt, waited on rather than slept for: filing is a write to
  // IndexedDB and the button does not appear until it has returned.
  await page.getByTestId('report-undo').waitFor()
}
