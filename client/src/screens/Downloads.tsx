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
// profile - is deliberately not a CARD here. It is small, it is what makes
// the app an app rather than a map viewer, and it is fetched by default
// whenever it is missing (lib/trailData.ts, App.tsx), so presenting it as a
// decision would be offering someone a choice they have already been given.
// Since #1103 it does get an ACCOUNT: a read-only list beside the sheets,
// measured off the store (lib/onThisPhone.ts), because "what is on this
// phone" is a question a hiker owns even about bytes they never chose -
// and the two words "trail data" were the whole answer before it.
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
import { formatBytes, formatBytesLive } from '../lib/formatBytes'
import { storedTrailData, type TrailDataAsset } from '../lib/onThisPhone'
import { estimateAvailableBytes, type PersistenceState } from '../lib/storageHealth'
import { ownPhotoUsage } from '../lib/poiPhotos'
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
  /**
   * What the whole sheet will take, at the chosen detail - or null where
   * nothing has measured it yet (#1167).
   *
   * Null is a real state rather than a gap: the hiking sheet's sizes come
   * from `latest.json` alone now, so a phone that has never reached it does
   * not know. Everything below that would otherwise print or compare against
   * this figure withholds instead of guessing.
   */
  sizeBytes: number | null
  /** Its own failure, if it has one - never a sibling sheet's. */
  error?: string | null
  /** Whether this sheet's bytes are on the phone and the map could not draw
   *  from them (lib/backgroundHealth.ts). Distinct from `error`, which is a
   *  transfer that failed; this one is a transfer that SUCCEEDED and left an
   *  archive the map cannot read (#334). */
  notDrawing?: boolean
  /** Whether this sheet's tap has landed and the trail data that has to
   *  arrive first is still coming (App.tsx). Before the transfer, not part of
   *  it - see DownloadCard. */
  preparing?: boolean
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
  /**
   * The sheet's own archives, named, with the size and state the store
   * reports for each (#1103). The card's one figure stays the sheet's - a
   * sheet is one decision - and this is the detail under it, for the hiker
   * who wants to know that "790 MB" is the vector cartography AND the
   * terrain, and which of the two is still coming. Built in App.tsx from
   * the same statuses the sheet figure is combined from, so the breakdown
   * and the clump cannot disagree.
   */
  assets?: readonly SheetAsset[]
  onStart: () => void
  onResume: () => void
  onDelete: () => void
}

