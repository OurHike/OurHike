import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness } from './test/appHarness'
import { OUTBOX_KEY } from './lib/outbox'
import { UNDO_WINDOW_MS } from './reporting/ReportWindow'
import { sendOutboxItem } from './lib/api'
import { BUILD_INFO } from './lib/buildInfo'

// #266: "Try again" cleared the refusal and sent nothing.
//
// The only flush trigger is useOutboxSync's effect, whose deps are both
// referentially stable, and outboxSync is "deliberately not on a timer" - so
// on a steady connection nothing ran. Worse than doing nothing: refreshOutbox
// moved the report out of the stuck list, so the screen replaced "could not be
// sent" plus its reason with "waiting to send" at the exact moment nothing was
// going to try, and the affordance pointing at the problem disappeared.
//
// A separate file from App.test.tsx on purpose. Making this assertion needs
// lib/api mocked as CONFIGURED, and that would switch on real flush behaviour
// for every unrelated test in that file - which currently relies on
// API_CONFIGURED being false so syncOutbox returns before touching anything.

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({
  readArchiveZooms: () => Promise.resolve(null),
  readArchiveFootprint: () => Promise.resolve(null),
}))
vi.mock('./lib/api', () => ({
  API_CONFIGURED: true,
  accessToken: vi.fn(async () => 'a-real-token'),
  sendOutboxItem: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  // The map's own reads (#232). App fetches these whenever it is online with
  // a backend configured, which this file is; they are irrelevant to the
  // retry path but a mock missing them makes App throw on mount.
  fetchReports: vi.fn(async () => []),
  fetchClosures: vi.fn(async () => []),
  fetchFieldNotes: vi.fn(async () => []),
  // Disputes ride the same read as the notes they are computed from (#876).
  fetchDisputes: vi.fn(async () => []),
  // The role read (#235). Same reason as the two above: App asks once per
  // sign-in, and a mock without it makes the whole screen throw on mount.
  fetchMyProfile: vi.fn(async () => ({ id: 'p-1', role: 'hiker', display_name: null })),
  // Fetched when the volunteer page is looked at, which openMore now does on
  // its way to the stuck-report alert (#1054).
  fetchMyVolunteerHours: vi.fn(async () => []),
}))
vi.mock('./lib/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/auth')>()),
  // Signed in, because the flush is gated on having an account as well as a
  // connection. Subscribing is what App actually reads.
  currentAccount: vi.fn(async () => ({ email: 'hiker@example.org' })),
  subscribeToAccount: (listener: (a: { email: string } | null) => void) => {
    listener({ email: 'hiker@example.org' })
    return () => {}
  },
}))

const mockedSend = vi.mocked(sendOutboxItem)
const app = appHarness()
const store = app.store

// `build` is THIS build's commit, and that is what makes the item genuinely
// stuck for the purposes of this file (#412). A failure recorded by a
// different build - or by one too old to record any, which is what this
// fixture was before - gets one automatic retry on the next flush, so the
// report would send itself on mount and "Try again" would have nothing left
// to do. That behaviour has its own tests in lib/outbox.test.ts; what this
// file is about is the affordance for a report this build has given up on.
const STUCK_ITEM = {
  id: 'r1',
  authoredAt: '2026-08-01T10:00:00.000Z',
  payload: { type: 'blowdown', reporter_type: 'thru', note: 'Tree down.' },
  failure: {
    reason: 'Its date is in the future.',
    at: '2026-08-01T10:00:05.000Z',
    build: BUILD_INFO.commit,
  },
}

beforeEach(() => app.onboard())

async function openMore(user: ReturnType<typeof userEvent.setup>) {
  render(<App />)
  await user.click(await screen.findByRole('tab', { name: 'More' }))
  // The stuck-report alert lives on the volunteer page since More became
  // five destinations (#1054).
  await user.click(await screen.findByRole('button', { name: /^volunteer & report/i }))
}

