// Downloads (WIREFRAMES.md §4, as amended by its own Known Deviations #1).
//
// The body of the download window, not a screen of its own since 2026-08-05 -
// DownloadsDialog.tsx is the window it sits in and owns the title and the way
// out. Kept as its own component because what it renders is the download and
// nothing else, which is what all of the tests below it are about.
//
// ONE DOWNLOAD, CHOSEN - NOT A LIST OF PIECES TO ASSEMBLE.
//
// The wireframe drew a per-section list with override sheets, roll-up totals
// and mixed-detail seam messaging; ROADMAP.md Phase 2 retired that in favour
// of one whole-corridor package, and none of it appears here. Since #192 the
// map's background is several archives underneath - a raster sheet, and
// (#185/#186) a vector basemap and a DEM - but that is a fact about storage,
// not a choice to hand a hiker. What they choose is what the background IS:
// its detail level here, and which sheet is drawn from it in the background
// picker. The archives follow from the choice.
//
// So this screen holds one card per downloadable THING, and today there is
// exactly one: the background (lib/packages.ts). The trail's own data - the
// centerline, the spurs, the POIs, the elevation profile - is deliberately
// not here at all. It is small, it is what makes the app an app rather than a
// map viewer, and it is fetched by default whenever it is missing
// (lib/trailData.ts, App.tsx), so presenting it as a decision would be
// offering someone a choice they have already been given.

import { useEffect, useState } from 'react'
import { formatBytes } from '../lib/formatBytes'
import type { DetailLevel } from '../lib/downloadDetail'
import { estimateAvailableBytes, type PersistenceState } from '../lib/storageHealth'
import { useDesktop } from '../lib/useDesktop'
import { DownloadCard, type DownloadStatus } from './DownloadCard'
import './downloads.css'

export interface DownloadsProps {
  /** The background, as one thing: its combined state across every archive it
   *  is made of (lib/backgroundStatus.ts). */
  status: DownloadStatus
  title: string
  summary: string
  /** What the whole background will take, at the chosen detail. */
  sizeBytes: number
  detailLevel: DetailLevel
  /** Its own failure, if it has one. */
  error?: string | null
  /** What asking for durable storage came to - null while unanswered. */
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

export function Downloads({
  status,
  title,
  summary,
  sizeBytes,
  detailLevel,
  error = null,
  persistence = null,
  onChangeDetail,
  onStart,
  onResume,
  onDelete,
}: DownloadsProps) {
  const isDesktop = useDesktop()
  const availableBytes = useAvailableBytes()

  // Warned, never refused: estimate() is deliberately fuzzy (browsers round
  // it against fingerprinting), and a hiker at a trailhead deciding to try
  // anyway is making an informed call, which is the whole point.
  //
  // Against the size of the WHOLE background, since that is what one tap now
  // brings down - not the size of whichever archive happens to be first.
  const spaceTight =
    (status.state === 'not-downloaded' || status.state === 'evicted') &&
    availableBytes !== null &&
    availableBytes < sizeBytes

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

      {spaceTight && (
        <p className="downloads__warning" role="status">
          {status.state === 'evicted'
            ? `Space still looks tight — about ${formatBytes(availableBytes ?? 0)} free against a ${formatBytes(
                sizeBytes,
              )} download. Freeing up space first makes another removal less likely.`
            : `This phone reports about ${formatBytes(availableBytes ?? 0)} free for the app — the ${formatBytes(
                sizeBytes,
              )} download may not fit. A lighter detail level might, or free up some space first.`}
        </p>
      )}

      <DownloadCard
        title={title}
        summary={summary}
        status={status}
        error={error}
        detail={{ level: detailLevel, onChange: onChangeDetail }}
        persistence={persistence}
        // The paragraph above has already named what is being downloaded, and
        // with one card a heading would only say it a second time.
        showHeading={false}
        onStart={onStart}
        onResume={onResume}
        onDelete={onDelete}
      />
    </div>
  )
}
