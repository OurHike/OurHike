import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SupportAsk } from './SupportAsk'
import { ApiError } from '../lib/api'
import {
  LOCAL_CHOICE_KEY,
  readLocalChoice,
  writeZeroChoice,
  type SupportSummary,
} from '../lib/support'
import { ZERO_CHOSEN } from '../lib/supportZeroChosen'

// The day-5 ask (#1876). A choice is required, $0 is a choice, and payment
// never happens inside the app: the website app is sent on to the provider's
// https page, the store apps get the link by email, and neither names the
// provider.

const PENDING: SupportSummary = {
  status: 'pending',
  amount_cents: 6000,
  cadence: 'year',
  provider: 'stripe',
  provider_label: 'Stripe',
  email: 'hiker@example.com',
  chosen_at: '2026-10-23T12:00:00Z',
  started_at: null,
  period_end: null,
  stop_requested_at: null,
  ended_at: null,
  supporting: false,
  can_stop: true,
  can_choose: true,
  support_emails: true,
}

function setup(over: Partial<Parameters<typeof SupportAsk>[0]> = {}) {
  const props = {
    days: 5,
    accountEmail: 'hiker@example.com',
    onSignIn: vi.fn(),
    onChosen: vi.fn(),
    onClose: vi.fn(),
    usageCounts: true,
    native: false,
    now: () => new Date('2026-10-23T12:00:00'),
    navigate: vi.fn(),
    choose: vi.fn().mockResolvedValue({
      support: PENDING,
      checkout_url: 'https://buy.stripe.com/test_ten?client_reference_id=choice-1',
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
  it('moves the choice with the arrow keys and keeps one tier in the tab order', async () => {
    setup()
    await userEvent.click(screen.getByRole('radio', { name: /^\$12 a year/ }))

    await userEvent.keyboard('{ArrowDown}')

    const sixty = screen.getByRole('radio', { name: /^\$60 a year/ })
    expect(sixty).toHaveAttribute('aria-checked', 'true')
    expect(sixty).toHaveFocus()
    expect(screen.getAllByRole('radio').filter((radio) => radio.tabIndex === 0)).toEqual([
      sixty,
    ])

    await userEvent.keyboard('{ArrowUp}{ArrowUp}')
    expect(screen.getByRole('radio', { name: /^\$0/ })).toHaveAttribute(
      'aria-checked',
      'true',
    )
  })

  it('offers $12, $60 and $120 a year and $0, and says any of them keeps everything working', () => {
    setup()
    for (const name of [/^\$12 a year/, /^\$60 a year/, /^\$120 a year/, /^\$0/]) {
      expect(screen.getByRole('radio', { name })).toBeInTheDocument()
    }
    expect(
      screen.getByText(/Any choice, including \$0, keeps everything working/),
    ).toBeInTheDocument()
  })

  it('has no way to skip it, but $0, Continue and "keep it" close it in three taps and remember the year', async () => {
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
    const one = buttons.findIndex((label) => label.includes('$12 a year'))
    const zero = buttons.findIndex((label) => /keep it at \$0/i.test(label))
    expect(one).toBeGreaterThanOrEqual(0)
    expect(zero).toBeGreaterThan(one)
  })

  it('sends the website app on to the checkout the backend names, asking for a redirect', async () => {
    const props = setup()
    await userEvent.click(screen.getByRole('radio', { name: /^\$60 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    // The yearly accounting email is hidden until something sends it.
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Continue to payment' }))

    expect(props.choose).toHaveBeenCalledWith({
      amount_cents: 6000,
      accounting_email: false,
      delivery: 'redirect',
      usage_counts: true,
    })
    expect(props.onChosen).toHaveBeenCalledWith(PENDING)
    expect(props.navigate).toHaveBeenCalledWith(
      'https://buy.stripe.com/test_ten?client_reference_id=choice-1',
    )
  })

  it('closes before it leaves for the payment page, so Back finds the map and not a disabled button', async () => {
    const props = setup()
    await userEvent.click(screen.getByRole('radio', { name: /^\$60 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue to payment' }))

    expect(props.onClose).toHaveBeenCalledTimes(1)
    expect(vi.mocked(props.onClose).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(props.navigate).mock.invocationCallOrder[0],
    )
  })

  it('tells the backend not to count the level when "Share usage statistics" is off', async () => {
    const props = setup({ usageCounts: false })
    await userEvent.click(screen.getByRole('radio', { name: /^\$12 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue to payment' }))

    expect(props.choose).toHaveBeenCalledWith(
      expect.objectContaining({ usage_counts: false }),
    )
  })

  it('never sends the website app anywhere but an https page', async () => {
    const props = setup({
      choose: vi.fn().mockResolvedValue({
        support: PENDING,
        checkout_url: 'javascript:alert(1)',
        emailed: false,
      }),
    })
    await userEvent.click(screen.getByRole('radio', { name: /^\$60 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue to payment' }))

    expect(props.navigate).not.toHaveBeenCalled()
    expect(await screen.findByRole('alert')).toHaveTextContent(/nothing was charged/)
  })

  it('names no payment provider on the website either', async () => {
    setup()
    await userEvent.click(screen.getByRole('radio', { name: /^\$60 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.queryByText(/Stripe|Buy Me a Coffee/)).not.toBeInTheDocument()
  })

  it('in the store apps, never names a checkout: the setup link goes by email', async () => {
    const props = setup({
      native: true,
      choose: vi
        .fn()
        .mockResolvedValue({ support: PENDING, checkout_url: null, emailed: true }),
    })
    expect(screen.queryByText(/Stripe|Buy Me a Coffee/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('radio', { name: /^\$120 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.queryByText(/Stripe|Buy Me a Coffee/)).not.toBeInTheDocument()
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
    // This view shows only on a US store account, where both stores allow a
    // link: email is OurHike's choice, and the line says so (review 4).
    expect(screen.queryByText(/don.t allow/)).not.toBeInTheDocument()
    expect(screen.getByText(/never in this app/)).toBeInTheDocument()
  })

  it('asks a signed-out hiker to sign in with the tier in hand, and sends nothing', async () => {
    const props = setup({ accountEmail: null })
    await userEvent.click(screen.getByRole('radio', { name: /^\$60 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await userEvent.click(screen.getByRole('button', { name: 'Sign in to continue' }))

    expect(props.onSignIn).toHaveBeenCalledWith(6000)
    expect(props.choose).not.toHaveBeenCalled()
  })

  it('says nothing was charged when the choice does not reach the server', async () => {
    setup({ choose: vi.fn().mockRejectedValue(new Error('offline')) })
    await userEvent.click(screen.getByRole('radio', { name: /^\$12 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue to payment' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/nothing was charged/)
  })
})

// The fourth #1885 review's probes, kept as the regressions for what each
// one found.
describe('the day-5 ask, after the fourth review', () => {
  it('a second $0 in the same year closes with no second nudge and no second count', async () => {
    writeZeroChoice(new Date('2026-07-20T12:00:00'))
    const announced = vi.fn()
    window.addEventListener(ZERO_CHOSEN, announced)
    try {
      const props = setup()
      await userEvent.click(screen.getByRole('radio', { name: /^\$0/ }))
      await userEvent.click(screen.getByRole('button', { name: 'Continue' }))

      expect(
        screen.queryByRole('dialog', { name: 'Before you pick $0' }),
      ).not.toBeInTheDocument()
      expect(props.onClose).toHaveBeenCalledTimes(1)
      expect(announced).not.toHaveBeenCalled()
    } finally {
      window.removeEventListener(ZERO_CHOSEN, announced)
    }
  })

  it('still nudges, and counts, a $0 kept last year', async () => {
    writeZeroChoice(new Date('2025-07-20T12:00:00'))
    setup()
    await userEvent.click(screen.getByRole('radio', { name: /^\$0/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))

    expect(screen.getByRole('dialog', { name: 'Before you pick $0' })).toBeInTheDocument()
  })

  it('does not call it "Day five" on the nudge, whatever day it is', async () => {
    setup({ days: 9 })
    await userEvent.click(screen.getByRole('radio', { name: /^\$0/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))

    expect(screen.queryByText(/Day five/)).not.toBeInTheDocument()
  })

  it('keeps keyboard focus inside the window each time its view changes', async () => {
    setup()
    await userEvent.click(screen.getByRole('radio', { name: /^\$0/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByRole('dialog').contains(document.activeElement)).toBe(true)
    expect(document.activeElement).toHaveRole('heading')

    await userEvent.click(screen.getByRole('button', { name: /\$12 a year/ }))
    expect(screen.getByRole('dialog').contains(document.activeElement)).toBe(true)

    await userEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.getByRole('dialog').contains(document.activeElement)).toBe(true)
  })

  it('says support is not taking payments, not "check your signal", when the server answers 503', async () => {
    setup({
      choose: vi.fn().mockRejectedValue(
        new ApiError(503, 'PUT /support/me failed: 503', {
          detail: 'Support is not switched on here yet.',
        }),
      ),
    })
    await userEvent.click(screen.getByRole('radio', { name: /^\$60 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue to payment' }))

    const alert = await screen.findByRole('alert')
    expect(alert).not.toHaveTextContent(/Check your signal/)
    expect(alert).toHaveTextContent(/isn.t taking payments/)
    expect(alert).toHaveTextContent(/Nothing was charged/)
  })

  it('says the account already gives, and where to stop it, when the server answers 409', async () => {
    setup({
      choose: vi
        .fn()
        .mockRejectedValue(new ApiError(409, 'PUT /support/me failed: 409', {})),
    })
    await userEvent.click(screen.getByRole('radio', { name: /^\$60 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue to payment' }))

    const alert = await screen.findByRole('alert')
    expect(alert).not.toHaveTextContent(/Check your signal/)
    expect(alert).toHaveTextContent(/More → Your support/)
  })

  it('closes when $0 is kept in another tab, but not over a paid confirmation', async () => {
    const props = setup()
    await userEvent.click(screen.getByRole('radio', { name: /^\$60 a year/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    // Another tab's $0 reaches this one as a storage event.
    localStorage.setItem(
      LOCAL_CHOICE_KEY,
      JSON.stringify({ year: 2026, chosenAt: '2026-10-23T12:00:00.000Z' }),
    )
    act(() => {
      window.dispatchEvent(new StorageEvent('storage', { key: LOCAL_CHOICE_KEY }))
    })
    expect(props.onClose).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: 'Back' }))
    act(() => {
      window.dispatchEvent(new StorageEvent('storage', { key: LOCAL_CHOICE_KEY }))
    })
    expect(props.onClose).toHaveBeenCalledTimes(1)
  })
})
