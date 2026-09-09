// First run's size step (#1054): the download now starts on the step that
// asks for it, so the step carries the detail picker, "Keep going" as the
// primary, and "Decide this later" as the way past - the reversal recorded
// in screens/Onboarding.tsx's header. Photographed BEFORE "Keep going" is
// tapped: the shot is the offer, and tapping it in a preview would start a
// transfer against whatever the preview serves.
export const caption =
  'First run, step 2 — the size offer, with every figure now read from the manifest (#1167)'
export const alt =
  'The second first-run card over the hero photo: "Take the whole trail with you", three enabled size options — Light, Standard marked as recommended, and Fine — each with its whole-sheet size, a Keep going button and a Decide this later link'

// RE-POINTED BY #1167, which took the hand-copied sizes out of
// hikingDetail.ts. Every figure on this card now comes from `latest.json`, so
// this shot is the evidence that the common path is unchanged: a phone that
// can reach the bucket still sees three priced rungs, and they are the
// bucket's own numbers rather than constants that had drifted up to 34.7%.
//
// first-run-download-offline.mjs is the other half - the same card with the
// manifest blocked, which is where the new "Unknown offline" appears.

// First run is the subject, so the runner must not skip it.
export const entry = true

export default async function drive(page) {
  await page.getByRole('button', { name: 'Continue' }).click()
}
