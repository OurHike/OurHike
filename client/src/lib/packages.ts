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
  /** One artifact, one size - what every package but the raster sheet is. */
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
 * The artifact name is publish.py's OFFLINE_SHEET_ARCHIVES key, and the
 * size is the published artifact's exact bytes (build-basemap.yml run of
 * 2026-08-06: 14-state corridor build, z0-14 cut, 83,818 tiles) - measured,
 * per the honesty bar packageSizeBytes documents.
 */
export const BASEMAP_PACKAGE: MapPackage = {
  id: 'basemap',
  idbKey: 'ourhike:basemap',
  title: 'Hiking sheet',
  summary: 'The styled topographic sheet, so the good map works offline too.',
  source: {
    kind: 'artifact',
    artifact: 'at_basemap_package.pmtiles',
    sizeBytes: 532_459_439,
  },
}

/**
 * The corridor DEM package - quantized terrarium WebP tiles, z0-13, built by
 * pipeline/export_dem.py (#186). map/demTiles.ts resolves the hillshade's
 * and the contour generator's elevation reads against this key first and
 * falls through to AWS Terrain Tiles where it does not answer (#187) - the
 * same local-first shape basemap.ts gives the vector sheet.
 *
 * The artifact name is publish.py's OFFLINE_SHEET_ARCHIVES key, and the
 * size is the published artifact's exact bytes (build-dem.yml run of
 * 2026-08-06: 21,758 corridor tiles z0-13, 0 absent, 0.5 m quantize per
 * #186's banding check) - measured, never an estimate.
 */
export const DEM_PACKAGE: MapPackage = {
  id: 'dem',
  idbKey: 'ourhike:dem',
  title: 'Terrain',
  summary: 'Hillshade and contours, drawn on the phone from downloaded elevation.',
  source: { kind: 'artifact', artifact: 'dem.pmtiles', sizeBytes: 607_265_661 },
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
 */
export const USGS_SHEET: BackgroundSheet = {
  id: 'usgs-sheet',
  title: 'USGS sheet',
  summary: 'The official government topo, as an optional second map.',
  packages: [CORRIDOR_BACKGROUND_PACKAGE],
}

/** Every sheet, default first. */
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
 * The sheets worth a card at all: those with at least one published archive.
 *
 * A sheet whose every package is `source: null` is not a decision anyone can
 * act on - rendering it would offer a download that 404s on a mountain, the
 * exact thing the null source exists to prevent. While the raster was the
 * only published artifact this returned the USGS sheet alone, which is why
 * the old single-bundle screen was right by accident (#237).
 */
export function offeredSheets(): BackgroundSheet[] {
  return BACKGROUND_SHEETS.filter((sheet) => offeredPackages(sheet).length > 0)
}

/** What one sheet will cost in total: every archive of it that is actually
 *  offered, at the chosen detail. Every one of them has a measured size, so
 *  this is a sum of measurements and never carries an estimate. */
export function sheetSizeBytes(sheet: BackgroundSheet, detail: DetailLevel): number {
  return offeredPackages(sheet).reduce(
    (total, pkg) => total + packageSizeBytes(pkg, detail),
    0,
  )
}

/**
 * Where this package's bytes are fetched from right now.
 *
 * The detail level is an argument rather than a lookup because it is the
 * hiker's live choice: a tap has to fetch the tier selected at the moment of
 * tapping, not the one selected when a callback was built.
 */
export function packageDownloadUrl(pkg: OfferedPackage, detail: DetailLevel): string {
  return pkg.source.kind === 'tiered' ? archiveUrl(detail) : dataUrl(pkg.source.artifact)
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
export function packageArtifactKey(pkg: OfferedPackage, detail: DetailLevel): string {
  return pkg.source.kind === 'tiered' ? archiveKey(detail) : pkg.source.artifact
}

/**
 * What this package will cost in bytes.
 *
 * Always a real number, and always a measured one: the sizes shown before a
 * download are held to ±0.6% against measured artifacts (pipeline/README.md),
 * and `OfferedPackage` exists so that a package with no measurement behind it
 * cannot reach this function at all.
 */
export function packageSizeBytes(pkg: OfferedPackage, detail: DetailLevel): number {
  return pkg.source.kind === 'tiered'
    ? getDownloadDetail(detail).sizeBytes
    : pkg.source.sizeBytes
}
