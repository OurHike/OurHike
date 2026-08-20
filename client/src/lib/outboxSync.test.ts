import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { syncOutbox, useOutboxSync } from './outboxSync'
import { flushOutbox, hasWorkThatNeedsNoAccount } from './outbox'
import { accessToken, sendOutboxItem, permanentFailureReason } from './api'

// #231's other half: the outbox had queued correctly since it was written and
// nothing had ever emptied it.
//
// The property most worth pinning is the overlap guard. `flushOutbox` reads
// the whole queue, sends every item, then writes back the failures - so two
// calls that overlap both read the same queue and file every report twice.
// Coming back into signal is precisely when that happens, because the `online`
// event and a screen mounting can land in the same tick.

vi.mock('./outbox', () => ({
  flushOutbox: vi.fn(),
  hasWorkThatNeedsNoAccount: vi.fn(),
}))
vi.mock('./api', () => ({
  accessToken: vi.fn(),
  sendOutboxItem: vi.fn(),
  permanentFailureReason: vi.fn(),
  API_CONFIGURED: true,
}))

const mockedFlush = vi.mocked(flushOutbox)
const mockedToken = vi.mocked(accessToken)
const mockedNeedsNoAccount = vi.mocked(hasWorkThatNeedsNoAccount)

beforeEach(() => {
  mockedToken.mockResolvedValue('a-real-token')
  mockedFlush.mockResolvedValue({ sent: 1, failed: 0, stuck: 0 })
  // The ordinary queue: reports and photo actions, all of which need an
  // account. The app-failure report is the exception, and the tests that are
  // about it say so.
  mockedNeedsNoAccount.mockResolvedValue(false)
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('syncOutbox', () => {
  it('flushes with the real sender, and the real failure classifier', async () => {
    // Both arguments matter. Without the classifier every failure looks
    // retryable, which is the state #243 is about: a report the server will
    // never accept sitting in the queue saying "waiting to send" forever.
    await syncOutbox()

    expect(mockedFlush).toHaveBeenCalledWith(sendOutboxItem, permanentFailureReason)
  })

  it('does not try when signed out - the queue waits for an account', async () => {
    mockedToken.mockResolvedValue(null)

    expect(await syncOutbox()).toBeNull()
    expect(mockedFlush).not.toHaveBeenCalled()
  })

  // #848. The app-failure report is the one write that takes no account, and
  // an unconditional "signed out, do not flush" left exactly that report
  // waiting for one - a hiker who has just been lost is not going to make an
  // account first, and should not have to.
  it('flushes while signed out when something queued needs no account', async () => {
    mockedToken.mockResolvedValue(null)
    mockedNeedsNoAccount.mockResolvedValue(true)

    await syncOutbox()

    expect(mockedFlush).toHaveBeenCalledWith(sendOutboxItem, permanentFailureReason)
  })

  it('reports a flush that ran, so a caller can record a real sync time', async () => {
    mockedFlush.mockResolvedValue({ sent: 2, failed: 1, stuck: 0 })

    expect(await syncOutbox()).toEqual({ sent: 2, failed: 1, stuck: 0 })
  })

  it('never rejects, even when the flush itself throws', async () => {
    // Background work behind a map someone is navigating by. An unhandled
    // rejection here would surface as an error over the trail.
    mockedFlush.mockRejectedValue(new Error('storage is gone'))

    expect(await syncOutbox()).toBeNull()
  })

  it('does not overlap two flushes, which would file every report twice', async () => {
    let release: (value: {
      sent: number
      failed: number
      stuck: number
    }) => void = () => {}
    mockedFlush.mockReturnValue(
      new Promise((resolve) => {
        release = resolve
      }),
    )

    // Both started before either can finish - the exact race the guard exists
    // for, not two calls one after another.
    const first = syncOutbox()
    const second = syncOutbox()
    release({ sent: 1, failed: 0, stuck: 0 })
    await Promise.all([first, second])

    expect(mockedFlush).toHaveBeenCalledTimes(1)
  })

  it('can flush again once the first one has finished', async () => {
    // The guard must not latch: coming back into signal a second time has to
    // send whatever was written in between.
    await syncOutbox()
    await syncOutbox()

    expect(mockedFlush).toHaveBeenCalledTimes(2)
  })
})

describe('useOutboxSync', () => {
  it('does nothing while there is no signal', async () => {
    const onSynced = vi.fn()

    renderHook(() => useOutboxSync(false, onSynced))

    // Waiting on the mock rather than asserting immediately: a promise that
    // had been scheduled would resolve after this line, and a bare assertion
    // would pass whether or not the guard works.
    await waitFor(() => expect(mockedToken).not.toHaveBeenCalled())
    expect(mockedFlush).not.toHaveBeenCalled()
    expect(onSynced).not.toHaveBeenCalled()
  })

  it('flushes once there is', async () => {
    const onSynced = vi.fn()

    renderHook(() => useOutboxSync(true, onSynced))

    await waitFor(() => expect(mockedFlush).toHaveBeenCalled())
  })

  it('reports the result back', async () => {
    const onSynced = vi.fn()
    mockedFlush.mockResolvedValue({ sent: 3, failed: 0, stuck: 0 })

    renderHook(() => useOutboxSync(true, onSynced))

    await waitFor(() =>
      expect(onSynced).toHaveBeenCalledWith({ sent: 3, failed: 0, stuck: 0 }),
    )
  })

  it('flushes when signal arrives, not only when it was there all along', async () => {
    const onSynced = vi.fn()
    const { rerender } = renderHook(({ enabled }) => useOutboxSync(enabled, onSynced), {
      initialProps: { enabled: false },
    })

    await waitFor(() => expect(mockedFlush).not.toHaveBeenCalled())
    rerender({ enabled: true })

    await waitFor(() => expect(mockedFlush).toHaveBeenCalledTimes(1))
  })

  it('says nothing when it could not even try', async () => {
    mockedToken.mockResolvedValue(null)
    const onSynced = vi.fn()

    renderHook(() => useOutboxSync(true, onSynced))

    // "Could not try" must not read as "synced": the status strip would say
    // "just now" on a device that has never reached the server.
    await waitFor(() => expect(mockedToken).toHaveBeenCalled())
    expect(onSynced).not.toHaveBeenCalled()
  })
})

describe('a build with no backend configured', () => {
  afterEach(() => {
    vi.resetModules()
  })

  it('does not even ask for a token', async () => {
    // Re-mocked and re-imported rather than asserting on the module-level mock
    // above, which is fixed at true. Asserting `API_CONFIGURED === true` there
    // would be a test that cannot fail (#175): it would check the mock, not
    // the guard.
    vi.resetModules()
    vi.doMock('./api', () => ({
      accessToken: mockedToken,
      sendOutboxItem,
      permanentFailureReason,
      API_CONFIGURED: false,
    }))
    const { syncOutbox: unconfiguredSync } = await import('./outboxSync')

    expect(await unconfiguredSync()).toBeNull()
    expect(mockedToken).not.toHaveBeenCalled()
    expect(mockedFlush).not.toHaveBeenCalled()
  })
})
