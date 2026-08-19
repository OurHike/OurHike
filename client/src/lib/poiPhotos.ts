// The hiker's own photos of a place: rung 1 of POI_PHOTOS.md's precedence
// ladder, stored on the device and nowhere else.
//
// "Private is not a setting to find; it is what happens." Nothing in this
// module touches the network, and nothing else in the app reads these keys.
// Sharing, if it ever happens, is a separate deliberate act on a separate
// path (#576/#577) - this store is the memento, not the pipeline.
//
// One IndexedDB key per POI, holding every photo of that place plus the
// hiker's choice of which one the card shows. One key rather than one per
// photo because every mutation here is add/remove/choose against a single
// place, and idb-keyval's `update` makes that a single read-modify-write in
// one transaction - the same shape outbox.ts adopted after #288, where four
// mutators sharing a key through separate get/set calls could interleave
// and lose whichever wrote first.
//
// What a photo record holds is deliberately small:
//   - the 640px JPEG the card renders, GPS-free BY CONSTRUCTION - it came
//     out of reportPhoto.ts's canvas re-encode, so it is a new file that
//     never had EXIF rather than one it was stripped from
//   - the capture date, read from the ORIGINAL file before the re-encode
//     destroyed it (lib/exifDate.ts), or null when the original had none
//   - the date it was added, which is the fallback the card dates it by
//   - which affordance it came through, because #573's honesty line differs:
//     a photo picked from the library has its original in that library, and
//     a photo taken through the app's camera may exist nowhere else

import { del, get, keys, update } from 'idb-keyval'

/**
 * The longest edge of a stored waypoint photo.
 *
 * 640 is POI_PHOTOS.md's number, fixed so there is one code path for what
 * the card's slot renders whatever the source: the Commons and ATC fetches
 * ask Wikimedia's and Drive's thumbnailers for 640px renderings, and the
 * hiker's own photos are resized to the same size on the device. The slot is
 * 264 CSS pixels wide, so 640 covers a DPR-2 phone with headroom and never
 * stores a 12 MB camera original to fill it.
 */
export const CARD_PHOTO_EDGE = 640

export const POI_PHOTOS_PREFIX = 'ourhike:my-photos:'

/** Which affordance the photo came through - the fact #573's wording turns on. */
export type OwnPhotoSource = 'camera' | 'library'

export interface OwnPhoto {
  id: string
  /** The 640px rendering, and the only bytes this app holds. */
  blob: Blob
  /** EXIF capture date of the original, "YYYY-MM-DD", or null. */
  taken: string | null
  /** The day it was kept, "YYYY-MM-DD" - the dating fallback. */
  added: string
  source: OwnPhotoSource
}

interface PoiPhotoRecord {
  photos: OwnPhoto[]
  /** The photo the hiker picked for the card, when they have picked one. */
  chosenId?: string
}

function keyFor(poiId: string): string {
  return `${POI_PHOTOS_PREFIX}${poiId}`
}

/** Today as "YYYY-MM-DD", in the device's own calendar - the date a hiker
 *  would say they added the photo, not UTC's opinion of it. */
function today(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

/**
 * Keep a photo of this place. The write IS the keep: the review step before
 * this holds everything in memory, so a discard is nothing-was-written
 * rather than written-then-deleted (#571).
 */
export async function addOwnPhoto(
  poiId: string,
  photo: { blob: Blob; taken: string | null; source: OwnPhotoSource },
): Promise<OwnPhoto> {
  const record: OwnPhoto = {
    id: crypto.randomUUID(),
    blob: photo.blob,
    taken: photo.taken,
    added: today(),
    source: photo.source,
  }
  await update<PoiPhotoRecord>(keyFor(poiId), (stored) => ({
    ...(stored ?? {}),
    photos: [...(stored?.photos ?? []), record],
  }))
  return record
}

/**
 * Every photo of this place, in the order the card shows them: the chosen
 * one first when a choice was made, then most recent first - "a hiker who
 * photographs a shelter twice a year apart usually wants the new one, but
 * they choose, and the choice sticks" (POI_PHOTOS.md).
 *
 * Recency is the capture date where the original carried one, else the day
 * it was added - the same date the card prints, so the order and the label
 * cannot disagree about which photo is newer.
 */
export async function listOwnPhotos(poiId: string): Promise<OwnPhoto[]> {
  const stored = await get<PoiPhotoRecord>(keyFor(poiId))
  if (stored === undefined || stored.photos.length === 0) return []
  const byRecency = [...stored.photos].sort((a, b) =>
    (b.taken ?? b.added).localeCompare(a.taken ?? a.added),
  )
  if (stored.chosenId === undefined) return byRecency
  const chosen = byRecency.find((photo) => photo.id === stored.chosenId)
  if (chosen === undefined) return byRecency
  return [chosen, ...byRecency.filter((photo) => photo !== chosen)]
}

/** Make this photo the one the card shows. The choice sticks until the
 *  photo is deleted or the hiker chooses again. */
export async function chooseOwnPhoto(poiId: string, id: string): Promise<void> {
  await update<PoiPhotoRecord>(keyFor(poiId), (stored) => {
    if (stored === undefined) return { photos: [] }
    if (!stored.photos.some((photo) => photo.id === id)) return stored
    return { ...stored, chosenId: id }
  })
}

/**
 * Delete one photo. Deleting the chosen one clears the choice - the order
 * falls back to recency rather than to a dangling id - and deleting the
 * last one removes the key outright, so the card falls back down the
 * ladder and storage holds nothing for a place with no photos.
 */
export async function deleteOwnPhoto(poiId: string, id: string): Promise<void> {
  let empty = false
  await update<PoiPhotoRecord>(keyFor(poiId), (stored) => {
    if (stored === undefined) return { photos: [] }
    const photos = stored.photos.filter((photo) => photo.id !== id)
    empty = photos.length === 0
    const next: PoiPhotoRecord = { photos }
    if (stored.chosenId !== undefined && stored.chosenId !== id) {
      next.chosenId = stored.chosenId
    }
    return next
  })
  if (empty) await del(keyFor(poiId))
}

/**
 * What the hiker's photos cost, for storage management. Measured by summing
 * the stored blobs rather than estimated - packages.ts's "sizes are
 * measured, never estimates" rule, kept cheap by the fact POI_PHOTOS.md
 * already states: a thru-hiker who photographs 200 places holds ~9 MB, so
 * walking every record is walking a small list.
 */
export async function ownPhotoUsage(): Promise<{ count: number; bytes: number }> {
  const allKeys = await keys()
  let count = 0
  let bytes = 0
  for (const key of allKeys) {
    if (typeof key !== 'string' || !key.startsWith(POI_PHOTOS_PREFIX)) continue
    const stored = await get<PoiPhotoRecord>(key)
    if (stored === undefined) continue
    for (const photo of stored.photos) {
      count += 1
      bytes += photo.blob.size
    }
  }
  return { count, bytes }
}
