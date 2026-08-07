import { describe, it, expect, vi, afterEach } from 'vitest'
import { cleanup, renderHook } from '@testing-library/react'
import { useAppUpdate, UPDATE_CHECK_MS } from './useAppUpdate'

// The bug this closes: a new build installed, sat in `waiting`, and the old
// bundle kept being served - so every deploy looked like it had not happened
// and the only escape was clearing site data through browser settings.

function stubServiceWorker({
  controlled,
  updateFails = false,
  getRegistrationFails = false,
  onLine = true,
}: {
  controlled: boolean
  updateFails?: boolean
  getRegistrationFails?: boolean
  /** What navigator.onLine reads. False is the definitive reading - the hook
   *  skips the fetch entirely rather than waking the radio to fail. */
  onLine?: boolean
}) {
  const listeners: Record<string, Array<() => void>> = {}

  // Counted by hand rather than with vi.fn(), and that is load-bearing for the
  // offline tests below. vi.fn() attaches its own handler to whatever promise
  // the implementation returns so it can record settled results - which marks
  // a rejected one as handled. A stub built on vi.fn() therefore swallows
  // exactly the unhandled rejection those tests exist to detect, and they pass
  // against the unfixed hook. A plain function leaves the rejection alone.
  let updateCalls = 0
  const update = () => {
    updateCalls += 1
    return updateFails
      ? Promise.reject(new TypeError('Failed to fetch'))
      : Promise.resolve()
  }

  const sw = {
    controller: controlled ? {} : null,
    addEventListener: (type: string, fn: () => void) => {
      listeners[type] = [...(listeners[type] ?? []), fn]
    },
    removeEventListener: (type: string, fn: () => void) => {
      listeners[type] = (listeners[type] ?? []).filter((f) => f !== fn)
    },
    getRegistration: () =>
      getRegistrationFails
        ? Promise.reject(new Error('no registration'))
        : Promise.resolve({ update }),
  }

  vi.stubGlobal('navigator', { serviceWorker: sw, onLine, userAgent: '', platform: '' })
  return {
    updateCalls: () => updateCalls,
    fireControllerChange: () => listeners.controllerchange?.forEach((fn) => fn()),
    listenerCount: () => (listeners.controllerchange ?? []).length,
  }
}

/**
 * Put the page in the state a reload is allowed in.
 *
 * jsdom reports 'visible' by default, which is the state this hook now
 * REFUSES to reload in - so every reload case has to say so out loud, and
 * every case that does not call this is asserting the deferral.
 */
function hide(state: DocumentVisibilityState = 'hidden') {
  Object.defineProperty(document, 'visibilityState', {
    value: state,
    configurable: true,
  })
  document.dispatchEvent(new Event('visibilitychange'))
}

