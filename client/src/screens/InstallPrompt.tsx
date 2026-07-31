// "Put this on your home screen", shown on the Downloads screen.
//
// Downloads is the right place for it: it is where someone is already deciding
// to make the map work without signal, and installing is part of that same
// decision rather than a separate ask. It is also where onboarding sends
// people, so it is seen without being pushed.
//
// Nothing here interrupts. It renders inline above the download, and it
// disappears for good once the app is installed - consistent with the rest of
// the app's refusal to manufacture engagement (features/HIKER_SAFETY.md).

import type { InstallPlatform } from '../lib/useInstallPrompt'
import './downloads.css'

export interface InstallPromptProps {
  platform: InstallPlatform
  canPrompt: boolean
  onInstall: () => void
}

export function InstallPrompt({ platform, canPrompt, onInstall }: InstallPromptProps) {
  // Already installed, or a desktop browser where installing means little for
  // a map meant to be carried.
  if (platform === 'installed' || platform === 'other') return null

  return (
    <section className="install-prompt" aria-labelledby="install-prompt-title">
      <h2 className="install-prompt__title" id="install-prompt-title">
        Add OurHike to your home screen
      </h2>
      <p className="install-prompt__body">
        Installed, it opens like any other app and the downloaded map stays put. A browser
        tab can have its storage cleared without warning.
      </p>

      {platform === 'android' &&
        (canPrompt ? (
          <button type="button" className="downloads__primary" onClick={onInstall}>
            Install OurHike
          </button>
        ) : (
          // The button is shown only once the browser confirms the page really
          // qualifies. Until then these steps are the honest answer, rather
          // than a button that might do nothing.
          <ol className="install-prompt__steps">
            <li>
              Open Chrome&rsquo;s <strong>⋮</strong> menu.
            </li>
            <li>
              Tap <strong>Install app</strong>, or <strong>Add to Home screen</strong>.
            </li>
          </ol>
        ))}

      {platform === 'ios' && (
        <>
          <ol className="install-prompt__steps">
            <li>
              Tap <strong>Share</strong> — the square with an arrow out of it.
            </li>
            <li>
              Scroll down and tap <strong>Add to Home Screen</strong>.
            </li>
          </ol>
          <p className="install-prompt__caveat" role="note">
            On iPhone this has to be done in Safari; other browsers cannot install it. iOS
            can also clear a web app&rsquo;s storage when space runs short, so check the
            map is still here before a trip.
          </p>
        </>
      )}
    </section>
  )
}
