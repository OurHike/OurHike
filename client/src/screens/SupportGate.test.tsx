import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ACTIVE_DAYS_KEY } from '../lib/activeDays'
import type { SupportState } from '../lib/useSupport'

// When the day-5 ask opens (#1876, the third #1885 review): once per
// launch, on the count this launch reaches, near the start - never at the
// hiker's first tap, never because the signal came back, and never for a
// signed-in hiker whose account could not be read.

const mocks = vi.hoisted(() => ({ support: null as SupportState | null }))

vi.mock('../lib/useSupport', () => ({ useSupport: () => mocks.support }))
vi.mock('../lib/api', async (original) => ({
  ...(await original<typeof import('../lib/api')>()),
  API_CONFIGURED: true,
}))

const { ASK_WINDOW_MS, SupportGate } = await import('./SupportGate')

const TITLE = 'OurHike runs on what hikers choose to give'
const NOW = new Date('2026-07-20T09:00:00')

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
  it('opens as the app comes up on day five, before any tap', () => {
    fourDaysBefore()
    gate()

    expect(screen.getByText(TITLE)).toBeInTheDocument()
  })

  it('does not open on day four, and the first tap of the day does not open it', () => {
    localStorage.setItem(
      ACTIVE_DAYS_KEY,
      JSON.stringify({ year: 2026, days: 3, last: '2026-07-14' }),
    )
    gate()

    fireEvent.pointerDown(window)

    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()
  })

  it('does not open when the signal comes back later in the launch', () => {
    fourDaysBefore()
    const { props, rerender } = gate({ online: false })

    rerender(<SupportGate {...props} online />)

    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()
  })

  it('does not open when the account answer arrives after the first moments of a launch', () => {
    fourDaysBefore()
    mocks.support = support({ settled: false })
    const { props, rerender } = gate({ accountEmail: 'hiker@example.com' })

    vi.setSystemTime(NOW.getTime() + ASK_WINDOW_MS + 1)
    mocks.support = support({ settled: true })
    rerender(<SupportGate {...props} />)

    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()
  })

  it('does not ask a signed-in hiker whose account could not be read, who may already pay', () => {
    fourDaysBefore()
    mocks.support = support({ server: null, error: true })
    gate({ accountEmail: 'hiker@example.com' })

    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()
  })

  it('still opens whenever the hiker asks for it from More → Your support', () => {
    const { props, rerender } = gate()
    expect(screen.queryByText(TITLE)).not.toBeInTheDocument()

    act(() => rerender(<SupportGate {...props} openRequest={1} />))

    expect(screen.getByText(TITLE)).toBeInTheDocument()
  })
})
