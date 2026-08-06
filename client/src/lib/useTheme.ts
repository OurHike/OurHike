// React binding for lib/theme.ts, shaped like lib/useFinePointer.ts: read the
// media query once, subscribe to it, unsubscribe on teardown.
//
// The subscription is the point. A hiker on 'auto' whose phone flips to dark
// at sunset - which is when a phone usually does it, and when this app is most
// likely to be out - should see the app follow within the same breath, not at
// the next cold start.

import { useEffect, useState } from 'react'
import { applyTheme, DARK_MEDIA_QUERY, resolveTheme, systemPrefersDark } from './theme'
import type { ResolvedTheme } from './theme'
import type { Theme } from './userPreferences'

/** Whether the OS wants a dark interface. Re-evaluates when it changes. */
export function useSystemDark(): boolean {
  const [systemDark, setSystemDark] = useState(systemPrefersDark)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return

    const query = window.matchMedia(DARK_MEDIA_QUERY)
    const update = (event: MediaQueryListEvent) => setSystemDark(event.matches)

    // Re-read on mount as well as on change, the same way useFinePointer.ts
    // does: the first render used whatever the query said before effects ran,
    // and under StrictMode's remount that read is one render stale.
    setSystemDark(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  return systemDark
}

/**
 * Resolves the preference against the OS, writes it to the document, and hands
 * back what got drawn.
 *
 * Returned as well as applied because the map is not CSS. Everything in the
 * chrome follows the `data-theme` attribute through the design tokens, but the
 * canvas is WebGL and its colours are paint properties on a style
 * (map/style.ts) - so the shell has to be able to pass the answer down as a
 * prop, not only stamp it on the document.
 */
export function useTheme(theme: Theme): ResolvedTheme {
  const systemDark = useSystemDark()
  const resolved = resolveTheme(theme, systemDark)

  useEffect(() => {
    applyTheme(resolved, document)
  }, [resolved])

  return resolved
}
