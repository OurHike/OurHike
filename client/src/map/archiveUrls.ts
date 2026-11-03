// The `pmtiles://` URL a downloaded package's archive is reached at, for the
// shell that names it without loading the handler that answers it (#1591).
//
// A LEAF, ON PURPOSE. map/protocol.ts registers the scheme and reads the
// archives through the pmtiles library; App.tsx only needs the corridor
// package's URL to hand MapView, and importing it from protocol.ts put the
// library - 14,288 raw bytes - in the bundle a launch parses before its first
// frame, on a Today screen that mounts no map. Measured 2026-09-30 by
// attributing the built chunks to their sources. protocol.ts re-exports all
// three names, so every reader that imported them from there still does.

import { CORRIDOR_ARCHIVE_KEY } from './pmtilesSource'

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
