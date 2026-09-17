// The paper-sheet footprints, held for the shell (#1574).
//
// One fetch when the phone has signal and the kept copy when it does not -
// lib/mapSheets.ts decides which. Re-run when `online` changes, so a phone
// that launched in a dead spot picks the archive up the first time it has
// signal, the way lib/useConditions.ts re-reads the conditions baseline.

import { useEffect, useState } from 'react'
import { fetchMapSheets, type MapSheets } from './mapSheets'

export function useMapSheets(online: boolean): MapSheets | null {
  const [sheets, setSheets] = useState<MapSheets | null>(null)

  useEffect(() => {
    let cancelled = false
    void fetchMapSheets(online).then((result) => {
      // A null result never clears what an earlier read found: an offline
      // read with nothing kept is "no news", not "the sheets went away".
      if (!cancelled && result !== null) setSheets(result)
    })
    return () => {
      cancelled = true
    }
  }, [online])

  return sheets
}
