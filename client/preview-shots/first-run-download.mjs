// First run's size step (#1054): the download now starts on the step that
// asks for it, so the step carries the detail picker, "Keep going" as the
// primary, and "Decide this later" as the way past - the reversal recorded
// in screens/Onboarding.tsx's header. Photographed BEFORE "Keep going" is
// tapped: the shot is the offer, and tapping it in a preview would start a
// transfer against whatever the preview serves.
export const caption = 'First run, step 2 — the download starts here now (#1054)'
export const alt =
  'The second first-run card over the hero photo: "Take the whole trail with you", the Standard and Fine size options, a Keep going button and a Decide this later link'

// First run is the subject, so the runner must not skip it.
export const entry = true

export default async function drive(page) {
  await page.getByRole('button', { name: 'Continue' }).click()
}
