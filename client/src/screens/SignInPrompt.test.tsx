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

describe('the marks on the doors (#1572)', () => {
  // Google's and GitHub's brand pages say what their buttons may look like,
  // and the tests pin the parts a reviewer cannot see in a diff: the G is
  // the standard four-colour one and not a recolour, the GitHub mark takes
  // the button's own colour, the email door carries OurHike's icon - and
  // none of it changes what a screen reader hears.

  it.each(['Continue with Google', 'Continue with GitHub', 'Continue with email'])(
    'keeps "%s" as the whole accessible name, so the mark adds nothing a screen reader hears',
    (name) => {
      render(<SignInPrompt {...PROPS} />)

      expect(screen.getByRole('button', { name })).toBeInTheDocument()
    },
  )

  it("draws Google's G in its four brand colours, in order, and hides it from assistive tech", () => {
    render(<SignInPrompt {...PROPS} />)
    const button = screen.getByRole('button', { name: 'Continue with Google' })
    const svg = button.querySelector('svg')
    const fills = Array.from(button.querySelectorAll('svg path')).map((path) =>
      path.getAttribute('fill'),
    )

    // Red, blue, yellow, green - the standard G, never a monochrome one
    // (developers.google.com/identity/branding-guidelines).
    expect(fills).toEqual(['#EA4335', '#4285F4', '#FBBC05', '#34A853'])
    expect(svg).toHaveAttribute('aria-hidden', 'true')
    expect(button).toHaveClass('reporting__provider--google')
  })

  it("draws GitHub's mark in currentColor, so it is white on the black button and black on the white one", () => {
    render(<SignInPrompt {...PROPS} />)
    const button = screen.getByRole('button', { name: 'Continue with GitHub' })
    const svg = button.querySelector('svg')

    expect(svg).toHaveAttribute('fill', 'currentColor')
    expect(svg).toHaveAttribute('aria-hidden', 'true')
    expect(svg?.querySelector('path')).not.toBeNull()
    expect(button).toHaveClass('reporting__provider--github')
  })

  it('puts the OurHike icon on the email door as a decorative image', () => {
    render(<SignInPrompt {...PROPS} />)
    const button = screen.getByRole('button', { name: 'Continue with email' })
    const img = button.querySelector('img')

    expect(img).toHaveAttribute('alt', '')
    // Vite hands a small SVG import back as a data: URL in this environment
    // and as a hashed /assets/ path in a build, so the assertion accepts the
    // shape rather than the name; what it pins is that an image is there.
    expect(img?.getAttribute('src')).toMatch(/^data:image\/svg\+xml|logo-icon/)
    expect(button).toHaveClass('reporting__provider--email')
  })

  it('draws no mark for Apple, whose asset ships with the provider (#92)', () => {
    render(<SignInPrompt {...PROPS} providers={['apple']} />)
    const button = screen.getByRole('button', { name: 'Continue with Apple' })

    expect(button.querySelector('svg, img')).toBeNull()
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

describe('when the ask opened because a round trip was refused (#1573)', () => {
  // Google and GitHub are a full off-origin navigation, so a refusal comes
  // back as a fresh page load with nothing left alive to have been told.
  // App.tsx reads it off the URL and re-opens this ask carrying the
  // sentence; this is the half that renders it.

  const REFUSAL = 'That sign-in was not finished, so nothing changed.'

  it('says why, in an alert, so a window that opened by itself is not silent', () => {
    render(<SignInPrompt {...PROPS} reportSaved={false} refusal={REFUSAL} />)

    expect(screen.getByRole('alert')).toHaveTextContent(REFUSAL)
  })

  it('puts the reason before the doors, which is the order it is read in', () => {
    // "Why am I looking at this" is the question the hiker arrives with, and
    // a sentence underneath three buttons answers it after they have already
    // decided. `compareDocumentPosition` rather than a snapshot: the claim is
    // about order, not markup.
    render(<SignInPrompt {...PROPS} reportSaved={false} refusal={REFUSAL} />)

    const alert = screen.getByRole('alert')
    const firstDoor = screen.getByRole('button', { name: /github/i })

    expect(alert.compareDocumentPosition(firstDoor)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
  })

  it('still offers every way in, because a refusal is not a lock-out', () => {
    render(<SignInPrompt {...PROPS} reportSaved={false} refusal={REFUSAL} />)

    expect(screen.getByRole('button', { name: /github/i })).toBeEnabled()
    expect(screen.getByRole('button', { name: /google/i })).toBeEnabled()
    expect(screen.getByRole('button', { name: /email/i })).toBeEnabled()
  })

  it('says nothing at all on the ordinary path, where somebody pressed a button', () => {
    // The defect's mirror image, and the cheaper one to ship: an alert in
    // front of a hiker who opened the ask deliberately.
    render(<SignInPrompt {...PROPS} />)

    expect(screen.queryByRole('alert')).toBe(null)
  })
})
