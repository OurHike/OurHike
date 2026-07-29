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
import { Protocol } from 'pmtiles'

export const PMTILES_SCHEME = 'pmtiles'

let registered: Protocol | null = null

export function registerPMTilesProtocol(): Protocol {
  if (registered !== null) return registered

  const protocol = new Protocol()
  addProtocol(PMTILES_SCHEME, protocol.tile)
  registered = protocol

  return protocol
}
