import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { useWakeLock } from './useWakeLock'

// Reported from a real walk: the recording stopped when the phone went to
// sleep. This hook is the half of that a web app can fix - the screen not
// darkening on its own - and every test below is about it either working or
// SAYING it does not, because the screen prints the difference.

function stubWakeLock(behaviour: 'grants' | 'refuses' | 'missing' = 'grants') {
  const release = vi.fn(() => Promise.resolve())

  // An EventTarget, because a real sentinel is one and the platform taking
  // the lock back is an event on it - the case the third field walk could
  // not rule out and this double previously could not express.
  const sentinel = Object.assign(new EventTarget(), { release })

  const request = vi.fn(() =>
    behaviour === 'refuses'
      ? Promise.reject(new Error('policy'))
      : Promise.resolve(sentinel as unknown as WakeLockSentinel),
  )

  vi.stubGlobal('navigator', behaviour === 'missing' ? {} : { wakeLock: { request } })

  return {
    request,
    release,
    /** The platform withdrawing the lock, as it does on a battery-saver
     *  threshold crossed mid-walk. */
    withdraw: () =>
      act(() => {
        sentinel.dispatchEvent(new Event('release'))
      }),
  }
}

/** Hide or show the tab, the way a browser reports it. */
function setHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { value: hidden, configurable: true })
  act(() => {
    document.dispatchEvent(new Event('visibilitychange'))
  })
}

/** A sentinel double whose `release()` fires the platform's own 'release'
 *  event, the way a real one does - so a test can tell a lock this hook let go
 *  of on purpose from one it reported as taken back. */
function fakeSentinel() {
  const target = new EventTarget()
  const release = vi.fn(() => {
    target.dispatchEvent(new Event('release'))
    return Promise.resolve()
  })
  return Object.assign(target, { release })
}

/** A wake lock whose grants are handed out by the test, one per request, so
 *  two `acquire()` calls can be left in flight together and resolved in either
 *  order. `stubWakeLock` cannot express this: it answers every request with
 *  the same already-resolved sentinel. */
function deferredWakeLock() {
  const grants: Array<{
    resolve: (sentinel: WakeLockSentinel) => void
    reject: (reason: Error) => void
  }> = []
  const request = vi.fn(
    () =>
      new Promise<WakeLockSentinel>((resolve, reject) => {
        grants.push({ resolve, reject })
      }),
  )
  vi.stubGlobal('navigator', { wakeLock: { request } })
  return { grants, request }
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
  Object.defineProperty(document, 'hidden', { value: false, configurable: true })
})

