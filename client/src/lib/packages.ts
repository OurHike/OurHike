// The catalog of offline map packages - the one place a package's identity
// lives (issues #192/#200).
//
// A package is one downloadable PMTiles archive with its own IndexedDB key,
// its own download lifecycle (partial/progress/source records derive from
// the key - see archiveDownload.ts), and its own pmtiles:// URL (protocol.ts
// registers every entry here). The offline map program (#184) ships several
// archives to the same phone - vector basemap, DEM, the USGS raster sheet -
// and multi-trail support means per-trail sets of each, so the store is
// keyed per package.
//
// The corridor background keeps the key it has always had: an archive
// already sitting in a tester's IndexedDB under 'ourhike:corridor-archive'
// stays readable after this change, rather than silently re-downloading.

import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'
import { archiveUrl, dataUrl } from './config'
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
  /** Stable identity in code and in trail manifests. */
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

export const CORRIDOR_BACKGROUND_PACKAGE: MapPackage = {
  id: 'corridor-background',
  idbKey: CORRIDOR_ARCHIVE_KEY,
  title: 'Offline map',
  summary: 'The whole trail as a map you can read with no signal.',
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
 * `source: null` until #185 publishes the artifact: the key is live and an
 * archive stored under it renders, but the Downloads screen does not offer
 * bytes nobody has uploaded. Filling this in is then the whole client-side
 * change that turns the vector sheet into a download.
 */
export const BASEMAP_PACKAGE: MapPackage = {
  id: 'basemap',
  idbKey: 'ourhike:basemap',
  title: 'Hiking sheet',
  summary: 'The styled topographic sheet, so the good map works offline too.',
  source: null,
}

/**
 * The corridor DEM package - quantized terrarium WebP tiles, z0-13, built by
 * pipeline/export_dem.py (#186). map/demTiles.ts resolves the hillshade's
 * and the contour generator's elevation reads against this key first and
 * falls through to AWS Terrain Tiles where it does not answer (#187) - the
 * same local-first shape basemap.ts gives the vector sheet.
 *
 * `source: null` for the same reason as the basemap: #186 ends at a
 * published artifact, and this is offered the day there is one.
 */
export const DEM_PACKAGE: MapPackage = {
  id: 'dem',
  idbKey: 'ourhike:dem',
  title: 'Terrain',
  summary: 'Hillshade and contours, drawn on the phone from downloaded elevation.',
  source: null,
}

/** Every package this build knows how to store and resolve. Order is the
 *  Downloads screen's display order. */
export const MAP_PACKAGES: readonly MapPackage[] = [
  CORRIDOR_BACKGROUND_PACKAGE,
  BASEMAP_PACKAGE,
  DEM_PACKAGE,
]

/**
 * What one trail's hikers download.
 *
 * The manifest exists so "download the AT" stays ONE tap that fans out to
 * however many archives the trail currently needs - which is what keeps the
 * Downloads screen from becoming a checklist somebody has to get right at a
 * trailhead, with a missing tick costing them the terrain on a ridge.
 * Multi-trail (#100, #193) adds manifests beside this one; the packages
 * themselves are shared, which is why they are referenced here rather than
 * redefined.
 *
 * Versioning deliberately does not live here. Which bytes are current is
 * `latest.json`'s per-artifact hashes (pipeline/DATA_RELEASES.md), and a
 * second scheme in the client would be a second answer to the same question.
 */
export interface TrailPackages {
  /** Matches the trail ids the pipeline publishes under. */
  trailId: string
  title: string
  /** Everything this trail's map is made of, in display order. */
  packages: readonly MapPackage[]
}

export const AT_PACKAGES: TrailPackages = {
  trailId: 'at',
  title: 'Appalachian Trail',
  packages: MAP_PACKAGES,
}

/**
 * The packages a hiker can be offered right now: catalogued, and with
 * something published behind them.
 *
 * Note what this does NOT filter on - whether the archive is already on the
 * phone. A downloaded package stays listed so it can be deleted, and an
 * evicted one stays listed so the screen can say so (#190).
 */
export function offeredPackages(trail: TrailPackages = AT_PACKAGES): MapPackage[] {
  return trail.packages.filter((pkg) => pkg.source !== null)
}

/**
 * Whether any of the trail is still on the phone once `removedKey` is gone.
 *
 * This is what decides the fate of the data that belongs to the TRAIL rather
 * than to any one package - the centerline, the POIs, the elevation profile.
 * Deleting those alongside whichever package a hiker happened to remove
 * first would strip the trail line off a map whose other packages they
 * deliberately kept.
 */
export function anyPackageRemains(
  packages: readonly MapPackage[],
  removedKey: string,
  isDownloaded: (idbKey: string) => boolean,
): boolean {
  return packages.some((pkg) => pkg.idbKey !== removedKey && isDownloaded(pkg.idbKey))
}

/**
 * Where this package's bytes are fetched from right now.
 *
 * The detail level is an argument rather than a lookup because it is the
 * hiker's live choice: a tap has to fetch the tier selected at the moment of
 * tapping, not the one selected when a callback was built.
 *
 * Null for a package with no source - which callers reach only by asking
 * about a package `offeredPackages()` filtered out.
 */
export function packageDownloadUrl(pkg: MapPackage, detail: DetailLevel): string | null {
  if (pkg.source === null) return null
  return pkg.source.kind === 'tiered' ? archiveUrl(detail) : dataUrl(pkg.source.artifact)
}

/**
 * What this package will cost in bytes, or null where nothing has measured
 * it yet.
 *
 * Null rather than a guess, and the room warning leaves a null out of its
 * sum: the sizes shown before a download are held to ±0.6% against measured
 * artifacts (pipeline/README.md), and an estimate quietly folded into that
 * total would be a number nobody measured presented at the same weight as
 * numbers somebody did.
 */
export function packageSizeBytes(pkg: MapPackage, detail: DetailLevel): number | null {
  if (pkg.source === null) return null
  return pkg.source.kind === 'tiered'
    ? getDownloadDetail(detail).sizeBytes
    : pkg.source.sizeBytes
}
