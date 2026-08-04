import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EmailSignIn } from './EmailSignIn'

// features/AUTHENTICATION.md asks for email + password, and for verification
// at account creation. Both shape this screen: a password field rather than a
// bare address, and a third outcome besides success and failure - the account
// exists but has no session behind it yet.

const ok = () => Promise.resolve({ ok: true as const })
const fails = (message: string) => () => Promise.resolve({ ok: false as const, message })

function setup(overrides: Partial<Parameters<typeof EmailSignIn>[0]> = {}) {
  const props = {
    onSignIn: vi.fn(ok),
    onSignUp: vi.fn(ok),
    onCancel: vi.fn(),
    ...overrides,
  }
  render(<EmailSignIn {...props} />)
  return props
}

async function fillIn(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/email/i), 'hiker@example.com')
  await user.type(screen.getByLabelText(/password/i), 'a good password')
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('EmailSignIn', () => {
  it('asks for a password, not only an address', () => {
    // A magic link would need only the address. The design doc asked for the
    // plain email + password option, so an address-only form would be a
    // different product decision wearing this one's clothes.
    setup()

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('signs in with what was typed', async () => {
    const user = userEvent.setup()
    const props = setup()

    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^sign in$/i }))

    expect(props.onSignIn).toHaveBeenCalledWith('hiker@example.com', 'a good password')
  })

  it('shows the reason a sign-in was refused', async () => {
    const user = userEvent.setup()
    setup({ onSignIn: vi.fn(fails('Invalid login credentials')) })

    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^sign in$/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /invalid login credentials/i,
    )
  })

  it('does not sign up when it was asked to sign in', async () => {
    const user = userEvent.setup()
    const props = setup()

    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^sign in$/i }))

    expect(props.onSignUp).not.toHaveBeenCalled()
  })

  it('can switch to creating an account', async () => {
    const user = userEvent.setup()
    const props = setup()

    await user.click(screen.getByRole('button', { name: /create an account instead/i }))
    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^create account$/i }))

    expect(props.onSignUp).toHaveBeenCalledWith('hiker@example.com', 'a good password')
    expect(props.onSignIn).not.toHaveBeenCalled()
  })

  it('says to go and confirm, rather than implying the account is already usable', async () => {
    // Supabase withholds the session until the emailed link is followed.
    // Reporting this as "signed in" would leave someone waiting for a
    // contribution to send that never would.
    const user = userEvent.setup()
    setup()

    await user.click(screen.getByRole('button', { name: /create an account instead/i }))
    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^create account$/i }))

    expect(
      await screen.findByRole('heading', { name: /check your email/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(/confirmation link/i)
  })

  it('names the address the confirmation went to', async () => {
    const user = userEvent.setup()
    setup()

    await user.click(screen.getByRole('button', { name: /create an account instead/i }))
    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^create account$/i }))

    expect(await screen.findByRole('status')).toHaveTextContent('hiker@example.com')
  })

  it('does not announce a confirmation when the sign-up was refused', async () => {
    const user = userEvent.setup()
    setup({ onSignUp: vi.fn(fails('User already registered')) })

    await user.click(screen.getByRole('button', { name: /create an account instead/i }))
    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^create account$/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/already registered/i)
    expect(screen.queryByText(/check your email/i)).toBe(null)
  })

  it('clears a failure when switching mode, so it cannot be read as the new one failing', async () => {
    const user = userEvent.setup()
    setup({ onSignIn: vi.fn(fails('Invalid login credentials')) })

    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^sign in$/i }))
    await screen.findByRole('alert')
    await user.click(screen.getByRole('button', { name: /create an account instead/i }))

    expect(screen.queryByRole('alert')).toBe(null)
  })

  it('can switch back to signing in after opening the create form', async () => {
    // The toggle has to work in both directions, or someone who tapped it by
    // mistake is stuck creating an account they already have.
    const user = userEvent.setup()
    const props = setup()

    await user.click(screen.getByRole('button', { name: /create an account instead/i }))
    await user.click(screen.getByRole('button', { name: /i already have an account/i }))
    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^sign in$/i }))

    expect(props.onSignIn).toHaveBeenCalledWith('hiker@example.com', 'a good password')
    expect(props.onSignUp).not.toHaveBeenCalled()
  })

  it('can be backed out of', async () => {
    const user = userEvent.setup()
    const props = setup()

    await user.click(screen.getByRole('button', { name: /not now/i }))

    expect(props.onCancel).toHaveBeenCalled()
  })

  it('still says reading the map never needs an account', async () => {
    // The same promise SignInPrompt makes. Someone who reached this screen has
    // gone one step deeper into a sign-in wall, which is exactly where the
    // reassurance matters most.
    setup()

    expect(screen.getByRole('note')).toHaveTextContent(/never needs an account/i)
  })
})
