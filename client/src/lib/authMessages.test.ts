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

describe('the failures worth telling apart', () => {
  it('a wrong password points at the way round it', () => {
    // A hiker who cannot remember a password has a sign-in link available,
    // and this is the moment to say so.
    expect(signInMessage('Invalid login credentials')).toMatch(/sign-in link/i)
  })

  it('an unconfirmed account says where the link is', () => {
    expect(signInMessage('Email not confirmed')).toMatch(/follow the link/i)
  })

  it('an existing account says to sign in rather than sign up', () => {
    expect(signInMessage('User already registered')).toMatch(/already an account/i)
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
