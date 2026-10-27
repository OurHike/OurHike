import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { YourSupport } from './YourSupport'
import { supportSummaryLine } from '../lib/support'
import type { SupportSummary } from '../lib/support'

// More → Your support (#1876): Stop is one tap and one confirm, asks no
// reason, and does not claim a cancellation that has not happened yet.

const ACTIVE: SupportSummary = {
  status: 'active',
  amount_cents: 6000,
  cadence: 'year',
  provider: 'stripe',
  provider_label: 'Stripe',
  email: 'hiker@example.com',
  chosen_at: '2026-10-20T12:00:00Z',
  started_at: '2026-10-21T12:00:00Z',
  period_end: '2027-10-21T12:00:00Z',
  stop_requested_at: null,
  ended_at: null,
  supporting: true,
  can_stop: true,
  can_choose: false,
  support_emails: true,
}

const NOW = new Date('2026-10-23T12:00:00')

function setup(over: Partial<Parameters<typeof YourSupport>[0]> = {}) {
  const props = {
    apiConfigured: true,
    signedIn: true,
    server: ACTIVE,
    local: null,
    error: false,
    now: NOW,
    onSignIn: vi.fn(),
    onChoose: vi.fn(),
    onStopped: vi.fn(),
    native: false,
    stop: vi.fn().mockResolvedValue({
      ...ACTIVE,
      status: 'stop_requested',
      stop_requested_at: '2026-10-23T12:00:00Z',
      can_stop: false,
      can_choose: true,
    }),
    ...over,
  }
  render(<YourSupport {...props} />)
  return props
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Your support', () => {
  it('stops in one tap and one confirm, with no reason asked', async () => {
    const props = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Stop my support' }))
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Yes, stop it' }))

    expect(props.stop).toHaveBeenCalledTimes(1)
    expect(props.onStopped).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'stop_requested' }),
    )
  })

  it('says a requested stop is cancelled for the hiker, rather than claiming it already is', () => {
    setup({
      server: {
        ...ACTIVE,
        status: 'stop_requested',
        stop_requested_at: '2026-10-23T12:00:00Z',
        can_stop: false,
      },
    })
    expect(screen.getByText(/cancelling it for you/)).toBeInTheDocument()
    expect(screen.queryByText(/cancelled it/)).not.toBeInTheDocument()
  })

  it('says a failed renewal plainly, and still offers Stop', () => {
    setup({ server: { ...ACTIVE, status: 'payment_failed' } })

    expect(screen.getByText(/Payment didn.t go through/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Stop my support' })).toBeInTheDocument()
    expect(supportSummaryLine({ ...ACTIVE, status: 'payment_failed' }, null, NOW)).toBe(
      "$60 a year, payment didn't go through",
    )
  })

  it('offers a different amount beside Stop when the server would take one', async () => {
    const props = setup({
      server: {
        ...ACTIVE,
        status: 'pending',
        started_at: null,
        supporting: false,
        can_choose: true,
      },
    })

    await userEvent.click(
      screen.getByRole('button', { name: 'Choose a different amount' }),
    )

    expect(props.onChoose).toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Stop my support' })).toBeInTheDocument()
  })

  it('turns emails about support off with a switch, and says what the server answered', async () => {
    const answered = { ...ACTIVE, support_emails: false }
    const setMail = vi.fn().mockResolvedValue(answered)
    const props = setup({ setMail, onMailChanged: vi.fn() })
    const toggle = screen.getByRole('switch', { name: 'Emails about my support' })
    expect(toggle).toHaveAttribute('aria-checked', 'true')

    await userEvent.click(toggle)

    expect(setMail).toHaveBeenCalledWith(false)
    expect(props.onMailChanged).toHaveBeenCalledWith(answered)
  })

  it('offers no paid choice in a store app on a non-US account, but still offers Stop', () => {
    setup({ paidAllowed: false, server: { ...ACTIVE, can_choose: true } })
    expect(screen.getByRole('button', { name: 'Stop my support' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Choose/ })).not.toBeInTheDocument()
    cleanup()

    setup({ paidAllowed: false, server: null })
    expect(screen.getByText(/\$0 is the only answer in this app/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Choose/ })).not.toBeInTheDocument()
  })

  it('shows no email switch with no support to hang it on', () => {
    setup({ server: { ...ACTIVE, status: 'none', amount_cents: null } })
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
  })

  it('offers Stop only when the server says it would do something', () => {
    setup({ server: { ...ACTIVE, status: 'cancel_scheduled', can_stop: false } })
    expect(
      screen.queryByRole('button', { name: 'Stop my support' }),
    ).not.toBeInTheDocument()
    expect(screen.getByText(/No more charges · ends Oct 21, 2027/)).toBeInTheDocument()
  })

  it('names the payment provider on the website and never in the store apps', () => {
    setup()
    expect(screen.getByText(/via Stripe/)).toBeInTheDocument()
    cleanup()
    setup({ native: true })
    expect(screen.queryByText(/Stripe/)).not.toBeInTheDocument()
  })

  it('says a cleared choice that was never paid needed no cancelling', () => {
    setup({
      server: {
        ...ACTIVE,
        status: 'stopped',
        started_at: null,
        ended_at: '2026-10-23T12:00:00Z',
        supporting: false,
        can_stop: false,
        can_choose: true,
      },
    })
    expect(
      screen.getByText(/Nothing was paid, so nothing needed cancelling/),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Choose an amount again' }),
    ).toBeInTheDocument()
  })

  it('treats $0 as a real answer and offers a paid amount without pressing it', () => {
    setup({
      server: null,
      signedIn: false,
      local: { year: 2026, chosenAt: '2026-06-01T12:00:00Z' },
    })
    expect(screen.getByText(/You chose \$0 for 2026/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Choose an amount' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Already supporting? Sign in' }),
    ).toBeInTheDocument()
  })

  it('keeps the ideals page link out of the store apps', () => {
    setup({ native: true })
    expect(
      screen.queryByRole('link', { name: /pay-what-you-want/ }),
    ).not.toBeInTheDocument()
  })

  it('says support is not switched on in a build with no backend', () => {
    setup({ apiConfigured: false, server: null })
    expect(screen.getByText(/isn.t switched on in this build/)).toBeInTheDocument()
  })
})

describe('the More row line', () => {
  it('names the amount, its state, or that $0 is an answer', () => {
    expect(supportSummaryLine(ACTIVE, null, NOW)).toBe('$60 a year')
    expect(supportSummaryLine({ ...ACTIVE, status: 'pending' }, null, NOW)).toBe(
      '$60 a year, waiting to be confirmed',
    )
    expect(supportSummaryLine({ ...ACTIVE, status: 'paused' }, null, NOW)).toBe(
      '$60 a year, paused',
    )
    expect(supportSummaryLine({ ...ACTIVE, status: 'cancel_scheduled' }, null, NOW)).toBe(
      '$60 a year, ending',
    )
    expect(supportSummaryLine(null, { year: 2026, chosenAt: '' }, NOW)).toBe(
      '$0 this year',
    )
    expect(supportSummaryLine(null, null, NOW)).toBe('Pay what you want, $0 included')
  })
})
