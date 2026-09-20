// Sign in with email: the address step, inside the same window (#279, #1596).
//
// ONE WINDOW, TWO VIEWS. The email path's second step swaps this window's
// contents rather than opening a screen of its own, which is what makes
// "send another code" and "use a different address" read as the same place.
// This shot is the first view; the map is still behind it.
//
// The code step is deliberately NOT driven. Reaching it means signInWithOtp
// against the preview's real project, which would create a user in
// production's auth pool for whatever address was typed and send an email to
// it. EmailSignIn.test.tsx holds the code step instead.
export const caption =
  'Sign in with email — the address step, in the same window the ask opened in, over the map (#279, #1596)'
export const alt =
  'A "Sign in with email" dialog over the trail map: the note that a 6-digit code will be emailed and typed in here, one Email field, an "Email me a code" button and "Not now"'

export default async function drive(page) {
  await page.getByRole('button', { name: 'Sign in' }).first().click()
  await page.getByRole('dialog', { name: 'Sign in' }).waitFor()
  await page.getByRole('button', { name: 'Continue with email' }).click()
  await page.getByRole('heading', { name: 'Sign in with email' }).waitFor()
}
