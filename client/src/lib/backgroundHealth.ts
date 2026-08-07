// What is wrong with the background on screen, when something is (#314).
//
// The failure this exists for is the worst screen this app can produce: a
// hiker offline, looking at blank paper, with every indicator green. Two ways
// there, and neither said a word before this module:
//
//   - A downloaded archive that is PRESENT and unreadable. Truncated, half
//     evicted, corrupt - the blob is under the key, so `archiveDownloaded`
//     stays true, the offline background is honoured, and every tile request
//     against it fails silently.
//   - A hiking sheet DELETED an hour ago. Its tiles fall through to the
//     network (map/basemap.ts), which offline answers nothing, and the status
//     strip suppressed its one relevant flag whenever the phone was offline -
//     that is, exactly when it mattered. Nobody connects a blank map to a
//     delete they made at lunch.
//
// WHY THE SOURCE FLAGS CANNOT ANSWER THIS ALONE
//
// map/liveSourceHealth.ts reports which background sources errored and never
// drew. That is a fact about the map, not a statement about the hiker's
// situation, and the same fact means opposite things on two phones:
// `archive: true` on a phone with no download is the ordinary, correct state
// (style.ts declares that source under both backgrounds, so it fails every
// request when there is nothing to read), while on a phone that HAS the
// download it means the download is not readable. What turns one into the
// other is what is on the phone, which the map cannot see. So the two are
// joined here, once, rather than at the two call sites that each want a
// different half of it.
//
// EVERY ANSWER HAS TO BE ACTIONABLE OR IT IS NOISE
//
// This deliberately does not report "your DEM is missing" or "the live sheet
// is thin here". A hillshade that fails costs relief on a sheet that still
// draws - terrain.ts promises exactly that degradation - and a strip that
// flags it has spent the hiker's attention on something they cannot act on
// and did not need. Everything below is a state where the map is blank or
// the fix is a download.

import type { LiveSourceHealth } from '../map/liveSourceHealth'
import {
  BASEMAP_PACKAGE,
  CORRIDOR_BACKGROUND_PACKAGE,
  type BackgroundSheet,
} from './packages'

/**
 * Why the background is not on screen, or `null` when nothing is wrong.
 *
 * A reason rather than a boolean, for the same argument lib/dataSaver.ts
 * makes about its overrides: these need opposite copy and imply opposite
 * actions. "Your download is broken" sends someone to the Downloads screen;
 * "you have no download" sends them to town for signal first. One flag
 * covering both would send half of them to the wrong place.
 */
export type BackgroundProblem =
  /** A sheet IS on this phone and its source drew nothing. The download is
   *  there and unreadable - the state #314 was filed for. */
  | 'download-not-drawing'
  /** The live sheet never arrived, and no download stands behind it. The
   *  network is the whole story here, which is why this one is about signal
   *  and the one above is not. */
  | 'live-unreachable'
  /** Offline with nothing downloaded: blank paper, honestly. "Offline" on its
   *  own does not say that a download is the missing half, and after a delete
   *  it is the half the hiker needs told. */
  | 'nothing-to-draw'

export interface BackgroundHealthInputs {
  /** Which background sources errored and never drew (liveSourceHealth.ts). */
  sources: LiveSourceHealth
  /** navigator.onLine's optimistic answer (lib/useOnline.ts). Read only to
   *  choose between two true statements, never to decide whether one is due. */
  online: boolean
  /** Whether the USGS raster archive is on the phone. */
  rasterArchiveDownloaded: boolean
  /** Whether the hiking sheet's vector package is on the phone. */
  hikingSheetDownloaded: boolean
}

export function backgroundProblem({
  sources,
  online,
  rasterArchiveDownloaded,
  hikingSheetDownloaded,
}: BackgroundHealthInputs): BackgroundProblem | null {
  // First, and above the connectivity questions below, because it is the only
  // one of the three that is both certainly wrong and fixable where the hiker
  // is standing. It also outranks them on truth: a phone holding a download
  // that will not draw is not suffering from being offline, and saying so
  // would send someone looking for signal they do not need.
  const downloadFailing =
    (sources.archive && rasterArchiveDownloaded) ||
    (sources.basemap && hikingSheetDownloaded)
  if (downloadFailing) return 'download-not-drawing'

  // Nothing that was expected to draw has failed. The archive source failing
  // on a phone with no archive is the ordinary state and is not reported -
  // see the header, and note that it is the live sheet, not the archive, that
  // is drawing for that hiker.
  if (!sources.basemap) return null

  // Unchanged from what this strip has always said, and kept unchanged
  // deliberately: a connection the phone believes in and a tile host that
  // does not answer is the case navigator.onLine cannot catch, and it is
  // worth saying even when the archive is drawing underneath - the sheet on
  // screen is then not the one the hiker chose, and this line is the only
  // thing that explains why it looks different today.
  if (online) return 'live-unreachable'

  // Offline. The archive is drawing underneath, which is the whole point of
  // stacking the live sheet over it (features/MAP_OPTIONS.md §1): the hiker
  // has a map, it is simply the downloaded one. Flagging that would be
  // flagging the arrangement working exactly as designed.
  if (rasterArchiveDownloaded) return null

  return 'nothing-to-draw'
}

/**
 * Which watched source draws a given package's bytes.
 *
 * The DEM is deliberately absent, and its absence is the rule rather than an
 * omission: a sheet whose hillshade failed still draws, so a DEM that never
 * arrived must not make its sheet's card say the download is not drawing.
 * The same exclusion `backgroundProblem` makes for the status strip, made
 * once here so the two screens cannot disagree about it.
 */
const PACKAGE_SOURCE: Record<string, keyof LiveSourceHealth> = {
  [CORRIDOR_BACKGROUND_PACKAGE.idbKey]: 'archive',
  [BASEMAP_PACKAGE.idbKey]: 'basemap',
}

/**
 * Whether a sheet's bytes are on the phone and its own source drew nothing -
 * the sentence the Downloads card owes a hiker whose map is blank (#334).
 *
 * `downloaded` is the card's OWN claim, passed in rather than re-derived, and
 * that is the point: this notice exists to contradict a card that says the
 * download finished, so it must be answering about the same status the card
 * is rendering. Every other combination stays silent - an archive that is
 * absent has no card claiming otherwise, and a source failing with nothing
 * downloaded is the ordinary state (see the header).
 */
export function sheetNotDrawing(
  sources: LiveSourceHealth,
  sheet: BackgroundSheet,
  downloaded: boolean,
): boolean {
  if (!downloaded) return false

  return sheet.packages.some((pkg) => {
    const flag = PACKAGE_SOURCE[pkg.idbKey]
    return flag !== undefined && sources[flag]
  })
}

/**
 * The same flags with one sheet's cleared - what a shell that REMEMBERS a
 * failure has to do when that sheet is fetched again.
 *
 * Without this, a hiker who saw "not drawing", deleted the archive and
 * downloaded a good one would be told the fresh copy is broken too: the
 * remembered flag describes bytes that are no longer on the phone, and the
 * map only contradicts it once it happens to ask that source for a tile and
 * succeed. Cleared per sheet rather than wholesale, so re-fetching the
 * hiking sheet says nothing about the USGS archive beside it.
 */
export function forgetSheet(
  sources: LiveSourceHealth,
  sheet: BackgroundSheet,
): LiveSourceHealth {
  const cleared = { ...sources }
  for (const pkg of sheet.packages) {
    const flag = PACKAGE_SOURCE[pkg.idbKey]
    if (flag !== undefined) cleared[flag] = false
  }
  return cleared
}
