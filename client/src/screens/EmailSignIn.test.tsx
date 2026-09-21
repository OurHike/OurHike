import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EmailSignIn, CODE_LENGTH, type EmailSignInProps } from './EmailSignIn'

// A 6-digit code, typed into the app (#279). The address step sends it and
// the code step signs in with it; neither claims a sign-in, because the
// session arriving is what closes the screen. What these pin is that the
// screen only moves on when a code was really sent, that every refusal is
// said out loud, and that there is a way back and a way out from both steps.

const ok = () => Promise.resolve({ ok: true as const })
const fails = (message: string) => () => Promise.resolve({ ok: false as const, message })

function setup(overrides: Partial<Parameters<typeof EmailSignIn>[0]> = {}) {
  const props = {
    onSendCode: vi.fn(ok),
    onVerifyCode: vi.fn(ok),
    onCancel: vi.fn(),
    ...overrides,
  }
  render(<EmailSignIn {...props} />)
  return props
}

type User = ReturnType<typeof userEvent.setup>

const typeEmail = (user: User) =>
  user.type(screen.getByLabelText(/email/i), 'hiker@example.com')

const askForCode = (user: User) =>
  user.click(screen.getByRole('button', { name: /email me a code/i }))

/** Through the address step to the code step, with a code sent. */
async function reachCodeStep(user: User) {
  await typeEmail(user)
  await askForCode(user)
  await screen.findByLabelText(/^code$/i)
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the address step', () => {
  it('asks for an address and nothing else - no code field yet, and no password ever', () => {
    setup()

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/^code$/i)).toBe(null)
    expect(screen.queryByLabelText(/password/i)).toBe(null)
  })

  it('says a code is coming and that a new address gets an account, before anything is typed', () => {
    // The "sign up or sign in?" question is answered here rather than asked:
    // onSendCode creates the user when the address is unknown.
    setup()

    expect(screen.getByRole('status')).toHaveTextContent(`${CODE_LENGTH}-digit code`)
    expect(screen.getByRole('status')).toHaveTextContent(/creates your account/i)
    expect(screen.queryByRole('button', { name: /create account/i })).toBe(null)
  })

  it('calls onSendCode with the address given', async () => {
    const user = userEvent.setup()
    const props = setup()

    await typeEmail(user)
    await askForCode(user)

    expect(props.onSendCode).toHaveBeenCalledWith('hiker@example.com')
    expect(props.onVerifyCode).not.toHaveBeenCalled()
  })

  it('moves to the code step and names the address the code went to', async () => {
    const user = userEvent.setup()
    setup()

    await reachCodeStep(user)

    expect(screen.getByRole('heading', { name: /check your email/i })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('hiker@example.com')
    expect(screen.getByRole('status')).toHaveTextContent(/no need to leave the app/i)
  })

  it('promises the report is still saved while the hiker looks for the email', async () => {
    const user = userEvent.setup()
    setup()

    await reachCodeStep(user)

    expect(screen.getByRole('status')).toHaveTextContent(/still saved on your phone/i)
  })

  it('stays on the address step and says why when the code was refused', async () => {
    // Saying "check your email" when nothing was sent leaves someone waiting
    // on a message that is not coming - the failure #397 named.
    const user = userEvent.setup()
    setup({
      onSendCode: vi.fn(
        fails('That was just sent. Give it a minute before asking again.'),
      ),
    })

    await typeEmail(user)
    await askForCode(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(/give it a minute/i)
    expect(screen.queryByRole('heading', { name: /check your email/i })).toBe(null)
    expect(screen.getByRole('button', { name: /email me a code/i })).toBeEnabled()
  })
})

