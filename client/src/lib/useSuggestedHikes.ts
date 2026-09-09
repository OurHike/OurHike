// The published routes this phone holds, for the shell (#1284).
//
// Two reads, in the order a phone at a trailhead needs them: the kept copy
// first, so the shelf is there with no signal, then the bucket when there is
// signal, which replaces the kept copy and the shelf together. A fetch that
// fails - and today every fetch 404s, see config.ts's SUGGESTED_HIKES_KEY -
// changes nothing; the kept copy stands.
//
// AND NEVER A REQUEST WITH NO SIGNAL, the gate usePublishedSizes.ts and
// useTrailData.ts both keep: a phone offline must reach the network zero
// times, not once-and-fail, and App.trailData.test.tsx pins exactly that.

import { useEffect, useRef, useState } from 'react'
import { DATA_CONFIGURED } from './config'
import type { SuggestedHike } from './suggestedHikes'
import {
  NO_SUGGESTED_HIKES,
  fetchSuggestedHikes,
  recallSuggestedHikes,
} from './suggestedHikesData'

/** @param ready Whether the launch is past its first frame (#1302); the kept
 *  copy and the fetch both wait for it. Defaults to true. */
export function useSuggestedHikes(
  online: boolean,
  ready = true,
): readonly SuggestedHike[] {
  const [hikes, setHikes] = useState<readonly SuggestedHike[]>(NO_SUGGESTED_HIKES)
  // Whether the bucket has answered this session. The kept copy is read
  // asynchronously and can resolve AFTER a fast fetch; when it does, the
  // fresher answer must not be overwritten by the older one.
  const fetched = useRef(false)

  useEffect(() => {
    if (!ready) return
    let wanted = true
    // Guarded on both sides: idb-keyval throws synchronously where there is
    // no IndexedDB at all (a test without the shim), and rejects where there
    // is one that refuses. Either way the answer is "nothing kept".
    void Promise.resolve()
      .then(recallSuggestedHikes)
      .then((kept) => {
        if (wanted && !fetched.current && kept !== null) setHikes(kept)
      })
      .catch(() => {})
    return () => {
      wanted = false
    }
  }, [ready])

  useEffect(() => {
    if (!DATA_CONFIGURED || !online || !ready) return
    const controller = new AbortController()
    let wanted = true
    void fetchSuggestedHikes(controller.signal)
      .then((fresh) => {
        if (!wanted || fresh === null) return
        fetched.current = true
        setHikes(fresh)
      })
      .catch(() => {})
    return () => {
      wanted = false
      controller.abort()
    }
  }, [online, ready])

  return hikes
}
