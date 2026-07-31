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
import { CORRIDOR_ARCHIVE_KEY, IndexedDbArchiveSource } from './pmtilesSource'

export const PMTILES_SCHEME = 'pmtiles'

/**
 * The style URL that resolves to the archive on this phone rather than to the
 * network. The key is part of the URL because `Protocol.add()` indexes an
 * archive by its source's `getKey()`, and this is the string a `pmtiles://`
 * lookup matches against.
 */
export const CORRIDOR_ARCHIVE_URL = `${PMTILES_SCHEME}://${CORRIDOR_ARCHIVE_KEY}`

let registered: Protocol | null = null

export function registerPMTilesProtocol(): Protocol {
  if (registered !== null) return registered

  const protocol = new Protocol()
  // Registering the archive is what makes this an offline map. An unregistered
  // pmtiles:// URL falls through to pmtiles' own FetchSource and is requested
  // over HTTP - which on a ridge with no signal renders nothing at all, having
  // downloaded the corridor package for no purpose.
  protocol.add(new PMTiles(new IndexedDbArchiveSource()))
  addProtocol(PMTILES_SCHEME, protocol.tile)
  registered = protocol

  return protocol
}
