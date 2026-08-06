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
//
// ONE SHEET AT A TIME, UNDER TABS (#298).
//
// The sheets were stacked when there were two of them, which read as a list
// of things to work through rather than as alternatives to choose between -
// and the list is expected to grow. Tabs say what stacking could not: these
// are the SAME kind of thing, you are looking at one of them, and the others
// are one tap away with their own sizes. The strip is built from whatever
// sheets are handed in, so the sheet after the USGS raster needs nothing here.
//
// With one sheet there is no strip: a single tab is a heading pretending to
// be a control.

import { useEffect, useState } from 'react'
import { formatBytes } from '../lib/formatBytes'
import { estimateAvailableBytes, type PersistenceState } from '../lib/storageHealth'
import { useDesktop } from '../lib/useDesktop'
import { facingFullDownload } from '../lib/backgroundStatus'
import { DownloadCard, type DownloadStatus } from './DownloadCard'
import type { DetailOption } from './DetailPicker'
import { Tabs } from './Tabs'
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
  /** This sheet's levels, its chosen one, and how to report a change. Every
   *  level the app knows comes through, with a null size where this sheet
   *  has none of it, so the picker is the same shape under every tab
   *  (DetailPicker). */
  detail: {
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

export function Downloads({ sheets, persistence = null }: DownloadsProps) {
  const isDesktop = useDesktop()
  const availableBytes = useAvailableBytes()
  const [openSheetId, setOpenSheetId] = useState(sheets[0]?.id ?? '')

  // The default sheet, whenever the id in state names none of the ones being
  // offered - a build that publishes a different set, or a first render.
  // Falling back rather than storing the sheet itself keeps this a window
  // over data owned elsewhere: sheets arrive rebuilt on every status change.
  const openSheet = sheets.find((sheet) => sheet.id === openSheetId) ?? sheets[0]
  if (openSheet === undefined) return null

  /** One sheet, with the space warning that belongs to it. */
  const panel = (sheet: SheetDownload) => {
    // Warned, never refused: estimate() is deliberately fuzzy (browsers
    // round it against fingerprinting), and a hiker at a trailhead deciding
    // to try anyway is making an informed call, which is the whole point.
    // Against this sheet's whole size, since that is what its one tap brings.
    const spaceTight =
      facingFullDownload(sheet.status) &&
      availableBytes !== null &&
      availableBytes < sheet.sizeBytes

    return (
      <>
        {/* What this sheet is, under the tab that names it. The card no
            longer carries a heading of its own - two of them under one tab
            would say the same words twice. */}
        <p className="downloads__item-summary">{sheet.summary}</p>

        {spaceTight && (
          <p className="downloads__warning" role="status">
            {sheet.status.state === 'evicted'
              ? `Space still looks tight — about ${formatBytes(availableBytes ?? 0)} free against a ${formatBytes(
                  sheet.sizeBytes,
                )} download. Freeing up space first makes another removal less likely.`
              : `This phone reports about ${formatBytes(availableBytes ?? 0)} free for the app — the ${formatBytes(
                  sheet.sizeBytes,
                )} download may not fit. ${
                  sheet.detail.options.some(
                    (option) =>
                      option.sizeBytes !== null && option.sizeBytes < sheet.sizeBytes,
                  )
                    ? 'A lighter detail level might, or free up some space first.'
                    : 'Freeing up some space first would make room for it.'
                }`}
          </p>
        )}
        <DownloadCard
          title={sheet.title}
          status={sheet.status}
          error={sheet.error ?? null}
          detail={sheet.detail}
          persistence={persistence}
          onStart={sheet.onStart}
          onResume={sheet.onResume}
          onDelete={sheet.onDelete}
        />
      </>
    )
  }

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

      {sheets.length > 1 ? (
        <Tabs
          label="Background maps"
          tabs={sheets.map((sheet) => ({ id: sheet.id, label: sheet.title }))}
          activeId={openSheet.id}
          onSelect={setOpenSheetId}
          idPrefix="downloads-sheet"
        >
          {panel(openSheet)}
        </Tabs>
      ) : (
        panel(openSheet)
      )}
    </div>
  )
}
