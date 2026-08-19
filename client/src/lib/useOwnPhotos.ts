// The card-side view of lib/poiPhotos.ts: the hiker's own photos of the
// place a card is showing, as object URLs the media box can render, plus
// the three verbs the card offers - keep, choose, remove.
//
// Object URLs are owned here because they are the leak-prone part. Every
// stored blob the card shows needs one, every reload mints fresh ones, and
// a URL nobody revokes pins its blob in memory for the life of the tab -
// on a phone that took two hundred photos, that is the whole store. So the
// hook keeps the list it minted, revokes it on every replacement and on
// unmount, and nothing else in the card touches createObjectURL.
//
// Failure means absence, silently. This store is an enhancement on a card
// that must render without it - a browser with no IndexedDB, a first visit,
// a storage error mid-read all land on "no own photos", which draws exactly
// the card that shipped before this feature existed. That is the ladder's
// own rule: nothing degrades, the slot falls through to the next rung.

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  addOwnPhoto,
  chooseOwnPhoto,
  deleteOwnPhoto,
  listOwnPhotos,
  type OwnPhotoSource,
} from './poiPhotos'

export interface OwnCardPhoto {
  id: string
  /** An object URL for the stored 640px rendering. */
  url: string
  /** The date the card prints, "YYYY-MM-DD": capture where the original
   *  carried one, else the day it was added. Never absent - dating the
   *  photo is the honesty rule, and the added date always exists. */
  taken: string
  source: OwnPhotoSource
}

export interface OwnPhotos {
  /** Card order: the chosen one first when a choice was made, then most
   *  recent first. The first entry is what the card's slot shows. */
  photos: OwnCardPhoto[]
  add(photo: { blob: Blob; taken: string | null; source: OwnPhotoSource }): Promise<void>
  choose(id: string): Promise<void>
  remove(id: string): Promise<void>
}

export function useOwnPhotos(poiId: string): OwnPhotos {
  const [photos, setPhotos] = useState<OwnCardPhoto[]>([])
  // Bumped by every mutation so the listing effect re-runs; the effect owns
  // the URLs, so minting and revoking stay in one place.
  const [version, setVersion] = useState(0)
  const urls = useRef<string[]>([])

  useEffect(() => {
    let cancelled = false

    void listOwnPhotos(poiId)
      .then((stored) => {
        if (cancelled) return
        const next = stored.map((photo) => ({
          id: photo.id,
          url: URL.createObjectURL(photo.blob),
          taken: photo.taken ?? photo.added,
          source: photo.source,
        }))
        // Replace, THEN revoke what was replaced. Revoking first - say in
        // this effect's own cleanup - would break the URLs the card is
        // still rendering for the frames between a mutation and its
        // reload, and the img's onError would read that as a photo failing.
        const replaced = urls.current
        urls.current = next.map((photo) => photo.url)
        setPhotos(next)
        for (const url of replaced) URL.revokeObjectURL(url)
      })
      .catch(() => {
        // No IndexedDB, or a read that failed: the card renders without
        // rung 1, which is the card as it was.
        if (!cancelled) setPhotos([])
      })

    return () => {
      cancelled = true
    }
  }, [poiId, version])

  // Unmount is the one time everything minted gets revoked - separate from
  // the listing effect on purpose, so a reload never revokes what is still
  // on screen.
  useEffect(
    () => () => {
      for (const url of urls.current) URL.revokeObjectURL(url)
      urls.current = []
    },
    [],
  )

  const reload = useCallback(() => setVersion((v) => v + 1), [])

  const add = useCallback(
    async (photo: { blob: Blob; taken: string | null; source: OwnPhotoSource }) => {
      await addOwnPhoto(poiId, photo)
      reload()
    },
    [poiId, reload],
  )

  const choose = useCallback(
    async (id: string) => {
      // Reordered in state BEFORE the store round-trip, so the card that
      // just offered "show this on the card" shows it now rather than
      // flashing whichever photo was first while the write and re-list
      // land. The store's own ordering arrives behind it and agrees - the
      // reload is confirmation, not the mechanism.
      setPhotos((previous) => {
        const chosen = previous.find((photo) => photo.id === id)
        if (chosen === undefined) return previous
        return [chosen, ...previous.filter((photo) => photo !== chosen)]
      })
      await chooseOwnPhoto(poiId, id)
      reload()
    },
    [poiId, reload],
  )

  const remove = useCallback(
    async (id: string) => {
      await deleteOwnPhoto(poiId, id)
      reload()
    },
    [poiId, reload],
  )

  return { photos, add, choose, remove }
}
