// One answer about the background, out of however many archives it is made
// of (#192).
//
// The background is one thing a hiker chooses and downloads - the DEM, the
// raster sheet and the vector basemap are pieces of it, not items on a
// checklist (lib/packages.ts). The store underneath is still per-archive,
// because that is what lets one piece resume, fail or be evicted without
// touching the others. This is the join between the two: N archive states in,
// one status out, for a screen that shows one card.
//
// The precedence below is ordered by what a hiker most needs to know, not by
// what is most common:
//
//   1. Something is transferring    - a live figure outranks everything.
//   1b. Something is being CHECKED   - the phone reading back bytes it holds
//                                     (#197). Work in progress, so it outranks
//                                     every resting state below.
//   2. Something was EVICTED        - "the phone removed your map" is the one
//                                     sentence #190 exists for, and it is
//                                     more urgent than "some is missing",
//                                     because it explains why.
//   3. Part of it is here           - offer to carry on, never to restart.
//   4. All of it is here            - the finished state.
//   5. None of it is here.
//
// Case 3 covers two situations that behave identically and are worth naming:
// an archive whose transfer stopped partway, and an archive that never
// started while its siblings finished. Both mean the background is partly on
// the phone, both are fixed by carrying on from where it got to, and the
// "Stopped at X of Y" the card renders is literally true of each.
//
// EVERY MULTI-ARCHIVE PATH HERE IS TEST-ONLY TODAY. The raster sheet is the
// only piece the pipeline publishes (#185/#186 are the other two), so the
// shipped app always combines exactly one status and gets it back unchanged.

import type { DownloadStatus } from '../screens/DownloadCard'

/** One archive's contribution to the whole. */
export interface ArchiveState {
  status: DownloadStatus
  /** Its measured published size. Never absent - see OfferedPackage. */
  sizeBytes: number
}

const NOT_DOWNLOADED: DownloadStatus = { state: 'not-downloaded' }

/**
 * Bytes here and bytes expected, for one archive.
 *
 * An archive that has not started contributes its PUBLISHED size as the
 * expectation, so a background part-way through does not show a total that
 * grows as each piece begins - which would read as a download that keeps
 * getting bigger.
 */
function bytesOf({ status, sizeBytes }: ArchiveState): {
  received: number
  total: number
} {
  switch (status.state) {
    case 'downloading':
    case 'failed':
      return { received: status.receivedBytes, total: status.totalBytes }
    case 'downloaded':
      return { received: status.totalBytes, total: status.totalBytes }
    case 'not-downloaded':
    case 'evicted':
    // An archive being checked holds partial bytes, but how many is not what
    // `checkedBytes` counts - that is progress through the re-read. Its
    // published size is the honest expectation until the transfer resumes and
    // starts reporting real figures.
    case 'checking':
      return { received: 0, total: sizeBytes }
  }
}

function sum(archives: readonly ArchiveState[]) {
  return archives.reduce(
    (running, archive) => {
      const { received, total } = bytesOf(archive)
      return { received: running.received + received, total: running.total + total }
    },
    { received: 0, total: 0 },
  )
}

/** The most recent completion among archives that have one, or null. Most
 *  recent rather than earliest: it answers "when was this map last whole". */
function latestCompletion(archives: readonly ArchiveState[]): Date | null {
  const dates = archives
    .map(({ status }) =>
      status.state === 'downloaded' || status.state === 'evicted'
        ? status.completedAt
        : null,
    )
    .filter((date): date is Date => date !== null)

  if (dates.length === 0) return null
  return dates.reduce((latest, date) => (date > latest ? date : latest))
}

export function combineBackgroundStatus(
  archives: readonly ArchiveState[],
): DownloadStatus {
  if (archives.length === 0) return NOT_DOWNLOADED

  const states = archives.map(({ status }) => status.state)
  const { received, total } = sum(archives)

  if (states.includes('downloading')) {
    return { state: 'downloading', receivedBytes: received, totalBytes: total }
  }

  // Below a live transfer and above everything else: it is work in progress,
  // so offering "Resume" or announcing an eviction underneath it would be
  // describing a phone that is already busy doing the thing.
  if (states.includes('checking')) {
    const checking = archives.filter(({ status }) => status.state === 'checking')
    return {
      state: 'checking',
      checkedBytes: checking.reduce(
        (n, { status }) => n + (status.state === 'checking' ? status.checkedBytes : 0),
        0,
      ),
      totalBytes: checking.reduce(
        (n, { status }) => n + (status.state === 'checking' ? status.totalBytes : 0),
        0,
      ),
    }
  }

  if (states.includes('evicted')) {
    return { state: 'evicted', completedAt: latestCompletion(archives) }
  }

  const anyHere = states.some(
    (state) => state === 'downloaded' || state === 'failed' || state === 'downloading',
  )
  const allHere = states.every((state) => state === 'downloaded')

  if (allHere) {
    const completedAt = latestCompletion(archives)
    return {
      state: 'downloaded',
      totalBytes: total,
      // Non-null whenever every archive is downloaded, since that state
      // carries a date - the fallback keeps this total rather than partial.
      completedAt: completedAt ?? new Date(),
    }
  }

  if (anyHere) {
    return { state: 'failed', receivedBytes: received, totalBytes: total }
  }

  return NOT_DOWNLOADED
}