/** One named archive inside a sheet - see SheetDownload.assets. */
export interface SheetAsset {
  title: string
  summary: string
  /** null where the catalog cannot price this asset at the chosen level. */
  sizeBytes: number | null
  status: DownloadStatus
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
/**
 * What vector trail data the store holds, read when the window opens - the
 * same moment-of-asking reasoning as useAvailableBytes below. Null until the
 * read lands, and the section simply does not render.
 */
function useStoredTrailData(): TrailDataAsset[] | null {
  const [assets, setAssets] = useState<TrailDataAsset[] | null>(null)

  useEffect(() => {
    let cancelled = false
    void storedTrailData().then((read) => {
      if (!cancelled) setAssets(read)
    })
    return () => {
      cancelled = true
    }
  }, [])

  return assets
}

/** One archive's state, in the card's own words (DownloadCard.tsx) - the
 *  breakdown must never coin a new vocabulary for a state the card above it
 *  already names. */
function assetStateLine(asset: SheetAsset): string {
  const { status } = asset
  switch (status.state) {
    case 'downloading':
      return `${formatBytesLive(status.receivedBytes)} of ${formatBytes(status.totalBytes)} · arriving`
    case 'checking':
      return `${formatBytesLive(status.checkedBytes)} of ${formatBytes(status.totalBytes)} · checking`
    case 'downloaded':
      return asset.sizeBytes === null
        ? 'downloaded'
        : `${formatBytes(asset.sizeBytes)} · downloaded`
    case 'failed':
      return `stopped at ${formatBytesLive(status.receivedBytes)} of ${formatBytes(status.totalBytes)}`
    case 'hash-mismatch':
      return 'did not match what was published'
    case 'evicted':
      return 'removed by the phone to free space'
    default:
      return asset.sizeBytes === null
        ? 'not downloaded'
        : `${formatBytes(asset.sizeBytes)} · not downloaded`
  }
}

/** The trail-data rows' names, hiker words for pipeline artifacts.
 *
 *  Exported for onThisPhone.test.ts, which asserts the two ends cover each
 *  other: a row with no name here renders `undefined` in the window, and a
 *  name with no row is a line nobody will ever see. TypeScript's `Record`
 *  catches the first at compile time and neither at runtime, and the second
 *  not at all - `network-overview` existed as a stored artifact with no row
 *  for a whole release, and nothing anywhere went red. */
export const TRAIL_DATA_LABEL: Record<TrailDataAsset['id'], string> = {
  'trail-line': 'Trail line',
  waypoints: 'Waypoints',
  elevation: 'Elevation profile',
  'nearby-trails': 'Nearby trails network',
  // The same network as the row above, drawn for the opening view. Named for
  // WHEN a hiker sees it rather than for what it is - "corridor-view sketch"
  // is the pipeline's phrase and answers nothing somebody is asking while
  // looking at a storage list.
  'network-overview': 'Nearby trails, zoomed out',
  // Named for what it DOES rather than for what it is. "Junction graph" is the
  // pipeline's word and answers no question a hiker has; this row exists so
  // somebody can tell whether the day-hike builder will work at a trailhead
  // with no signal (#1050).
  'day-hike-routing': 'Day-hike routing',
}

/** One trail-data artifact's state: a measured figure where the store holds
 *  one, presence where it does not, and a stated absence - absent means not
 *  here, never zero. */
function trailAssetLine(asset: TrailDataAsset): string {
  if (!asset.present) return 'not here yet — arrives with signal'
  if (asset.bytes !== null) return `${formatBytes(asset.bytes)} on this phone`
  if (asset.count !== null)
    return `${asset.count.toLocaleString('en-US')} ${
      asset.id === 'waypoints' ? 'places' : 'samples'
    }`
  return 'on this phone'
}

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

/**
 * What the hiker's own waypoint photos take, measured when the window opens.
 *
 * POI_PHOTOS.md's rule for them is visibility, not a cap: "they should be
 * visible in storage management for the same reason everything else is."
 * This screen is the app's storage management, so this is where the line
 * lives. Null until answered or where there is nothing to say - a phone
 * with no photos gets no line rather than a zero.
 */
function useOwnPhotoBytes(): { count: number; bytes: number } | null {
  const [usage, setUsage] = useState<{ count: number; bytes: number } | null>(null)

  useEffect(() => {
    let cancelled = false
    ownPhotoUsage()
      .then((measured) => {
        if (!cancelled && measured.count > 0) setUsage(measured)
      })
      // No IndexedDB, or a read that failed: nothing to report is the
      // honest state, and the line simply does not render.
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  return usage
}

export function Downloads({ sheets, persistence = null }: DownloadsProps) {
  const isDesktop = useDesktop()
  const availableBytes = useAvailableBytes()
  const ownPhotos = useOwnPhotoBytes()
  const trailData = useStoredTrailData()
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
    // An unmeasured sheet raises no warning, which is the conservative
    // direction here rather than the reckless one: the alternative is warning
    // against a number this app does not have. A hiker who taps anyway meets
    // the same storage failure they would have met with a wrong figure, and
    // was not told something false on the way (#1167).
    // Bound to a const so the warning below can read it narrowed - TypeScript
    // cannot carry a narrowing through the separate `spaceTight` boolean.
    const sheetSize = sheet.sizeBytes
    const spaceTight =
      facingFullDownload(sheet.status) &&
      availableBytes !== null &&
      sheetSize !== null &&
      availableBytes < sheetSize

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
                  sheetSize ?? 0,
                )} download. Freeing up space first makes another removal less likely.`
              : `This phone reports about ${formatBytes(availableBytes ?? 0)} free for the app — the ${formatBytes(
                  sheetSize ?? 0,
                )} download may not fit. ${
                  sheet.detail.options.some(
                    (option) =>
                      option.sizeBytes !== null &&
                      sheetSize !== null &&
                      option.sizeBytes < sheetSize,
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
          notDrawing={sheet.notDrawing ?? false}
          preparing={sheet.preparing ?? false}
          detail={sheet.detail}
          persistence={persistence}
          onStart={sheet.onStart}
          onResume={sheet.onResume}
          onDelete={sheet.onDelete}
        />
        {/* The detail under the card's one figure (#1103): which archives
            the sheet's decision buys, each in the state the store reports.
            Only where there is a breakdown to show - a sheet of one archive
            IS its own detail, and a list of one would just repeat the card. */}
        {sheet.assets !== undefined && sheet.assets.length > 1 && (
          <ul className="downloads__assets" data-testid={`downloads-assets-${sheet.id}`}>
            {sheet.assets.map((asset) => (
              <li key={asset.title} className="downloads__asset">
                <span className="downloads__asset-name">{asset.title}</span>
                <span className="downloads__asset-state">{assetStateLine(asset)}</span>
              </li>
            ))}
          </ul>
        )}
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
            The whole trail, downloaded. On a desktop the map streams what it needs as you
            look at it &mdash; the download is for the phone you&rsquo;ll actually be
            carrying.
          </>
        ) : (
          <>
            The whole trail, downloaded. Once it&rsquo;s on your phone, the map works with
            no signal.
          </>
        )}
      </p>

      {/* The hiker's own waypoint photos, stated beside the sheets rather
          than inside them: they are not a package with a lifecycle, just
          bytes worth being able to see (POI_PHOTOS.md - visible, never
          capped). Removal stays on each waypoint's card, where the photo
          and the person who took it are. */}
      {ownPhotos !== null && (
        <p className="downloads__own-photos" data-testid="downloads-own-photos">
          {`Your waypoint photos: ${ownPhotos.count === 1 ? 'one photo' : `${ownPhotos.count} photos`} · ${formatBytes(
            ownPhotos.bytes,
          )} on this phone. Remove one from its waypoint's card.`}
        </p>
      )}

      {/* The vector trail data, stated beside the sheets it is not part of
          (#1103): the line, the waypoints, the elevation, the neighbouring
          network - fetched on their own with signal and until now accounted
          for by the two words "trail data". Every figure is measured off
          what the store actually holds, never a size somebody expects; an
          absent artifact gets a stated absence, because absent means not
          here and never zero. The whole list renders, present or not - a
          missing row would be an artifact this window forgot to answer
          for. */}
      {trailData !== null && (
        <div className="downloads__trail-data" data-testid="downloads-trail-data">
          <p className="downloads__trail-data-title">Trail data on this phone</p>
          <ul className="downloads__assets">
            {trailData.map((asset) => (
              <li key={asset.id} className="downloads__asset">
                <span className="downloads__asset-name">
                  {TRAIL_DATA_LABEL[asset.id]}
                </span>
                <span className="downloads__asset-state">{trailAssetLine(asset)}</span>
              </li>
            ))}
          </ul>
          <p className="downloads__trail-data-note">
            These arrive on their own when the app has signal — nothing here to press.
          </p>
        </div>
      )}

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
