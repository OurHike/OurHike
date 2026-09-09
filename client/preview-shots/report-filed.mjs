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

export const caption =
  'One tap files it — and the Undo that makes that safe to do (#1133)'
export const alt =
  'The report window after tapping Blow down: a green-tinted receipt reading “Filed — blow down at here” over “It waits in your outbox and sends itself”, with an “Undo · 7s” button counting down beside it; below a rule, an optional note field labelled “Add detail — optional”, a filled “Done” button and an outlined “Note something else”. No Cancel.'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Today' }).click()
  await page.getByRole('button', { name: 'Report a problem' }).click()
  await page.getByRole('dialog', { name: 'What did you find?' }).waitFor()

  // A blow-down, because it is the plainest of the six and the one the
  // receipt's own copy uses as its example.
  await page.getByTestId('report-tile-blowdown').click()

  // The receipt, waited on rather than slept for: filing is a write to
  // IndexedDB and the button does not appear until it has returned.
  await page.getByTestId('report-undo').waitFor()
}
