// Downloads (WIREFRAMES.md §4, as amended by its own Known Deviations #1).
//
// The body of the download window, not a screen of its own since 2026-08-05 -
// DownloadsDialog.tsx is the window it sits in and owns the title and the way
// out. Kept as its own component because what it renders is the download and
// nothing else, which is what all of the tests below it are about.
//
// ONE whole-corridor package. The wireframe drew a per-section list with
// override sheets, roll-up totals and mixed-detail seam messaging; ROADMAP.md
// Phase 2 had already settled on a single package, and this builds to the
// roadmap. None of the retired model appears here.
//
// A failed transfer offers RESUME, never restart (WIREFRAMES.md `7a`).
// Re-fetching 314 MB from zero because the connection dropped at 90% is
// precisely the failure someone on trailhead wifi cannot afford.
//
// The detail picker only appears when there is a download to start. Once the
// package is on the phone, changing detail means re-downloading it, which is
// what Settings' "detail for new downloads" row is for - offering the choice
// here would imply it could be changed in place.

import { useEffect, useState } from 'react'
import { formatBytes, formatBytesLive } from '../lib/formatBytes'
import { getDownloadDetail, type DetailLevel } from '../lib/downloadDetail'
import { estimateAvailableBytes, type PersistenceState } from '../lib/storageHealth'
import { useDesktop } from '../lib/useDesktop'
import { DetailPicker } from './DetailPicker'
import './downloads.css'

export type DownloadStatus =
  | { state: 'not-downloaded' }
  | { state: 'downloading'; receivedBytes: number; totalBytes: number }
  | { state: 'failed'; receivedBytes: number; totalBytes: number }
  | { state: 'downloaded'; totalBytes: number; completedAt: Date }
  /** An archive finished here and its bytes are gone - evicted by the OS,
   *  not deleted by the hiker (storageHealth.ts's marker tells the two
   *  apart, #190). completedAt is when it finished, when that survived. */
  | { state: 'evicted'; completedAt: Date | null }

export interface DownloadsProps {
  status: DownloadStatus
  detailLevel: DetailLevel
  /** What asking for durable storage came to - null while unanswered. Drives
   *  wording only: best-effort storage is stated, never silently assumed
   *  away (#190). */
  persistence?: PersistenceState | null
  onChangeDetail: (level: DetailLevel) => void
  onStart: () => void
  onResume: () => void
  onDelete: () => void
}

/**
 * The browser's own guess at remaining room, read when the window opens.
 *
 * A hook here rather than state threaded from the shell because the number
 * is only worth anything at the moment of choosing - this component mounts
 * when the download window opens, which is exactly that moment. Null where
 * the browser will not say, and the warning simply does not render.
 */
function useAvailableBytes(): number | null {
  const [available, setAvailable] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    void estimateAvailableBytes().then((bytes) => {
      if (!cancelled) setAvailable(bytes)
    })
    return () => {
      cancelled = true
    }
  }, [])

  return available
}

function percent(received: number, total: number): number {
  return total === 0 ? 0 : Math.round((received / total) * 100)
}

