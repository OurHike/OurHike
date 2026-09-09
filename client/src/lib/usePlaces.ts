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

import { useEffect, useRef, useState } from 'react'
import { DATA_CONFIGURED } from './config'
import { NO_PLACES, type PlacesDocument } from './places'
import { fetchPlaces, recallPlaces } from './placesData'

export function usePlaces(online: boolean, wanted = true): PlacesDocument {
  const [places, setPlaces] = useState<PlacesDocument>(NO_PLACES)
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
    return () => {
      live = false
    }
  }, [wanted])

  useEffect(() => {
    if (!DATA_CONFIGURED || !online || !wanted) return
    const controller = new AbortController()
    let live = true
    void fetchPlaces(controller.signal)
      .then((fresh) => {
        if (!live || fresh === null) return
        fetched.current = true
        setPlaces(fresh)
      })
      .catch(() => {})
    return () => {
      live = false
      controller.abort()
    }
  }, [online, wanted])

  return places
}
