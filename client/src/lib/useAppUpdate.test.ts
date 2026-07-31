import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useAppUpdate } from './useAppUpdate'

// The bug this closes: a new build installed, sat in `waiting`, and the old
// bundle kept being served - so every deploy looked like it had not happened
// and the only escape was clearing site data through browser settings.

function stubServiceWorker({ controlled }: { controlled: boolean }) {
  const listeners: Record<string, Array<() => void>> = {}
  const update = vi.fn(() => Promise.resolve())

  const sw = {
    controller: controlled ? {} : null,
    addEventListener: (type: string, fn: () => void) => {
      listeners[type] = [...(listeners[type] ?? []), fn]
    },
    removeEventListener: (type: string, fn: () => void) => {
      listeners[type] = (listeners[type] ?? []).filter((f) => f !== fn)
    },
    getRegistration: () => Promise.resolve({ update }),
  }

  vi.stubGlobal('navigator', { serviceWorker: sw, userAgent: '', platform: '' })
  return {
    update,
    fireControllerChange: () => listeners.controllerchange?.forEach((fn) => fn()),
    listenerCount: () => (listeners.controllerchange ?? []).length,
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe('useAppUpdate', () => {
  it('asks for a new version as soon as the app opens', async () => {
    const sw = stubServiceWorker({ controlled: true })

    renderHook(() => useAppUpdate())
    await vi.waitFor(() => expect(sw.update).toHaveBeenCalled())
  })

  it('keeps asking, since a PWA can stay open for days without navigating', async () => {
    vi.useFakeTimers()
    const sw = stubServiceWorker({ controlled: true })

    renderHook(() => useAppUpdate(1000))
    await vi.advanceTimersByTimeAsync(3500)

    // Once on mount plus three intervals.
    expect(sw.update.mock.calls.length).toBeGreaterThanOrEqual(4)
  })

  it('reloads once the new worker takes control of an already-controlled page', () => {
    const reload = vi.fn()
    vi.stubGlobal('location', { reload })
    const sw = stubServiceWorker({ controlled: true })

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
