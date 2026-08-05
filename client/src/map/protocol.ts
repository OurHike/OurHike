// Registers pmtiles' MapLibre protocol handler, so a style can reference the
// on-device archive as `pmtiles://...`.
//
// pmtiles' own documentation is explicit that the Protocol "must be added once
// globally." Registering twice would leave MapLibre holding two handlers for
// the same scheme, each with its own decoded-directory cache, so tile lookups
// would miss a cache that the other one had already warmed. Since several
// components may reasonably want to guarantee the protocol exists before they
// build a map, the guarantee is made idempotent here rather than pushed onto
// every caller to coordinate.

import { addProtocol } from 'maplibre-gl'
import { PMTiles, Protocol } from 'pmtiles'
import { MAP_PACKAGES } from '../lib/packages'
import { CORRIDOR_ARCHIVE_KEY, IndexedDbArchiveSource } from './pmtilesSource'

export const PMTILES_SCHEME = 'pmtiles'

/**
 * The style URL that resolves to a package's archive on this phone rather
 * than to the network. The key is part of the URL because `Protocol.add()`
 * indexes an archive by its source's `getKey()`, and this is the string a
 * `pmtiles://` lookup matches against.
 */
export function packageArchiveUrl(idbKey: string): string {
  return `${PMTILES_SCHEME}://${idbKey}`
}

export const CORRIDOR_ARCHIVE_URL = packageArchiveUrl(CORRIDOR_ARCHIVE_KEY)

let registered: Protocol | null = null

export function registerPMTilesProtocol(): Protocol {
  if (registered !== null) return registered

  const protocol = new Protocol()
  // Registering the archives is what makes this an offline map. An
  // unregistered pmtiles:// URL falls through to pmtiles' own FetchSource and
  // is requested over HTTP - which on a ridge with no signal renders nothing
  // at all, having downloaded the package for no purpose. Every catalog
  // package is registered up front rather than on first download: a source
  // whose archive is absent throws ArchiveNotDownloadedError on read (a
  // real, reportable state), and registration order can never depend on
  // which packages a hiker happens to hold.
  for (const pkg of MAP_PACKAGES) {
    protocol.add(new PMTiles(new IndexedDbArchiveSource(pkg.idbKey)))
  }
  addProtocol(PMTILES_SCHEME, protocol.tile)
  registered = protocol

  return protocol
}
