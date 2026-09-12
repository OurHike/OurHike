// First run's second card, "What brings you out?" - the mode, asked rather
// than assigned (the maintainer's review of #1374, 2026-09-10: "There should
// be a step to select Day hike, long hike or Volunteer. That drives a lot of
// functionality. We shouldn't assign that silently."). The shot is the
// evidence that nothing is preselected, that the three rows carry a sentence
// each saying what the mode changes, that Continue appears only once a row
// is taken and names the choice, and that the skip says what skipping means.
//
// Photographed WITH a row taken, so the frame shows both the selected state
// and the primary it summons; the untaken state is the same card minus the
// button, and the test holds that (screens/Onboarding.test.tsx).

export const caption =
  'First run, card 2 of 5 — "What brings you out?", the mode asked rather than assigned: nothing preselected, one sentence per mode, Continue only once a row is taken (#1374 review)'
export const alt =
  'The second first-run card over the hero photo: "What brings you out?" with the sentence "Today changes with the answer — what leads, what is nearby, what a plan builds. Switch it any day from the Today screen.", then three rows each with a glyph, a name and a line under it — Day hike ("Out and back by dark. Walks near you, and a builder for one of your own."), Long hike ("One trail, broken into days. Sections, water and camp to camp."), Volunteer ("Workdays and the crew, with the trail in the background.") — with Day hike outlined as taken; under them a "Continue as day hike" button and a "Skip — day hike for now, change it on Today" link'

// First run is the subject, so the runner must not skip it.
export const entry = true

export default async function drive(page) {
  await page.getByRole('button', { name: 'Get set up' }).click()
  await page.getByRole('heading', { name: 'What brings you out?' }).waitFor()
  await page.getByRole('radio', { name: /^Day hike/ }).click()
  await page.getByRole('button', { name: 'Continue as day hike' }).waitFor()
}
