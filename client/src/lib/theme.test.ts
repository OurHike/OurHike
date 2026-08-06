import { describe, it, expect, afterEach, vi } from 'vitest'
import {
  applyTheme,
  DARK_MEDIA_QUERY,
  resolveTheme,
  systemPrefersDark,
  THEME_ATTRIBUTE,
  THEME_COLORS,
} from './theme'

// The three-way preference resolved to the one thing every stylesheet reads.
//
// The case worth naming, because it is the one a media query alone cannot
// serve at all: someone who wants the app light while the phone is dark.
// features/UX_CUSTOMIZATION.md called auto-detection "near-free" and the
// manual override small polish on top, which is true of the code and not of
// the outcome - auto-detection alone means the app is only ever as right as
// the OS setting, and a hiker who keeps their phone dark and wants a readable
// map in daylight has nowhere to say so.

/** A matchMedia that answers one way for the dark query and false otherwise,
 *  and records the listeners registered against it. */
function stubMatchMedia(dark: boolean) {
  const listeners: Array<(event: MediaQueryListEvent) => void> = []
  window.matchMedia = ((query: string) =>
    ({
      matches: query === DARK_MEDIA_QUERY ? dark : false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: (_: string, listener: (event: MediaQueryListEvent) => void) =>
        listeners.push(listener),
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList) as typeof window.matchMedia
  return listeners
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.documentElement.removeAttribute(THEME_ATTRIBUTE)
  document.querySelector('meta[name="theme-color"]')?.remove()
})

describe('resolveTheme', () => {
  it('follows the OS on auto, in both directions', () => {
    expect(resolveTheme('auto', true)).toBe('dark')
    expect(resolveTheme('auto', false)).toBe('light')
  })

  it('lets an explicit choice beat the OS, in both directions', () => {
    // Both halves matter. Dark-while-the-phone-is-light is the obvious one;
    // light-while-the-phone-is-dark is the one auto-detection cannot express,
    // and is why this is a three-way preference rather than a media query.
    expect(resolveTheme('dark', false)).toBe('dark')
    expect(resolveTheme('light', true)).toBe('light')
  })
})

describe('systemPrefersDark', () => {
  it('reads the standard query', () => {
    stubMatchMedia(true)
    expect(systemPrefersDark()).toBe(true)

    stubMatchMedia(false)
    expect(systemPrefersDark()).toBe(false)
  })

  it('answers light where matchMedia does not exist', () => {
    // jsdom's own gap, and the honest answer to "cannot tell": light is the
    // theme every colour in the app has been looked at in.
    const original = window.matchMedia
    // @ts-expect-error deliberately removing the API to model an old engine
    delete window.matchMedia

    expect(systemPrefersDark()).toBe(false)

    window.matchMedia = original
  })
})

describe('applyTheme', () => {
  it('writes the attribute the tokens key their dark block off', () => {
    applyTheme('dark', document)
    expect(document.documentElement.getAttribute(THEME_ATTRIBUTE)).toBe('dark')

    applyTheme('light', document)
    expect(document.documentElement.getAttribute(THEME_ATTRIBUTE)).toBe('light')
  })

  it('creates the theme-color meta rather than needing one in index.html', () => {
    expect(document.querySelector('meta[name="theme-color"]')).toBeNull()

    applyTheme('dark', document)

    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    expect(meta?.content).toBe(THEME_COLORS.dark)
  })

  it('reuses the one meta rather than stacking a new one per change', () => {
    // Left to accumulate, a phone that flips theme a few times ends up with a
    // head full of theme-color tags and the browser reading the first one -
    // which would be whichever theme the app opened in, forever.
    applyTheme('dark', document)
    applyTheme('light', document)
    applyTheme('dark', document)

    const metas = document.querySelectorAll('meta[name="theme-color"]')
    expect(metas.length).toBe(1)
    expect((metas[0] as HTMLMetaElement).content).toBe(THEME_COLORS.dark)
  })

  it('carries a different chrome colour per theme', () => {
    expect(THEME_COLORS.light).not.toBe(THEME_COLORS.dark)
    for (const value of Object.values(THEME_COLORS)) {
      expect(value).toMatch(/^#[0-9a-f]{6}$/i)
    }
  })
})
