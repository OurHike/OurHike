// Whether anything is arriving right now, for the chrome that has to say so
// while the download window is shut.
//
// A download does not live in the window it was started from - the shell holds
// it (App.tsx), so closing the window leaves several hundred megabytes still
// coming with nothing on screen admitting it. A hiker who taps Download, shuts
// the window and goes back to the map sees an app that looks idle while it
// spends their data, and the only way to find out otherwise is to reopen the
// window and hope. This is the one answer the footer link needs to say
// otherwise (chrome/DownloadsLink.tsx).
//
// It is handed the SHEET statuses - the ones the cards already render - rather
// than the archives underneath, and that is not a convenience. lib/
// backgroundStatus.ts has already turned N archives into one honest figure per
// sheet, and a second summation over raw archives would drift from it AND read
// wrong: an archive that finishes while its sibling is still coming leaves
// 'downloading' entirely, so a sum of only what is downloading travels
// BACKWARDS at the moment a piece completes. Per sheet the finished piece is
// still counted, because combineBackgroundStatus counts it.
//
// The precedence is that module's, for its reasons: a live transfer outranks a
// check, and everything at rest is not activity at all. Nothing here reports a
// FAILED download - "stopped" is not "in progress", and offering a bar for it
// would say the phone is working on something it has given up on. The window
// is where the resume lives.

import type { DownloadStatus } from '../screens/DownloadCard'

type Downloading = Extract<DownloadStatus, { state: 'downloading' }>
type Checking = Extract<DownloadStatus, { state: 'checking' }>

/**
 * What is being waited on, and how far along it is where that is knowable.
 *
 * A union rather than one shape with optional numbers, because the first kind
 * genuinely has none and a `0 of 0` would be a figure invented to fill a slot.
 * The trail data is four fetches of unequal, unannounced size (lib/
 * trailData.ts), and the honest thing to say about it is that it is happening.
 *
 * The two that DO carry numbers are kept apart from each other for the reason
 * the card keeps them apart: bytes coming over the network and bytes already
 * here being read back to catch their hash up (#197) look identical and are
 * not - only one is spending signal, and they ask opposite things of someone
 * standing in a dead spot.
 */
export type DownloadActivity =
  /** The canary before the transfer: the trail's own data, which has to land
   *  before several hundred megabytes are spent finding out the bucket was
   *  misconfigured (App.tsx's `ensureTrailData`). */
  | { kind: 'preparing' }
  | { kind: 'downloading'; doneBytes: number; totalBytes: number }
  | { kind: 'checking'; doneBytes: number; totalBytes: number }

function combine(
  statuses: readonly (Downloading | Checking)[],
  kind: 'downloading' | 'checking',
): DownloadActivity {
  return {
    kind,
    doneBytes: statuses.reduce(
      (n, status) =>
        n + (status.state === 'downloading' ? status.receivedBytes : status.checkedBytes),
      0,
    ),
    totalBytes: statuses.reduce((n, status) => n + status.totalBytes, 0),
  }
}

/**
 * What is moving across every sheet, or null when nothing is.
 *
 * Sheets are summed rather than ranked because a hiker who started two of them
 * is waiting on both, and two bars in a footer is a footer nobody reads. The
 * sum jumps when a second download is started - which is true, and is the
 * hiker's own doing.
 *
 * `preparing` is passed alongside rather than found among the statuses because
 * it is not one: no archive is ever in that state, it is the step before any
 * archive has been asked for (App.tsx). It ranks LAST, under both figures,
 * which is the right way round whenever both are true - a second sheet fetching
 * a canary must not replace a live transfer's percentage with a word.
 */
export function activeDownload(
  statuses: readonly DownloadStatus[],
  preparing = false,
): DownloadActivity | null {
  const downloading = statuses.filter(
    (status): status is Downloading => status.state === 'downloading',
  )
  if (downloading.length > 0) return combine(downloading, 'downloading')

  const checking = statuses.filter(
    (status): status is Checking => status.state === 'checking',
  )
  if (checking.length > 0) return combine(checking, 'checking')

  return preparing ? { kind: 'preparing' } : null
}

/**
 * How far along, as a whole percent.
 *
 * One answer for both bars that draw it - the window's (screens/DownloadCard.tsx)
 * and the footer's - so a hiker glancing between them is never shown two
 * roundings of the same download. Zero total is 0%, not a division by zero:
 * a transfer whose length the server never declared is at the start of
 * something, not finished.
 */
export function downloadPercent(doneBytes: number, totalBytes: number): number {
  return totalBytes === 0 ? 0 : Math.round((doneBytes / totalBytes) * 100)
}

/**
 * How far along, for a bar's FILL - tenths of a percent, floored.
 *
 * The whole-percent answer above stays what the text says and what a screen
 * reader hears, but a bar whose width steps in whole percents sits still for
 * 7.9 MB at a time on the first sheet (789,552,460 bytes - #449 measured),
 * about four seconds per step at trailhead speeds - and a bar that does not
 * move is this app's own signal for "stalled", a distinction the `checking`
 * state (#197) exists to keep trustworthy.
 *
 * One decimal rather than the raw ratio, on lib/formatBytes.ts's reasoning
 * about figures that change faster than anyone can read: a tenth of a percent
 * of that sheet is ~790 KB, so the fill creeps steadily without the style
 * churning on literally every chunk. Floored rather than rounded, also that
 * file's rule: a fill that overstates reads as a lie the moment the transfer
 * stalls, and flooring means the bar never shows 100% before the last byte.
 */
export function downloadFillPercent(doneBytes: number, totalBytes: number): number {
  if (totalBytes === 0) return 0
  return Math.min(100, Math.floor((doneBytes / totalBytes) * 1000) / 10)
}
