import { describe, it, expect, afterEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useOnline } from './useOnline'

// Whether there is signal decides what several screens are allowed to claim -
// a report says "will send when you're back in range" rather than "sent", and
// the download screen stops offering a transfer that cannot start. Getting it
// wrong in the optimistic direction is the one that misleads.

function setOnline(value: boolean) {
  Object.defineProperty(navigator, 'onLine', { value, configurable: true })
}

afterEach(() => {
  setOnline(true)
})

describe('useOnline', () => {
  it('starts from whatever the browser already says', () => {
    setOnline(false)

    const { result } = renderHook(() => useOnline())

    expect(result.current).toBe(false)
  })

  it('notices going offline, which is the whole point out here', () => {
    setOnline(true)
    const { result } = renderHook(() => useOnline())

    act(() => {
      setOnline(false)
      window.dispatchEvent(new Event('offline'))
    })

    expect(result.current).toBe(false)
  })

  it('notices coming back into signal', () => {
    setOnline(false)
    const { result } = renderHook(() => useOnline())

    act(() => {
      setOnline(true)
      window.dispatchEvent(new Event('online'))
    })

    expect(result.current).toBe(true)
  })

  it('stops listening on unmount', () => {
    setOnline(true)
    const { result, unmount } = renderHook(() => useOnline())
    unmount()

    act(() => {
      setOnline(false)
      window.dispatchEvent(new Event('offline'))
    })

    // Still the value it held when it unmounted - the listener is gone.
    expect(result.current).toBe(true)
  })
})
