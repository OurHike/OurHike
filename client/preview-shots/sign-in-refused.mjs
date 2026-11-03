// Landing back from a sign-in Google or GitHub refused (#1573) - the state
// that used to be a hiker on the map, signed out, with nothing said.
//
// WHAT THIS SHOT IS EVIDENCE FOR. The other two sign-in shots photograph an
// ask somebody asked for. This one photographs one that opened BY ITSELF, so
// the picture has to answer a question the others never raise: why is this
// in front of me. The alert line is that answer, and it is above the doors
// rather than beside one of them - which button was tapped is not in the URL
// Supabase redirects with, and a sentence under a guess is worse than a
// sentence where the eye already is.
//
// THE DRIVE IS A RELOAD, and that is the subject rather than an awkwardness.
// `signInWithProvider` is a full off-origin navigation: the tab leaves, and
// the refusal comes back as a FRESH PAGE LOAD carrying `#error=…`. No tap
// inside the app can reach this state, because no component that could have
// been told about it is still alive. A recipe that set the fragment without
// reloading would photograph a screen the app never boots into.
//
// The fragment below is the shape GoTrue redirects with, read off OAuth2 RFC
// 6749 §4.1.2.1 and GoTrue's `api/external.go` rather than off a refusal
// seen against the live project - the `@unvalidated` footing lib/
// authMessages.ts's header gives both patterns. So the picture is evidence
// about THIS APP's behaviour given that URL, which is the half the
// repository owns, and not about how Google spells a cancellation.
//
// Nobody's data: the preview's phone has never signed in, there is no
// account on the button, and the refusal is one this recipe wrote itself.

/** What Supabase puts on the URL when a consent screen is cancelled. The
 *  description is prose this app cannot recognise and the code beside it is
 *  the one it can, which is the case lib/authRefusal.ts reads every key for
 *  rather than taking the first one present. */
const REFUSED =
  '#error=server_error&error_code=access_denied&error_description=The+user+denied+the+request'

export const caption =
  'Coming back from a sign-in that was refused at the provider (#1573): the ask re-opens by itself with the reason above the doors, rather than dropping the hiker on the map with nothing said'
export const alt =
  'A "Sign in" dialog docked to the foot of the Today screen, led by a pale panel carrying a rust-red sentence reading "That sign-in was not finished, so nothing changed. You can try again, or use a different way in." Below it the three doors are all still enabled — "Continue with GitHub" in black, "Continue with Google" in white, "Continue with email" in dark green carrying the OurHike app icon — then "Not now", and the note that reading the map never needs an account.'

export default async function drive(page) {
  // Same document, so this sets the fragment without re-running the app...
  const here = page.url().split('#')[0]
  await page.goto(`${here}${REFUSED}`)
  // ...and this is what makes it a launch, which is the only way this state
  // is reachable. The reload keeps the fragment, and the context's IndexedDB
  // with it, so first run stays skipped.
  await page.reload({ waitUntil: 'load' })

  await page.getByRole('dialog', { name: 'Sign in' }).waitFor()
  // The alert specifically, not just the dialog: the dialog opening is what
  // the other two shots already prove, and the sentence is the whole of what
  // #1573 added.
  await page.getByRole('alert').waitFor()
}
