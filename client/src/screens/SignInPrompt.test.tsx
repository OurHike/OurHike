import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SignInPrompt } from './SignInPrompt'

// WIREFRAMES.md §6: Google / Apple / email, plus "a green callout [that]
// states that reading the map — water, shelters, closures, warnings — never
// needs an account."
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
  it.each([/google/i, /apple/i, /email/i])('offers %s', (provider) => {
    render(<SignInPrompt {...PROPS} />)

    expect(screen.getByRole('button', { name: provider })).toBeInTheDocument()
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
