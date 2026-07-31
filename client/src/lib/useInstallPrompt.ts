// Installing the app to the home screen.
//
// This lives in the app rather than on the landing page, and that placement is
// the whole point: a page can only be installed if IT has the manifest and
// service worker. The landing page at /OurHike/ has neither, so Chrome there
// offers "Add to Home screen", which makes a plain bookmark - it opens in a
// tab with browser chrome, has no service worker, and works offline not at
// all. It looks exactly like a successful install, which is what makes it
// dangerous: someone would carry that bookmark into the woods believing they
// had the app.
//
// `beforeinstallprompt` is Chromium-only. Safari has no install API whatsoever,
// so iOS is told what to tap instead - a button that silently does nothing is
// worse than no button on the one screen whose job is getting someone
// installed.

import { useCallback, useEffect, useState } from 'react'

export type InstallPlatform = 'installed' | 'android' | 'ios' | 'other'

/** The event Chromium fires when a page qualifies for installation. Not in
 *  TypeScript's DOM lib, since it is not a standard. */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export function isStandalone(): boolean {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    // Safari's own non-standard flag, the only signal iOS gives.
    (window.navigator as { standalone?: boolean }).standalone === true
  )
}

export function detectInstallPlatform(): InstallPlatform {
  if (isStandalone()) return 'installed'

  const ua = navigator.userAgent
  if (/iPad|iPhone|iPod/.test(ua)) return 'ios'
  // iPadOS 13+ reports itself as a Mac; the touch points give it away.
  if (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1) return 'ios'
  if (/Android/.test(ua)) return 'android'

  return 'other'
}

export interface InstallState {
  platform: InstallPlatform
  /** True only once the browser has confirmed the page really is installable,
   *  so the button is never shown on a promise this build cannot keep. */
  canPrompt: boolean
  install: () => void
}

export function useInstallPrompt(): InstallState {
  const [platform, setPlatform] = useState<InstallPlatform>(detectInstallPlatform)
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null)

  useEffect(() => {
    const onBeforeInstall = (event: Event) => {
      // Chrome shows its own mini-infobar unless the event is prevented; the
      // app asks at a moment it chooses instead.
      event.preventDefault()
      setDeferred(event as BeforeInstallPromptEvent)
    }
    const onInstalled = () => {
      setDeferred(null)
      setPlatform('installed')
    }

    window.addEventListener('beforeinstallprompt', onBeforeInstall)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstall)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  const install = useCallback(() => {
    if (deferred === null) return
    void deferred.prompt()
    void deferred.userChoice.finally(() => setDeferred(null))
  }, [deferred])

  return { platform, canPrompt: deferred !== null, install }
}
