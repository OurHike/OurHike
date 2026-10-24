import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SupportAsk } from './SupportAsk'
import { readLocalChoice, type SupportSummary } from '../lib/support'

// The day-5 ask (#1876). A choice is required, $0 is a choice, and payment
// never happens inside the app: the website app is sent on to Buy Me a
// Coffee, the store apps get the link by email.

const PENDING: SupportSummary = {
  status: 'pending',
  amount_cents: 1000,
  cadence: 'year',
  provider: 'buymeacoffee',
  email: 'hiker@example.com',
  chosen_at: '2026-10-23T12:00:00Z',
  started_at: null,
  stop_requested_at: null,
  ended_at: null,
}

function setup(over: Partial<Parameters<typeof SupportAsk>[0]> = {}) {
  const props = {
    days: 5,
    accountEmail: 'hiker@example.com',
    onSignIn: vi.fn(),
    onChosen: vi.fn(),
    onClose: vi.fn(),
    native: false,
    now: () => new Date('2026-10-23T12:00:00'),
    navigate: vi.fn(),
    choose: vi.fn().mockResolvedValue({
      support: PENDING,
      checkout_url: 'https://buymeacoffee.com/ourhike/membership',
      emailed: false,
    }),
    ...over,
  }
  render(<SupportAsk {...props} />)
  return props
}

beforeEach(() => localStorage.clear())
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the day-5 ask', () => {
  it('offers $1, $10 and $100 a year and $0, and says any of them keeps everything working', () => {
    setup()
    for (const name of [/^\$1 a year/, /^\$10 a year/, /^\$100 a year/, /^\$0/]) {
      expect(screen.getByRole('radio', { name })).toBeInTheDocument()
    }
    expect(
      screen.getByText(/Any choice, including \$0, keeps everything working/),
    ).toBeInTheDocument()
  })

  it('has no way to skip it, but $0 then "keep it" closes it in two taps and remembers the year', async () => {
    const props = setup()
    expect(
      screen.queryByRole('button', { name: /not now|skip|close/i }),
    ).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('radio', { name: /^\$0/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await userEvent.click(screen.getByRole('button', { name: /keep it at \$0/i }))

    expect(props.onClose).toHaveBeenCalled()
    expect(readLocalChoice()).toMatchObject({ year: 2026 })
    expect(props.choose).not.toHaveBeenCalled()
  })

  it('shows the $0 nudge with paid buttons above a readable "keep it at $0"', async () => {
    setup()
    await userEvent.click(screen.getByRole('radio', { name: /^\$0/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))

    const buttons = screen
      .getAllByRole('button')
      .map((button) => button.textContent ?? '')
    const one = buttons.findIndex((label) => label.includes('$1 a year'))
    const zero = buttons.findIndex((label) => /keep it at \$0/i.test(label))
    expect(one).toBeGreaterThanOrEqual(0)
    expect(zero).toBeGreaterThan(one)
  })

  it('sends the website app on to the checkout the backend names, asking for a redirect', async () => {
    const props = setup()
    await userEvent.click(screen.getByRole('radio', { name: /^\$10 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await userEvent.click(screen.getByRole('checkbox', { name: /yearly accounting/ }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Continue to Buy Me a Coffee' }),
    )

    expect(props.choose).toHaveBeenCalledWith({
      amount_cents: 1000,
      accounting_email: true,
      delivery: 'redirect',
    })
    expect(props.onChosen).toHaveBeenCalledWith(PENDING)
    expect(props.navigate).toHaveBeenCalledWith(
      'https://buymeacoffee.com/ourhike/membership',
    )
  })

  it('in the store apps, never names a checkout: the setup link goes by email', async () => {
    const props = setup({
      native: true,
      choose: vi
        .fn()
        .mockResolvedValue({ support: PENDING, checkout_url: null, emailed: true }),
    })
    expect(screen.queryByText(/Buy Me a Coffee/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('radio', { name: /^\$100 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.queryByText(/Buy Me a Coffee/)).not.toBeInTheDocument()
    await userEvent.click(
      screen.getByRole('button', { name: 'Email me how to set it up' }),
    )

    expect(props.choose).toHaveBeenCalledWith(
      expect.objectContaining({ delivery: 'email' }),
    )
    expect(props.navigate).not.toHaveBeenCalled()
    expect(
      await screen.findByRole('heading', { name: 'Check your email' }),
    ).toBeInTheDocument()
  })

  it('asks a signed-out hiker to sign in with the tier in hand, and sends nothing', async () => {
    const props = setup({ accountEmail: null })
    await userEvent.click(screen.getByRole('radio', { name: /^\$10 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await userEvent.click(screen.getByRole('button', { name: 'Sign in to continue' }))

    expect(props.onSignIn).toHaveBeenCalledWith(1000)
    expect(props.choose).not.toHaveBeenCalled()
  })

  it('says nothing was charged when the choice does not reach the server', async () => {
    setup({ choose: vi.fn().mockRejectedValue(new Error('offline')) })
    await userEvent.click(screen.getByRole('radio', { name: /^\$1 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Continue to Buy Me a Coffee' }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(/nothing was charged/)
  })
})
