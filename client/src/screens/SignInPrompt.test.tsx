import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SignInPrompt } from './SignInPrompt'

// WIREFRAMES.md §6: Google / Apple / email - and GitHub since #1572 - plus
// "a green callout [that] states that reading the map — water, shelters,
// closures, warnings — never needs an account."
//
// The callout is not reassurance decoration. This is the first and only time
// OurHike asks anyone to sign in, and the honest thing to say at that moment
// is what an account is NOT required for - otherwise a sign-in wall here
// reads as one for the whole app.
//
// The screen must also say the report is already saved. Someone asked to
// authenticate mid-trail needs to know they can decline, or fail, without
// losing what they just wrote.

const PROPS = {
  onSignIn: vi.fn(),
  onCancel: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('SignInPrompt', () => {
  it.each([/google/i, /apple/i, /github/i, /email/i])('offers %s', (provider) => {
    render(<SignInPrompt {...PROPS} />)

    expect(screen.getByRole('button', { name: provider })).toBeInTheDocument()
  })

  it('labels GitHub "Continue with GitHub" and reports it as github, the name Supabase keys on', async () => {
    const user = userEvent.setup()
    render(<SignInPrompt {...PROPS} />)

    await user.click(screen.getByRole('button', { name: 'Continue with GitHub' }))

    expect(PROPS.onSignIn).toHaveBeenCalledWith('github')
  })

  it('reports which provider was chosen', async () => {
    const user = userEvent.setup()
    render(<SignInPrompt {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /google/i }))

    expect(PROPS.onSignIn).toHaveBeenCalledWith('google')
  })

  it('states that reading the map never needs an account', () => {
    render(<SignInPrompt {...PROPS} />)

    expect(screen.getByText(/never needs an account/i)).toBeInTheDocument()
  })

  it('names what stays free, rather than claiming it vaguely', () => {
    render(<SignInPrompt {...PROPS} />)
    const callout = screen.getByRole('note')

    expect(callout).toHaveTextContent(/water/i)
    expect(callout).toHaveTextContent(/shelter/i)
    expect(callout).toHaveTextContent(/closure/i)
    expect(callout).toHaveTextContent(/warning/i)
  })

  it('says the report is already saved, so signing in is not a gate on keeping it', () => {
    render(<SignInPrompt {...PROPS} />)

    expect(screen.getByText(/already saved|saved on your phone/i)).toBeInTheDocument()
  })

  it('can be backed out of without losing anything', async () => {
    const user = userEvent.setup()
    render(<SignInPrompt {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /not now|cancel/i }))

    expect(PROPS.onCancel).toHaveBeenCalled()
  })

  it('never suggests the report will be lost by declining', () => {
    render(<SignInPrompt {...PROPS} />)

    expect(screen.queryByText(/will be lost|discard|you will lose/i)).toBe(null)
  })
})

describe('the providers a build can actually complete', () => {
  // The three do not cost the same to switch on - Apple needs a $99/yr
  // membership Google and email do not - so which appear is build
  // configuration. A button whose credentials do not exist reaches an error
  // page rather than an account, which is worse than an absent option.

  it('offers a narrowed set when one is given', () => {
    render(<SignInPrompt {...PROPS} providers={['google', 'email']} />)

    expect(screen.getByRole('button', { name: /google/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /email/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /apple/i })).toBe(null)
  })

  it('lists them in the order given, so the screen is not reshuffled per build', () => {
    render(<SignInPrompt {...PROPS} providers={['email', 'google']} />)
    const labels = screen
      .getAllByRole('button')
      .map((button) => button.textContent)
      .filter((text) => text?.startsWith('Continue'))

    expect(labels).toEqual(['Continue with email', 'Continue with Google'])
  })

  it('offline, holds every provider that leaves the app - GitHub with Google - and names them', () => {
    // #315: Google, Apple and GitHub are a full off-origin navigation, so
    // offline they take the hiker out of the app rather than merely failing.
    // Email is a fetch that fails inside the app, so it stays enabled.
    render(
      <SignInPrompt
        {...PROPS}
        providers={['google', 'github', 'email']}
        online={false}
      />,
    )

    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Continue with GitHub' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Continue with email' })).toBeEnabled()
    const notes = screen.getAllByRole('note').map((note) => note.textContent)
    expect(notes.some((text) => /Google and GitHub need signal/.test(text ?? ''))).toBe(
      true,
    )
    expect(notes.some((text) => /Email works from here/.test(text ?? ''))).toBe(true)
  })

  it('offline with one provider held, says "needs signal" in the singular and does not promise email', () => {
    render(<SignInPrompt {...PROPS} providers={['google']} online={false} />)

    const notes = screen.getAllByRole('note').map((note) => note.textContent ?? '')
    expect(notes.some((text) => /Google needs signal/.test(text))).toBe(true)
    expect(notes.some((text) => /Email works from here/.test(text))).toBe(false)
  })

  it('still lets someone back out when no provider is configured at all', () => {
    // An empty set is a real configuration - a build with no credentials yet.
    // Leaving it without an exit would be a screen a hiker cannot leave.
    render(<SignInPrompt {...PROPS} providers={[]} />)

    expect(screen.queryByRole('button', { name: /continue with/i })).toBe(null)
    expect(screen.getByRole('button', { name: /not now/i })).toBeInTheDocument()
  })
})

describe('when there is no report behind it', () => {
  // The same screen serves the account row in Settings, where nothing has
  // been written. Promising that a report is saved would be a claim about
  // something that does not exist.

  it('does not say a report is saved', () => {
    render(<SignInPrompt {...PROPS} reportSaved={false} />)

    expect(screen.queryByText(/already saved|saved on your phone/i)).toBe(null)
  })

  it('still says what stays free without an account', () => {
    // This is the load-bearing half of the screen, and it is true in both
    // contexts.
    render(<SignInPrompt {...PROPS} reportSaved={false} />)

    expect(screen.getByRole('note')).toHaveTextContent(/never needs an account/i)
  })

  it('still offers the providers and a way out', () => {
    render(<SignInPrompt {...PROPS} reportSaved={false} />)

    expect(screen.getByRole('button', { name: /google/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /not now/i })).toBeInTheDocument()
  })
})
