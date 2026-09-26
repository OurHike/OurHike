// The podcast episodes this phone holds, for the shell (#1683).
//
// lib/useSuggestedHikes.ts's two reads in the same order, for the same
// reason: the kept copy first, so the cards are there with no signal, then
// the bucket when there is signal. And never a request with no signal - a
// phone offline must reach the network zero times, not once-and-fail.

import { useEffect, useRef, useState } from 'react'
import { DATA_CONFIGURED } from './config'
import {
  NO_PODCAST_EPISODES,
  fetchPodcastEpisodes,
  type PodcastEpisode,
} from './podcasts'

/** @param ready Whether the launch is past its first frame (#1302); both
 *  reads wait for it, like every other non-essential fetch. */
export function usePodcastEpisodes(
  online: boolean,
  ready = true,
): readonly PodcastEpisode[] {
  const [episodes, setEpisodes] = useState<readonly PodcastEpisode[]>(NO_PODCAST_EPISODES)
  // The kept copy can resolve after a fast fetch; the fresher answer wins.
  const fetched = useRef(false)

  useEffect(() => {
    if (!DATA_CONFIGURED || !ready) return
    let wanted = true
    // Guarded like useSuggestedHikes: idb-keyval throws synchronously where
    // there is no IndexedDB at all, and either way the answer is "nothing".
    void Promise.resolve()
      .then(() => fetchPodcastEpisodes(false))
      .then((kept) => {
        if (wanted && !fetched.current && kept !== null) setEpisodes(kept)
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
    void fetchPodcastEpisodes(true, controller.signal)
      .then((fresh) => {
        if (!wanted || fresh === null) return
        fetched.current = true
        setEpisodes(fresh)
      })
      .catch(() => {})
    return () => {
      wanted = false
      controller.abort()
    }
  }, [online, ready])

  return episodes
}
