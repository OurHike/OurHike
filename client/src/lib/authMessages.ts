// What a sign-in failure says to a hiker, as against what supabase-js says
// to a developer (#315).
//
// `lib/auth.ts` returned `error.message` verbatim from five call sites, and
// `EmailSignIn` renders that in a `role="alert"` — so the strings a hiker was
// read out loud included `AuthRetryableFetchError: Failed to fetch` and "For
// security purposes, you can only request this after 51 seconds". The first
// names a class from a library they have never heard of to describe having no
// signal; the second is a rate limit phrased as a security accusation.
//
// Kept out of auth.ts so that module stays the seam to Supabase and this one
// stays the seam to a person — they change for different reasons, the same
// split lib/atcNoticeText.ts keeps from lib/atcUpdates.ts.
//
// WHY MATCHING ON TEXT, WHICH IS THE OBVIOUS OBJECTION
//
// supabase-js does carry error codes, and matching them would be sturdier.
// It is not what this can do honestly: the codes are not exhaustively
// documented for the paths this app uses, and a mapping keyed on codes
// nobody here has verified would be a guess wearing a lookup table's
// clothes. Text matching is fragile in a KNOWN way — a reworded upstream
// message falls through to the general case, which is a true sentence — so
// the failure mode of being wrong is a vaguer message rather than a
// confidently wrong one.
//
// `@unvalidated`: the first two patterns come from the strings quoted in
// #315's audit; the code-path ones below come from Supabase's own docs and
// GoTrue's error strings ("Token has expired or is invalid", "Email address
// not authorized", "Error sending magic link email"), not from a failure
// observed against this project. What would settle it is a real sign-in
// failing in each of these ways against the live project, which needs
// #1572's dashboard steps done.

/** The general case, and a true sentence about every failure this maps. */
const UNCLEAR = 'Sign-in did not go through. Nothing was lost — you can try again.'

/**
 * One supabase-js message as a hiker reads it.
 *
 * The offline case is the one that matters most and is the most disguised:
 * `Failed to fetch` is what a browser says when a request never left, which
 * on this trail is the ordinary state rather than a fault.
 */
export function signInMessage(raw: string): string {
  const text = raw.toLowerCase()

  if (text.includes('failed to fetch') || text.includes('networkerror')) {
    return 'No signal, so sign-in could not reach anyone. Everything you have written is still saved on this phone.'
  }
  if (text.includes('only request this after') || text.includes('rate limit')) {
    // Deliberately drops the seconds. The upstream string is precise and
    // unhelpful — a hiker cannot act on 51 seconds differently from a minute,
    // and "for security purposes" reads as an accusation about them.
    return 'That was just sent. Give it a minute before asking again.'
  }
  if (text.includes('token has expired or is invalid') || text.includes('otp_expired')) {
    // A mistyped code and a code left an hour are one case to a hiker: the
    // way out of both is the same, and saying which it was would be a guess.
    return 'That code did not match, or it has expired. Check the six digits, or ask for a new code.'
  }
  if (text.includes('email address not authorized')) {
    // What a project with no sender says: Supabase's built-in mailer sends
    // only to the project's own team members (LAUNCH_CHECKLIST.md 4.3c). A
    // hiker cannot act on that, so the sentence says what stays true for
    // them; backend/check_supabase_config.py is what tells a maintainer.
    return 'Email sign-in is not switched on in this version of the app, so no code can be sent. Everything on the map still works without an account.'
  }
  if (text.includes('error sending')) {
    // The sender exists and refused just now - "Error sending magic link
    // email" is GoTrue's wording whether the email carries a link or a code.
    return 'The code could not be sent just now. That is on our side, not yours — try again in a little while. Everything on the map still works without an account.'
  }
  if (text.includes('signups not allowed')) {
    return 'New accounts are not being created right now. Everything on the map still works without an account.'
  }
  return UNCLEAR
}

/**
 * What a build with no auth project configured says.
 *
 * The old wording named Supabase, which tells a hiker the name of a vendor
 * they have no relationship with and nothing they can do. This says what is
 * true FOR THEM: the reading half of the app is what they came for and it is
 * unaffected.
 */
export const NOT_CONFIGURED_MESSAGE =
  'This version of the app cannot sign in. Everything on the map still works.'
