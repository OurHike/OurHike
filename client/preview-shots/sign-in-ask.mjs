// The sign-in ask, reached for its own sake from More → You (#1572).
//
// WHAT THIS SHOT IS EVIDENCE FOR. Which doors this build offers, and the
// sentence under them. The buttons are ENABLED_PROVIDERS (lib/supabase.ts):
// the AUTH_PROVIDERS repository variable, which is `google` alone until
// #1572's dashboard steps are done and it is switched to
// `google,github,email` - so the frame reads one button or three depending
// on the day it was taken, and either is honest. What is fixed is the note
// that reading the map never needs an account, and "Not now".
//
// Nobody's data: the preview's phone has never signed in, so there is no
// address to show, and the ask is reached from Settings rather than after a
// report, so it makes no promise about one being saved.
export const caption =
  'The sign-in ask from More → You: one "Continue with …" per provider this build offers (#1572)'
export const alt =
  'A "Sign in" screen with a "Continue with …" button for each configured provider, a "Not now" button, and the note that reading the map never needs an account'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'More' }).click()
  await page.locator('.more__row').filter({ hasText: 'You' }).first().click()
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('heading', { name: 'Sign in' }).waitFor()
}
