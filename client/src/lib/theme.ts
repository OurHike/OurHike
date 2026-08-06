// Turning the hiker's three-way theme preference into the one thing every
// stylesheet keys off.
//
// `theme` is 'light' | 'dark' | 'auto' (lib/userPreferences.ts). CSS cannot
// express that: `prefers-color-scheme` answers what the OS wants, and has no
// opinion about someone who has overridden it. So the resolution happens here,
// in one function, and the answer is written to `<html data-theme>` -
// tokens/colors.css re-points its semantic aliases off that attribute and
// nothing else.
//
// Deliberately NOT a media query in the stylesheet with the attribute as an
// override. That spelling needs the dark token block written twice - once
// inside `@media (prefers-color-scheme: dark)` for the auto case and once
// under `[data-theme='dark']` for the explicit one - and two copies of forty
// colour declarations drift. What they drift into is a theme that is almost
// right, which is the hardest kind to notice.
//
// The cost of resolving in JS is that the attribute has to be on the element
// before the first paint, or the app flashes the light theme. main.tsx stamps
// it at module scope, before `createRoot(...).render()`, using the OS query
// alone: preferences live in IndexedDB and cannot be read synchronously, and
// the OS answer IS the stored answer for everyone on the default.

import type { Theme } from './userPreferences'

/** What actually gets drawn, once 'auto' has been resolved. */
export type ResolvedTheme = 'light' | 'dark'

/** Where the OS preference is read from. Exported so tests name the same
 *  string the hook subscribes to rather than a copy of it. */
export const DARK_MEDIA_QUERY = '(prefers-color-scheme: dark)'

/** The attribute tokens/colors.css keys the dark block off. */
export const THEME_ATTRIBUTE = 'data-theme'

/**
 * The browser chrome's colour - the address bar on Android, the status bar in
 * the installed shell.
 *
 * Part of the theme rather than a detail of it: an app that goes dark while
 * the bar above it stays paper-white looks broken, and on a phone at night
 * that strip is a real amount of light. The values are `--bg-page` in each
 * theme, resolved to literals because a `<meta>` content attribute is not a
 * place a CSS variable can be read.
 */
export const THEME_COLORS: Record<ResolvedTheme, string> = {
  light: '#f7f3e9',
  dark: '#15140f',
}

/**
 * Whether the OS is asking for a dark interface right now.
 *
 * Guarded rather than assumed, and defaulting light, for the reason
 * lib/useFinePointer.ts gives about the same API: jsdom has no `matchMedia`
 * unless a test stubs one, and "cannot tell" has to answer something. Light is
 * the safer miss - it is the theme the app was designed in, and every colour
 * in it has been looked at on a real screen.
 */
export function systemPrefersDark(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function')
    return false
  return window.matchMedia(DARK_MEDIA_QUERY).matches
}

/**
 * The preference plus the OS, resolved to what gets drawn.
 *
 * 'auto' is the default and follows the OS. An explicit choice wins over the
 * OS in both directions - including a hiker who wants light while the phone is
 * dark, which is the case a bare media query cannot serve at all.
 */
export function resolveTheme(theme: Theme, systemDark: boolean): ResolvedTheme {
  if (theme === 'auto') return systemDark ? 'dark' : 'light'
  return theme
}

/**
 * Writes the resolved theme onto the document.
 *
 * Two things, because a theme is not only a palette. The attribute is what
 * every stylesheet reads; the `theme-color` meta is what the browser and the
 * installed shell paint their own chrome with, and it is created if the
 * document does not carry one yet rather than being a required line in
 * index.html - one file owning both halves is what keeps them agreeing.
 *
 * `color-scheme` is deliberately NOT set here. It travels with the tokens
 * (tokens/colors.css), where the same attribute selector that re-points the
 * palette also tells the browser which form controls, scrollbars and default
 * canvas to draw - one rule rather than a stylesheet and a script that have to
 * be kept in step.
 */
export function applyTheme(resolved: ResolvedTheme, doc: Document): void {
  doc.documentElement.setAttribute(THEME_ATTRIBUTE, resolved)

  let meta = doc.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
  if (meta === null) {
    meta = doc.createElement('meta')
    meta.name = 'theme-color'
    doc.head.appendChild(meta)
  }
  meta.content = THEME_COLORS[resolved]
}
