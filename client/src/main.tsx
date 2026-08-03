import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './design-system/styles.css'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary, ScreenFailed } from './chrome/ErrorBoundary'

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
    <ErrorBoundary fallback={() => <ScreenFailed what="OurHike" />}>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
