import { describe, it, expect } from 'vitest'
import { signInMessage, NOT_CONFIGURED_MESSAGE } from './authMessages'

// What a sign-in failure says to a hiker (#315).
//
// The audit's own examples are the cases worth pinning, because they are the
// strings that were really being read out loud in a `role="alert"`:
// `AuthRetryableFetchError: Failed to fetch` for having no signal, and "For
// security purposes, you can only request this after 51 seconds" for asking
// for a second link.

describe('the strings #315 found on screen', () => {
  it('says "no signal" rather than naming a library exception', () => {
    // The most disguised of the lot: a browser says "Failed to fetch" when a
    // request never left, which on this trail is the ordinary state rather
    // than a fault - and the class name in front of it names a library the
    // hiker has never heard of.
    const said = signInMessage('AuthRetryableFetchError: Failed to fetch')

    expect(said).toMatch(/no signal/i)
    expect(said).not.toMatch(/fetch|autherror|auth[a-z]*error/i)
  })

  it('says the map keeps what they wrote, because that is what they will worry about', () => {
    expect(signInMessage('AuthRetryableFetchError: Failed to fetch')).toMatch(
      /still saved on this phone/i,
    )
  })

  it('does not accuse somebody of a security problem for asking twice', () => {
    // "For security purposes" reads as being about them. It is a rate limit.
    const said = signInMessage(
      'For security purposes, you can only request this after 51 seconds',
    )

    expect(said).toMatch(/give it a minute/i)
    expect(said).not.toMatch(/security/i)
  })

  it('drops the exact seconds, which nobody can act on differently', () => {
    expect(signInMessage('you can only request this after 51 seconds')).not.toMatch(/51/)
  })
})

describe('the failures of the emailed code (#279)', () => {
  it('"Token has expired or is invalid" offers a new code without blaming the digits', () => {
    // GoTrue's ONE string for three different things: a mistyped code, a code
    // left too long, and a code the project never minted. The way out of all
    // three is the same, so the sentence offers that and guesses at nothing.
    const said = signInMessage('Token has expired or is invalid')

    // NOT "check the six digits". #1600 is why: a hiker was told exactly that
    // about a code that could not have worked however carefully they read it,
    // so they read it again, and again. An instruction that cannot help is
    // worse than no instruction.
    expect(said).toMatch(/was not accepted/i)
    expect(said).toMatch(/ask for a new one/i)
    expect(said).not.toMatch(/six digits/i)
    expect(said).not.toMatch(/token/i)
  })

  it('"Email address not authorized" says this build cannot send email, and that the map still works', () => {
    // What a project on Supabase's built-in mailer answers for any address
    // outside its own team (LAUNCH_CHECKLIST.md 4.3c). Nothing a hiker can
    // do about it, so the sentence is about what stays true for them.
    const said = signInMessage('Email address not authorized')

    expect(said).toMatch(/not switched on/i)
    expect(said).toMatch(/map still works/i)
    expect(said).not.toMatch(/authorized/i)
  })

  it('"Error sending magic link email" is the sender failing now, so it says to try again later', () => {
    // GoTrue's wording whether the email carries a link or a code.
    const said = signInMessage('Error sending magic link email')

    expect(said).toMatch(/could not be sent just now/i)
    expect(said).toMatch(/on our side/i)
    expect(said).not.toMatch(/magic link/i)
  })

  it('"Signups not allowed for otp" says accounts are not being created, without blaming the hiker', () => {
    expect(signInMessage('Signups not allowed for otp')).toMatch(/not being created/i)
  })
})

describe('a round trip refused at Google or GitHub (#1573)', () => {
  // These two arrive in the fragment of a redirect rather than as the
  // message of a rejected promise, which is why they were missing: nothing
  // read that fragment until lib/authRefusal.ts did.

  it('does not tell somebody they cancelled, because the server may have', () => {
    // RFC 6749 §4.1.2.1 spends `access_denied` on both "the resource owner
    // denied" and "the authorization server denied". A sentence that picks
    // the first is an app arguing with a hiker who did not do it.
    const said = signInMessage('access_denied')

    expect(said).toMatch(/was not finished/i)
    expect(said).not.toMatch(/you cancelled|you denied|you tapped/i)
  })

  it('does not name a provider for access_denied, since the string does not say', () => {
    // Google and GitHub both answer with this code and neither is in it.
    expect(signInMessage('access_denied')).not.toMatch(/google|github/i)
  })

  it('says nothing changed, which is the thing worth knowing after a refusal', () => {
    expect(signInMessage('access_denied')).toMatch(/nothing changed/i)
  })

  it('explains an account with no verified address, and says where to fix it', () => {
    // GoTrue answers this when the provider hands back no address; in
    // practice that is a GitHub account with none verified. The only refusal
    // in this file a hiker can go and do something about, so it says what.
    const said = signInMessage('Error getting user email from external provider')

    expect(said).toMatch(/verified email address/i)
    expect(said).toMatch(/github/i)
  })

  it('reads a refusal whatever case the provider sent it in', () => {
    expect(signInMessage('ACCESS_DENIED')).toMatch(/was not finished/i)
  })
})

describe('when the message is one nothing here knows', () => {
  it('falls through to a sentence that is still true', () => {
    // The intended failure mode of matching on text: a reworded upstream
    // message becomes vaguer, never confidently wrong.
    const said = signInMessage('some new upstream wording nobody has seen')

    expect(said).toMatch(/did not go through/i)
    expect(said).toMatch(/nothing was lost/i)
  })

  it('never leaks the raw text through the general case', () => {
    expect(signInMessage('PGRST301: JWT expired')).not.toMatch(/PGRST301|JWT/)
  })

  it('is case-insensitive, since upstream casing is not ours to rely on', () => {
    expect(signInMessage('FAILED TO FETCH')).toMatch(/no signal/i)
  })
})

describe('a build with no auth project', () => {
  it('says what the hiker can still do, and does not name a vendor', () => {
    expect(NOT_CONFIGURED_MESSAGE).toMatch(/map still works/i)
    expect(NOT_CONFIGURED_MESSAGE).not.toMatch(/supabase/i)
  })
})
