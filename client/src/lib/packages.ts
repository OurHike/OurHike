// The catalog of offline map packages - the one place a package's identity
// lives (issues #192/#200).
//
// A package is one downloadable PMTiles archive with its own IndexedDB key,
// its own download lifecycle (partial/progress/source records derive from
// the key - see archiveDownload.ts), and its own pmtiles:// URL (protocol.ts
// registers every entry here). The offline map program (#184) ships several
// archives to the same phone - vector basemap, DEM, the USGS raster sheet -
// so the store is keyed per package.
//
// Several archives, but never a checklist to a hiker: they group into
// background SHEETS (BACKGROUND_SHEETS below) - the hiking sheet everyone
// gets, and the USGS raster as an optional second one (#237). Each sheet is
// chosen and downloaded as one decision. The archives are also shared
// between trails rather than owned by one - see the sheet comment for why
// both of those matter.
//
// The corridor background keeps the key it has always had: an archive
// already sitting in a tester's IndexedDB under 'ourhike:corridor-archive'
// stays readable after this change, rather than silently re-downloading.

import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'
import { archiveKey, archiveUrl, dataUrl } from './config'
import { getDownloadDetail, type DetailLevel } from './downloadDetail'
import { getHikingDetail } from './hikingDetail'
import { NO_PUBLISHED_SIZES, type PublishedSizes } from './usePublishedSizes'
import type { HikingDetailLevel } from './userPreferences'

/**
 * Where a package's bytes are fetched from, or `null` while nothing
 * publishes them yet.
 *
 * Nullable on purpose, and it is this file's honesty mechanism: a package
 * with no source is still catalogued - its key is registered, and an archive
 * already stored under it still resolves and can still be deleted - but it
 * is never OFFERED. Offering a download whose artifact `publish.py` cannot
 * produce is a 404 on a mountain, which is the same failure the pipeline's
 * `BACKGROUND_ARCHIVES` was made a named mapping to prevent when the app was
 * offering a Light tier that did not exist.
 */
export type PackageSource =
  /**
   * One published artifact per download tier, so both the URL and the size
   * depend on the hiker's Light/Standard/Fine choice (downloadDetail.ts,
   * and config.ts's BACKGROUND_ARCHIVES, which names the same three files
   * publish.py writes).
   */
  | { kind: 'tiered' }
  /**
   * One published artifact per HIKING level (#276), resolved through
   * hikingDetail.ts the same way 'tiered' resolves through downloadDetail.ts.
   * A separate kind because the two sheets' level choices are separate
   * preferences and must never share one dial.
   *
   * `of` says WHICH of the level's two artifacts this package is. Both the
   * basemap and the DEM vary by level since #1088 - the basemap by its zoom
   * cut, the DEM by how hard its corridor tapers - so the kind alone no longer
   * identifies the artifact. Spelled as a discriminant rather than inferred
   * from the package id, because the id is a display concern and this is a
   * fetch one: getting it wrong downloads the wrong archive under the right
   * hash and fails verification on a mountain.
   */
  | { kind: 'leveled'; of: 'basemap' | 'dem' }
  /** One artifact, one size. Nothing in the hiking sheet is this any more -
   *  the DEM became leveled with #1088 - but the raster sheet's future
   *  siblings may be, and removing the case would make the union a
   *  single-member one that says nothing. */
  | { kind: 'artifact'; artifact: string; sizeBytes: number }

export interface MapPackage {
  /** Stable identity in code and in the published catalog. */
  id: string
  /** IndexedDB key of the completed archive; download records derive from it. */
  idbKey: string
  /** What the Downloads screen calls it. */
  title: string
  /** One line under that title, saying what the bytes buy. */
  summary: string
  /** How to fetch it, or null while nothing publishes it - see PackageSource. */
  source: PackageSource | null
}

/**
 * A package with something published behind it.
 *
 * A distinct type rather than a runtime check, because it is what makes a
 * missing size unrepresentable: every `PackageSource` carries a size (a tier
 * table for the raster sheet, a measured number for everything else), so a
 * package that can be downloaded always has one, and nothing downstream needs
 * a null branch it could get wrong. `offeredPackages()` is the only way to
 * obtain one, and it is the same filter that keeps unpublished packages off
 * the screen.
 */
export type OfferedPackage = MapPackage & { source: PackageSource }

