// Which podcast app this hiker listens in (#1690 - Let a hiker pick their
// podcast app once), asked the first time they tap Listen or ↓ on a podcast
// card and changed in More → Settings.
//
// ON THIS PHONE, NEVER A UserPreferences KEY - the same call Settings makes
// for the hiker mode and the default place. It is not worth an account
// round trip, and a second phone may well have a different app on it.
//
// Null until picked, and null is a real answer: the card then asks rather
// than assuming Spotify (the maintainer's frame 1A, poll 2026-09-26).

import { useEffect, useState } from 'react'
import { PODCAST_APPS, type PodcastApp } from './podcasts'

const KEY = 'ourhike:podcast-app'

/** Fired on this window when the choice changes, so a card and the Settings
 *  row on screen together agree without a reload. Other tabs hear the
 *  browser's own `storage` event. */
const CHANGED = 'ourhike:podcast-app-changed'

export function readPodcastApp(): PodcastApp | null {
  try {
    const stored = localStorage.getItem(KEY)
    return (PODCAST_APPS as readonly string[]).includes(stored ?? '')
      ? (stored as PodcastApp)
      : null
  } catch {
    return null
  }
}

export function writePodcastApp(app: PodcastApp | null): void {
  try {
    if (app === null) localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, app)
  } catch {
    // Storage refused: the choice holds for this screen only, and the next
    // card asks again - an extra question, never a wrong app.
  }
  window.dispatchEvent(new Event(CHANGED))
}

export function usePodcastApp(): PodcastApp | null {
  const [app, setApp] = useState<PodcastApp | null>(readPodcastApp)
  useEffect(() => {
    const refresh = () => setApp(readPodcastApp())
    window.addEventListener(CHANGED, refresh)
    window.addEventListener('storage', refresh)
    return () => {
      window.removeEventListener(CHANGED, refresh)
      window.removeEventListener('storage', refresh)
    }
  }, [])
  return app
}
