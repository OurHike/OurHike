import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'
import { appHarness } from './test/appHarness'
import { ACTIVE_DAYS_KEY, localDate } from './lib/activeDays'
import type { SupportSummary } from './lib/api'

// The day-5 ask, end to end, on a launch whose stored session is slow to
// come back (the fourth #1885 review). App.tsx hands SupportGate
// `account?.email ?? null`, and lib/useAuth.ts starts that at null and only
// fills it once supabase-js's getSession() resolves - which, for a stored
// session whose access token has expired (any launch more than an hour after
// the last, so every new day), waits on a network refresh
// (@supabase/auth-js 2.115.0, GoTrueClient._recoverAndRefresh). The gate used
// to decide the moment `useSupport(false)` reported settled - as a signed-out
// hiker, before the account was known - and asked a $60-a-year supporter.
//
// The account here arrives `RESTORE_MS` after launch, well inside
// ASK_WINDOW_MS.

const SUPPORTING: SupportSummary = {
  status: 'active',
  amount_cents: 6000,
  cadence: 'year',
  provider: 'stripe',
  provider_label: 'Stripe',
  email: 'hiker@example.org',
  chosen_at: '2026-01-20T12:00:00Z',
  started_at: '2026-01-21T12:00:00Z',
  period_end: '2027-01-21T12:00:00Z',
  stop_requested_at: null,
  ended_at: null,
  supporting: true,
  can_stop: true,
  can_choose: false,
  support_emails: true,
}

const RESTORE_MS = 400
const timing = vi.hoisted(() => ({ restoreMs: 400 }))
const answer = vi.hoisted(() => ({ summary: null as unknown }))

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({
  readArchiveZooms: () => Promise.resolve(null),
  readArchiveFootprint: () => Promise.resolve(null),
}))
vi.mock('./lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/api')>()),
  API_CONFIGURED: true,
  accessToken: vi.fn(async () => 'a-real-token'),
  sendOutboxItem: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  fetchReports: vi.fn(async () => []),
  fetchClosures: vi.fn(async () => []),
  fetchFieldNotes: vi.fn(async () => []),
  fetchDisputes: vi.fn(async () => []),
  fetchMyProfile: vi.fn(async () => ({ id: 'p-1', role: 'hiker', display_name: null })),
  fetchMyVolunteerHours: vi.fn(async () => []),
}))
vi.mock('./lib/supportApi', () => ({
  fetchSupport: vi.fn(async () => answer.summary),
  chooseSupport: vi.fn(),
  stopSupport: vi.fn(),
  setSupportMail: vi.fn(),
  supportAccepting: vi.fn(async () => true),
}))
vi.mock('./lib/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/auth')>()),
  // A stored session that needs a token refresh before it is handed back.
  currentAccount: vi.fn(
    () =>
      new Promise((resolve) =>
        setTimeout(() => resolve({ email: 'hiker@example.org' }), timing.restoreMs),
      ),
  ),
  subscribeToAccount: (listener: (a: { email: string } | null) => void) => {
    const timer = setTimeout(
      () => listener({ email: 'hiker@example.org' }),
      timing.restoreMs,
    )
    return () => clearTimeout(timer)
  },
}))

const app = appHarness({ navigator: { onLine: true } })

beforeEach(() => {
  app.onboard()
  sessionStorage.clear()
  timing.restoreMs = RESTORE_MS
  answer.summary = SUPPORTING
  const yesterday = new Date(Date.now() - 86_400_000)
  // Four days counted this year, the last of them yesterday: today is day five.
  localStorage.setItem(
    ACTIVE_DAYS_KEY,
    JSON.stringify({
      year: new Date().getFullYear(),
      days: 4,
      last: localDate(yesterday),
    }),
  )
})

const NOT_CHOSEN = {
  ...SUPPORTING,
  status: 'none',
  amount_cents: null,
  supporting: false,
  can_stop: false,
  can_choose: true,
  started_at: null,
  chosen_at: null,
  period_end: null,
} satisfies SupportSummary

describe('the day-5 ask and a session still restoring at launch', () => {
  it('does not ask a supporter whose session is restored at once', async () => {
    timing.restoreMs = 0
    render(<App />)
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: 'More' })).toBeInTheDocument(),
    )
    await new Promise((resolve) => setTimeout(resolve, 1000))

    expect(
      screen.queryByRole('dialog', { name: 'Choose what you give' }),
    ).not.toBeInTheDocument()
  }, 20_000)

  it('does not ask a hiker who already pays $60 a year, once their account is in', async () => {
    render(<App />)
    // The account is in, and the gate's own fetch has the answer.
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: 'More' })).toBeInTheDocument(),
    )
    await new Promise((resolve) => setTimeout(resolve, RESTORE_MS + 1000))

    expect(
      screen.queryByRole('dialog', { name: 'Choose what you give' }),
    ).not.toBeInTheDocument()
  }, 20_000)

  it('back from a sign-in redirect with $60 picked, opens at the $60 confirmation, not at the top', async () => {
    answer.summary = NOT_CHOSEN
    sessionStorage.setItem(
      'ourhike:support-pending',
      JSON.stringify({ tier: 6000, at: Date.now() - 60_000 }),
    )
    render(<App />)

    expect(
      await screen.findByRole(
        'dialog',
        { name: 'Confirm your choice' },
        { timeout: RESTORE_MS + 3000 },
      ),
    ).toBeInTheDocument()
  }, 20_000)

  it('once the hiker goes back from that confirmation and keeps $0, the window stays closed', async () => {
    answer.summary = NOT_CHOSEN
    sessionStorage.setItem(
      'ourhike:support-pending',
      JSON.stringify({ tier: 6000, at: Date.now() - 60_000 }),
    )
    render(<App />)
    await screen.findByRole(
      'dialog',
      { name: 'Confirm your choice' },
      { timeout: RESTORE_MS + 3000 },
    )
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    fireEvent.click(await screen.findByRole('radio', { name: /^\$0/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    const keep = document.querySelector<HTMLButtonElement>('.support-nudge__zero')
    if (keep === null) throw new Error('no "Keep it at $0" button')
    fireEvent.click(keep)
    await new Promise((resolve) => setTimeout(resolve, 500))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  }, 20_000)
})
