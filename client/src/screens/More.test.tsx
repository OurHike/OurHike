import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { More } from './More'
import { DEFAULT_PREFERENCES } from '../lib/userPreferences'

// The tab that owns reporting. Settings has its own tests; what is left here is
// the contribute section on top of it, and the outbox count in particular -
// that number is the only thing telling someone with no signal that their
// report still exists.

const PROPS = {
  account: null as { email: string } | null,
  reporterType: 'thru' as const,
  onSignIn: vi.fn(),
  onSignOut: vi.fn(),
  preferences: DEFAULT_PREFERENCES,
  onChange: vi.fn(),
  lastSyncedAt: null,
  onSync: vi.fn(),
  onExport: vi.fn(),
  onStartReport: vi.fn(),
  queuedReportCount: 0,
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('More', () => {
  it('offers the way into reporting', async () => {
    const user = userEvent.setup()
    render(<More {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /report a problem/i }))

    expect(PROPS.onStartReport).toHaveBeenCalledTimes(1)
  })

  it('says nothing about an outbox that is empty', () => {
    render(<More {...PROPS} />)

    expect(screen.queryByRole('status')).toBe(null)
  })

  it('counts a single waiting report in the singular', () => {
    render(<More {...PROPS} queuedReportCount={1} />)

    expect(screen.getByRole('status')).toHaveTextContent('1 report waiting to send.')
  })

  it('counts several in the plural', () => {
    render(<More {...PROPS} queuedReportCount={3} />)

    expect(screen.getByRole('status')).toHaveTextContent('3 reports waiting to send.')
  })

  it('still renders the settings underneath it', () => {
    render(<More {...PROPS} />)

    expect(screen.getByRole('heading', { name: 'You' })).toBeInTheDocument()
  })
})

// --- A report that will never send (#243) --------------------------------
//
// "Waiting to send" is true right up until it is not, and a phone with a
// wrong clock has every report refused - so without this the app tells
// someone their report is on its way, indefinitely, while it never moves.

const STUCK = [
  {
    id: 'r1',
    reason: 'The server would not accept it. Check your phone’s date and time.',
  },
]

describe('More, when a report was refused for good', () => {
  it('says so, in words, rather than leaving it in the waiting count', () => {
    render(<More {...PROPS} stuckReports={STUCK} />)

    expect(screen.getByRole('alert')).toHaveTextContent('1 report could not be sent.')
  })

  it('shows the reason, because "failed" alone is not actionable', () => {
    render(<More {...PROPS} stuckReports={STUCK} />)

    expect(screen.getByRole('alert')).toHaveTextContent(/date and time/i)
  })

  it('promises the writing is not lost, which is the fear this creates', () => {
    render(<More {...PROPS} stuckReports={STUCK} />)

    expect(screen.getByRole('alert')).toHaveTextContent(/nothing has been lost/i)
  })

  it('keeps the two counts apart', () => {
    // One waiting for signal, one refused. Rolling them together is the bug.
    render(<More {...PROPS} queuedReportCount={1} stuckReports={STUCK} />)

    expect(screen.getByRole('status')).toHaveTextContent('1 report waiting to send.')
    expect(screen.getByRole('alert')).toHaveTextContent('1 report could not be sent.')
  })

  it('pluralises', () => {
    render(<More {...PROPS} stuckReports={[...STUCK, { id: 'r2', reason: 'Nope.' }]} />)

    expect(screen.getByRole('alert')).toHaveTextContent('2 reports could not be sent.')
  })

  it('offers a retry, for the cause a hiker can actually fix', async () => {
    const user = userEvent.setup()
    const onRetryReport = vi.fn()
    render(<More {...PROPS} stuckReports={STUCK} onRetryReport={onRetryReport} />)

    await user.click(screen.getByRole('button', { name: /try again/i }))

    expect(onRetryReport).toHaveBeenCalledWith('r1')
  })

  it('offers a way out, so a doomed report is not permanent furniture', async () => {
    const user = userEvent.setup()
    const onDiscardReport = vi.fn()
    render(<More {...PROPS} stuckReports={STUCK} onDiscardReport={onDiscardReport} />)

    await user.click(screen.getByRole('button', { name: /delete/i }))

    expect(onDiscardReport).toHaveBeenCalledWith('r1')
  })

  it('says nothing when nothing is stuck', () => {
    render(<More {...PROPS} queuedReportCount={2} />)

    expect(screen.queryByRole('alert')).toBe(null)
  })
})
