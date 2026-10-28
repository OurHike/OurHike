// What a claim needs when there is no signal (#1911; PLAN.md, decided 2026-10-24:
// "Claimed sites: detail, plan, checklist and map saved on claiming; photos
// queue on the phone").
//
// Two things are kept in IndexedDB, on this phone only, each under the
// account it belongs to:
// - each claim the phone has opened that this account is on the crew of, as
//   the API last returned it, so the claim screen still opens on the trail
//   (the site's detail and plan are already in the precached sites.json, and
//   the checklist ticks in claims.ts);
// - photos taken while the API could not be reached, until it can, and photos
//   the API refused, until their owner saves or discards them.
//
// Under the account, because a session can end without anybody signing out
// (a token revoked or refused): nothing here is then deleted, since it may be
// photos nobody else has, but the next account to sign in on the phone
// neither sees it nor sends it (the adversarial review's third pass, P3,
// 2026-10-27). Signing out, or deleting your data, deletes your own.
//
// NOTHING A PHOTO'S OWNER HAS NOT SEEN IS DELETED. Before the third pass
// (P1), a photo the API refused was dropped with one line of explanation, so
// a volunteer who worked on day 14 with no signal and found signal on day 15,
// after the claim had run out, lost every before and after photo they took.

import { createStore, del, entries, get, set, type UseStore } from 'idb-keyval'
import { ApiError, type ClaimDetail, type PhotoPhase, type RemediationApi } from './api'

let store: UseStore | null = null

function db(): UseStore {
  store ??= createStore('site-remediation', 'offline')
  return store
}

const claimKey = (userId: string, claimId: string) => `${userId}/claim/${claimId}`
const photoKey = (userId: string, photoId: string) => `${userId}/photo/${photoId}`

const CHANGED = 'site-remediation-offline'

/** Tells every screen showing the queue that it changed (a send, a discard). */
function changed(): void {
  window.dispatchEvent(new Event(CHANGED))
}

/** Fired when the sign-in is renewed after failing for lack of signal (account.tsx). */
export const SIGNAL_BACK = 'site-remediation-signal-back'

export function onOfflineChange(listener: () => void): () => void {
  window.addEventListener(CHANGED, listener)
  return () => window.removeEventListener(CHANGED, listener)
}

export interface SavedClaim {
  claim: ClaimDetail
  savedAt: string
}

/** Why the API said no to a queued photo, kept with it. */
export interface Refusal {
  status: number
  reason: string
  at: string
}

/** A photo waiting for signal. Kept as bytes and a type rather than a Blob:
 *  Safari before 14 could not keep Blobs in IndexedDB, and bytes survive every
 *  structured-clone implementation, the tests' in-memory one included. */
export interface QueuedPhoto {
  id: string
  userId: string
  claimId: string
  phase: PhotoPhase
  point: number | null
  bytes: ArrayBuffer
  type: string
  queuedAt: string
  /** For a before or after photo: the id of the photo in its slot when this
   *  one was taken, or 'nothing'. Sent with it, so a slot someone has
   *  photographed since is not overwritten by an older photo (the API
   *  answers 412, and the photo is kept as refused). */
  replaces?: string
  /** Set when the API refused it: it is no longer sent, only kept. */
  refused?: Refusal
}

export function queuedBlob(queued: QueuedPhoto): Blob {
  return new Blob([queued.bytes], { type: queued.type })
}

/** Keeps a claim for offline, if this account is on its crew. A claim seen
 *  as a reviewer holds other people's names and notes and has no use on the
 *  trail, so it is not kept (the third pass's P6). */
export async function saveClaim(userId: string, claim: ClaimDetail): Promise<void> {
  try {
    if (claim.crew.some((member) => member.you)) {
      await set(
        claimKey(userId, claim.id),
        { claim, savedAt: new Date().toISOString() } satisfies SavedClaim,
        db(),
      )
    } else {
      await del(claimKey(userId, claim.id), db())
    }
  } catch {
    // No IndexedDB (a private window): the claim simply is not kept.
  }
}

