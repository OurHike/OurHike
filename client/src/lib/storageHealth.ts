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
 *
 * A DELETE THIS APP PERFORMED IS COUNTED AS FREE, EVEN WHILE THE BROWSER STILL
 * COUNTS IT AS USED (#554).
 *
 * Measured in Chromium via `scripts/storage-probe/run.mjs --reclaim`, storing
 * 200 MiB as the seven segment records a real download leaves and deleting them
 * through `deleteArchive`:
 *
 *   usage after storing   209,717,908
 *   delete completed in   10 ms, and the archive is unreadable immediately
 *   usage 10 s later      209,718,780   (unmoved)
 *   usage after a reload  209,718,780   (unmoved)
 *
 * So the bytes are gone and the accounting is not - and it is not a flush or a
 * transaction boundary that would settle on its own, because a page load does
 * not shift it either. That distinction decides where the fix belongs: nothing
 * `deleteArchive` can do reclaims harder, because there is nothing left to
 * reclaim, so the room check has to stop refusing on a figure it can prove is
 * stale.
 *
 * It has to stop, rather than merely being allowed to: "delete this sheet and
 * download again" is the app's own printed remedy - DownloadCard's locked detail
 * picker says exactly that, and #544's refusal message says freeing up space
 * makes room. Refusing straight afterwards, on the bytes the hiker just freed
 * because they were told to, is the app disbelieving its own instruction. On a
 * trailhead connection that is a wasted trip.
 *
 * THE CREDIT CANNOT DOUBLE-COUNT, which is the reason it is expressed as it is
 * rather than as a flat addition. It is only ever the part of the released bytes
 * the accounting has NOT yet given back: as `usage` falls, the credit falls with
 * it, and once the browser has caught up the credit is zero and this returns the
 * plain estimate again. A browser that reclaims promptly gets no credit at all
 * and needs none.
 */
export async function estimateAvailableBytes(): Promise<number | null> {
  const storage = storageManager()
  if (storage?.estimate === undefined) return null
  try {
    const { quota, usage } = await storage.estimate()
    if (typeof quota !== 'number' || typeof usage !== 'number') return null
    return Math.max(0, quota - usage + staleReleasedBytes(usage))
  } catch {
    return null
  }
}

/**
 * What the browser currently reports as used, unadjusted - the raw number the
 * credit above is measured against.
 *
 * Separate from `estimateAvailableBytes` on purpose: crediting a release inside
 * the function that records the baseline would make the baseline depend on the
 * credit, and the note would decay against itself.
 */
export async function estimateUsageBytes(): Promise<number | null> {
  const storage = storageManager()
  if (storage?.estimate === undefined) return null
  try {
    const { usage } = await storage.estimate()
    return typeof usage === 'number' ? usage : null
  } catch {
    return null
  }
}

/** Where the released-bytes note lives. One key for the origin, not one per
 *  package: what it describes is the origin's quota accounting, and two deletes
 *  in a row are one lag to correct for. */
export const RELEASED_KEY = 'ourhike:released-bytes'

/**
 * How long a release stays creditable.
 *
 * Not a guess about when the browser catches up - the measurement above says it
 * may never, inside a session or across a reload. It is a bound on how wrong
 * this can be: a note that outlived its truth (a browser restart reclaimed the
 * space and re-counted it, another tab filled the origin) stops being applied
 * within a day rather than for the life of the installation. A stale credit
 * makes a download start and then run out partway, which since #553 keeps every
 * byte that arrived and says something true - so the cost of being wrong here is
 * bounded, and it is smaller than the cost of refusing a download that fits.
 */
const RELEASE_TTL_MS = 24 * 60 * 60 * 1000

interface ReleaseNote {
  /** How many bytes were deleted. */
  bytes: number
  /** What `usage` still reported immediately afterwards - the baseline the
   *  credit decays against. */
  usageAfter: number
  /** When, so the note can expire. */
  at: number
}

function readRelease(): ReleaseNote | null {
  try {
    const raw = localStorage.getItem(RELEASED_KEY)
    if (raw === null) return null
    const note = JSON.parse(raw) as Partial<ReleaseNote>
    if (
      typeof note.bytes !== 'number' ||
      typeof note.usageAfter !== 'number' ||
      typeof note.at !== 'number'
    )
      return null
    return { bytes: note.bytes, usageAfter: note.usageAfter, at: note.at }
  } catch {
    return null
  }
}

/**
 * The part of a recent release the browser's `usage` has not yet given back.
 *
 * Zero once it has, zero once the note expires, and zero when there is no note
 * - so every caller that has not deleted anything sees the plain estimate.
 */
function staleReleasedBytes(usage: number): number {
  const note = readRelease()
  if (note === null) return 0
  if (Date.now() - note.at > RELEASE_TTL_MS) {
    clearReleased()
    return 0
  }
  // How much of the release the accounting HAS returned, floored at zero so
  // that usage rising for an unrelated reason cannot inflate the credit.
  const returned = Math.max(0, note.usageAfter - usage)
  return Math.max(0, note.bytes - returned)
}

/**
 * Notes that this app deleted `bytes` and that the browser still reported
 * `usageAfter` immediately afterwards.
 *
 * Recorded in localStorage for the reason the completion marker is: it has to
 * outlive the IndexedDB records it describes, and it must still be readable in
 * exactly the situations where IndexedDB is not. Silent on failure for the same
 * reason too - losing the note costs a refusal that could have been avoided,
 * never any data.
 */
export function recordReleased(bytes: number, usageAfter: number): void {
  if (bytes <= 0) return
  try {
    const note: ReleaseNote = { bytes, usageAfter, at: Date.now() }
    localStorage.setItem(RELEASED_KEY, JSON.stringify(note))
  } catch {
    // See the docstring.
  }
}

export function clearReleased(): void {
  try {
    localStorage.removeItem(RELEASED_KEY)
  } catch {
    // See recordReleased.
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
