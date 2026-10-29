import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { SupportSummary } from '../lib/api'

// The More row and the Your support page each hold a `useSupport`. A Stop on
// the page used to replace the page's answer only, so the row kept reading
// "$60 a year" until the window next gained focus (the fourth #1885 review).
// Both are real here; only the network is not.

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

const STOPPING: SupportSummary = {
  ...ACTIVE,
  status: 'stop_requested',
  stop_requested_at: '2026-10-23T12:00:00Z',
  supporting: false,
  can_stop: false,
  can_choose: true,
}

vi.mock('../lib/api', async (original) => ({
  ...(await original<typeof import('../lib/api')>()),
  API_CONFIGURED: true,
}))
vi.mock('../lib/supportApi', () => ({
  fetchSupport: vi.fn(async () => ACTIVE),
  chooseSupport: vi.fn(),
  stopSupport: vi.fn(async () => STOPPING),
  setSupportMail: vi.fn(),
  supportAccepting: vi.fn(async () => true),
}))

const { SupportGate, YourSupportPage } = await import('./SupportGate')

beforeEach(() => localStorage.clear())
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the More row after a Stop on Your support', () => {
  it('reads "Stopping" once the hiker has stopped, without waiting for focus', async () => {
    const onSummary = vi.fn()
    render(
      <>
        <SupportGate
          accountEmail="hiker@example.com"
          online
          held={false}
          openRequest={0}
          onSignIn={vi.fn()}
          onSummary={onSummary}
          usageCounts
          storedAccount={async () => ({ email: 'hiker@example.com' })}
        />
        <YourSupportPage apiConfigured signedIn onSignIn={vi.fn()} onChoose={vi.fn()} />
      </>,
    )
    await waitFor(() => expect(onSummary).toHaveBeenLastCalledWith('$60 a year'))
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Stop my support' }))
    await user.click(screen.getByRole('button', { name: 'Yes, stop it' }))
    await screen.findByText('Stop requested')

    expect(onSummary).toHaveBeenLastCalledWith('Stopping')
  })
})
