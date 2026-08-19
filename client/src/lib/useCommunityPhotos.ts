// Rung 2 of the waypoint card's photo ladder: the community's photos of the
// place a card is showing, fetched from the backend (#576) and rendered
// between the hiker's own photos and the artifacts' (#578).
//
// This rung needs the network and must degrade SILENTLY - POI_PHOTOS.md's
// ladder falls through downward, photos are an enhancement and never
// safety-relevant, and a card offline shows exactly what it showed before
// this rung existed. So every failure here - no backend configured, no
// signal, a 500 - lands on an empty list without a word. The one thing kept
// across failures is this session's cache: a card re-opened in a dead spot
// still shows what was fetched while there was signal.
//
// The cache is small and honest about what it holds. Entries expire before
// the signed URLs inside them do (backend PHOTO_URL_TTL_SECONDS is five
// minutes): serving a cached list with dead URLs would render broken images
// where the placeholder should be, so past the refresh age the list is
// re-fetched and the stale copy is only the fallback when that fetch fails
// - stale URLs behind a failed refresh may 403, which the card already
// treats as a photo failing (the placeholder, arrows still live).

import { useEffect, useState } from 'react'
import { fetchPoiPhotos, type PoiPhotoSummary } from './api'

/** Refresh a cached gallery after this long - inside the signed URLs' five
 *  minutes, so a served cache normally holds working links. */
const CACHE_FRESH_MS = 4 * 60 * 1000

interface CachedGallery {
  photos: PoiPhotoSummary[]
  at: number
}

const cache = new Map<string, CachedGallery>()

/** Test seam: a session cache is per-module state, and tests that prove the
 *  fetch happens need to start without one. */
export function clearCommunityPhotoCache(): void {
  cache.clear()
}

export function useCommunityPhotos(poiId: string): PoiPhotoSummary[] {
  const cached = cache.get(poiId)
  const [photos, setPhotos] = useState<PoiPhotoSummary[]>(cached?.photos ?? [])

  useEffect(() => {
    const held = cache.get(poiId)
    setPhotos(held?.photos ?? [])
    if (held !== undefined && Date.now() - held.at < CACHE_FRESH_MS) return

    const controller = new AbortController()
    fetchPoiPhotos(poiId, controller.signal)
      .then((fresh) => {
        cache.set(poiId, { photos: fresh, at: Date.now() })
        if (!controller.signal.aborted) setPhotos(fresh)
      })
      .catch(() => {
        // Offline, unconfigured, refused - all the same silent fall-through.
        // Whatever the cache held (possibly nothing) is already showing.
      })

    return () => controller.abort()
  }, [poiId])

  return photos
}