describe('useWakeLock', () => {
  it('asks for nothing while inactive', () => {
    const { request } = stubWakeLock()

    const { result } = renderHook(() => useWakeLock(false))

    expect(request).not.toHaveBeenCalled()
    expect(result.current).toBe('off')
  })

  it('holds the screen once active', async () => {
    const { request } = stubWakeLock()

    const { result } = renderHook(() => useWakeLock(true))

    await waitFor(() => expect(result.current).toBe('held'))
    expect(request).toHaveBeenCalledWith('screen')
  })

  it('stops saying held once the platform takes the lock back', async () => {
    // THE THIRD WALK'S UNANSWERED QUESTION. Fixes stopped dead 45 seconds
    // after the last screen tap while the hiker stood still on purpose. The
    // hook set 'held' once and never took it back, so the screen could have
    // been promising a lock that was already gone - and the trace recorded
    // nothing either way. Both halves are fixed; this is the first.
    const { withdraw } = stubWakeLock()

    const { result } = renderHook(() => useWakeLock(true))
    await waitFor(() => expect(result.current).toBe('held'))

    withdraw()

    await waitFor(() => expect(result.current).toBe('released'))
  })

  it('says so when the browser has no wake lock at all', () => {
    // The screen prints a different sentence for this, because the tester has
    // to do something about it - lengthen the screen timeout, or hold the
    // phone. Reporting 'held' here would be the same lie in a smaller font.
    stubWakeLock('missing')

    const { result } = renderHook(() => useWakeLock(true))

    expect(result.current).toBe('unsupported')
  })

  it('says so when the browser refuses, rather than throwing', async () => {
    // A phone under about 20% battery declines this on several platforms.
    // That is a normal answer, not a crash.
    stubWakeLock('refuses')

    const { result } = renderHook(() => useWakeLock(true))

    await waitFor(() => expect(result.current).toBe('refused'))
  })

  it('releases the screen when recording stops', async () => {
    const { release } = stubWakeLock()

    const { result, rerender } = renderHook(({ on }) => useWakeLock(on), {
      initialProps: { on: true },
    })
    await waitFor(() => expect(result.current).toBe('held'))

    rerender({ on: false })

    await waitFor(() => expect(release).toHaveBeenCalled())
    expect(result.current).toBe('off')
  })

  it('releases the screen on unmount', async () => {
    const { release } = stubWakeLock()

    const { result, unmount } = renderHook(() => useWakeLock(true))
    await waitFor(() => expect(result.current).toBe('held'))

    unmount()

    await waitFor(() => expect(release).toHaveBeenCalled())
  })

  it('asks again after the page comes back, because the platform drops it', async () => {
    // THE PART THAT IS EASY TO MISS. The lock is released every time the page
    // hides and is not given back on return, so without the listener the first
    // glance at another app ends it for the rest of the walk - silently, which
    // is the same shape as the bug this hook exists to fix.
    const { request, release } = stubWakeLock()

    const { result } = renderHook(() => useWakeLock(true))
    await waitFor(() => expect(result.current).toBe('held'))
    expect(request).toHaveBeenCalledTimes(1)

    setHidden(true)
    setHidden(false)

    await waitFor(() => expect(request).toHaveBeenCalledTimes(2))
    expect(release).not.toHaveBeenCalled()
  })

  it('does not ask while the page is hidden', () => {
    // Requesting from a hidden page rejects on every platform that implements
    // it, and a rejection here would report 'refused' at a phone that had
    // simply been pocketed for a moment.
    const { request } = stubWakeLock()

    Object.defineProperty(document, 'hidden', { value: true, configurable: true })
    renderHook(() => useWakeLock(true))

    expect(request).not.toHaveBeenCalled()
  })

  // THE FLAP. `acquire` runs on mount and again from `reacquire` on every
  // visibilitychange, so a hidden -> visible -> hidden -> visible flap inside
  // the time one request takes to resolve leaves two in flight. Each resolves
  // with its own sentinel and only one can be `sentinel`; the other is then
  // held by nothing this hook can reach. Three tests, because the race has
  // three orderings and the counter alone only settles the first.

  it('releases a sentinel that lands after a later request has replaced it', async () => {
    const { grants } = deferredWakeLock()

    const { result } = renderHook(() => useWakeLock(true))
    expect(grants).toHaveLength(1)

    setHidden(true)
    setHidden(false)
    expect(grants).toHaveLength(2)

    // The second request is granted first, so the first is already superseded
    // by the time the platform answers it.
    const second = fakeSentinel()
    const first = fakeSentinel()
    await act(async () => {
      grants[1].resolve(second as unknown as WakeLockSentinel)
    })
    await act(async () => {
      grants[0].resolve(first as unknown as WakeLockSentinel)
    })

    await waitFor(() => expect(first.release).toHaveBeenCalled())
    expect(second.release).not.toHaveBeenCalled()
    expect(result.current).toBe('held')
  })

  it('releases the sentinel it already holds rather than overwriting the reference', async () => {
    // The ordering a generation counter alone does not cover: the first
    // request has already landed as `sentinel`, so it is not superseded when
    // it resolves - it is superseded later, by the assignment.
    const { grants } = deferredWakeLock()

    const { result } = renderHook(() => useWakeLock(true))
    const first = fakeSentinel()
    await act(async () => {
      grants[0].resolve(first as unknown as WakeLockSentinel)
    })
    await waitFor(() => expect(result.current).toBe('held'))

    setHidden(true)
    setHidden(false)
    expect(grants).toHaveLength(2)

    const second = fakeSentinel()
    await act(async () => {
      grants[1].resolve(second as unknown as WakeLockSentinel)
    })

    await waitFor(() => expect(first.release).toHaveBeenCalled())
    expect(second.release).not.toHaveBeenCalled()
    // And the screen does not read as taken back on the way past. Releasing
    // the old sentinel fires its 'release' event; the state must survive that,
    // because a lock IS held - the replacement.
    expect(result.current).toBe('held')
  })

  it('does not report refused for a request a later one has already replaced', async () => {
    // A phone that declines under battery saver declines the stale request
    // too, and its rejection arrives after the live one was granted. Reporting
    // 'refused' there says the screen will sleep while it is being held awake,
    // which is the lie in the other direction.
    const { grants } = deferredWakeLock()

    const { result } = renderHook(() => useWakeLock(true))
    setHidden(true)
    setHidden(false)
    expect(grants).toHaveLength(2)

    const second = fakeSentinel()
    await act(async () => {
      grants[1].resolve(second as unknown as WakeLockSentinel)
    })
    await waitFor(() => expect(result.current).toBe('held'))

    await act(async () => {
      grants[0].reject(new Error('policy'))
    })

    expect(result.current).toBe('held')
  })

  it('releases a sentinel that arrives after recording stopped', async () => {
    // The race the `cancelled` flag exists for: a lock granted after the
    // effect tore down would hold the screen on for the life of the tab, with
    // nothing left holding a reference to turn it off.
    const release = vi.fn(() => Promise.resolve())
    let grant: (sentinel: WakeLockSentinel) => void = () => {}
    const request = vi.fn(
      () =>
        new Promise<WakeLockSentinel>((resolve) => {
          grant = resolve
        }),
    )
    vi.stubGlobal('navigator', { wakeLock: { request } })

    const { unmount } = renderHook(() => useWakeLock(true))
    unmount()
    await act(async () => {
      grant({ release } as unknown as WakeLockSentinel)
    })

    await waitFor(() => expect(release).toHaveBeenCalled())
  })
})
