// Whether the downloaded map will still be there tomorrow, told honestly
// (#190).
//
// The corridor archive lives in IndexedDB, which every browser treats as
// BEST-EFFORT storage until told otherwise: under disk pressure the OS may
// evict an origin's data wholesale, and a hiker whose 314 MB map vanished
// overnight would otherwise see the Downloads screen politely offering a
// fresh download - on a ridge, with no signal, that is a blank map with no
// explanation. This is the failure class of FarOut's 2023 airplane-mode
// incident, and HIKER_SAFETY.md's bar applies: "your map is gone and here
// is why" is materially different from "no map downloaded."
//
// Three small tools, all best-effort by nature and honest about it:
//
//   persistence   navigator.storage.persist() asks the browser to exempt
//                 the origin from eviction. Chrome decides silently from
//                 engagement heuristics, Firefox asks the user, Safari has
//                 its own rules - so the answer is recorded and REPORTED,
//                 never assumed. A denial does not block anything; it
//                 changes what the Downloads screen claims about durability.
//
//   estimate      navigator.storage.estimate() before committing to a
//                 tier, so "this 1.18 GB download may not fit" is said
//                 before the transfer fails at 90% rather than after.
//
//   markers       a per-package "an archive was completed here" note in
//                 localStorage, written on completion and cleared on
//                 delete. If the marker exists and the blob does not, the
//                 archive was lost rather than never fetched - the one
//                 distinction that turns a silent vanish into an honest
//                 sentence. localStorage rather than a second IndexedDB
//                 record because the known real-world losses (WebKit's
//                 2023 incident among them) hit IndexedDB specifically;
//                 full origin eviction takes both, and then the phone
//                 honestly looks like a fresh install - best-effort is
//                 the ceiling here, not a bug.

/** What asking for durable storage came to. `unsupported` is old WebKit and
 *  jsdom; `denied` is a browser that heard the request and said no. */
export type PersistenceState = 'granted' | 'denied' | 'unsupported'

interface StorageManagerLike {
  persist?: () => Promise<boolean>
  persisted?: () => Promise<boolean>
  estimate?: () => Promise<{ quota?: number; usage?: number }>
}

function storageManager(): StorageManagerLike | null {
  const nav = globalThis.navigator as { storage?: StorageManagerLike } | undefined
  return nav?.storage ?? null
}

/**
 * Ask the browser to protect this origin's storage from eviction.
 *
 * Called at download time, not app start, deliberately: Firefox surfaces
 * this as a permission prompt, and a permission asked for in the context of
 * "you just chose to store 314 MB" is answerable, where one at first paint
 * is noise to dismiss. Idempotent from the browser's side - asking again
 * when already granted resolves true without a prompt.
 */
export async function requestPersistence(): Promise<PersistenceState> {
  const storage = storageManager()
  if (storage?.persist === undefined) return 'unsupported'
  try {
    return (await storage.persist()) ? 'granted' : 'denied'
  } catch {
    return 'unsupported'
  }
}

/** The standing answer, without prompting - what persisted() reports today. */
export async function readPersistence(): Promise<PersistenceState> {
  const storage = storageManager()
  if (storage?.persisted === undefined) return 'unsupported'
  try {
    return (await storage.persisted()) ? 'granted' : 'denied'
  } catch {
    return 'unsupported'
  }
}

/**
 * How many bytes the browser thinks this origin can still store, or null
 * where it will not say. An ESTIMATE by specification - browsers round and
 * pad it against fingerprinting - which is why the copy built on it says
 * "about" and warns rather than refuses.
 */
export async function estimateAvailableBytes(): Promise<number | null> {
  const storage = storageManager()
  if (storage?.estimate === undefined) return null
  try {
    const { quota, usage } = await storage.estimate()
    if (typeof quota !== 'number' || typeof usage !== 'number') return null
    return Math.max(0, quota - usage)
  } catch {
    return null
  }
}

/** The marker key, derived from the package key the archive lives under -
 *  the same one-suffix-scheme archiveDownload.ts uses for its records. */
export const completedMarkerKeyFor = (packageKey: string) => `${packageKey}:completed`

/** Records that a whole archive finished here. localStorage can be absent or
 *  throwing (private browsing); losing the marker costs the eviction
 *  message, never the archive, so failures are deliberately silent. */
export function recordCompleted(packageKey: string, at: Date = new Date()): void {
  try {
    localStorage.setItem(completedMarkerKeyFor(packageKey), at.toISOString())
  } catch {
    // Nothing to do - see the docstring.
  }
}

export function clearCompleted(packageKey: string): void {
  try {
    localStorage.removeItem(completedMarkerKeyFor(packageKey))
  } catch {
    // As above.
  }
}

/** When an archive last finished here, or null if none ever did (or the
 *  marker is unreadable - indistinguishable, and treated as the safe case:
 *  no eviction claim is made that cannot be backed). */
export function completedMarker(packageKey: string): Date | null {
  try {
    const stored = localStorage.getItem(completedMarkerKeyFor(packageKey))
    if (stored === null) return null
    const parsed = new Date(stored)
    return Number.isNaN(parsed.getTime()) ? null : parsed
  } catch {
    return null
  }
}