describe('Try again, on a report the server refused', () => {
  it('actually sends it', async () => {
    store.set(OUTBOX_KEY, [STUCK_ITEM])
    const user = userEvent.setup()
    await openMore(user)

    // Positive control first: a stuck item must NOT be flushed on mount, or
    // the assertion below could pass on the mount flush rather than the tap.
    await screen.findByRole('alert')
    expect(mockedSend).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: /try again/i }))

    await waitFor(() => expect(mockedSend).toHaveBeenCalledTimes(1))
    expect(mockedSend.mock.calls[0][0].id).toBe('r1')
  })

  it('leaves the queue empty once the send goes through', async () => {
    store.set(OUTBOX_KEY, [STUCK_ITEM])
    const user = userEvent.setup()
    await openMore(user)
    await screen.findByRole('alert')

    await user.click(screen.getByRole('button', { name: /try again/i }))

    await waitFor(() => expect(store.get(OUTBOX_KEY)).toEqual([]))
  })

  it('stops claiming the report could not be sent', async () => {
    store.set(OUTBOX_KEY, [STUCK_ITEM])
    const user = userEvent.setup()
    await openMore(user)
    await screen.findByRole('alert')

    await user.click(screen.getByRole('button', { name: /try again/i }))

    await waitFor(() => expect(screen.queryByRole('alert')).toBe(null))
  })

  it('sends a freshly filed report once its undo window shuts', async () => {
    // #640, and #1133's near-miss with it. The original rule: enqueueing
    // changes neither of useOutboxSync's deps, so on a steady connection
    // nothing flushed and a freshly filed report sat as "waiting to send"
    // until the connection flapped. The submit handler's own flush is what
    // fixed it.
    //
    // The report window re-opened that hole in a way that would have been
    // very quiet. It files on the tap and HOLDS the report for the length of
    // the undo window; `Done` is right there, so a hiker closes in about two
    // seconds; so the flush on close drains everything EXCEPT the report they
    // just wrote. Nothing would then flush again until the connection
    // flapped - which is #640, word for word, on a new path.
    //
    // What closes it is FlushResult.held: a flush that reports a held item
    // schedules one more past the window. This test is that behaviour, and
    // it would pass without the follow-up if it only waited for the close.
    // `shouldAdvanceTime` so the clock still runs on its own: findBy* and
    // waitFor are built on real timers, and a frozen clock deadlocks them.
    // What the fake clock is for here is the one jump past the undo window,
    // which is otherwise an eight-second wait in the suite.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
      render(<App />)
      await screen.findByRole('tab', { name: 'More' })
      expect(mockedSend).not.toHaveBeenCalled()

      await user.click(screen.getByRole('tab', { name: 'More' }))
      await user.click(
        await screen.findByRole('button', { name: /^volunteer & report/i }),
      )
      await user.click(await screen.findByRole('button', { name: /report a problem/i }))
      await user.click(await screen.findByRole('button', { name: /blow down/i }))
      await user.click(screen.getByTestId('report-done'))

      // Held, so nothing has gone yet - which is the promise the Undo button
      // was making while it was on screen.
      expect(mockedSend).not.toHaveBeenCalled()

      await act(async () => {
        await vi.advanceTimersByTimeAsync(UNDO_WINDOW_MS + 1_000)
      })

      await waitFor(() => expect(mockedSend).toHaveBeenCalledTimes(1))
      expect(mockedSend.mock.calls[0][0].payload?.type).toBe('blowdown')
    } finally {
      vi.useRealTimers()
    }
  })

  it('does not claim the report is waiting when the send failed again', async () => {
    // The honesty case. A retry with no signal has to leave the report
    // readable as waiting - it genuinely is - but must not silently drop the
    // hiker's only route back to it.
    mockedSend.mockRejectedValueOnce(new Error('still no signal'))
    store.set(OUTBOX_KEY, [STUCK_ITEM])
    const user = userEvent.setup()
    await openMore(user)
    await screen.findByRole('alert')

    await user.click(screen.getByRole('button', { name: /try again/i }))

    await waitFor(() => expect(mockedSend).toHaveBeenCalled())
    // Still queued, not lost.
    await waitFor(() => expect((store.get(OUTBOX_KEY) as unknown[]).length).toBe(1))
    expect(screen.getByRole('status')).toHaveTextContent('1 report waiting to send.')
  })
})