afterEach(() => {
  // Unmount first, and this file needs it for the same reason
  // useGeolocation.test.ts does (#313): these hooks listen on `document`, so a
  // single dispatched `visibilitychange` reaches every hook the file has ever
  // rendered - each one calling the CURRENT test's reload stub. Two reloads
  // where one was expected is what surfaced it.
  cleanup()
  hide('visible')
  vi.unstubAllGlobals()
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe('useAppUpdate', () => {
  it('asks for a new version as soon as the app opens', async () => {
    const sw = stubServiceWorker({ controlled: true })

    renderHook(() => useAppUpdate())
    await vi.waitFor(() => expect(sw.updateCalls()).toBeGreaterThan(0))
  })

  it('keeps asking, since a PWA can stay open for days without navigating', async () => {
    vi.useFakeTimers()
    const sw = stubServiceWorker({ controlled: true })

    renderHook(() => useAppUpdate(1000))
    await vi.advanceTimersByTimeAsync(3500)

    // Once on mount plus three intervals.
    expect(sw.updateCalls()).toBeGreaterThanOrEqual(4)
  })

  it('never wakes the radio while the browser says there is no network', async () => {
    // navigator.onLine true proves nothing, but false is definitive - and a
    // fetch that was going to fail still costs a cold cellular radio woken
    // once an hour for the length of a hike. The tick keeps ticking; the
    // fetch waits for signal.
    vi.useFakeTimers()
    const sw = stubServiceWorker({ controlled: true, onLine: false })

    renderHook(() => useAppUpdate(1000))
    await vi.advanceTimersByTimeAsync(3500)

    expect(sw.updateCalls()).toBe(0)
  })

  it('reloads once the new worker takes control of a hidden, idle page', () => {
    const reload = vi.fn()
    vi.stubGlobal('location', { reload })
    const sw = stubServiceWorker({ controlled: true })
    hide()

    renderHook(() => useAppUpdate())
    sw.fireControllerChange()

    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('does not reload a first-ever visit, which would bounce every new user once', () => {
    // On a first visit the worker claims a page that had no controller. That
    // is an install, not an update, and reloading for it is pure noise.
    const reload = vi.fn()
    vi.stubGlobal('location', { reload })
    const sw = stubServiceWorker({ controlled: false })

    renderHook(() => useAppUpdate())
    sw.fireControllerChange()

    expect(reload).not.toHaveBeenCalled()
  })

  it('reloads at most once, however many times control changes', () => {
    const reload = vi.fn()
    vi.stubGlobal('location', { reload })
    const sw = stubServiceWorker({ controlled: true })
    hide()

    renderHook(() => useAppUpdate())
    sw.fireControllerChange()
    sw.fireControllerChange()

    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('stops listening when the app unmounts', () => {
    const sw = stubServiceWorker({ controlled: true })

    const { unmount } = renderHook(() => useAppUpdate())
    expect(sw.listenerCount()).toBe(1)
    unmount()

    expect(sw.listenerCount()).toBe(0)
  })

  it('does nothing where service workers are unavailable', () => {
    vi.stubGlobal('navigator', { userAgent: '', platform: '' })

    expect(() => renderHook(() => useAppUpdate())).not.toThrow()
  })
})

// Offline is not an edge case here - it is the condition this whole app exists
// for. update() re-fetches the worker script, so with no signal it rejects
// every single time the interval fires. Unhandled, that is an
// `unhandledrejection` an hour, for days, on exactly the hike the app is built
// around: noise in any error reporting added later, and noise at the hiker in a
// browser that surfaces them. There is nothing to act on either way - the next
// tick tries again and the running app is fine meanwhile - so it is caught.
describe('useAppUpdate with no signal', () => {
  // Listens on `process`, not on window's `unhandledrejection`. jsdom does not
  // dispatch that event for rejections originating in test code, so a window
  // listener sits there seeing nothing and the assertion passes whether the
  // bug is present or not - it was written that way first and proved toothless
  // against the pre-fix code. Node is what actually reports these (it is what
  // Vitest's own "Unhandled Errors" section reads), and a listener added here
  // observes without suppressing, since process handlers do not mark a
  // rejection handled.
  async function rejectionsWhile(run: () => void): Promise<unknown[]> {
    const seen: unknown[] = []
    const onUnhandled = (reason: unknown) => seen.push(reason)
    process.on('unhandledRejection', onUnhandled)
    try {
      run()
      // Node reports an unhandled rejection only after the microtask queue has
      // drained and the promise is still without a handler, so this has to
      // outlast a macrotask rather than a single await.
      await new Promise((resolve) => setTimeout(resolve, 50))
    } finally {
      process.off('unhandledRejection', onUnhandled)
    }
    return seen
  }

  it('stays quiet when the update check cannot reach the network', async () => {
    const sw = stubServiceWorker({ controlled: true, updateFails: true })

    const rejections = await rejectionsWhile(() => renderHook(() => useAppUpdate()))

    expect(sw.updateCalls()).toBeGreaterThan(0)
    expect(rejections).toEqual([])
  })

  it('stays quiet when the registration itself cannot be read', async () => {
    stubServiceWorker({ controlled: true, getRegistrationFails: true })

    const rejections = await rejectionsWhile(() => renderHook(() => useAppUpdate()))

    expect(rejections).toEqual([])
  })

  it('keeps checking after a failed check, rather than giving up', async () => {
    // A hiker who walks back into signal should get the new build. A check
    // that stopped rescheduling itself on the first offline failure would
    // leave them on the old one until they closed the app.
    vi.useFakeTimers()
    const sw = stubServiceWorker({ controlled: true, updateFails: true })

    renderHook(() => useAppUpdate(1000))
    await vi.advanceTimersByTimeAsync(3500)

    expect(sw.updateCalls()).toBeGreaterThanOrEqual(4)
  })
})

describe('waiting for a moment the reload costs nothing (#311)', () => {
  // The failure this closes: a deploy lands within the hour, the page reloads
  // under whoever is holding it, and React state goes with it - the camera
  // they panned to, the report they were half way through typing.

  it('does not reload a page someone is looking at', () => {
    const reload = vi.fn()
    vi.stubGlobal('location', { reload })
    const sw = stubServiceWorker({ controlled: true })

    renderHook(() => useAppUpdate())
    sw.fireControllerChange()

    expect(reload).not.toHaveBeenCalled()
  })

  it('reloads as soon as the phone goes back in the pocket', () => {
    // The whole design in one case: the update is not abandoned, it is
    // deferred, and the next time the screen goes away it lands unwatched.
    const reload = vi.fn()
    vi.stubGlobal('location', { reload })
    const sw = stubServiceWorker({ controlled: true })

    renderHook(() => useAppUpdate())
    sw.fireControllerChange()
    expect(reload).not.toHaveBeenCalled()

    hide()

    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('holds even while hidden when something is at stake', () => {
    // A phone put down with a half-written report open is hidden and is still
    // holding something worth keeping. Hidden alone is not enough.
    const reload = vi.fn()
    vi.stubGlobal('location', { reload })
    const sw = stubServiceWorker({ controlled: true })
    hide()

    renderHook(() => useAppUpdate(UPDATE_CHECK_MS, { hold: true }))
    sw.fireControllerChange()

    expect(reload).not.toHaveBeenCalled()
  })

  it('takes the update the moment the hold is released', () => {
    // Releasing a hold fires no event of its own - putting a form away is
    // just a render - so the hook has to notice the prop changing.
    const reload = vi.fn()
    vi.stubGlobal('location', { reload })
    const sw = stubServiceWorker({ controlled: true })
    hide()

    const { rerender } = renderHook(
      ({ hold }) => useAppUpdate(UPDATE_CHECK_MS, { hold }),
      {
        initialProps: { hold: true },
      },
    )
    sw.fireControllerChange()
    expect(reload).not.toHaveBeenCalled()

    rerender({ hold: false })

    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('does not re-attach its listeners when the hold changes', () => {
    // The hold is read through a ref for this reason: putting it in the
    // effect's deps would re-read `controller`, re-register every listener and
    // restart the hourly timer each time a hiker opened a sheet - and reset
    // the pending update with them.
    const sw = stubServiceWorker({ controlled: true })

    const { rerender } = renderHook(
      ({ hold }) => useAppUpdate(UPDATE_CHECK_MS, { hold }),
      {
        initialProps: { hold: false },
      },
    )
    rerender({ hold: true })
    rerender({ hold: false })

    expect(sw.listenerCount()).toBe(1)
  })

  it('keeps a pending update across a hold, rather than losing it', () => {
    const reload = vi.fn()
    vi.stubGlobal('location', { reload })
    const sw = stubServiceWorker({ controlled: true })

    // Control changes while the page is visible AND holding.
    const { rerender } = renderHook(
      ({ hold }) => useAppUpdate(UPDATE_CHECK_MS, { hold }),
      {
        initialProps: { hold: true },
      },
    )
    sw.fireControllerChange()

    // Both conditions clear, one after the other, long after the event.
    rerender({ hold: false })
    expect(reload).not.toHaveBeenCalled()
    hide()

    expect(reload).toHaveBeenCalledTimes(1)
  })
})
