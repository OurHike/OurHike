// Step 3's rest-day control with a nearo chosen, and the sentence under it
// (#1053).
//
// WHAT THIS SHOT IS EVIDENCE FOR - one line of copy. The note under
// "Zero · Nearo" used to say a nearo "walks up to 6 mi to the next place to
// sleep", while lib/restRhythm.ts has always aimed at the FURTHEST place to
// sleep inside that window. The maintainer chose the furthest (poll,
// 2026-09-25), so the sentence moved to match the code: "walks to the
// furthest place to sleep within 6 mi, short of the next day's stop".
//
// WHAT IT IS NOT EVIDENCE FOR: where any particular nearo lands. That is
// restRhythm.test.ts's job - two stops inside one window, and a stop past
// tomorrow's that used to turn a real nearo into a zero. A day row that
// says "nearo · your rest day" appears only once the plan is saved, and
// plan-timeline-rests.mjs already photographs that badge.
//
// The drive is plan-step-3.mjs's, reused rather than copied, and it inherits
// that recipe's guards: where the bucket gives the stop picker nothing to
// name, the frame is whatever screen the drive reached and the rest control
// is not in it. Nobody's data: the shared long-hike fixture, no account, no
// location fix.
import driveToStepThree from './plan-step-3.mjs'

export const caption =
  'Step 3 with a nearo every 3 days, and the sentence saying where a nearo walks to (#1053)'
export const alt =
  'Step 3 of planning a long hike, scrolled to "A rest day · every 3 days" with a slider, Zero and Nearo buttons with Nearo pressed, and the note "A nearo walks to the furthest place to sleep within 6 mi, short of the next day’s stop — and is a zero where there isn’t one."; or, where the drive could not name a start, the screen it reached instead'

export const wait = 4000

export default async function drive(page) {
  await driveToStepThree(page)

  const slider = page.getByRole('slider', {
    name: 'A rest day every how many walking days',
  })
  if ((await slider.count()) === 0) return
  await slider.fill('3')
  await page.getByRole('button', { name: 'Nearo', exact: true }).click()
  const note = page.getByRole('note').filter({ hasText: 'A nearo walks' })
  await note.waitFor({ timeout: 5000 })
  await note.scrollIntoViewIfNeeded()
}
