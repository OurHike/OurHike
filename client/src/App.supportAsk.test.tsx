import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'
import { appHarness } from './test/appHarness'
import { ACTIVE_DAYS_KEY, localDate } from './lib/activeDays'
import { currentAccount } from './lib/auth'
import { fetchSupport, supportAccepting } from './lib/supportApi'
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
// THE SLOW RESTORE IS A PROMISE THE TEST RELEASES, not a timer. It stood in
// here as a real 400 ms setTimeout, followed by a second-and-a-half sleep and
// an assertion that no window had opened - TESTING.md's worst shape, which
// passes on the broken gate exactly as readily as on the fixed one when the
// runner is loaded. Now the stored session (`restore`) and the account's
// support answer (`answer`) each land when the test says so, after the
// observable that proves the gate is up and waiting: its own read of the
// stored session (the second `currentAccount` call this launch, after
// lib/useAuth.ts's), and its fetch of the answer. Releasing inside `act`
// flushes every render and effect that landing causes before the next line
// runs, so "no window" after it is a statement about a sequence that has
// finished. The clock is set too (TESTING.md's first rule): `ASK_WINDOW_MS`
// is measured from the gate's mount on it, and day five is counted on it.

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

const NOW = new Date('2026-07-20T09:00:00Z')

/** A value handed over when the test says, as lib/deferredScreen.test.tsx's
 *  held load is. Hoisted because the mocks below close over it. */
const held = vi.hoisted(() => {
  function held<T>() {
    let settle: (value: T) => void = () => {}
    let promise = new Promise<T>((resolve) => {
      settle = resolve
    })
    return {
      read: () => promise,
      release: (value: T) => settle(value),
      reset: () => {
        promise = new Promise<T>((resolve) => {
          settle = resolve
        })
      },
    }
  }
  return {
    /** The stored session, as lib/auth.ts hands it back. */
    restore: held<{ email: string } | null>(),
    /** The account's support, as GET /support/me answers. */
    answer: held<unknown>(),
  }
})
const { restore, answer } = held
const ACCOUNT = { email: 'hiker@example.org' }

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
  fetchSupport: vi.fn(() => answer.read()),
  chooseSupport: vi.fn(),
  stopSupport: vi.fn(),
  setSupportMail: vi.fn(),
  supportAccepting: vi.fn(async () => true),
}))
vi.mock('./lib/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/auth')>()),
  // A stored session that needs a token refresh before it is handed back.
  currentAccount: vi.fn(() => restore.read()),
  subscribeToAccount: (listener: (a: { email: string } | null) => void) => {
    let live = true
    void restore.read().then((account) => {
      if (live) listener(account)
    })
    return () => {
      live = false
    }
  },
}))

const app = appHarness({ navigator: { onLine: true } })

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(NOW)
  app.onboard()
  sessionStorage.clear()
  restore.reset()
  answer.reset()
  const yesterday = new Date(NOW.getTime() - 86_400_000)
  // Four days counted this year, the last of them yesterday: today is day five.
  localStorage.setItem(
    ACTIVE_DAYS_KEY,
    JSON.stringify({
      year: NOW.getFullYear(),
      days: 4,
      last: localDate(yesterday),
    }),
  )
})
afterEach(() => {
  vi.useRealTimers()
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

const ASK = { name: 'Choose what you give' }

/** The gate is up: it has read the stored session for itself, the second
 *  read this launch after lib/useAuth.ts's. Before the fourth #1885 review's
 *  fix it had decided by now, as a signed-out hiker. A count, not a signal:
 *  a third launch-time caller of currentAccount in App.tsx would make this
 *  resolve before the gate has read, and the slow-restore tests below would
 *  then release the restore too early and pass without proving anything -
 *  the premise breaks, not the pass. If one is added, wait on the gate's own
 *  read instead. */
async function gateUp() {
  await waitFor(() => expect(currentAccount).toHaveBeenCalledTimes(2))
}

/** The account's answer, handed to a gate that has asked for it. */
async function answerWith(summary: SupportSummary) {
  await waitFor(() => expect(fetchSupport).toHaveBeenCalled())
  await act(async () => {
    answer.release(summary)
  })
}

/** The More row's second line, lib/support.ts's `supportSummaryLine`: what
 *  the gate reports once an answer has reached it. */
async function moreRowReads(line: string) {
  fireEvent.click(screen.getByRole('tab', { name: 'More' }))
  expect(await screen.findByText(line)).toBeInTheDocument()
}

describe('the day-5 ask and a session still restoring at launch', () => {
  it('does not ask a supporter whose session is restored at once', async () => {
    restore.release(ACCOUNT)
    render(<App />)
    await screen.findByRole('tab', { name: 'More' })

    await answerWith(SUPPORTING)

    await moreRowReads('$60 a year')
    expect(screen.queryByRole('dialog', ASK)).not.toBeInTheDocument()
    expect(supportAccepting).not.toHaveBeenCalled()
  })

  it('does not ask a hiker who already pays $60 a year, once their account is in', async () => {
    render(<App />)
    await screen.findByRole('tab', { name: 'More' })
    await gateUp()

    await act(async () => {
      restore.release(ACCOUNT)
    })
    await answerWith(SUPPORTING)

    await moreRowReads('$60 a year')
    expect(screen.queryByRole('dialog', ASK)).not.toBeInTheDocument()
    // Nor was the server asked whether it takes a choice from nobody, which
    // is the signed-out path the gate used to take before the account was in.
    expect(supportAccepting).not.toHaveBeenCalled()
  })

  it('back from a sign-in redirect with $60 picked, opens at the $60 confirmation, not at the top', async () => {
    sessionStorage.setItem(
      'ourhike:support-pending',
      JSON.stringify({ tier: 6000, at: NOW.getTime() - 60_000 }),
    )
    render(<App />)
    await screen.findByRole('tab', { name: 'More' })
    await gateUp()

    await act(async () => {
      restore.release(ACCOUNT)
    })
    await answerWith(NOT_CHOSEN)

    expect(
      await screen.findByRole('dialog', { name: 'Confirm your choice' }),
    ).toBeInTheDocument()
  })

  it('once the hiker goes back from that confirmation and keeps $0, the window stays closed', async () => {
    sessionStorage.setItem(
      'ourhike:support-pending',
      JSON.stringify({ tier: 6000, at: NOW.getTime() - 60_000 }),
    )
    render(<App />)
    await screen.findByRole('tab', { name: 'More' })
    await gateUp()
    await act(async () => {
      restore.release(ACCOUNT)
    })
    await answerWith(NOT_CHOSEN)
    await screen.findByRole('dialog', { name: 'Confirm your choice' })

    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    fireEvent.click(await screen.findByRole('radio', { name: /^\$0/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    const keep = document.querySelector<HTMLButtonElement>('.support-nudge__zero')
    if (keep === null) throw new Error('no "Keep it at $0" button')
    fireEvent.click(keep)

    // The $0 has reached the gate - the same commit whose effects decide
    // whether to open again - and the More row says so.
    await moreRowReads('$0 this year')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
