// The sign-in ask, one tap from the map's own header (#1596).
//
// WHAT THIS SHOT IS EVIDENCE FOR, and it is two things now. Which doors this
// build offers - the buttons are ENABLED_PROVIDERS in lib/supabase.ts, a
// reviewed constant since #1572 rather than a repository variable - and that
// the ask is a WINDOW over the map rather than a screen instead of it. The
// map is still drawn behind and below it, which is the change #1596 made and
// the reason this recipe no longer drives through More.
//
// It was More → You → Sign in until 2026-09-20, three taps into the settings
// tab. The camera moved with the door.
//
// Nobody's data: the preview's phone has never signed in, so there is no
// address on the button, and the ask is raised for its own sake rather than
// after a report, so it promises nothing about one being saved.
export const caption =
  'The sign-in ask, one tap from the map header, as a window over the map rather than a screen instead of it — each door in its own colours (#1596, #1572)'
export const alt =
  'A "Sign in" dialog docked to the foot of the screen over the trail map, with a "Continue with …" button for each configured provider - Google\'s white button with the multicolour G, GitHub\'s black button with its mark, and OurHike\'s pine button with the app icon for email - a "Not now" button, and the note that reading the map never needs an account. The map is still visible above it.'

export default async function drive(page) {
  await page.getByRole('button', { name: 'Sign in' }).first().click()
  await page.getByRole('dialog', { name: 'Sign in' }).waitFor()
}
