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
//
// What deliberately does NOT live here yet: the trail manifest ("the AT
// needs these N packages") and the Downloads screen's package list - both
// only mean something once a second package is actually published, and both
// stay tracked by #192.

import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'

export interface MapPackage {
  /** Stable identity in code and (later) in trail manifests. */
  id: string
  /** IndexedDB key of the completed archive; download records derive from it. */
  idbKey: string
  /** What the Downloads screen calls it. */
  title: string
}

export const CORRIDOR_BACKGROUND_PACKAGE: MapPackage = {
  id: 'corridor-background',
  idbKey: CORRIDOR_ARCHIVE_KEY,
  title: 'Offline map',
}

/**
 * The vector basemap package - the hiking sheet's own tiles, cut by
 * pipeline/extract_package.py from the periodic Planetiler build (#184).
 *
 * map/basemap.ts resolves the sheet's `basemap://` tile requests against
 * this key first and falls through to the network where the package does
 * not answer (#189). The download UX that puts a blob under this key
 * follows the store rework (#192); until then the key resolves the same
 * way every catalog entry does - an absent archive is a real, reportable
 * state, and reads simply fall through to the live source.
 */
export const BASEMAP_PACKAGE: MapPackage = {
  id: 'basemap',
  idbKey: 'ourhike:basemap',
  title: 'Hiking sheet',
}

/**
 * The corridor DEM package - quantized terrarium WebP tiles, z0-13, built by
 * pipeline/export_dem.py (#186). map/demTiles.ts resolves the hillshade's
 * and the contour generator's elevation reads against this key first and
 * falls through to AWS Terrain Tiles where it does not answer (#187) - the
 * same local-first shape basemap.ts gives the vector sheet, and the same
 * story for the download UX (follows #192).
 */
export const DEM_PACKAGE: MapPackage = {
  id: 'dem',
  idbKey: 'ourhike:dem',
  title: 'Terrain',
}

/** Every package this build knows how to store and resolve. Order is the
 *  Downloads screen's display order, when it grows a list (#192). */
export const MAP_PACKAGES: readonly MapPackage[] = [
  CORRIDOR_BACKGROUND_PACKAGE,
  BASEMAP_PACKAGE,
  DEM_PACKAGE,
]
