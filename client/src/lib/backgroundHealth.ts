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

import {
  SOURCE_FLAGS,
  type LiveSourceHealth,
  type SourceReport,
} from '../map/liveSourceHealth'
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
  /** Whether the hiking sheet's tiles are on the phone - the whole vector
   *  package, or any cell of it (lib/coverageCells.ts, #557). */
  hikingSheetDownloaded: boolean
  /**
   * Whether the view is past the edge of everything downloaded
   * (lib/archiveCoverage.ts's `coverageAt`), which changes what a failing
   * source MEANS.
   *
   * A phone holding a stretch rather than the whole sheet, panned off it with
   * no signal, has a basemap source that errors on every request - for the
   * ordinary reason that the tiles beyond the stretch fall through to a
   * network that is not there. That is not a download failing to draw, and
   * calling it one is #352 again: a hiker past the edge of their package told
   * their download was damaged. Nor is it "no downloaded map", which is false
   * of a phone with a stretch on it. Both readings stand down, and the strip's
   * own "Outside what you downloaded" says the true thing instead. Defaults to
   * false, which is every phone that has not established an edge.
   */
  outsideDownload?: boolean
}

export function backgroundProblem({
  sources,
  online,
  rasterArchiveDownloaded,
  hikingSheetDownloaded,
  outsideDownload = false,
}: BackgroundHealthInputs): BackgroundProblem | null {
  // First, and above the connectivity questions below, because it is the only
  // one of the three that is both certainly wrong and fixable where the hiker
  // is standing. It also outranks them on truth: a phone holding a download
  // that will not draw is not suffering from being offline, and saying so
  // would send someone looking for signal they do not need.
  //
  // Unless the view is past the download's own edge - then a source that
  // draws nothing is drawing exactly what the phone has there, which is
  // nothing, and the edge flag is the honest sentence (see `outsideDownload`).
  const downloadFailing =
    (sources.archive && rasterArchiveDownloaded) ||
    (sources.basemap && hikingSheetDownloaded)
  if (downloadFailing && !outsideDownload) return 'download-not-drawing'

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

  // Offline, past the edge of a download that exists. "No downloaded map"
  // would be false - there is one, a few miles back - and the strip already
  // carries the flag that says where it ends.
  if (outsideDownload) return null

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
 * What the shell should remember, given what it remembered and what the map
 * has just reported.
 *
 * THE RULE, AND THE TWO WAYS THE FIRST ATTEMPT BROKE IT (#352)
 *
 * A source that has DRAWN is drawing: forget any failure remembered against
 * it, whichever map observed that failure. A source that errored and has
 * never drawn is not: remember it. A source that has done neither leaves the
 * memory alone, which is what carries a real failure across the teardown the
 * downloads window costs (#334).
 *
 * That last clause is why this cannot be "trust the latest report". A fresh
 * map has observed nothing; treating its silence as good news would clear a
 * genuine failure the moment the hiker walked to the screen that fixes it.
 * And treating a teardown's `HEALTHY` as good news does the same - hence
 * `withdrawn`, which the caller drops before it ever gets here.
 *
 * The inverse mistake was the shipped one. With only failures reported, a
 * healthy map said nothing at all, so nothing could ever lower a remembered
 * flag and a single transient error condemned a good archive for the session.
 * It was patched with a hand-maintained clear on the download path, which
 * then had to be remembered on every OTHER path that replaces bytes - and was
 * not, on resume. `drew` makes the clearing fall out of the same fold instead
 * of being a second mechanism to keep in step.
 */
export function rememberNotDrawing(
  remembered: LiveSourceHealth,
  report: SourceReport,
): LiveSourceHealth {
  const next = { ...remembered }
  for (const flag of SOURCE_FLAGS) {
    if (report.drew[flag]) next[flag] = false
    else if (report.unreachable[flag]) next[flag] = true
  }
  return next
}

/**
 * The same flags with the given packages' cleared - what a shell has to do
 * when those exact bytes are fetched again.
 *
 * Kept even though `rememberNotDrawing` now retracts a failure the moment the
 * source draws, because the two cover different gaps. A finished download
 * does not make the map re-request the tiles it already gave up on: MapLibre
 * holds those as errored until something rebuilds the map or the hiker pans,
 * so without this a fresh, good archive can wear the old one's verdict until
 * they happen to move the camera. This clears it at the moment the bytes are
 * known to be replaced.
 *
 * Takes the package keys actually being fetched rather than a whole sheet.
 * Clearing a sheet wholesale (#352) cleared `basemap` when only the DEM
 * beside it was being downloaded, silently withdrawing a "No live map" that
 * was still true and that the map had no way to state again.
 */
export function forgetPackages(
  sources: LiveSourceHealth,
  idbKeys: readonly string[],
): LiveSourceHealth {
  const cleared = { ...sources }
  for (const key of idbKeys) {
    const flag = PACKAGE_SOURCE[key]
    if (flag !== undefined) cleared[flag] = false
  }
  return cleared
}
