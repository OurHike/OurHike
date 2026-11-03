/**
 * Which room the Plan tab is showing, and the one line that decides it.
 *
 * WHY THIS IS NOT IN `screens/PlanHome.tsx`, where it was until 2026-09-18.
 * It is two lines about a mode, and App.tsx needs it to decide what to pass
 * the Plan tab - so App imported it from the screen, and a static import is
 * a static import: the whole 13.5 KB of `PlanHome.tsx` and everything it
 * pulls in went into the chunk parsed before a hiker's first frame, to
 * answer `mode === 'long'`.
 *
 * That is exactly what `screens/deferred.ts` exists to prevent, and the Plan
 * screen was already in it - `PlanScreen` is behind `import()` and has been
 * since #1302. The deferral did nothing while this function sat in the
 * screen's own module, which is the shape worth recognising again: a helper
 * that belongs to a screen's VOCABULARY rather than its rendering will be
 * imported by the shell sooner or later, and takes the screen with it.
 *
 * Measured, on this branch with `main` at 57868716 and the build
 * `.github/workflows/build-shells.yml` runs (Node 24, `npm ci`, no `VITE_`
 * variables): moving these two lines took the eager closure
 * `client/scripts/check-build-output.mjs` budgets from 255,946 to the figure
 * in that commit's message, and took `screens/PlanHome.tsx`,
 * `screens/HikeRoom.tsx` and what only they reach out of it entirely.
 */

import type { HikerMode } from './hikerMode'

/**
 * Which room the tab is showing, derived from the app's mode and whether a
 * long hike is picked - never stored, and never a second answer to a
 * question `hikerMode` already answers. `screens/PlanHome.tsx`'s header has
 * the argument for the fork and why it is the app's mode that picks.
 */
export type PlanRoom = 'day' | 'sections'

export function planRoomFor(mode: HikerMode): PlanRoom {
  return mode === 'long' ? 'sections' : 'day'
}