export async function savedClaim(userId: string, id: string): Promise<SavedClaim | null> {
  try {
    return ((await get(claimKey(userId, id), db())) as SavedClaim | undefined) ?? null
  } catch {
    return null
  }
}

let sequence = 0

/** Ids that sort in the order photos were taken, even two in one millisecond:
 *  the time, zero-padded, then a counter, then randomness against two tabs.
 *  Sent with the photo, so the API can tell a repeat from a new one: given
 *  before a photo's first send, and kept if that send ends in the queue, so a
 *  photo whose first answer was lost is still recognised. */
export function newPhotoId(): string {
  sequence = (sequence + 1) % 1_000_000
  return `${String(Date.now()).padStart(15, '0')}-${String(sequence).padStart(6, '0')}-${Math.random().toString(36).slice(2, 8)}`
}

/** Asks the browser not to clear this site's storage when it runs short, or
 *  after Safari's seven days without a visit. A browser may say no, or ask the
 *  person; either way the photo is kept as well as the browser allows. */
async function keepStorage(): Promise<void> {
  try {
    await navigator.storage?.persist?.()
  } catch {
    // Not offered here.
  }
}

export async function queuePhoto(item: {
  /** The id its first send went under, if it had one (newPhotoId). */
  id?: string
  userId: string
  claimId: string
  phase: PhotoPhase
  point: number | null
  /** What was in the slot when it was taken (QueuedPhoto.replaces). */
  replaces?: string
  photo: Blob
}): Promise<QueuedPhoto> {
  const queued: QueuedPhoto = {
    id: item.id ?? newPhotoId(),
    userId: item.userId,
    claimId: item.claimId,
    phase: item.phase,
    point: item.point,
    ...(item.replaces && item.point !== null ? { replaces: item.replaces } : {}),
    bytes: await item.photo.arrayBuffer(),
    type: item.photo.type || 'image/jpeg',
    queuedAt: new Date().toISOString(),
  }
  await set(photoKey(item.userId, queued.id), queued, db())
  await dropWaiting(item.userId, item.claimId, item.phase, item.point, queued.id)
  void keepStorage()
  changed()
  return queued
}

/**
 * Forgets photos still waiting for one before or after slot, which a newer
 * photo of that slot has replaced: sent later, an older one would replace the
 * newer on the server. Refused photos are kept regardless. Extras have no
 * slot, so none is ever replaced.
 */
export async function dropWaiting(
  userId: string,
  claimId: string,
  phase: PhotoPhase,
  point: number | null,
  keep?: string,
): Promise<void> {
  if (point === null) return
  for (const queued of await queuedPhotos(userId, claimId)) {
    if (
      !queued.refused &&
      queued.id !== keep &&
      queued.phase === phase &&
      queued.point === point
    )
      await del(photoKey(userId, queued.id), db())
  }
  changed()
}

/** Every photo this account has kept on the phone, oldest first: waiting and refused. */
export async function queuedPhotos(
  userId: string,
  claimId?: string,
): Promise<QueuedPhoto[]> {
  try {
    const prefix = `${userId}/photo/`
    const all = (await entries(db()))
      .filter(([key]) => String(key).startsWith(prefix))
      .map(([, value]) => value as QueuedPhoto)
      .sort((a, b) => a.id.localeCompare(b.id))
    return claimId ? all.filter((p) => p.claimId === claimId) : all
  } catch {
    return []
  }
}

export const waitingPhotos = (photos: QueuedPhoto[]) => photos.filter((p) => !p.refused)
export const refusedPhotos = (photos: QueuedPhoto[]) => photos.filter((p) => p.refused)

/** A refused photo goes back in the queue, for its owner's "Try again": sent
 *  as it is this time, over a newer photo of its point if there is one,
 *  since its owner has seen why it was refused. */
