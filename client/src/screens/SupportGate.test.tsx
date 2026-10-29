import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ACTIVE_DAYS_KEY } from '../lib/activeDays'
import type { SupportSummary } from '../lib/api'
import { holdPendingSupportTier } from '../lib/supportPending'
import type { SupportState } from '../lib/useSupport'

// When the day-5 ask opens (#1876, the third and fourth #1885 reviews): once
// per launch, on the count this launch reaches, near the start - never at
// or after the hiker's first tap, never because the signal came back, never
// before the stored session has been read, never for a signed-in hiker whose
// account could not be read, and never while the server takes no choice.

const mocks = vi.hoisted(() => ({ support: null as SupportState | null }))

vi.mock('../lib/useSupport', () => ({ useSupport: () => mocks.support }))
vi.mock('../lib/api', async (original) => ({
  ...(await original<typeof import('../lib/api')>()),
  API_CONFIGURED: true,
}))

const { ASK_WINDOW_MS, SupportGate } = await import('./SupportGate')

const TITLE = 'OurHike runs on what hikers choose to give'
const NOW = new Date('2026-07-20T09:00:00')

const NONE: SupportSummary = {
  status: 'none',
  amount_cents: null,
  cadence: null,
  provider: null,
  provider_label: null,
  email: null,
  chosen_at: null,
  started_at: null,
  period_end: null,
  stop_requested_at: null,
  ended_at: null,
  supporting: false,
  can_stop: false,
  can_choose: true,
  support_emails: true,
}

const PAYING: SupportSummary = {
  ...NONE,
  status: 'active',
  amount_cents: 6000,
  cadence: 'year',
  provider: 'stripe',
  provider_label: 'Stripe',
  email: 'hiker@example.com',
  supporting: true,
  can_stop: true,
  can_choose: false,
}

/** Lets the stored-session read and the `accepting` answer land. */
async function settle() {
  await act(async () => {
    await Promise.resolve()
  })
}

function support(over: Partial<SupportState> = {}): SupportState {
  return {
    server: null,
    local: null,
    settled: true,
    error: false,
    refresh: vi.fn(),
    replace: vi.fn(),
    ...over,
  }
}

/** Four days counted before today, so today is day five. */
function fourDaysBefore() {
  localStorage.setItem(
    ACTIVE_DAYS_KEY,
    JSON.stringify({ year: 2026, days: 4, last: '2026-07-14' }),
  )
}

function gate(over: Partial<Parameters<typeof SupportGate>[0]> = {}) {
  const props = {
    accountEmail: null,
    online: true,
    held: false,
    openRequest: 0,
    onSignIn: vi.fn(),
    onSummary: vi.fn(),
    usageCounts: true,
    storedAccount: vi.fn(async () => null),
    accepting: vi.fn(async () => true),
    ...over,
  }
  return { props, ...render(<SupportGate {...props} />) }
}

