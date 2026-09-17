// Sign in with email: the address step of screens/EmailSignIn.tsx (#279,
// #1572).
//
// TWO TRUE FRAMES, and the caption names both. "Continue with email" exists
// only when the build offers email - the AUTH_PROVIDERS repository
// variable, which #1572 switches on as its last step. Until then this drive
// stops at the sign-in ask, the same screen sign-in-ask.mjs shows. After it,
// the frame is the address step: one email field, "Email me a code", and
// the sentence that a new address also creates the account.
//
// The code step is deliberately NOT driven. Reaching it means
// signInWithOtp against the preview's real project, which would create a
// user in production's auth pool for whatever address was typed and send an
// email to it. EmailSignIn.test.tsx holds the code step instead.
export const caption =
  'Sign in with email — the address step behind "Continue with email", or the ask it sits behind while the build offers no email (#279, #1572)'
export const alt =
  'A "Sign in with email" screen: the note that a 6-digit code will be emailed and typed in here, one Email field, an "Email me a code" button and "Not now" - or, when the build offers no email, the sign-in ask with its provider buttons'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'More' }).click()
  await page.locator('.more__row').filter({ hasText: 'You' }).first().click()
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('heading', { name: 'Sign in' }).waitFor()
  const email = page.getByRole('button', { name: 'Continue with email' })
  if ((await email.count()) > 0) {
    await email.click()
    await page.getByRole('heading', { name: 'Sign in with email' }).waitFor()
  }
}