export async function retryPhoto(queued: QueuedPhoto): Promise<void> {
  const { refused: _, replaces: __, ...waiting } = queued
  await set(photoKey(queued.userId, queued.id), waiting, db())
  changed()
}

/** Gone from the phone: only ever at its owner's asking. */
export async function discardPhoto(queued: QueuedPhoto): Promise<void> {
  await del(photoKey(queued.userId, queued.id), db())
  changed()
}

/** True for a failure that means "no signal" rather than "the server said no". */
export function isOffline(error: unknown): boolean {
  // fetch rejects with a TypeError when there is no connection at all; 502 and
  // 504 are a gateway between here and the API with no answer. A 503 is the
  // API itself saying no (photo storage not set up), so it is not "no signal".
  if (error instanceof ApiError) return [0, 408, 502, 504].includes(error.status)
  return error instanceof TypeError
}

/** Answers that say "not now" rather than "not this": the photo stays waiting.
 *  401 is a sign-in to renew, 429 a limit that passes, any 5xx the server's
 *  own trouble. */
function notNow(error: unknown): boolean {
  if (!(error instanceof ApiError)) return true
  return isOffline(error) || [401, 429].includes(error.status) || error.status >= 500
}

/** Answers about the claim rather than the photo (no longer the crew's, no
 *  longer open, full): every other photo for that claim would get the same. */
const ABOUT_THE_CLAIM = [403, 404, 409]

export interface FlushResult {
  sent: number
  /** Photos the API refused in this run; kept on the phone, marked, not sent again. */
  refused: QueuedPhoto[]
  /** True when the run stopped with photos still waiting, for signal or a sign-in. */
  stopped: boolean
}

let running: Promise<unknown> = Promise.resolve()

/**
 * Sends this account's waiting photos, oldest first. One run at a time: the
 * screen opening, the phone coming back online and "Send now" can all ask at
 * once, and before the third pass (P2) two runs sent one photo twice. A run
 * that waited reads the queue afresh, so it sends only what is still waiting.
 */
export function flushPhotos(
  api: RemediationApi,
  userId: string,
  claimId?: string,
): Promise<FlushResult> {
  const run = running.then(() => flushNow(api, userId, claimId))
  running = run.catch(() => undefined)
  return run
}

async function flushNow(
  api: RemediationApi,
  userId: string,
  claimId?: string,
): Promise<FlushResult> {
  const result: FlushResult = { sent: 0, refused: [], stopped: false }
  const closed = new Map<string, Refusal>()
  for (const queued of waitingPhotos(await queuedPhotos(userId, claimId))) {
    let refusal = closed.get(queued.claimId)
    if (!refusal) {
      try {
        // The queue's id goes with it, so a photo whose answer was lost is
        // recognised when it is sent again rather than stored twice.
        await api.uploadPhoto(
          queued.claimId,
          queued.phase,
          queued.point,
          queuedBlob(queued),
          {
            clientId: queued.id,
            replaces: queued.replaces,
          },
        )
        await del(photoKey(userId, queued.id), db())
        result.sent += 1
        continue
      } catch (error) {
        if (notNow(error)) {
          result.stopped = true
          break
        }
        const { status, message } = error as ApiError
        refusal = { status, reason: message, at: new Date().toISOString() }
        if (ABOUT_THE_CLAIM.includes(status)) closed.set(queued.claimId, refusal)
      }
    }
    const kept = { ...queued, refused: refusal }
    await set(photoKey(userId, queued.id), kept, db())
    result.refused.push(kept)
  }
  changed()
  return result
}

/** Everything this account kept on the phone: on sign-out and on deleting your data. */
export async function clearOffline(userId: string): Promise<void> {
  try {
    const prefix = `${userId}/`
    for (const [key] of await entries(db()))
      if (String(key).startsWith(prefix)) await del(key, db())
  } catch {
    // Nothing kept, or no IndexedDB.
  }
  changed()
}
