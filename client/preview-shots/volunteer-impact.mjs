// "What you've put back" - the impact panel (#969, wireframe 2e frame 2).
//
// REACHABLE WITHOUT A BACKEND, which is why this screen can be photographed at
// all and most cannot. A preview is built with no backend on purpose, so the
// hours the server holds are never there — but a logged day is saved to the
// outbox and echoed into the record immediately (App.tsx's handleLogHours, the
// same immediately-real contract the field notes keep), so the drive below logs
// a day and the panel summarises it. Every number in the shot is one this drive
// typed in, which is also what makes it safe: nothing here is anybody's data.
//
// The panel does not render at all for a hiker with nothing logged, which is
// rule 2 of features/VOLUNTEERING.md §5 and not an accident — so the log step
// is the shot rather than a preamble to it.
//
// Driven and looked at in an agent sandbox before it was pushed
// (`node scripts/photograph-preview.mjs --dist preview-shots/volunteer-impact.mjs`),
// which is possible here only because nothing in this drive needs data the
// preview does not have — the whole reason this screen is photographable and
// the waypoint card of #953 is not.
export const caption = "What you've put back — the impact panel (#969)"
export const alt =
  'The Volunteer page scrolled to a panel headed What you have put back, subtitled Kept for you seen by no one: two tiles reading 1 Day out and 3 Hours you wrote down, the second carrying 3 not yet confirmed by a club inside it, then a line saying field notes and water reports are not counted because the phone forgets what it filed, and a ticked Show what I have put back checkbox'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /volunteer/i }).click()

  // A day's work, typed the way a volunteer types it. Three hours on one day,
  // so the tiles read "1 Day out" and "3 Hours you wrote down" — small numbers
  // chosen so the shot cannot be mistaken for a record somebody accumulated.
  await page.getByTestId('hours-count').fill('3')
  await page.getByTestId('hours-log').click()

  // Saving with no account asks for one afterwards, and covers the screen with
  // it (contributionFlow.ts's ordering: saved first, sign-in asked after). Not
  // a conditional step - a preview is built with no backend and nobody is ever
  // signed in here, so this prompt always appears. Declining it is what a hiker
  // photographing their own logbook would do, and the record is already kept
  // either way, which is the whole point of that ordering.

  await page.getByRole('button', { name: 'Not now' }).click()

  // The panel itself, by the heading that IS the change. Scrolling to it rather
  // than to a pixel offset: the hours form and the record list above it grow
  // with what has been logged.
  await page
    .getByRole('heading', { name: "What you've put back" })
    .scrollIntoViewIfNeeded()
}
