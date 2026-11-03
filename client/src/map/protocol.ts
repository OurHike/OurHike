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
//
// `addProtocol` ARRIVES AS AN ARGUMENT, and the reason is #1300. This module
// used to import it from `maplibre-gl` at its top, and `App.tsx` imports
// `CORRIDOR_ARCHIVE_URL` from here - a string - which made the whole engine
// part of the shell's eager chunk again: 406 KB of `maplibre-gl-shared.mjs`
// modulepreloaded on every launch, on a Today screen that mounts no map,
// undoing the deferral #722 measured at 860 ms of parse on a throttled phone.
// The only thing here that needs the library is the one call that hands
// MapLibre the handler, so the caller that already holds the library
// (map/engine.ts, the seam `import()` reaches) passes it in, and this file
// imports nothing but a type. scripts/check-build-output.mjs fails the build
// if the engine ever reaches the eager closure again.

import type { addProtocol as AddProtocol } from 'maplibre-gl'
import { PMTiles, Protocol, SharedPromiseCache } from 'pmtiles'
import type { Entry, Header, Source } from 'pmtiles'
import { MAP_PACKAGES } from '../lib/packages'
import { IndexedDbArchiveSource } from './pmtilesSource'
import { PMTILES_SCHEME } from './archiveUrls'

// The scheme and the URL helpers live in map/archiveUrls.ts (#1591), so the
// shell can name an archive without loading this handler and the library
// under it; they are re-exported here for the readers that always found them
// here.
export { CORRIDOR_ARCHIVE_URL, PMTILES_SCHEME, packageArchiveUrl } from './archiveUrls'

/**
 * pmtiles' SharedPromiseCache, minus one behaviour that breaks the offline
 * map: it caches the header PROMISE before it settles and never evicts a
 * rejection.
 *
 * The style declares the archive source on every background (style.ts), so on
 * a phone that has not downloaded yet the first header read rejects with
 * ArchiveNotDownloadedError - correctly. But with that rejection cached, the
 * download finishing changes nothing: every later read replays the cached
 * failure, and a hiker who downloads the corridor at a trailhead and switches
 * to it gets blank paper until they happen to restart the app. The archive's
 * own Source already refuses to memoise failure (pmtilesSource.ts), and this
 * class is the same rule applied one layer up, where the caching actually
 * happens. basemap.ts:126 and demTiles.ts:99 are the pattern's other two
 * appearances.
 */
class RetryOnFailureCache extends SharedPromiseCache {
  override getHeader(source: Source): Promise<Header> {
    const header = super.getHeader(source)
    header.catch(() => {
      // The header entry is keyed by the source's key alone; the root
      // directory that arrives with it is keyed with a `key|...` prefix.
      // Both are settled-or-absent after this, never settled-rejected.
      const prefix = source.getKey()
      for (const key of [...this.cache.keys()]) {
        if (key === prefix || key.startsWith(`${prefix}|`)) this.cache.delete(key)
      }
    })
    return header
  }

  override getDirectory(
    source: Source,
    offset: number,
    length: number,
    header: Header,
  ): Promise<Entry[]> {
    const directory = super.getDirectory(source, offset, length, header)
    directory.catch(() => {
      // The same composed key the parent stores under.
      this.cache.delete(`${source.getKey()}|${header.etag ?? ''}|${offset}|${length}`)
    })
    return directory
  }
}

let registered: Protocol | null = null

export function registerPMTilesProtocol(addProtocol: typeof AddProtocol): Protocol {
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
    protocol.add(
      new PMTiles(new IndexedDbArchiveSource(pkg.idbKey), new RetryOnFailureCache()),
    )
  }
  addProtocol(PMTILES_SCHEME, protocol.tile)
  registered = protocol

  return protocol
}
