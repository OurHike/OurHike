// The catalog of offline map packages - the one place a package's identity
// lives (issues #192/#200).
//
// A package is one downloadable PMTiles archive with its own IndexedDB key,
// its own download lifecycle (partial/progress/source records derive from
// the key - see archiveDownload.ts), and its own pmtiles:// URL (protocol.ts
// registers every entry here). The offline map program (#184) ships several
// archives to the same phone - vector basemap, DEM, the USGS raster sheet -
// and multi-trail support means per-trail sets of each, so the store is
// keyed even while this catalog has one member.
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

/** Every package this build knows how to store and resolve. Order is the
 *  Downloads screen's display order, when it grows a list (#192). */
export const MAP_PACKAGES: readonly MapPackage[] = [CORRIDOR_BACKGROUND_PACKAGE]
