import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EmailSignIn } from './EmailSignIn'

// A link is the default path and a password is the fallback. The link is one
// field, nothing to remember, and following it does the email verification
// features/AUTHENTICATION.md asks for without a second step. The password
// stays because a link means leaving for an email client and coming back,
// which on a ridge with one bar is the fragile part.

const ok = () => Promise.resolve({ ok: true as const })
const fails = (message: string) => () => Promise.resolve({ ok: false as const, message })

function setup(overrides: Partial<Parameters<typeof EmailSignIn>[0]> = {}) {
  const props = {
    onMagicLink: vi.fn(ok),
    onSignIn: vi.fn(ok),
    onSignUp: vi.fn(ok),
    onCancel: vi.fn(),
    ...overrides,
  }
  render(<EmailSignIn {...props} />)
  return props
}

const typeEmail = (user: ReturnType<typeof userEvent.setup>) =>
  user.type(screen.getByLabelText(/email/i), 'hiker@example.com')

async function fillIn(user: ReturnType<typeof userEvent.setup>) {
  await typeEmail(user)
  await user.type(screen.getByLabelText(/password/i), 'a good password')
}

const usePassword = (user: ReturnType<typeof userEvent.setup>) =>
  user.click(screen.getByRole('button', { name: /use a password instead/i }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the link, which is the way in by default', () => {
  it('asks for an address and nothing else', () => {
    // The whole advantage: one field, and no password to set now or recall
    // six weeks up the trail.
    setup()

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/password/i)).toBe(null)
  })

  it('sends the link to the address given', async () => {
    const user = userEvent.setup()
    const props = setup()

    await typeEmail(user)
    await user.click(screen.getByRole('button', { name: /email me a sign-in link/i }))

    expect(props.onMagicLink).toHaveBeenCalledWith('hiker@example.com')
  })

  it('does not ask whether the account is new, because the link covers both', async () => {
    // Supabase creates the user when the address is unknown, so a "sign up or
    // sign in?" question before the form would be one the app already knows
    // it does not need answered.
    setup()

    expect(screen.queryByRole('button', { name: /^create account$/i })).toBe(null)
  })

  it('says the link is on its way, rather than implying it signed anyone in', async () => {
    const user = userEvent.setup()
    setup()

    await typeEmail(user)
    await user.click(screen.getByRole('button', { name: /email me a sign-in link/i }))

    expect(
      await screen.findByRole('heading', { name: /check your email/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(/sign-in link/i)
    expect(screen.getByRole('status')).toHaveTextContent('hiker@example.com')
  })

  it('promises the report is still saved while the hiker leaves for their email', async () => {
    // Which is the moment that promise matters most - this path deliberately
    // sends someone out of the app.
    const user = userEvent.setup()
    setup()

    await typeEmail(user)
    await user.click(screen.getByRole('button', { name: /email me a sign-in link/i }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      /still saved on your phone/i,
    )
  })

  it('shows why it was refused', async () => {
    const user = userEvent.setup()
    setup({ onMagicLink: vi.fn(fails('Email rate limit exceeded')) })

    await typeEmail(user)
    await user.click(screen.getByRole('button', { name: /email me a sign-in link/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/rate limit/i)
    expect(screen.queryByRole('heading', { name: /check your email/i })).toBe(null)
  })
})

describe('the password fallback', () => {
  it('is reachable, because a link means leaving the app and coming back', async () => {
    const user = userEvent.setup()
    setup()

    await usePassword(user)

    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('signs in with what was typed', async () => {
    const user = userEvent.setup()
    const props = setup()

    await usePassword(user)
    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^sign in$/i }))

    expect(props.onSignIn).toHaveBeenCalledWith('hiker@example.com', 'a good password')
    expect(props.onMagicLink).not.toHaveBeenCalled()
  })

  it('shows the reason a sign-in was refused', async () => {
    const user = userEvent.setup()
    setup({ onSignIn: vi.fn(fails('Invalid login credentials')) })

    await usePassword(user)
    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^sign in$/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /invalid login credentials/i,
    )
  })

  it('can go back to the link', async () => {
    const user = userEvent.setup()
    setup()

    await usePassword(user)
    await user.click(screen.getByRole('button', { name: /email me a link instead/i }))

    expect(screen.queryByLabelText(/password/i)).toBe(null)
  })

  it('can create a password account, for someone who wants one', async () => {
    const user = userEvent.setup()
    const props = setup()

    await usePassword(user)
    await user.click(
      screen.getByRole('button', { name: /create an account with a password/i }),
    )
    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^create account$/i }))

    expect(props.onSignUp).toHaveBeenCalledWith('hiker@example.com', 'a good password')
    expect(props.onSignIn).not.toHaveBeenCalled()
  })

  it('says to go and confirm a new account, rather than implying it is usable', async () => {
    // Supabase withholds the session until the emailed link is followed.
    const user = userEvent.setup()
    setup()

    await usePassword(user)
    await user.click(
      screen.getByRole('button', { name: /create an account with a password/i }),
    )
    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^create account$/i }))

    expect(await screen.findByRole('status')).toHaveTextContent(/confirmation link/i)
  })

  it('does not announce a confirmation when the sign-up was refused', async () => {
    const user = userEvent.setup()
    setup({ onSignUp: vi.fn(fails('User already registered')) })

    await usePassword(user)
    await user.click(
      screen.getByRole('button', { name: /create an account with a password/i }),
    )
    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^create account$/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/already registered/i)
    expect(screen.queryByRole('heading', { name: /check your email/i })).toBe(null)
  })

  it('can get back from creating to signing in', async () => {
    const user = userEvent.setup()
    const props = setup()

    await usePassword(user)
    await user.click(
      screen.getByRole('button', { name: /create an account with a password/i }),
    )
    await user.click(screen.getByRole('button', { name: /i already have an account/i }))
    await fillIn(user)
    await user.click(screen.getByRole('button', { name: /^sign in$/i }))

    expect(props.onSignIn).toHaveBeenCalled()
    expect(props.onSignUp).not.toHaveBeenCalled()
  })
})

describe('EmailSignIn, whichever path is showing', () => {
  it('clears a failure when switching path, so it cannot be read as the new one failing', async () => {
    const user = userEvent.setup()
    setup({ onMagicLink: vi.fn(fails('Email rate limit exceeded')) })

    await typeEmail(user)
    await user.click(screen.getByRole('button', { name: /email me a sign-in link/i }))
    await screen.findByRole('alert')
    await usePassword(user)

    expect(screen.queryByRole('alert')).toBe(null)
  })

  it('keeps the address across a switch, so it is not typed twice', async () => {
    const user = userEvent.setup()
    setup()

    await typeEmail(user)
    await usePassword(user)

    expect(screen.getByLabelText(/email/i)).toHaveValue('hiker@example.com')
  })

  it('can be backed out of', async () => {
    const user = userEvent.setup()
    const props = setup()

    await user.click(screen.getByRole('button', { name: /not now/i }))

    expect(props.onCancel).toHaveBeenCalled()
  })

  it('still says reading the map never needs an account', () => {
    // Someone who reached this screen has gone one step deeper into a sign-in
    // wall, which is exactly where the reassurance matters most.
    setup()

    expect(screen.getByRole('note')).toHaveTextContent(/never needs an account/i)
  })
})
