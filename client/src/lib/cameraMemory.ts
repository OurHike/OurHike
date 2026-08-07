// Where the hiker had the map, kept across a reload (#311).
//
// The shell already remembers the camera in React state, so a trip through
// another tab comes back to the same view. A reload is the case that state
// cannot cover, and the app has one it does not control: a new service worker
// takes over and the page restarts. lib/useAppUpdate.ts now waits for a
// moment when that costs nothing visible - but "nothing visible" is not
// "nothing": the map still comes back on the whole corridor, which is not
// where anyone left it.
//
// WHY SESSION STORAGE, WHICH IS THE WHOLE DESIGN
//
// This is a memory of what the hiker is LOOKING AT, not a preference. It has
// to survive a reload of this tab and it must not survive the tab closing:
// opening the app fresh belongs on the whole trail (App.tsx's CORRIDOR_BOUNDS
// and the note above it), and restoring last Tuesday's view over Georgia to
// someone starting in Maine would be a confident answer to a question nobody
// asked. `sessionStorage` is exactly that lifetime, which is why the
// preferences in lib/preferences.ts - real, durable choices - live in
// IndexedDB instead.
//
// Everything here is best-effort. Private browsing, a full quota and a
// hardened embedder all make storage throw on ACCESS rather than on write, so
// every path is guarded and every failure means the same harmless thing: the
// map opens on the corridor, exactly as it did before this file existed.

/** One camera position, the shape App.tsx keeps and MapView opens on. */
export interface RememberedCamera {
  center: [number, number]
  zoom: number
}

export const CAMERA_MEMORY_KEY = 'ourhike:camera'

/** Guarded because merely READING `window.sessionStorage` throws in a
 *  hardened embedder, before any get or set is attempted. */
function storage(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

/**
 * The view to open on, or `null` for the corridor.
 *
 * Validated field by field rather than cast, and not out of ceremony: this
 * value is handed straight to MapLibre as an opening camera, and a NaN zoom
 * or a one-element centre from a half-written entry is a map that fails to
 * build at all. A shape that does not convince goes back as null, which is a
 * state the caller already handles on every first run.
 */
export function readCamera(): RememberedCamera | null {
  const raw = storage()?.getItem(CAMERA_MEMORY_KEY)
  if (raw === null || raw === undefined) return null

  try {
    const parsed = JSON.parse(raw) as Partial<RememberedCamera>
    const { center, zoom } = parsed
    if (!Array.isArray(center) || center.length !== 2) return null
    if (!center.every((n) => typeof n === 'number' && Number.isFinite(n))) return null
    if (typeof zoom !== 'number' || !Number.isFinite(zoom)) return null
    return { center: [center[0], center[1]], zoom }
  } catch {
    return null
  }
}

/** Remembers the view. Silent on failure - see the header. */
export function writeCamera(camera: RememberedCamera): void {
  try {
    storage()?.setItem(CAMERA_MEMORY_KEY, JSON.stringify(camera))
  } catch {
    // A quota error here costs the view across one reload and nothing else.
  }
}
