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
