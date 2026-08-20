import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness } from './test/appHarness'
import { OUTBOX_KEY } from './lib/outbox'
import { sendOutboxItem } from './lib/api'

// #848, end to end: Settings → "It broke while I was out there" → the outbox
// → the send.
//
// **Signed out on purpose, which is the whole subject of this file.** Every
// other write in the app needs an account, and lib/outboxSync.ts used to
// decline to flush at all without one. A hiker whose app just failed on a
// ridge may never have signed in - browsing the map has never asked them to -
// so a report that waited for an account would be a report that never
// arrived. The unit tests hold each half of that; only rendering the real App
// proves the halves are joined.
//
// A separate file from App.test.tsx for the reason App.outboxRetry.test.tsx
// gives: this needs lib/api mocked as CONFIGURED, and that would switch on
// real flush behaviour for every unrelated test in that file.

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({ readArchiveZooms: () => Promise.resolve(null) }))
vi.mock('./lib/api', () => ({
  API_CONFIGURED: true,
  // Signed out. This is the condition the whole file is about.
  accessToken: vi.fn(async () => null),
  sendOutboxItem: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  // The map's own reads, irrelevant here and required for App to mount.
  fetchReports: vi.fn(async () => []),
  fetchClosures: vi.fn(async () => []),
  fetchMyProfile: vi.fn(async () => ({ id: 'p-1', role: 'hiker', display_name: null })),
}))
vi.mock('./lib/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/auth')>()),
  currentAccount: vi.fn(async () => null),
  subscribeToAccount: (listener: (a: { email: string } | null) => void) => {
    listener(null)
    return () => {}
  },
}))

const mockedSend = vi.mocked(sendOutboxItem)
const app = appHarness()
const store = app.store

beforeEach(() => app.onboard())

/** Settings → the About tab → the app-failure form, as a hiker reaches it. */
async function openTheForm(user: ReturnType<typeof userEvent.setup>) {
  render(<App />)
  await user.click(await screen.findByRole('tab', { name: 'Settings' }))
  await user.click(await screen.findByRole('tab', { name: 'About' }))
  await user.click(
    await screen.findByRole('button', { name: /broke while I was out there/i }),
  )
}

describe('reporting that the app failed on the trail, signed out', () => {
  it('reaches the form from Settings without an account', async () => {
    const user = userEvent.setup()

    await openTheForm(user)

    expect(
      await screen.findByRole('heading', { name: /broke while I was out there/i }),
    ).toBeInTheDocument()
  })

  // The assertion this file exists for. Before #848 the flush declined
  // outright while signed out, so this send never happened - the report sat
  // in the queue waiting for an account the hiker had no reason to make.
  it('sends it straight away rather than waiting for an account', async () => {
    const user = userEvent.setup()
    await openTheForm(user)
    // Positive control: nothing has been sent yet, so a send below can only
    // have come from filing this report.
    expect(mockedSend).not.toHaveBeenCalled()

    await user.type(
      screen.getByLabelText(/what happened/i),
      'It put me on the wrong side of the ford.',
    )
    await user.type(screen.getByLabelText(/reach you/i), 'sparrow@example.com')
    await user.click(screen.getByRole('button', { name: /^send$/i }))

    await waitFor(() => expect(mockedSend).toHaveBeenCalledTimes(1))
    const sent = mockedSend.mock.calls[0][0]
    expect(sent.appFailure?.what_happened).toBe(
      'It put me on the wrong side of the ford.',
    )
    expect(sent.appFailure?.contact).toBe('sparrow@example.com')
  })

  it('keeps the whole report queued when the send fails, rather than losing it', async () => {
    // The ordinary case out here, and the one the outbox exists for: the
    // report is written where the app broke, which is where there is no
    // signal. It has to survive to the next time there is some.
    mockedSend.mockRejectedValueOnce(new Error('no signal'))
    const user = userEvent.setup()
    await openTheForm(user)

    await user.type(screen.getByLabelText(/what happened/i), 'The map went blank.')
    await user.type(screen.getByLabelText(/reach you/i), 'sparrow@example.com')
    await user.click(screen.getByRole('button', { name: /^send$/i }))

    await waitFor(() => expect(mockedSend).toHaveBeenCalled())
    await waitFor(() => {
      const queue = store.get(OUTBOX_KEY) as Array<{
        appFailure?: { what_happened: string; contact?: string }
      }>
      // Still the only copy of what somebody wrote down, contact included.
      expect(queue).toHaveLength(1)
      expect(queue[0].appFailure?.what_happened).toBe('The map went blank.')
      expect(queue[0].appFailure?.contact).toBe('sparrow@example.com')
    })
  })

  it('says what happens next, and returns to Settings when that is read', async () => {
    const user = userEvent.setup()
    await openTheForm(user)

    await user.type(screen.getByLabelText(/what happened/i), 'The map went blank.')
    await user.click(screen.getByRole('button', { name: /^send$/i }))

    await user.click(await screen.findByRole('button', { name: /done/i }))

    expect(await screen.findByRole('tab', { name: 'Settings' })).toBeInTheDocument()
  })
})
