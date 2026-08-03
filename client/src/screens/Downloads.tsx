// Downloads (WIREFRAMES.md §4, as amended by its own Known Deviations #1).
//
// ONE whole-corridor package. The wireframe drew a per-section list with
// override sheets, roll-up totals and mixed-detail seam messaging; ROADMAP.md
// Phase 2 had already settled on a single package, and this screen builds to
// the roadmap. None of the retired model appears here.
//
// A failed transfer offers RESUME, never restart (WIREFRAMES.md `7a`).
// Re-fetching 314 MB from zero because the connection dropped at 90% is
// precisely the failure someone on trailhead wifi cannot afford.
//
// The detail picker only appears when there is a download to start. Once the
// package is on the phone, changing detail means re-downloading it, which is
// what Settings' "detail for new downloads" row is for - offering the choice
// here would imply it could be changed in place.

import { formatBytes } from '../lib/formatBytes'
import type { DetailLevel } from '../lib/downloadDetail'
import { useDesktop } from '../lib/useDesktop'
import { DetailPicker } from './DetailPicker'
import './downloads.css'

export type DownloadStatus =
  | { state: 'not-downloaded' }
  | { state: 'downloading'; receivedBytes: number; totalBytes: number }
  | { state: 'failed'; receivedBytes: number; totalBytes: number }
  | { state: 'downloaded'; totalBytes: number; completedAt: Date }

export interface DownloadsProps {
  status: DownloadStatus
  detailLevel: DetailLevel
  onChangeDetail: (level: DetailLevel) => void
  onStart: () => void
  onResume: () => void
  onDelete: () => void
}

function percent(received: number, total: number): number {
  return total === 0 ? 0 : Math.round((received / total) * 100)
}

export function Downloads({
  status,
  detailLevel,
  onChangeDetail,
  onStart,
  onResume,
  onDelete,
}: DownloadsProps) {
  const isDesktop = useDesktop()

  return (
    <main className="downloads">
      <h1 className="downloads__title">Offline map</h1>
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
          <button type="button" className="downloads__primary" onClick={onStart}>
            Download the map
          </button>
        </>
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
          <p className="downloads__bytes">
            {`${formatBytes(status.receivedBytes)} of ${formatBytes(status.totalBytes)}`}
          </p>
        </div>
      )}

      {status.state === 'failed' && (
        <div className="downloads__failed">
          <p className="downloads__bytes">
            {`Stopped at ${formatBytes(status.receivedBytes)} of ${formatBytes(
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
          <button type="button" className="downloads__secondary" onClick={onDelete}>
            Delete the map
          </button>
        </div>
      )}
    </main>
  )
}
