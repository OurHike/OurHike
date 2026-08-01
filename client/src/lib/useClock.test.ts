import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useClock, CLOCK_INTERVAL_MS } from './useClock'

// The clock behind "last synced 3 hours ago" and the time in the status strip.
// It exists because those readings go stale silently: nothing re-renders the
// shell just because a minute passed, so without a tick the app would sit
// showing a time from whenever it last happened to render.

afterEach(() => {
  vi.useRealTimers()
})

describe('useClock', () => {
  it('starts at the current time', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-31T12:00:00Z'))

    const { result } = renderHook(() => useClock())

    expect(result.current).toEqual(new Date('2026-07-31T12:00:00Z'))
  })

  it('moves on as time passes, so a stale reading cannot sit on screen', () => {
    // advanceTimersByTime moves the faked system clock along with the timer
    // queue, so the tick reads back exactly the interval it waited.
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-31T12:00:00Z'))
    const { result } = renderHook(() => useClock(1000))

    act(() => {
      vi.advanceTimersByTime(1000)
    })

    expect(result.current).toEqual(new Date('2026-07-31T12:00:01Z'))
  })

  it('ticks once a minute by default', () => {
    // Fine enough for "3 hours ago" and cheap enough to leave running for
    // days, which is how long this app stays open.
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-31T12:00:00Z'))
    const { result } = renderHook(() => useClock())

    act(() => {
      vi.advanceTimersByTime(CLOCK_INTERVAL_MS - 1)
    })
    expect(result.current).toEqual(new Date('2026-07-31T12:00:00Z'))

    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(result.current).toEqual(new Date('2026-07-31T12:01:00Z'))
  })

  it('stops ticking on unmount, rather than waking the phone forever', () => {
    vi.useFakeTimers()
    const clearInterval = vi.spyOn(globalThis, 'clearInterval')

    const { unmount } = renderHook(() => useClock(1000))
    unmount()

    expect(clearInterval).toHaveBeenCalled()
  })
})
