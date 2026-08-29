import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { useWakeLock } from './useWakeLock'

// Reported from a real walk: the recording stopped when the phone went to
// sleep. This hook is the half of that a web app can fix - the screen not
// darkening on its own - and every test below is about it either working or
// SAYING it does not, because the screen prints the difference.

function stubWakeLock(behaviour: 'grants' | 'refuses' | 'missing' = 'grants') {
  const release = vi.fn(() => Promise.resolve())

  const request = vi.fn(() =>
    behaviour === 'refuses'
      ? Promise.reject(new Error('policy'))
      : Promise.resolve({ release } as unknown as WakeLockSentinel),
  )

  vi.stubGlobal('navigator', behaviour === 'missing' ? {} : { wakeLock: { request } })

  return { request, release }
}

/** Hide or show the tab, the way a browser reports it. */
function setHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { value: hidden, configurable: true })
  act(() => {
    document.dispatchEvent(new Event('visibilitychange'))
  })
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
