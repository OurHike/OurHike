// The challenge map for a screen that draws it (#1965): the kept copy at
// once, then the release's when it answers. Imported only by deferred
// screens (the Where view, the season strip), so nothing of the map reaches
// the first frame - the launch budget has no room for it.

import { useEffect, useState } from 'react'
import {
  fetchChallengeMap,
  recallChallengeMap,
  stateAtMile,
  type ChallengeMap,
} from './challengeMap'
import { stateAtMile as approximateStateAtMile, type StateOfMile } from './seasonStrip'

/** `ask: false` reads the kept copy only - for Today's strip, which must not
 *  download a map nobody opened. */
export function useChallengeMap({
  ask = true,
}: { ask?: boolean } = {}): ChallengeMap | null {
  const [map, setMap] = useState<ChallengeMap | null>(null)
  useEffect(() => {
    let live = true
    const controller = new AbortController()
    void recallChallengeMap()
      .then((kept) => {
        if (live && kept !== null) setMap((current) => current ?? kept)
      })
      .catch(() => {})
    if (ask) {
      void fetchChallengeMap(controller.signal)
        .then((fresh) => {
          if (live && fresh !== null) setMap(fresh)
        })
        .catch(() => {})
    }
    return () => {
      live = false
      controller.abort()
    }
  }, [ask])
  return map
}

/** Which state a mile is in: the map's measured runs when the phone holds
 *  them, the brief's approximate bands when it does not (lib/seasonStrip.ts
 *  says how far apart the two are). */
export function stateLookup(map: ChallengeMap | null): StateOfMile {
  if (map === null || map.stateRuns.length === 0) return approximateStateAtMile
  return (mile) => stateAtMile(map.stateRuns, mile)
}
