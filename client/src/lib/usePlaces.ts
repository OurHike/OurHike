// The places this phone can name, for the shell (#1373).
//
// lib/useSuggestedHikes.ts's two reads, in the same order and for the same
// reasons: the kept copy first so a search works with no signal, then the
// bucket when there is signal, and NEVER A REQUEST WITH NO SIGNAL - a phone
// offline reaches the network zero times, not once-and-fail.
//
// `wanted` gates both reads: first run wants the document the moment the
// "where do you hike?" field can be typed into, and nothing else needs it
// until a place search opens. A launch that never opens one never pays for it
// (features/LAUNCH_BUDGET.md).
//
// `settled` is the second answer, and the field is why it exists: with no
// places yet, "still looking" and "there are none" are different sentences
// to put in front of somebody typing, and a document alone cannot tell them
// apart. It is true once the kept copy has answered and the bucket has too,
// or was never going to be asked.

import { useEffect, useRef, useState } from 'react'
import { DATA_CONFIGURED } from './config'
import { NO_PLACES, type PlacesDocument } from './places'
import { fetchPlaces, recallPlaces } from './placesData'

export interface PlacesRead {
  readonly places: PlacesDocument
  /** Every read this phone will make has answered - a document with no
   *  places is then "there are none", not "not yet". */
  readonly settled: boolean
}

export function usePlaces(online: boolean, wanted = true): PlacesRead {
  const [places, setPlaces] = useState<PlacesDocument>(NO_PLACES)
  const [keptRead, setKeptRead] = useState(false)
  const [fetchDone, setFetchDone] = useState(false)
  const fetched = useRef(false)

  useEffect(() => {
    if (!wanted) return
    let live = true
    void Promise.resolve()
      .then(recallPlaces)
      .then((kept) => {
        if (live && !fetched.current && kept !== null) setPlaces(kept)
      })
      .catch(() => {})
      .finally(() => {
        if (live) setKeptRead(true)
      })
    return () => {
      live = false
    }
  }, [wanted])

  const willFetch = DATA_CONFIGURED && online && wanted
  useEffect(() => {
    if (!willFetch) return
    const controller = new AbortController()
    let live = true
    void fetchPlaces(controller.signal)
      .then((fresh) => {
        if (!live || fresh === null) return
        fetched.current = true
        setPlaces(fresh)
      })
      .catch(() => {})
      .finally(() => {
        if (live) setFetchDone(true)
      })
    return () => {
      live = false
      controller.abort()
    }
  }, [willFetch])

  return { places, settled: keptRead && (!willFetch || fetchDone) }
}