/** Typed as offered, not merely catalogued: it is the one piece of the
 *  background the pipeline publishes today, so its size and URL are always
 *  answerable and callers need no null branch for it. */
export const CORRIDOR_BACKGROUND_PACKAGE: OfferedPackage = {
  id: 'corridor-background',
  idbKey: CORRIDOR_ARCHIVE_KEY,
  title: 'USGS sheet',
  summary: 'The whole corridor as a topographic picture.',
  source: { kind: 'tiered' },
}

/**
 * The vector basemap package - the hiking sheet's own tiles, cut by
 * pipeline/extract_package.py from the periodic Planetiler build (#184).
 *
 * map/basemap.ts resolves the sheet's `basemap://` tile requests against
 * this key first and falls through to the network where the package does
 * not answer (#189).
 *
 * Leveled since #276: the hiker's hiking_detail_level preference picks the
 * z13 Standard cut or the z14 Fine one (lib/hikingDetail.ts carries the
 * artifacts and their exact published bytes). One store key across levels,
 * like the raster tiers: switching level re-downloads under the same key.
 */
export const BASEMAP_PACKAGE: MapPackage = {
  id: 'basemap',
  idbKey: 'ourhike:basemap',
  title: 'Hiking sheet',
  summary: 'The styled topographic sheet, so the good map works offline too.',
  source: { kind: 'leveled', of: 'basemap' },
}

/**
 * The corridor DEM package - quantized terrarium WebP tiles, z0-13, built by
 * pipeline/export_dem.py (#186). map/demTiles.ts resolves the hillshade's
 * and the contour generator's elevation reads against this key first and
 * falls through to AWS Terrain Tiles where it does not answer (#187) - the
 * same local-first shape basemap.ts gives the vector sheet.
 *
 * Leveled since #1088, and NOT by zoom the way the basemap is: capping the
 * DEM at z12 measured worse than the 1 m quantize step already rejected
 * (66.4% of hillshade pixels shifted in the Smokies - pipeline/LIGHT_DOWNLOAD.md).
 * What differs per level is how hard the terrain CORRIDOR tapers - 30 miles
 * through z11, 15 at z12, 6 at z13 at Standard, harder at Light - so every
 * level is z0-13 and they differ in ground covered, not in detail. A hiker who
 * drops to Light loses hillshade out on the flank, never sharpness underfoot.
 *
 * The artifact names are publish.py's OFFLINE_SHEET_ARCHIVES keys and the
 * sizes are the published artifacts' exact bytes (lib/hikingDetail.ts, which
 * also carries the `published` gate keeping an unbuilt level off the screen).
 */
export const DEM_PACKAGE: MapPackage = {
  id: 'dem',
  idbKey: 'ourhike:dem',
  title: 'Terrain',
  summary: 'Hillshade and contours, drawn on the phone from downloaded elevation.',
  source: { kind: 'leveled', of: 'dem' },
}

/** Every package this build knows how to store and resolve, in the order
 *  they matter to a hiker. */
export const MAP_PACKAGES: readonly MapPackage[] = [
  CORRIDOR_BACKGROUND_PACKAGE,
  BASEMAP_PACKAGE,
  DEM_PACKAGE,
]

/**
 * One background SHEET: a map drawn under the trail, downloaded as one
 * decision, made of one or more archives underneath.
 *
 * Plural since #237 (decided 2026-08-06): the hiking sheet - vector basemap
 * plus DEM, the exact cartography the app already draws - is the background
 * a hiker gets by default, and the USGS raster is an OPTIONAL SECOND SHEET
 * they opt into. Bundling both would hand every hiker over a gigabyte of
 * government scan they did not ask for, on top of the sheet that replaced
 * it; a checklist of raw archives would make them assemble a map out of
 * plumbing. A sheet is the honest middle: hikers choose sheets, never
 * archive schemas.
 *
 * SHARED ACROSS TRAILS, WHICH IS THE POINT OF GROUPING SHEETS AT ALL.
 *
 * A hiker who has the AT's background and then adds NYNJTC's network must not
 * re-download the ground both of them stand on. So these packages are keyed
 * by what they ARE - `ourhike:dem`, `ourhike:corridor-archive` - and never by
 * which trail wanted them. Nothing in this file is trail-scoped, and nothing
 * downstream may make it so: a per-trail key would silently duplicate several
 * hundred megabytes of identical tiles on one phone, which is the failure
 * #193 exists to prevent.
 *
 * What IS per-trail is the trail data - the centerline, the spurs, the POIs,
 * the elevation profile (lib/trailData.ts). That is small, it is downloaded
 * by default whenever it is missing rather than being something to choose,
 * and it is deliberately not a sheet here.
 *
 * Versioning deliberately does not live here. Which bytes are current is
 * `latest.json`'s per-artifact hashes (pipeline/DATA_RELEASES.md), and a
 * second scheme in the client would be a second answer to the same question.
 */
