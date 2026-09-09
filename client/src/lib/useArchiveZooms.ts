// The downloaded archive's zoom range, as state the shell can render from.
//
// Keyed on whether the archive is present rather than read once on mount: the
// header does not exist until a download finishes, so a phone that arrives
// empty and downloads mid-session has to pick it up without a reload. That is
// the first run of the app on a new phone, which is not an edge case.

import { useEffect, useState } from 'react'
import { readArchiveFootprint, readArchiveZooms } from '../map/archiveZooms'
import type { ArchiveZooms, Footprint } from './archiveCoverage'

/**
 * @param archivePresent whether a FINISHED archive is on the phone. A partial
 *   one has no readable header, and asking anyway would spend a byte-range
 *   read per render on a file that cannot answer.
 */
export function useArchiveZooms(
  idbKey: string,
  archivePresent: boolean,
): ArchiveZooms | null {
  const [zooms, setZooms] = useState<ArchiveZooms | null>(null)

  useEffect(() => {
    if (!archivePresent) {
      // Back to not-knowing, which is what a deleted archive leaves. Holding
      // the old range would let the app go on describing the coverage of a
      // file the hiker has just reclaimed the space from.
      setZooms(null)
      return
    }

    let cancelled = false
    void readArchiveZooms(idbKey).then((next) => {
      if (!cancelled) setZooms(next)
    })

    return () => {
      cancelled = true
    }
  }, [idbKey, archivePresent])

  return zooms
}

/**
 * The same archive's declared ground, on the same contract: keyed on
 * presence, null while there is no finished archive to ask, and null again
 * the moment it is deleted so the app cannot go on describing the edge of a
 * file the hiker just reclaimed the space from (#557).
 */
export function useArchiveFootprint(
  idbKey: string,
  archivePresent: boolean,
): Footprint | null {
  const [footprint, setFootprint] = useState<Footprint | null>(null)

  useEffect(() => {
    if (!archivePresent) {
      setFootprint(null)
      return
    }

    let cancelled = false
    void readArchiveFootprint(idbKey).then((next) => {
      if (!cancelled) setFootprint(next)
    })

    return () => {
      cancelled = true
    }
  }, [idbKey, archivePresent])

  return footprint
}
