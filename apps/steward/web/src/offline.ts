// What a claim needs when there is no signal (#1911; PLAN.md, decided 2026-10-24:
// "Claimed sites: detail, plan, checklist and map saved on claiming; photos
// queue on the phone").
//
// Two things are kept in IndexedDB, on this phone only:
// - each claim the phone has opened, as the API last returned it, so the claim
//   screen still opens on the trail (the site's detail and plan are already in
//   the precached sites.json, and the checklist ticks in claims.ts);
// - photos taken while the API could not be reached, until it can.
//
// Signing out or deleting your data clears both: they are someone's work, and a
// shared phone should not keep them.

import { createStore, del, entries, get, set, type UseStore } from 'idb-keyval'
import { ApiError, type ClaimDetail, type PhotoPhase, type StewardApi } from './api'

let store: UseStore | null = null

function db(): UseStore {
  store ??= createStore('campsite-steward', 'offline')
  return store
}

export interface SavedClaim {
  claim: ClaimDetail
  savedAt: string
}

/** A photo waiting for signal. Kept as bytes and a type rather than a Blob:
 *  Safari before 14 could not keep Blobs in IndexedDB, and bytes survive every
 *  structured-clone implementation, the tests' in-memory one included. */
export interface QueuedPhoto {
  id: string
  claimId: string
  phase: PhotoPhase
  point: number | null
  bytes: ArrayBuffer
  type: string
  queuedAt: string
}

export function queuedBlob(queued: QueuedPhoto): Blob {
  return new Blob([queued.bytes], { type: queued.type })
}

export async function saveClaim(claim: ClaimDetail): Promise<void> {
  try {
    await set(
      `claim:${claim.id}`,
      { claim, savedAt: new Date().toISOString() } satisfies SavedClaim,
      db(),
    )
  } catch {
    // No IndexedDB (a private window): the claim simply is not kept.
  }
}

export async function savedClaim(id: string): Promise<SavedClaim | null> {
  try {
    return ((await get(`claim:${id}`, db())) as SavedClaim | undefined) ?? null
  } catch {
    return null
  }
}

let sequence = 0

/** Ids that sort in the order photos were taken, even two in one millisecond:
 *  the time, zero-padded, then a counter, then randomness against two tabs. */
function nextId(): string {
  sequence = (sequence + 1) % 1_000_000
  return `${String(Date.now()).padStart(15, '0')}-${String(sequence).padStart(6, '0')}-${Math.random().toString(36).slice(2, 8)}`
}

export async function queuePhoto(item: {
  claimId: string
  phase: PhotoPhase
  point: number | null
  photo: Blob
}): Promise<QueuedPhoto> {
  const queued: QueuedPhoto = {
    id: nextId(),
    claimId: item.claimId,
    phase: item.phase,
    point: item.point,
    bytes: await item.photo.arrayBuffer(),
    type: item.photo.type || 'image/jpeg',
    queuedAt: new Date().toISOString(),
  }
  await set(`photo:${queued.id}`, queued, db())
  return queued
}

export async function queuedPhotos(claimId?: string): Promise<QueuedPhoto[]> {
  try {
    const all = (await entries(db()))
      .filter(([key]) => String(key).startsWith('photo:'))
      .map(([, value]) => value as QueuedPhoto)
      .sort((a, b) => a.id.localeCompare(b.id))
    return claimId ? all.filter((p) => p.claimId === claimId) : all
  } catch {
    return []
  }
}

/** True for a failure that means "no signal" rather than "the server said no". */
export function isOffline(error: unknown): boolean {
  // fetch rejects with a TypeError when there is no connection at all; 502 and
  // 504 are a gateway between here and the API with no answer. A 503 is the
  // API itself saying no (photo storage not set up), so it is not "no signal".
  if (error instanceof ApiError) return [0, 408, 502, 504].includes(error.status)
  return error instanceof TypeError
}

export interface FlushResult {
  sent: number
  /** Photos the server refused for good (a closed claim, not a photo); dropped, with why. */
  refused: { photo: QueuedPhoto; reason: string }[]
  /** True when the signal went before everything was sent; the rest stays queued. */
  stopped: boolean
}

/**
 * Sends queued photos, oldest first. A photo the server refuses for good is
 * dropped and reported, so one bad photo cannot hold the queue forever; a lost
 * signal stops the run and keeps the rest for next time.
 */
export async function flushPhotos(
  api: StewardApi,
  claimId?: string,
): Promise<FlushResult> {
  const result: FlushResult = { sent: 0, refused: [], stopped: false }
  for (const queued of await queuedPhotos(claimId)) {
    try {
      await api.uploadPhoto(
        queued.claimId,
        queued.phase,
        queued.point,
        queuedBlob(queued),
      )
      await del(`photo:${queued.id}`, db())
      result.sent += 1
    } catch (error) {
      if (
        isOffline(error) ||
        (error instanceof ApiError &&
          (error.status === 401 || error.status === 429 || error.status === 503))
      ) {
        result.stopped = true
        break
      }
      await del(`photo:${queued.id}`, db())
      result.refused.push({ photo: queued, reason: (error as Error).message })
    }
  }
  return result
}

/** Everything kept offline: on sign-out and on deleting your data. */
export async function clearOffline(): Promise<void> {
  try {
    for (const [key] of await entries(db())) await del(key, db())
  } catch {
    // Nothing kept, or no IndexedDB.
  }
}
