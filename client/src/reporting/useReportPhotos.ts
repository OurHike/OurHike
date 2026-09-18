// The photos a report carries, as picked: one state machine per tile, shared
// by the long form and the report window's receipt (#1439, D17; #1563).
//
// WHAT THIS REPLACES. The long form owned this - the picks, the shrink on
// pick, the thumbnails and their release - and the receipt had no photos at
// all, though features/REPORT_A_PROBLEM.md step 5 had promised them there
// ("a note, and photos, on the receipt"). The maintainer asked for them
// (2026-09-18: "add the ability to add pictures above the note"), and a
// second copy of the machine would have been the second copy of the focus
// trap over again. So the hook is the machine and reporting/PhotoTiles.tsx
// is the row of tiles; a surface renders the tiles and reads `ready`.
//
// **THE RACE IS GONE BY CONSTRUCTION, not by a token.** It used to be one
// `photo` and a `livePick` ref: pick A (a slow HEIC), then B before it
// finished, and B attached first, then A resolved and overwrote it - so the
// hiker sent the photo they believed they had replaced (#657). Each pick
// owns a tile, keyed by its own id, so nothing can land on top of anything:
// a slow first pick resolves into ITS tile, whatever has arrived since.
//
// **A FAILURE COSTS ITS OWN TILE AND NOTHING ELSE.** The entry goes to
// `failed` with the words a hiker can act on, and the ready ones stay
// attached - which is the whole argument for tiles over one field.

import { useEffect, useRef, useState } from 'react'
import { MAX_REPORT_PHOTOS, PhotoUnusable, prepareReportPhoto } from '../lib/reportPhoto'

/**
 * One picked photo, and the whole state machine it can be in.
 *
 * A union rather than a record with three optional fields, so a tile that is
 * both "preparing" and "failed" cannot be described - which is the shape the
 * old single `photo` plus `preparing` plus `photoError` triple could, and did
 * for the length of one slow HEIC pick.
 */
export type PhotoPick =
  | { id: string; state: 'preparing' }
  | { id: string; state: 'ready'; blob: Blob; url: string }
  | { id: string; state: 'failed'; message: string }

export interface ReportPhotos {
  picks: readonly PhotoPick[]
  /** The picks that finished shrinking - what a surface sends. */
  ready: readonly { id: string; blob: Blob; url: string }[]
  /** Whether any tile is still shrinking - what holds Send or Done. */
  preparing: boolean
  /** Whether the cap is reached, past which no `+` tile is drawn. */
  full: boolean
  /** Shrink and re-encode one picked file under its own tile. */
  choosePhoto: (file: File | null) => Promise<void>
  /** Take one back, in any state. A pick removed mid-shrink never returns. */
  removePick: (id: string) => void
  /** Everything gone, thumbnails released - for a receipt moving on to the
   *  next report, whose photos are its own. */
  clear: () => void
}

/** `3 photos · 180 KB so far` - what is attached, and what it weighs, which
 *  is the figure a hiker about to send over one bar of EDGE is owed. Only the
 *  ready ones count: a tile still shrinking has no size yet, and a failed one
 *  will never have a size at all. */
export function photoSummary(ready: readonly { blob: Blob }[]): string {
  const kb = Math.round(ready.reduce((total, pick) => total + pick.blob.size, 0) / 1024)
  return `${ready.length} ${ready.length === 1 ? 'photo' : 'photos'} · ${kb} KB so far`
}

export function useReportPhotos(): ReportPhotos {
  const [picks, setPicks] = useState<readonly PhotoPick[]>([])

  const choosePhoto = async (file: File | null) => {
    if (file === null) return
    const id = crypto.randomUUID()
    setPicks((current) => [...current, { id, state: 'preparing' }])

    try {
      const blob = await prepareReportPhoto(file)
      setPicks((current) =>
        // Replaced by id, and skipped entirely if the hiker removed the tile
        // while it was shrinking - a pick taken back must not come back.
        current.map((pick) =>
          pick.id === id
            ? { id, state: 'ready', blob, url: URL.createObjectURL(blob) }
            : pick,
        ),
      )
    } catch (error) {
      // The message is written for a hiker to read (lib/reportPhoto.ts);
      // anything else that got this far is not, so it does not get shown.
      const message =
        error instanceof PhotoUnusable
          ? error.message
          : 'That photo could not be prepared. Try taking another.'
      setPicks((current) =>
        current.map((pick) => (pick.id === id ? { id, state: 'failed', message } : pick)),
      )
    }
  }

  const removePick = (id: string) =>
    setPicks((current) => {
      const going = current.find((pick) => pick.id === id)
      if (going?.state === 'ready') URL.revokeObjectURL(going.url)
      return current.filter((pick) => pick.id !== id)
    })

  const clear = () =>
    setPicks((current) => {
      for (const pick of current) {
        if (pick.state === 'ready') URL.revokeObjectURL(pick.url)
      }
      return []
    })

  // Every thumbnail this surface minted, released when the surface goes. An
  // object URL is a reference the browser holds until it is told otherwise,
  // and these surfaces open from a ridge on a phone with the map already
  // resident.
  //
  // Through a ref rather than by listing `picks` in the cleanup's deps: a
  // deps list would revoke on every pick, taking down the thumbnail of the
  // photo that is still attached.
  const picksRef = useRef<readonly PhotoPick[]>([])
  useEffect(() => {
    picksRef.current = picks
  }, [picks])
  useEffect(
    () => () => {
      for (const pick of picksRef.current) {
        if (pick.state === 'ready') URL.revokeObjectURL(pick.url)
      }
    },
    [],
  )

  const ready = picks.flatMap((pick) => (pick.state === 'ready' ? [pick] : []))
  return {
    picks,
    ready,
    preparing: picks.some((pick) => pick.state === 'preparing'),
    full: picks.length >= MAX_REPORT_PHOTOS,
    choosePhoto,
    removePick,
    clear,
  }
}