beforeEach(() => {
  localStorage.clear()
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(NOW)
  mocks.support = support()
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe('when the day-5 ask opens', () => {
  it('opens as the app comes up on day five, before any tap', async () => {
    fourDaysBefore()
    gate()

    expect(await screen.findByText(TITLE)).toBeInTheDocument()
  })

  it('does not open on day four, and the first tap of the day does not open it', async () => {
    localStorage.setItem(
      ACTIVE_DAYS_KEY,
      JSON.stringify({ year: 2026, days: 3, last: '2026-07-14' }),
    )
    gate()

    fireEvent.pointerDown(window)
    await settle()

    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()
  })

  it('does not open when the signal comes back later in the launch', async () => {
    fourDaysBefore()
    const { props, rerender } = gate({ online: false })
    await settle()

    rerender(<SupportGate {...props} online />)
    await settle()

    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()
  })

  it('does not open when the account answer arrives after the first moments of a launch', async () => {
    fourDaysBefore()
    mocks.support = support({ settled: false })
    const { props, rerender } = gate({ accountEmail: 'hiker@example.com' })
    await settle()

    vi.setSystemTime(NOW.getTime() + ASK_WINDOW_MS + 1)
    mocks.support = support({ settled: true, server: NONE })
    rerender(<SupportGate {...props} />)
    await settle()

    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()
  })

  it('does not ask a signed-in hiker whose account could not be read, who may already pay', async () => {
    fourDaysBefore()
    mocks.support = support({ server: null, error: true })
    gate({ accountEmail: 'hiker@example.com' })
    await settle()

    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()
  })

  it('asks a signed-in hiker whose account answers that nothing is chosen yet', async () => {
    fourDaysBefore()
    mocks.support = support({ server: NONE })
    gate({ accountEmail: 'hiker@example.com' })

    expect(await screen.findByText(TITLE)).toBeInTheDocument()
  })

  it('never opens in a store app on a non-US account, even when asked for', async () => {
    fourDaysBefore()
    const { props, rerender } = gate({ paidAllowed: false })
    await settle()

    act(() => rerender(<SupportGate {...props} openRequest={1} />))
    await settle()

    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()
  })

  it('waits for the store to answer, then opens on a US account', async () => {
    fourDaysBefore()
    const { props, rerender } = gate({ paidAllowed: null })
    await settle()
    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()

    rerender(<SupportGate {...props} paidAllowed />)

    expect(await screen.findByText(TITLE)).toBeInTheDocument()
  })

  it('still opens whenever the hiker asks for it from More → Your support', () => {
    const { props, rerender } = gate()
    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()

    act(() => rerender(<SupportGate {...props} openRequest={1} />))

    expect(screen.getByText(TITLE)).toBeInTheDocument()
  })
})

// The fourth #1885 review's probes, kept as the regressions for what each
// one found.
describe('what the day-5 ask waits for', () => {
  it('waits for the stored session, and does not ask a supporter whose session restores slowly', async () => {
    fourDaysBefore()
    let restore: (account: unknown) => void = () => {}
    const storedAccount = vi.fn(
      () => new Promise<unknown>((resolve) => (restore = resolve)),
    )
    const { props, rerender } = gate({ storedAccount })
    await settle()
    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()

    // App.tsx's account fills in once supabase-js hands the session back,
    // and the gate's fetch says this hiker pays $60 a year.
    await act(async () => restore({ email: 'hiker@example.com' }))
    mocks.support = support({ server: PAYING })
    rerender(<SupportGate {...props} accountEmail="hiker@example.com" />)
    await settle()

    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()
  })

  it('does not open once the hiker has started tapping, when the account answer is slow', async () => {
    fourDaysBefore()
    mocks.support = support({ settled: false })
    const { props, rerender } = gate({ accountEmail: 'hiker@example.com' })
    await settle()

    fireEvent.pointerDown(window)
    mocks.support = support({ server: NONE })
    rerender(<SupportGate {...props} />)
    await settle()

    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()
  })

  it('does not open for a tap that lands while the server is asked whether it takes a choice', async () => {
    fourDaysBefore()
    let answer: (yes: boolean) => void = () => {}
    gate({
      accepting: vi.fn(() => new Promise<boolean>((resolve) => (answer = resolve))),
    })
    await settle()

    fireEvent.pointerDown(window)
    await act(async () => answer(true))

    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()
  })

  it('does not ask a signed-in hiker when the server says no new choice would be taken', async () => {
    fourDaysBefore()
    mocks.support = support({ server: { ...NONE, can_choose: false } })
    gate({ accountEmail: 'hiker@example.com' })
    await settle()

    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()
  })

  it('does not ask a signed-out hiker while the server takes no paid choice', async () => {
    fourDaysBefore()
    const accepting = vi.fn(async () => false)
    gate({ accepting })
    await settle()

    expect(accepting).toHaveBeenCalledTimes(1)
    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()
  })
})

describe('a paid tier held across a sign-in', () => {
  it("opens at that tier's confirmation when the hiker comes back signed in", async () => {
    holdPendingSupportTier(6000, NOW.getTime())
    mocks.support = support({ server: NONE })
    gate({ accountEmail: 'hiker@example.com' })

    expect(
      await screen.findByRole('dialog', { name: 'Confirm your choice' }),
    ).toBeInTheDocument()
  })

  it('opens nothing when the account already pays', async () => {
    holdPendingSupportTier(6000, NOW.getTime())
    mocks.support = support({ server: PAYING })
    gate({ accountEmail: 'hiker@example.com' })
    await settle()

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('is let go once the hiker answers $0 from the top, so a later sign-in does not reopen it', async () => {
    fourDaysBefore()
    holdPendingSupportTier(6000, NOW.getTime())
    const { props, rerender } = gate()
    await screen.findByText(TITLE)

    fireEvent.click(screen.getByRole('radio', { name: /^\$0/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    const keep = document.querySelector<HTMLButtonElement>('.support-nudge__zero')
    if (keep === null) throw new Error('no "Keep it at $0" button')
    fireEvent.click(keep)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    mocks.support = support({ server: NONE })
    rerender(<SupportGate {...props} accountEmail="hiker@example.com" />)
    await settle()

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('counting days of use', () => {
  it('counts the next day the hiker uses an app that was never relaunched', async () => {
    localStorage.setItem(
      ACTIVE_DAYS_KEY,
      JSON.stringify({ year: 2026, days: 1, last: '2026-07-19' }),
    )
    gate()
    await settle()
    fireEvent.pointerDown(window) // July 20: day two
    fireEvent.pointerDown(window) // the same day again: still two

    // The phone keeps the app in memory overnight, and the hiker opens it
    // on the trail the next morning.
    vi.setSystemTime(new Date('2026-07-21T07:00:00'))
    fireEvent.pointerDown(window)

    expect(JSON.parse(localStorage.getItem(ACTIVE_DAYS_KEY) ?? '{}').days).toBe(3)
  })
})