export interface BackgroundSheet {
  id: string
  /** What the Downloads screen calls this sheet. */
  title: string
  summary: string
  /** Every archive the sheet is made of, in the order they matter. */
  packages: readonly MapPackage[]
  /**
   * Set while this sheet is deliberately not on offer, though its archives
   * are still published and this build can still read them.
   *
   * A DIFFERENT FACT FROM `source: null`, and the distinction is the whole
   * reason it is its own field. A null source says the bytes do not exist -
   * offering them would 404 on a mountain. This says the bytes exist, a
   * phone may well be carrying them, and we have stopped asking anyone to
   * take more. So the two are filtered in opposite directions: an
   * unpublished package is never listed at all, and a withdrawn sheet stays
   * listed for exactly as long as its archive is on the phone, because the
   * card is where the Delete button lives (#855). Withdrawing an offer must
   * not strand somebody's storage.
   *
   * Optional, and read as a boolean rather than a reason string: the reason
   * belongs in a comment on the sheet, where it can be a paragraph, and no
   * screen renders one.
   */
  withdrawn?: boolean
}

/**
 * The default background: the hiking sheet's own tiles and terrain, so the
 * map the app draws every day is the one that works with no signal. What
 * `background_source: 'hiking_topo_live'` draws - live over the network,
 * local-first from these packages once they are on the phone (#187/#189).
 */
export const HIKING_SHEET: BackgroundSheet = {
  id: 'hiking-sheet',
  title: 'Hiking sheet',
  summary: 'The map you are looking at - cartography and terrain, offline.',
  packages: [BASEMAP_PACKAGE, DEM_PACKAGE],
}

/**
 * The opt-in second sheet: the USGS quads as a topographic picture, for
 * hikers who want the authoritative government map beside the drawn one.
 * What `background_source: 'usgs_topo_offline'` draws. Never bundled into
 * anyone's download unasked (#237) - it has its own card, its own size, and
 * deleting it never touches the sheet a hiker navigates by.
 *
 * WITHDRAWN FOR v2, AND THIS LINE IS THE SWITCH (#855).
 *
 * The maintainer's call, 2026-08-20: the raster is not good enough to be
 * worth what it costs to build. That is a judgement about the sheet, not a
 * measurement of it, and it is recorded as one - what IS measured is the
 * build. `build-raster.yml` fans out one render job per 1x1-degree corridor
 * cell (its own header says 51) with a 150-minute timeout each, then
 * reconverges them on a single runner with a 300-minute one. Nothing else in
 * this repository is shaped like that, and the sheet it produces is the
 * optional second background rather than the one a hiker navigates by.
 *
 * Withdrawn rather than deleted, and `source` deliberately left alone: the
 * tiers are in the bucket and somebody may be carrying up to 1.2 GB of them
 * (downloadDetail.ts's measured figures). They keep their card and their
 * Delete button for as long as those bytes are on the phone - see
 * `withdrawn` on BackgroundSheet, and `catalogSheets` in App.tsx.
 *
 * Deleting this one property is the whole of turning it back on.
 */
export const USGS_SHEET: BackgroundSheet = {
  id: 'usgs-sheet',
  title: 'USGS sheet',
  summary: 'The official government topo, as an optional second map.',
  packages: [CORRIDOR_BACKGROUND_PACKAGE],
  withdrawn: true,
}

/** Every sheet, default first. Catalogued rather than offered: what a hiker
 *  may actually be asked to download is `offeredSheets()`. */
export const BACKGROUND_SHEETS: readonly BackgroundSheet[] = [HIKING_SHEET, USGS_SHEET]

