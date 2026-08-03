// Tests for useDesktop.ts.
//
// Why this exists
// ---------------
// Almost all of the desktop layout is CSS, which cannot regress the phone
// because it is behind a media query. This hook is the exception: it decides
// things a stylesheet cannot, like whether the legend announces itself as a
// modal dialog. So the failure mode is not "the layout looks wrong" - it is a
// screen reader being told the rest of the app is inert when it is not.
//
// The default when nothing can be determined is therefore load-bearing, and
// gets its own test: the phone layout works at every width, and the desktop
// layout at 375px is a sidebar eating half the map.

import { renderHook, act } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DESKTOP_MEDIA_QUERY, DESKTOP_MIN_WIDTH, useDesktop } from './useDesktop'

type Listener = (event: MediaQueryListEvent) => void

/** A matchMedia jsdom does not provide, with a handle to fire a change. */
function stubMatchMedia(initial: boolean) {
  const listeners = new Set<Listener>()

  const query = {
    matches: initial,
    media: DESKTOP_MEDIA_QUERY,
    addEventListener: (_: string, listener: Listener) => listeners.add(listener),
    removeEventListener: (_: string, listener: Listener) => listeners.delete(listener),
  }

  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => query),
  )

  return {
    resizeTo(matches: boolean) {
      query.matches = matches
      for (const listener of listeners) listener({ matches } as MediaQueryListEvent)
    },
    get listenerCount() {
      return listeners.size
    },
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useDesktop', () => {
  it('is true above the breakpoint', () => {
    stubMatchMedia(true)

    expect(renderHook(() => useDesktop()).result.current).toBe(true)
  })

  it('is false below it', () => {
    stubMatchMedia(false)

    expect(renderHook(() => useDesktop()).result.current).toBe(false)
  })

  it('follows a resize across the breakpoint', () => {
    const media = stubMatchMedia(false)
    const { result } = renderHook(() => useDesktop())

    act(() => media.resizeTo(true))

    expect(result.current).toBe(true)
  })

  it('falls back to the phone layout when matchMedia does not exist', () => {
    // The load-bearing default. The phone layout works at every width; the
    // desktop layout at 375px is a sidebar eating half the map. Guessing wrong
    // in that direction is the expensive one.
    vi.stubGlobal('matchMedia', undefined)

    expect(renderHook(() => useDesktop()).result.current).toBe(false)
  })

  it('stops listening when the component goes away', () => {
    const media = stubMatchMedia(false)
    const { unmount } = renderHook(() => useDesktop())

    unmount()

    expect(media.listenerCount).toBe(0)
  })

  it('names the breakpoint WEBSITE.md §6 specifies', () => {
    // Not a tautology: this constant has to equal the one in desktop.css, and
    // desktopLayout.test.ts asserts the other half of that pair.
    expect(DESKTOP_MIN_WIDTH).toBe(900)
    expect(DESKTOP_MEDIA_QUERY).toBe('(min-width: 900px)')
  })
})
