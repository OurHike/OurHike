import { describe, it, expect, afterEach } from 'vitest'
import { renderHook, act, cleanup } from '@testing-library/react'
import { useSystemDark, useTheme } from './useTheme'
import { DARK_MEDIA_QUERY, THEME_ATTRIBUTE } from './theme'
import type { Theme } from './userPreferences'

// The subscription is the part worth testing. A hiker on 'auto' whose phone
// flips to dark at sunset - which is when a phone usually does it, and when
// this app is most likely to be out - should see the app follow now, not at the
// next cold start.

type Listener = (event: MediaQueryListEvent) => void

/** A controllable `prefers-color-scheme` query. `flip` fires the change event
 *  the same way a real MediaQueryList does. */
function stubMatchMedia(dark: boolean) {
  let matches = dark
  const listeners = new Set<Listener>()

  window.matchMedia = ((query: string) => {
    const list = {
      get matches() {
        return query === DARK_MEDIA_QUERY ? matches : false
      },
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: (_: string, listener: Listener) => {
        if (query === DARK_MEDIA_QUERY) listeners.add(listener)
      },
      removeEventListener: (_: string, listener: Listener) => {
        listeners.delete(listener)
      },
      dispatchEvent: () => false,
    }
    return list as unknown as MediaQueryList
  }) as typeof window.matchMedia

  return {
    flip(next: boolean) {
      matches = next
      for (const listener of listeners) {
        listener({ matches: next } as MediaQueryListEvent)
      }
    },
    get subscribed() {
      return listeners.size
    },
  }
}

afterEach(() => {
  cleanup()
  document.documentElement.removeAttribute(THEME_ATTRIBUTE)
  document.querySelector('meta[name="theme-color"]')?.remove()
})

describe('useSystemDark', () => {
  it('reads the query and then follows it', () => {
    const media = stubMatchMedia(false)
    const { result } = renderHook(() => useSystemDark())

    expect(result.current).toBe(false)

    act(() => media.flip(true))
    expect(result.current).toBe(true)
  })

  it('unsubscribes on unmount', () => {
    const media = stubMatchMedia(false)
    const { unmount } = renderHook(() => useSystemDark())
    expect(media.subscribed).toBe(1)

    unmount()
    expect(media.subscribed).toBe(0)
  })
})

describe('useTheme', () => {
  it('writes the resolved theme onto the document', () => {
    stubMatchMedia(true)
    const { result } = renderHook(() => useTheme('auto'))

    expect(result.current).toBe('dark')
    expect(document.documentElement.getAttribute(THEME_ATTRIBUTE)).toBe('dark')
  })

  it('re-applies when the phone changes theme under an auto preference', () => {
    const media = stubMatchMedia(false)
    const { result } = renderHook(() => useTheme('auto'))
    expect(document.documentElement.getAttribute(THEME_ATTRIBUTE)).toBe('light')

    act(() => media.flip(true))

    expect(result.current).toBe('dark')
    expect(document.documentElement.getAttribute(THEME_ATTRIBUTE)).toBe('dark')
  })

  it('ignores the phone when the hiker has chosen', () => {
    // The whole reason the preference is three-way. Someone who keeps their
    // phone dark and wants the paper map in daylight says so once, and a
    // sunset on the OS side does not overrule them.
    const media = stubMatchMedia(false)
    const { result } = renderHook(() => useTheme('light'))

    act(() => media.flip(true))

    expect(result.current).toBe('light')
    expect(document.documentElement.getAttribute(THEME_ATTRIBUTE)).toBe('light')
  })

  it('follows the preference when it changes', () => {
    stubMatchMedia(false)
    const { result, rerender } = renderHook(
      ({ theme }: { theme: Theme }) => useTheme(theme),
      {
        initialProps: { theme: 'light' as Theme },
      },
    )
    expect(result.current).toBe('light')

    rerender({ theme: 'dark' })

    expect(result.current).toBe('dark')
    expect(document.documentElement.getAttribute(THEME_ATTRIBUTE)).toBe('dark')
  })
})