/**
 * One sheet's archives a hiker can be offered right now: catalogued, and
 * with something published behind them.
 *
 * Note what this does NOT filter on - whether the archive is already on the
 * phone. A downloaded package stays included so it can be deleted, and an
 * evicted one stays included so the screen can say so (#190).
 */
export function offeredPackages(sheet: BackgroundSheet): OfferedPackage[] {
  return sheet.packages.filter((pkg): pkg is OfferedPackage => pkg.source !== null)
}

/**
 * The sheets a hiker can be asked to download right now: at least one
 * published archive, and not withdrawn.
 *
 * A sheet whose every package is `source: null` is not a decision anyone can
 * act on - rendering it would offer a download that 404s on a mountain, the
 * exact thing the null source exists to prevent. While the raster was the
 * only published artifact this returned the USGS sheet alone, which is why
 * the old single-bundle screen was right by accident (#237).
 *
 * A withdrawn sheet is excluded for a different reason and this is the only
 * place the two meet: its bytes are perfectly obtainable and we have stopped
 * asking (#855). Every screen that OFFERS a download reads this - the
 * window's tabs, first run's - and none of them may show a withdrawn sheet.
 * What a phone already holds is `withdrawnSheets()`'s question, not this
 * one.
 */
export function offeredSheets(): BackgroundSheet[] {
  return BACKGROUND_SHEETS.filter(
    (sheet) => offeredPackages(sheet).length > 0 && sheet.withdrawn !== true,
  )
}

/**
 * The sheets that are no longer offered but whose archives this build still
 * knows how to read, store and delete.
 *
 * Separate from `offeredSheets()` rather than a flag on it, because the two
 * answers are used by different screens for opposite purposes: one is "what
 * may a hiker be asked to take", the other is "what may a hiker still be
 * carrying". App.tsx joins them - a withdrawn sheet reaches the download
 * window only while its bytes are actually here, and arrives there with no
 * Download button, because DownloadCard only offers one in `not-downloaded`.
 *
 * Empty in the ordinary case, and that is the point: nothing downstream
 * needs to know a withdrawal ever happened.
 */
export function withdrawnSheets(): BackgroundSheet[] {
  return BACKGROUND_SHEETS.filter(
    (sheet) => offeredPackages(sheet).length > 0 && sheet.withdrawn === true,
  )
}

/**
 * Whether `background_source: 'usgs_topo_offline'` is a choice a hiker can
 * still make on this phone.
 *
 * The rule lives here rather than on either picker because both pickers are
 * the same component rendered twice (chrome/BackgroundPicker.tsx) from two
 * screens that do not share a parent - and a rule about what the catalog
 * offers, spelled out separately in the legend and in Settings, is a rule
 * with two chances to drift.
 *
 * It is the SAME question the download window asks about the USGS card, one
 * step along: that background draws the raster archive and nothing else, so
 * it is a choice exactly while the sheet behind it is one - published, and
 * either still on offer or already on this phone. A withdrawn sheet somebody
 * downloaded before the withdrawal keeps both (#855); a withdrawn sheet
 * nobody took offers neither.
 */
export function offlineBackgroundAvailable(rasterArchiveDownloaded: boolean): boolean {
  return (
    offeredPackages(USGS_SHEET).length > 0 &&
    (USGS_SHEET.withdrawn !== true || rasterArchiveDownloaded)
  )
}

/** The hiking sheet's total at a level (#276) - what its picker shows per
 *  option. The raster detail argument is irrelevant to this sheet (none of
 *  its packages are tiered), so any value yields the same sum; 'standard'
 *  is passed as the arbitrary constant. */
export function hikingSheetSizeBytes(
  level: HikingDetailLevel,
  published: PublishedSizes = NO_PUBLISHED_SIZES,
): number | null {
  return sheetSizeBytes(HIKING_SHEET, 'standard', level, published)
}

/**
 * What one sheet will cost in total: every archive of it that is actually
 * offered, at the chosen levels - or null if any one of them is unpriced.
 *
 * ALL OR NOTHING, deliberately. A sheet is one decision to a hiker, and a
 * total that quietly omitted the archive nobody had measured would understate
 * it - the direction that strands somebody who freed exactly enough. Summing
 * what is known would be arithmetic on a number this app does not have.
 */
