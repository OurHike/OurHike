// Downloads (WIREFRAMES.md §4, as amended by its own Known Deviations #1).
//
// The body of the download window, not a screen of its own since 2026-08-05 -
// DownloadsDialog.tsx is the window it sits in and owns the title and the way
// out. Kept as its own component because what it renders is the downloads and
// nothing else, which is what all of the tests below it are about.
//
// ONE CARD PER SHEET, CHOSEN - NOT A LIST OF ARCHIVES TO ASSEMBLE.
//
// The wireframe drew a per-section list with override sheets, roll-up totals
// and mixed-detail seam messaging; ROADMAP.md Phase 2 retired that in favour
// of one whole-corridor package. Since #192 a sheet is several archives
// underneath - the hiking sheet is a vector basemap plus a DEM - but that is
// a fact about storage, not a choice to hand a hiker: one tap takes a whole
// sheet, and lib/backgroundStatus.ts folds its archives into the one status
// its card shows.
//
// What became plural in #237 is the SHEET, because that is a real choice:
// the hiking sheet is the map this app draws and the download everyone gets,
// and the USGS raster is the authoritative government picture some hikers
// want beside it - at over a gigabyte, exactly the thing to never bundle
// into a download nobody asked to grow. Each sheet is its own card, its own
// size, its own delete; taking or dropping one never touches the other.
//
// The trail's own data - the centerline, the spurs, the POIs, the elevation
// profile - is deliberately not here at all. It is small, it is what makes
// the app an app rather than a map viewer, and it is fetched by default
// whenever it is missing (lib/trailData.ts, App.tsx), so presenting it as a
// decision would be offering someone a choice they have already been given.

import { useEffect, useState } from 'react'
import { formatBytes } from '../lib/formatBytes'
import { estimateAvailableBytes, type PersistenceState } from '../lib/storageHealth'
import { useDesktop } from '../lib/useDesktop'
import { DownloadCard, type DownloadStatus } from './DownloadCard'
import type { DetailOption } from './DetailPicker'
import './downloads.css'

/** One sheet, ready to render: its combined state across every archive it is
 *  made of (lib/backgroundStatus.ts), its whole cost, and its own buttons. */
export interface SheetDownload {
  id: string
  title: string
  summary: string
  status: DownloadStatus
  /** What the whole sheet will take, at the chosen detail. */
  sizeBytes: number
  /** Its own failure, if it has one - never a sibling sheet's. */
  error?: string | null
  /** Present where the sheet has levels to choose between - both sheets do
   *  now, with their own level sets (DetailPicker's builders). Absent
   *  renders no picker. */
  detail?: {
    options: readonly DetailOption[]
    value: string
    onChange: (id: string) => void
    name?: string
  }
  onStart: () => void
  onResume: () => void
  onDelete: () => void
}

export interface DownloadsProps {
  /** Every sheet on offer, default first. */
  sheets: readonly SheetDownload[]
  /** What asking for durable storage came to - null while unanswered. One
   *  answer for the origin, shown against each sheet holding bytes. */
  persistence?: PersistenceState | null
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

/** The states in which this sheet's next tap fetches its whole size - where
 *  a too-small disk is worth a warning before the tap, not after. */
function facingFullDownload(status: DownloadStatus): boolean {
  return (
    status.state === 'not-downloaded' ||
    status.state === 'evicted' ||
    status.state === 'hash-mismatch'
  )
}

export function Downloads({ sheets, persistence = null }: DownloadsProps) {
  const isDesktop = useDesktop()
  const availableBytes = useAvailableBytes()

  return (
    <div className="downloads">
      {/* "Download for offline use" means something different on a machine
          that is not going up a mountain (WEBSITE.md §6). The download is
          still offered - a laptop is a legitimate place to look at the map,
          and someone may well be on a cabin connection - but the reason for
          it is stated honestly rather than borrowed from the phone. */}
      <p className="downloads__scope">
        {isDesktop ? (
          <>
            The whole trail, downloaded. This browser has signal, so the map already works
            without it &mdash; the download is for the phone you&rsquo;ll actually be
            carrying.
          </>
        ) : (
          <>
            The whole trail, downloaded. Once it&rsquo;s on your phone, the map works with
            no signal.
          </>
        )}
      </p>

      {sheets.map((sheet) => {
        // Warned, never refused: estimate() is deliberately fuzzy (browsers
        // round it against fingerprinting), and a hiker at a trailhead
        // deciding to try anyway is making an informed call, which is the
        // whole point. Against this sheet's whole size, since that is what
        // its one tap brings down.
        const spaceTight =
          facingFullDownload(sheet.status) &&
          availableBytes !== null &&
          availableBytes < sheet.sizeBytes

        return (
          <div key={sheet.id}>
            {spaceTight && (
              <p className="downloads__warning" role="status">
                {sheet.status.state === 'evicted'
                  ? `Space still looks tight — about ${formatBytes(availableBytes ?? 0)} free against a ${formatBytes(
                      sheet.sizeBytes,
                    )} download. Freeing up space first makes another removal less likely.`
                  : `This phone reports about ${formatBytes(availableBytes ?? 0)} free for the app — the ${formatBytes(
                      sheet.sizeBytes,
                    )} download may not fit. ${
                      sheet.detail !== undefined
                        ? 'A lighter detail level might, or free up some space first.'
                        : 'Freeing up some space first would make room for it.'
                    }`}
              </p>
            )}
            <DownloadCard
              title={sheet.title}
              summary={sheet.summary}
              status={sheet.status}
              error={sheet.error ?? null}
              detail={sheet.detail}
              persistence={persistence}
              // With one sheet the paragraph above has already named what is
              // being downloaded; with two, each card must say which map it
              // is about - #192's naming rule, live for the first time.
              showHeading={sheets.length > 1}
              onStart={sheet.onStart}
              onResume={sheet.onResume}
              onDelete={sheet.onDelete}
            />
          </div>
        )
      })}
    </div>
  )
}
