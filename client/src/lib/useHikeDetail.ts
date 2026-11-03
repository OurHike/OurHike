// One hike's prose, loaded when somebody opens it (#1473).
//
// WHY THIS EXISTS: `suggested_hikes.json` carried every hike's full
// turn-by-turn and had reached 1.70 MB of conditionsCache.ts's 2 MB ceiling -
// a ceiling that DELETES the copy a phone holds rather than trimming it, so
// the publish that crossed it would have emptied the shelf offline on every
// phone at once. Measured over the 201 records published on 2026-09-15,
// `description` alone was 58.1% of those bytes. The shelf now carries what the
// shelf and the finder read; this fetches the rest, for the one hike a hiker
// actually opened.
//
// Two reads in the order a phone at a trailhead needs them, the same order
// useSuggestedHikes.ts uses: the kept copy first so an already-opened hike
// reads with no signal, then the bucket when there is signal.
//
// AND NEVER A REQUEST WITH NO SIGNAL - the gate useSuggestedHikes.ts,
// usePublishedSizes.ts and useTrailData.ts all keep. A phone offline reaches
// the network zero times, not once-and-fail.
//
// NULL IS NOT A FAILURE STATE HERE, which is the property that makes fetching
// prose on demand safe. Every field in SuggestedHikeDetail is optional and
// absent has always meant "the publisher did not say" - so no signal, a 404
// and an unparseable object all land on the state the screen was built around
// long before this split.

import { useEffect, useState } from 'react'
import type { SuggestedHike, SuggestedHikeDetail } from './suggestedHikes'
import { fetchHikeDetail, recallHikeDetail } from './suggestedHikesData'

/**
 * What the detail screen should print for this hike: the fields the shelf
 * already carries, with whatever prose has arrived merged over them.
 *
 * THE FETCHED OBJECT IS SPREAD SECOND, so it wins any key both sides carry -
 * and the reason that is safe is that they carry none in common.
 * `routeProvenance`, `routeGrade` and `routeNotes` are in
 * export_suggested_hikes.py's SHELF_FIELDS, which is the same list the
 * detail object is built by EXCLUDING, so a fetched detail cannot contain
 * them and cannot blank them. Those three live on the shelf precisely so a
 * drawn line is never separated from its provenance: App.tsx draws
 * `segments` from the shelf record, nowhere near this screen.
 *
 * If that ever stops being true - if a detail object starts carrying a field
 * the shelf also has - this becomes a real precedence decision and should be
 * made explicitly rather than inherited from spread order.
 *
 * @param online Whether to ask the bucket at all.
 */
export function useHikeDetail(
  hike: SuggestedHike | null,
  online: boolean,
): SuggestedHikeDetail | undefined {
  const [fetched, setFetched] = useState<SuggestedHikeDetail | null>(null)
  const id = hike?.id ?? null

  // Cleared on the way IN rather than only on the way out: without this, a
  // hiker who opens one walk and then another reads the first one's prose
  // under the second one's name for as long as the second fetch takes.
  useEffect(() => {
    setFetched(null)
  }, [id])

  useEffect(() => {
    if (id === null) return
    let wanted = true
    // Guarded on both sides, like useSuggestedHikes: idb-keyval throws
    // synchronously where there is no IndexedDB at all and rejects where
    // there is one that refuses. Either way the answer is "nothing kept".
    void Promise.resolve()
      .then(() => recallHikeDetail(id))
      .then((kept) => {
        if (wanted && kept !== null) setFetched((current) => current ?? kept)
      })
      .catch(() => {})
    return () => {
      wanted = false
    }
  }, [id])

  useEffect(() => {
    if (id === null || !online) return
    const controller = new AbortController()
    let wanted = true
    void fetchHikeDetail(id, controller.signal)
      .then((arrived) => {
        // A fetch that came back with nothing changes nothing: the kept copy
        // stands, exactly as it does for the shelf. A bucket that stopped
        // carrying an object is not evidence the prose was withdrawn.
        if (wanted && arrived !== null) setFetched(arrived)
      })
      .catch(() => {})
    return () => {
      wanted = false
      controller.abort()
    }
  }, [id, online])

  if (hike === null) return undefined
  if (fetched === null) return hike.detail
  return { ...hike.detail, ...fetched }
}