export function sheetSizeBytes(
  sheet: BackgroundSheet,
  detail: DetailLevel,
  hikingLevel: HikingDetailLevel,
  published: PublishedSizes = NO_PUBLISHED_SIZES,
): number | null {
  return offeredPackages(sheet).reduce<number | null>((total, pkg) => {
    if (total === null) return null
    const size = packageSizeBytes(pkg, detail, hikingLevel, published)
    return size === null ? null : total + size
  }, 0)
}

/**
 * Where this package's bytes are fetched from right now.
 *
 * The detail level is an argument rather than a lookup because it is the
 * hiker's live choice: a tap has to fetch the tier selected at the moment of
 * tapping, not the one selected when a callback was built.
 */
export function packageDownloadUrl(
  pkg: OfferedPackage,
  detail: DetailLevel,
  hikingLevel: HikingDetailLevel,
): string {
  return pkg.source.kind === 'tiered'
    ? archiveUrl(detail)
    : dataUrl(packageArtifactKey(pkg, detail, hikingLevel))
}

/**
 * Which artifact this package is, as `latest.json` names it.
 *
 * The same choice `packageDownloadUrl` makes, expressed as the manifest's own
 * key rather than as a URL - and it is the catalog's answer to give. Reading
 * it back off the URL worked only while every artifact's URL happened to end
 * in its manifest key, and the cost of the first one that did not would have
 * been a download that quietly skipped verification (lib/archiveDownload.ts).
 */
export function packageArtifactKey(
  pkg: OfferedPackage,
  detail: DetailLevel,
  hikingLevel: HikingDetailLevel,
): string {
  if (pkg.source.kind === 'tiered') return archiveKey(detail)
  if (pkg.source.kind === 'leveled') {
    const detail = getHikingDetail(hikingLevel)
    return pkg.source.of === 'dem' ? detail.demArtifact : detail.artifact
  }
  return pkg.source.artifact
}

/**
 * What this package will cost in bytes, or null where nothing has measured it.
 *
 * ALWAYS MEASURED WHEN IT IS A NUMBER, which is the property worth keeping and
 * the reason null exists at all: every figure this returns came off the bucket,
 * either from `latest.json` (#505) or from a table whose artifacts nothing
 * rebuilds. It never returns an estimate, and since #1167 it never returns a
 * hand-copied constant for the hiking sheet - those had drifted up to 34.7%.
 *
 * A null is a real state rather than an error: the manifest has not landed
 * (first run, no signal) and this level's size is genuinely not known yet. It
 * reaches a hiker as withheld rather than guessed - an honest unknown outranks
 * a confident answer, and a figure somebody frees exactly enough room for is
 * the confidently wrong one.
 */
export function packageSizeBytes(
  pkg: OfferedPackage,
  detail: DetailLevel,
  hikingLevel: HikingDetailLevel,
  published: PublishedSizes = NO_PUBLISHED_SIZES,
): number | null {
  // The bucket's own measurement wins wherever it exists (#505). The constants
  // below stop being the source of truth and become the answer for a phone
  // that has not been able to ask - which is a real state, not a degenerate
  // one: first run on a slow connection reads them before latest.json lands,
  // and a build with no bucket at all never gets to ask.
  //
  // Looked up by packageArtifactKey rather than by a second mapping from
  // package to key, because that function is already "the catalog's answer to
  // give" and the cost of two spellings drifting apart is a size that silently
  // describes a different archive.
  const measured = published[packageArtifactKey(pkg, detail, hikingLevel)]
  if (measured !== undefined) return measured

  if (pkg.source.kind === 'tiered') return getDownloadDetail(detail).sizeBytes
  // NULL RATHER THAN A CONSTANT, for the hiking sheet only (#1167). Its two
  // artifacts are rebuilt often enough that a hand-copied figure had already
  // drifted 34.7% from one environment; hikingDetail.ts's header carries the
  // measurements. So a level the manifest has not priced has no price here,
  // and the picker says so instead of showing a number nobody stands behind.
  //
  // This is the one branch that can answer null, which is why the return type
  // widened rather than every caller gaining a guard for cases that cannot
  // happen: `tiered` still falls back to downloadDetail.ts's table (its build
  // is withdrawn under #855, so nothing is rebuilding those archives for a
  // constant to drift away from), and a fixed package carries its own size.
  if (pkg.source.kind === 'leveled') return null
  return pkg.source.sizeBytes
}