export function Downloads({
  status,
  detailLevel,
  persistence = null,
  onChangeDetail,
  onStart,
  onResume,
  onDelete,
}: DownloadsProps) {
  const isDesktop = useDesktop()
  const availableBytes = useAvailableBytes()
  const chosenBytes = getDownloadDetail(detailLevel).sizeBytes

  // Warned, never refused: estimate() is deliberately fuzzy (browsers round
  // it against fingerprinting), and a hiker at a trailhead deciding to try
  // anyway is making an informed call, which is the whole point.
  const spaceTight =
    (status.state === 'not-downloaded' || status.state === 'evicted') &&
    availableBytes !== null &&
    availableBytes < chosenBytes

  return (
    <div className="downloads">
      {/* "Download 314 MB for offline use" means something different on a
          machine that is not going up a mountain (WEBSITE.md §6). The download
          is still offered - a laptop is a legitimate place to look at the map,
          and someone may well be on a cabin connection - but the reason for it
          is stated honestly rather than borrowed from the phone. */}
      <p className="downloads__scope">
        {isDesktop ? (
          <>
            The whole trail, in one download. This browser has signal, so the map already
            works without it &mdash; the download is for the phone you&rsquo;ll actually
            be carrying.
          </>
        ) : (
          <>
            The whole trail, in one download. Once it&rsquo;s on your phone, the map works
            with no signal.
          </>
        )}
      </p>

      {status.state === 'not-downloaded' && (
        <>
          <DetailPicker value={detailLevel} onChange={onChangeDetail} />
          {spaceTight && (
            <p className="downloads__warning" role="status">
              {`This phone reports about ${formatBytes(availableBytes ?? 0)} free for the app — the ${formatBytes(
                chosenBytes,
              )} download may not fit. A lighter detail level might, or free up some space first.`}
            </p>
          )}
          <button type="button" className="downloads__primary" onClick={onStart}>
            Download the map
          </button>
        </>
      )}

      {status.state === 'evicted' && (
        <div className="downloads__evicted">
          {/* The one sentence #190 exists for. "No map downloaded" here would
              be false - one WAS downloaded, and the phone removed it - and on
              a ridge that difference is the difference between re-downloading
              in town and staring at blank paper wondering what you did
              wrong. */}
          <p>
            {status.completedAt === null
              ? 'The map you downloaded is no longer on this phone.'
              : `The map you downloaded on ${status.completedAt.toLocaleDateString(
                  'en-US',
                  {
                    month: 'long',
                    day: 'numeric',
                  },
                )} is no longer on this phone.`}{' '}
            The phone removed it to free up space — that can happen when storage runs low.
            Downloading it again is the only fix, and it needs signal.
          </p>
          <DetailPicker value={detailLevel} onChange={onChangeDetail} />
          {spaceTight && (
            <p className="downloads__warning" role="status">
              {`Space still looks tight — about ${formatBytes(availableBytes ?? 0)} free against a ${formatBytes(
                chosenBytes,
              )} download. Freeing up space first makes another removal less likely.`}
            </p>
          )}
          <button type="button" className="downloads__primary" onClick={onStart}>
            Download it again
          </button>
        </div>
      )}

      {status.state === 'downloading' && (
        <div className="downloads__progress">
          <div
            role="progressbar"
            aria-label="Download progress"
            aria-valuenow={percent(status.receivedBytes, status.totalBytes)}
            aria-valuemin={0}
            aria-valuemax={100}
            className="downloads__bar"
          >
            <span
              className="downloads__bar-fill"
              style={{ width: `${percent(status.receivedBytes, status.totalBytes)}%` }}
            />
          </div>
          {/* The received figure changes on every chunk; formatBytesLive keeps
              its digits calm, and the reserved slot (sized to the total, the
              widest the counter can get, exact in ch because the font is
              monospace) keeps "of 314 MB" from shuffling sideways as 9 MB
              becomes 10 MB. */}
          <p className="downloads__bytes">
            <span
              className="downloads__bytes-received"
              style={{ minWidth: `${formatBytesLive(status.totalBytes).length}ch` }}
            >
              {formatBytesLive(status.receivedBytes)}
            </span>
            {` of ${formatBytes(status.totalBytes)}`}
          </p>
        </div>
      )}

      {status.state === 'failed' && (
        <div className="downloads__failed">
          <p className="downloads__bytes">
            {`Stopped at ${formatBytesLive(status.receivedBytes)} of ${formatBytes(
              status.totalBytes,
            )}.`}
          </p>
          <p>
            What you already have is kept — picking this up again carries on from there.
          </p>
          <button type="button" className="downloads__primary" onClick={onResume}>
            Resume
          </button>
        </div>
      )}

      {status.state === 'downloaded' && (
        <div className="downloads__done">
          <p className="downloads__bytes">
            {`${formatBytes(status.totalBytes)} on this phone, finished ${status.completedAt.toLocaleDateString(
              'en-US',
              { month: 'long', day: 'numeric' },
            )}.`}
          </p>
          {/* Durability, stated at its honest weight. `granted` earns no
              banner - protected is the expected state and saying so is
              noise. A denial or an old browser gets one calm sentence,
              because best-effort storage CAN be reclaimed by the OS and a
              hiker planning around this download deserves to know that
              before the trailhead, not from a blank map (#190). */}
          {(persistence === 'denied' || persistence === 'unsupported') && (
            <p className="downloads__note">
              This phone treats the download as reclaimable if storage runs very low. It
              was asked to protect it{persistence === 'denied' ? ' and declined' : ''} —
              if the map ever disappears, this screen will say so, and downloading again
              restores it.
            </p>
          )}
          <button type="button" className="downloads__secondary" onClick={onDelete}>
            Delete the map
          </button>
        </div>
      )}
    </div>
  )
}
