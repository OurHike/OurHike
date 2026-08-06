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
// Several archives, but ONE thing to a hiker: they are the background data
// (BACKGROUND_DATA below), chosen and downloaded together, never presented as
// a checklist of archives to assemble. They are also shared between trails
// rather than owned by one - see that comment for why both of those matter.
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

/** Every package this build knows how to store and resolve, in the order
 *  they matter to a hiker. */
export const MAP_PACKAGES: readonly MapPackage[] = [
  CORRIDOR_BACKGROUND_PACKAGE,
  BASEMAP_PACKAGE,
  DEM_PACKAGE,
]

/**
 * The background data: the map drawn UNDER the trail, and one thing to a
 * hiker rather than a set of archives to assemble.
 *
 * SHARED ACROSS TRAILS, WHICH IS THE POINT OF GROUPING IT AT ALL.
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
 * the elevation profile (lib/trailData.ts). That is the corridor sheet, it is
 * small, and it is downloaded by default whenever it is missing rather than
 * being something to choose. Keeping the two apart is what lets the heavy
 * half be shared and the trail-shaped half be per-trail.
 *
 * Honest about today: `background.pmtiles` is still built corridor-shaped,
 * by buffering the AT centerline. So it is shared in the way this client
 * treats it - one key, one download, reusable by any trail it covers - and
 * not yet in the way it is BUILT. The regional build-once-extract-many that
 * makes it genuinely shared is #185.
 *
 * Versioning deliberately does not live here. Which bytes are current is
 * `latest.json`'s per-artifact hashes (pipeline/DATA_RELEASES.md), and a
 * second scheme in the client would be a second answer to the same question.
 */
export interface BackgroundData {
  id: string
  /** What the Downloads screen calls the whole thing. */
  title: string
  summary: string
  /** Every archive the background is made of, in the order they matter. */
  packages: readonly MapPackage[]
}

/**
 * The background as it is TODAY: every archive that is published, which is
 * the raster sheet alone.
 *
 * Right for now, and knowingly not the end state. Decided 2026-08-06: the
 * USGS raster is an OPTIONAL SECOND SHEET a hiker opts into, not part of the
 * background everyone gets (#237). While it is the only published piece it
 * is also the whole background by default, because there is nothing else to
 * be - but the moment #185 and #186 publish the vector basemap and the DEM,
 * bundling all three would hand every hiker several hundred megabytes of
 * raster they did not ask for, on top of the vector sheet that replaced it.
 *
 * So this stays one bundle only until there is a second sheet to choose
 * BETWEEN. #237 is where that turns into a choice; nothing here should be
 * read as a decision that it will not.
 */
export const BACKGROUND_DATA: BackgroundData = {
  id: 'background',
  title: 'Offline map',
  summary: 'The whole corridor as a map you can read with no signal.',
  packages: MAP_PACKAGES,
}

/**
 * The background archives a hiker can be offered right now: catalogued, and
 * with something published behind them.
 *
 * Note what this does NOT filter on - whether the archive is already on the
 * phone. A downloaded package stays included so it can be deleted, and an
 * evicted one stays included so the screen can say so (#190).
 */
export function offeredPackages(
  background: BackgroundData = BACKGROUND_DATA,
): OfferedPackage[] {
  return background.packages.filter((pkg): pkg is OfferedPackage => pkg.source !== null)
}

/** What the background will cost in total: every archive that is actually
 *  offered, at the chosen detail. Every one of them has a measured size, so
 *  this is a sum of measurements and never carries an estimate. */
export function backgroundSizeBytes(
  detail: DetailLevel,
  background: BackgroundData = BACKGROUND_DATA,
): number {
  return offeredPackages(background).reduce(
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
