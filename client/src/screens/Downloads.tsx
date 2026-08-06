// Downloads (WIREFRAMES.md §4, as amended by its own Known Deviations #1).
//
// The body of the download window, not a screen of its own since 2026-08-05 -
// DownloadsDialog.tsx is the window it sits in and owns the title and the way
// out. Kept as its own component because what it renders is the download and
// nothing else, which is what all of the tests below it are about.
//
// ONE TRAIL, several packages, since #192. The wireframe drew a per-section
// list with override sheets, roll-up totals and mixed-detail seam messaging;
// ROADMAP.md Phase 2 had already settled on a single whole-corridor package,
// and none of that retired model appears here. What changed is a different
// axis entirely: the offline map program (#184) ships a raster sheet, a
// vector basemap and a DEM to the same phone, so the screen lists the
// PACKAGES a trail is made of - never geographic sections of one.
//
// The distinction is the whole point of the fan-out button below. Sections
// were a choice a hiker had to get right, mile by mile, with a wrong answer
// costing them map where they were walking. Packages are not a choice: the
// trail's manifest (lib/packages.ts) says what its map is made of, and one
// tap takes all of it. The list exists so that progress, failures and
// deletion are reportable per package - not so that anyone has to plan.
//
// Each package's own card - and every honesty property it carries - is
// PackageCard.tsx.

import { useEffect, useState } from 'react'
import { formatBytes } from '../lib/formatBytes'
import type { DetailLevel } from '../lib/downloadDetail'
import type { MapPackage } from '../lib/packages'
import { estimateAvailableBytes, type PersistenceState } from '../lib/storageHealth'
import { useDesktop } from '../lib/useDesktop'
import { PackageCard, type DownloadStatus } from './PackageCard'
import './downloads.css'

/** One package, as the screen needs it: what it is, where its download has
 *  got to, and what tapping does. Built by the shell, which is where the
 *  store and the catalog meet (App.tsx). */
export interface PackageDownload {
  pkg: MapPackage
  status: DownloadStatus
  error?: string | null
  /** What this package will take, where that is knowable before the transfer
   *  starts. Null for a package whose published size is not yet measured -
   *  the room warning then simply leaves it out rather than guessing. */
  sizeBytes: number | null
  detail?: { level: DetailLevel; onChange: (level: DetailLevel) => void }
  onStart: () => void
  onResume: () => void
  onDelete: () => void
}

export interface DownloadsProps {
  /** The trail's packages, in display order. Never empty in the shipped app;
   *  a build with no data source configured says so above this. */
  packages: readonly PackageDownload[]
  /** What asking for durable storage came to - null while unanswered. */
  persistence?: PersistenceState | null
  /** Start every package that is not already on the phone. Offered only when
   *  there is more than one, since with one package it would be a second
   *  button doing what the card's own button does. */
  onStartAll?: () => void
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

/** Packages whose bytes are not on the phone - what a download would add. A
 *  failed one is left out: some of it is already stored, so counting its full
 *  size would overstate what is still to come. */
function isAbsent(entry: PackageDownload): boolean {
  return entry.status.state === 'not-downloaded' || entry.status.state === 'evicted'
}

export function Downloads({ packages, persistence = null, onStartAll }: DownloadsProps) {
  const isDesktop = useDesktop()
  const availableBytes = useAvailableBytes()

  const absent = packages.filter(isAbsent)
  const pendingBytes = absent.reduce((total, entry) => total + (entry.sizeBytes ?? 0), 0)

  // Warned, never refused: estimate() is deliberately fuzzy (browsers round
  // it against fingerprinting), and a hiker at a trailhead deciding to try
  // anyway is making an informed call, which is the whole point.
  const spaceTight =
    pendingBytes > 0 && availableBytes !== null && availableBytes < pendingBytes

  const everythingEvicted =
    absent.length > 0 && absent.every((entry) => entry.status.state === 'evicted')

  // One tap for the trail's whole manifest. Withheld for a single package
  // because it would then be a duplicate of that card's own button, and
  // withheld when nothing is missing because there would be nothing to do.
  const showStartAll =
    onStartAll !== undefined && packages.length > 1 && absent.length > 0

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
          {everythingEvicted
            ? `Space still looks tight — about ${formatBytes(availableBytes ?? 0)} free against a ${formatBytes(
                pendingBytes,
              )} download. Freeing up space first makes another removal less likely.`
            : `This phone reports about ${formatBytes(availableBytes ?? 0)} free for the app — the ${formatBytes(
                pendingBytes,
              )} download may not fit. A lighter detail level might, or free up some space first.`}
        </p>
      )}

      {showStartAll && (
        <button type="button" className="downloads__primary" onClick={onStartAll}>
          Download everything the map needs
        </button>
      )}

      <ul className="downloads__packages">
        {packages.map((entry) => (
          <li key={entry.pkg.id}>
            <PackageCard
              pkg={entry.pkg}
              status={entry.status}
              error={entry.error}
              detail={entry.detail}
              persistence={persistence}
              // With one package the paragraph above has already named what
              // is being downloaded, and a heading would only say it twice.
              showHeading={packages.length > 1}
              onStart={entry.onStart}
              onResume={entry.onResume}
              onDelete={entry.onDelete}
            />
          </li>
        ))}
      </ul>
    </div>
  )
}
