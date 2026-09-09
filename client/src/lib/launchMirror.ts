// What a launch has to know before IndexedDB can answer (#1301).
//
// THE GAP THIS CLOSES. App.tsx used to render nothing - no tab bar, no Today
// header, the page colour and that is all - until two IndexedDB reads had come
// back: the preferences and the hiker mode. The reason was sound: a returning
// hiker must never see a flash of the first-run steps, and the only thing
// that says whether onboarding is done is a record in a store that cannot be
// read synchronously. So the whole tree waited on storage, on every launch,
// for a question whose answer has not changed since the last launch.
//
// SO THE ANSWER IS MIRRORED WHERE A LAUNCH CAN READ IT WITHOUT WAITING.
// `localStorage` is synchronous, and lib/cameraMemory.ts and lib/pace.ts
// already use web storage for exactly this shape of thing - a small value the
// first frame needs. Three fields, chosen because each one decides what the
// first frame IS: whether the steps or the tabs are up, which theme the page
// paints in (main.tsx already answers the OS half of that before React starts;
// this is the hiker's override), and which mode the Today header shows.
//
// WHAT IT IS NOT. IndexedDB stays the record. The mirror is written from the
// record every time the record is read or changed, and read only to choose
// the first frame; the record's own read still runs and overwrites whatever
// the mirror said, a tick later. A phone with no mirror - the first launch
// after this shipped, or storage that was cleared - takes the old path and
// waits, which is slower and never wrong. A mirror that disagrees with the
// record costs one launch a corrected frame, and the write below corrects the
// mirror in the same tick. Nothing else reads it, and nothing in it is a
// safety decision.

import { normaliseHikerMode, type HikerMode } from './hikerMode'
import { THEME_VALUES, type Theme, type UserPreferences } from './userPreferences'

export const LAUNCH_MIRROR_KEY = 'ourhike:launch'

export interface LaunchMirror {
  onboardingCompleted: boolean
  theme: Theme
  hikerMode: HikerMode
}

/** `localStorage`, or null where reaching for it throws - a browser set to
 *  block site data, or a WebView with storage disabled. Null reads as "no
 *  mirror", which is the slow path and the honest one. */
function storage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/**
 * The mirror, or null when there is none worth trusting.
 *
 * Anything that is not the shape below - missing, unparseable, written by a
 * build that spelled it differently - is null, never a guess: a null mirror
 * makes the launch wait for the record, which is the state every launch was
 * in before this existed.
 */
export function readLaunchMirror(): LaunchMirror | null {
  const raw = storage()?.getItem(LAUNCH_MIRROR_KEY)
  if (raw === null || raw === undefined) return null
  try {
    const parsed = JSON.parse(raw) as Partial<Record<keyof LaunchMirror, unknown>> | null
    if (parsed === null || typeof parsed !== 'object') return null
    if (typeof parsed.onboardingCompleted !== 'boolean') return null
    return {
      onboardingCompleted: parsed.onboardingCompleted,
      // The same repair the record gets (lib/preferences.ts's KNOWN_ENUM_VALUES
      // and lib/hikerMode.ts's normaliseHikerMode): a word this build does
      // not know falls back to the default rather than reaching a `match`.
      theme: THEME_VALUES.includes(parsed.theme as Theme)
        ? (parsed.theme as Theme)
        : 'auto',
      hikerMode: normaliseHikerMode(parsed.hikerMode),
    }
  } catch {
    return null
  }
}

/** Writes the mirror from the record. Best-effort: a write that fails (quota,
 *  private mode) costs the next launch the fast path and nothing else. */
export function writeLaunchMirror(
  preferences: Pick<UserPreferences, 'onboarding_completed' | 'theme'>,
  hikerMode: HikerMode,
): void {
  const mirror: LaunchMirror = {
    onboardingCompleted: preferences.onboarding_completed,
    theme: preferences.theme,
    hikerMode,
  }
  try {
    storage()?.setItem(LAUNCH_MIRROR_KEY, JSON.stringify(mirror))
  } catch {
    // See above.
  }
}

/** Drops the mirror, so the next launch reads the record before it paints.
 *  For whatever resets the record outside the shell - a test, a reset flow -
 *  because a mirror the record no longer agrees with is the one case that
 *  costs a frame. */
export function forgetLaunchMirror(): void {
  try {
    storage()?.removeItem(LAUNCH_MIRROR_KEY)
  } catch {
    // Nothing to forget where nothing could be written.
  }
}
