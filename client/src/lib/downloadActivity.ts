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

export interface DownloadActivity {
  /**
   * Which wait this is.
   *
   * Bytes coming over the network, or bytes already here being read back to
   * catch their hash up (#197) - kept apart for the same reason the card keeps
   * them apart: only one of the two is spending signal, and they ask opposite
   * things of someone standing in a dead spot.
   */
  kind: 'downloading' | 'checking'
  /** How much of `totalBytes` is behind it - received, or checked. */
  doneBytes: number
  totalBytes: number
}

function combine(
  statuses: readonly (Downloading | Checking)[],
  kind: DownloadActivity['kind'],
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
 */
export function activeDownload(
  statuses: readonly DownloadStatus[],
): DownloadActivity | null {
  const downloading = statuses.filter(
    (status): status is Downloading => status.state === 'downloading',
  )
  if (downloading.length > 0) return combine(downloading, 'downloading')

  const checking = statuses.filter(
    (status): status is Checking => status.state === 'checking',
  )
  if (checking.length > 0) return combine(checking, 'checking')

  return null
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
