import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './design-system/styles.css'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary, ScreenFailed } from './chrome/ErrorBoundary'
import { applyTheme, systemPrefersDark } from './lib/theme'

// Before anything renders, and deliberately not inside a component.
//
// The stored preference is in IndexedDB, which cannot be read synchronously,
// so App only learns it a tick or two in. Painting light for those ticks and
// then flipping is the flash every theme implementation is judged by - and on
// a phone at night it is a bright white frame in the dark, which is worse than
// a cosmetic complaint.
//
// So the OS query answers for the first paint. For everyone on the default
// ('auto', lib/userPreferences.ts) that IS the stored answer and nothing
// changes afterwards; only someone who has overridden their OS sees a
// correction, and only on a cold start.
applyTheme(systemPrefersDark() ? 'dark' : 'light', document)

// The outer net. App has its own boundary around the map, which is where a
// throw is most likely and where losing the other tabs would hurt most - this
// one is for everything that boundary cannot see: the shell's own render,
// onboarding, the reporting flow, and any effect cleanup running above the map
// screen.
//
// It cannot offer the tab bar, because at this level the thing that renders the
// tab bar is what failed. What it does promise is that something is on screen
// with words on it, rather than the blank page React's default unmount leaves.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary
      fallback={() => (
        <ScreenFailed
          what="OurHike"
          // There is no tab bar at this level - the thing that renders it is
          // what failed - so the default "switch tabs" line would be an
          // instruction with nothing to tap. Closing and reopening works
          // offline: the app shell is served by the service worker on the
          // web, and shipped inside the binary in the Capacitor shells
          // (#101, where WKWebView has no service worker at all) - either
          // way nothing on the phone is touched by a restart.
          recovery="Close the app fully and open it again. That works without any signal."
        />
      )}
    >
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