describe('the code step', () => {
  it('asks for a numeric code the OS can fill from the notification', async () => {
    const user = userEvent.setup()
    setup()

    await reachCodeStep(user)
    const field = screen.getByLabelText(/^code$/i)

    expect(field).toHaveAttribute('inputmode', 'numeric')
    expect(field).toHaveAttribute('autocomplete', 'one-time-code')
  })

  it('calls onVerifyCode with the address and the code typed', async () => {
    const user = userEvent.setup()
    const props = setup()

    await reachCodeStep(user)
    await user.type(screen.getByLabelText(/^code$/i), '123456')
    await user.click(screen.getByRole('button', { name: /^sign in$/i }))

    expect(props.onVerifyCode).toHaveBeenCalledWith('hiker@example.com', '123456')
  })

  it('shows a refused code and keeps the digits for another try', async () => {
    const user = userEvent.setup()
    setup({
      onVerifyCode: vi.fn(
        fails(
          'That code did not match, or it has expired. Check the six digits, or ask for a new code.',
        ),
      ),
    })

    await reachCodeStep(user)
    await user.type(screen.getByLabelText(/^code$/i), '999999')
    await user.click(screen.getByRole('button', { name: /^sign in$/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/did not match/i)
    expect(screen.getByLabelText(/^code$/i)).toHaveValue('999999')
    expect(screen.getByRole('button', { name: /^sign in$/i })).toBeEnabled()
  })

  it('"Send another code" asks onSendCode again for the same address and says so', async () => {
    const user = userEvent.setup()
    const props = setup()

    await reachCodeStep(user)
    await user.click(screen.getByRole('button', { name: /send another code/i }))

    expect(props.onSendCode).toHaveBeenCalledTimes(2)
    expect(props.onSendCode).toHaveBeenLastCalledWith('hiker@example.com')
    expect(await screen.findByRole('status')).toHaveTextContent(
      /another code is on its way/i,
    )
  })

  it('"Send another code" shows the rate limit as a sentence rather than as silence', async () => {
    const user = userEvent.setup()
    const onSendCode = vi
      .fn<EmailSignInProps['onSendCode']>()
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({
        ok: false,
        message: 'That was just sent. Give it a minute before asking again.',
      })
    setup({ onSendCode })

    await reachCodeStep(user)
    await user.click(screen.getByRole('button', { name: /send another code/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/give it a minute/i)
  })

  it('"Use a different address" goes back with the address still typed and no stale failure', async () => {
    const user = userEvent.setup()
    setup({
      onVerifyCode: vi.fn(fails('That code did not match, or it has expired.')),
    })

    await reachCodeStep(user)
    await user.type(screen.getByLabelText(/^code$/i), '000000')
    await user.click(screen.getByRole('button', { name: /^sign in$/i }))
    await screen.findByRole('alert')
    await user.click(screen.getByRole('button', { name: /use a different address/i }))

    expect(screen.getByLabelText(/email/i)).toHaveValue('hiker@example.com')
    expect(screen.queryByLabelText(/^code$/i)).toBe(null)
    expect(screen.queryByRole('alert')).toBe(null)
  })

  it('does not claim to have signed anyone in when the code is accepted', async () => {
    // The session arriving is what closes the screen (App.tsx). Until it
    // does, there is nothing true to say beyond the button going quiet.
    const user = userEvent.setup()
    setup()

    await reachCodeStep(user)
    await user.type(screen.getByLabelText(/^code$/i), '123456')
    await user.click(screen.getByRole('button', { name: /^sign in$/i }))

    expect(screen.queryByText(/signed in/i)).toBe(null)
    expect(await screen.findByRole('button', { name: /^sign in$/i })).toBeEnabled()
  })
})

describe('EmailSignIn, whichever step is showing', () => {
  it('can be backed out of from the address step', async () => {
    const user = userEvent.setup()
    const props = setup()

    await user.click(screen.getByRole('button', { name: /not now/i }))

    expect(props.onCancel).toHaveBeenCalled()
  })

  it('can be backed out of from the code step', async () => {
    const user = userEvent.setup()
    const props = setup()

    await reachCodeStep(user)
    await user.click(screen.getByRole('button', { name: /not now/i }))

    expect(props.onCancel).toHaveBeenCalled()
  })

  it('still says reading the map never needs an account, on both steps', async () => {
    // Someone who reached this screen has gone one step deeper into a sign-in
    // wall, which is exactly where the reassurance matters most.
    const user = userEvent.setup()
    setup()

    expect(screen.getByRole('note')).toHaveTextContent(/never needs an account/i)
    await reachCodeStep(user)
    expect(screen.getByRole('note')).toHaveTextContent(/never needs an account/i)
  })
})

/** The address step's one button, with onSendCode throwing instead of returning. */
async function renderThrowing(thrown: unknown) {
  const user = userEvent.setup()
  setup({
    onSendCode: vi.fn(() => {
      throw thrown
    }),
  })
  await typeEmail(user)
  await askForCode(user)
  return user
}

describe('when a sign-in call throws rather than returning (#315)', () => {
  it('says so, instead of leaving the button "Working…" for ever', async () => {
    // The handlers RETURN their failures, so the try existed for nothing -
    // right up until one of them throws, which supabase-js does for a
    // malformed response or a client it could not build. There is no catch
    // above this screen: the primary button stayed disabled and labelled
    // "Working…" for the rest of the session.
    await renderThrowing(new Error('Failed to fetch'))

    expect(await screen.findByRole('alert')).toHaveTextContent(/no signal/i)
    expect(screen.getByRole('button', { name: /email me a code/i })).toBeEnabled()
  })

  it('reads a thrown failure the same way as a returned one', async () => {
    // A hiker cannot tell which kind of failure they hit and should not be
    // shown two vocabularies for one event.
    await renderThrowing(
      new Error('For security purposes, you can only request this after 51 seconds'),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(/give it a minute/i)
  })

  it('survives something thrown that is not an Error at all', async () => {
    await renderThrowing('a bare string, which a library is entitled to throw')

    expect(await screen.findByRole('alert')).toHaveTextContent(/did not go through/i)
  })
})
