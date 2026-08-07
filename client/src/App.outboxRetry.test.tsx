import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { get, set } from 'idb-keyval'
import App from './App'
import { PREFERENCES_KEY } from './lib/preferences'
import { DEFAULT_PREFERENCES } from './lib/userPreferences'
import { OUTBOX_KEY } from './lib/outbox'
import { sendReport } from './lib/api'

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
vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))
vi.mock('./map/archiveZooms', () => ({ readArchiveZooms: () => Promise.resolve(null) }))
vi.mock('./lib/api', () => ({
  API_CONFIGURED: true,
  accessToken: vi.fn(async () => 'a-real-token'),
  sendReport: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  // The map's own reads (#232). App fetches these whenever it is online with
  // a backend configured, which this file is; they are irrelevant to the
  // retry path but a mock missing them makes App throw on mount.
  fetchReports: vi.fn(async () => []),
  fetchClosures: vi.fn(async () => []),
  // The role read (#235). Same reason as the two above: App asks once per
  // sign-in, and a mock without it makes the whole screen throw on mount.
  fetchMyProfile: vi.fn(async () => ({ id: 'p-1', role: 'hiker', display_name: null })),
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

const mockedSend = vi.mocked(sendReport)
const store = new Map<string, unknown>()

const STUCK_ITEM = {
  id: 'r1',
  authoredAt: '2026-08-01T10:00:00.000Z',
  payload: { type: 'blowdown', reporter_type: 'thru', note: 'Tree down.' },
  failure: { reason: 'Its date is in the future.', at: '2026-08-01T10:00:05.000Z' },
}

beforeEach(() => {
  store.clear()
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
  store.set(PREFERENCES_KEY, {
    ...DEFAULT_PREFERENCES,
    onboarding_completed: true,
    download_choice_made: true,
  })
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

async function openMore(user: ReturnType<typeof userEvent.setup>) {
  render(<App />)
  await user.click(await screen.findByRole('tab', { name: 'More' }))
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
