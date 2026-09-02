// Reads the zoom range out of a downloaded archive's own PMTiles header.
//
// The client used to have no idea what the archive on the phone contained; it
// pointed a raster source at it and hoped. That is how #216 survived - the
// pipeline exported from z6, the app opened at z4, and nothing anywhere
// compared the two. Asking the archive is the only version of this that
// cannot drift: a phone holding a z6 archive and a phone holding a z0 one
// give different answers, from the same code, on the same build.
//
// The header is the first 127 bytes of the file, so this is one small
// byte-range read against a Blob already in IndexedDB - cheap enough to do on
// mount and not worth caching beyond the hook that calls it.

import { PMTiles } from 'pmtiles'
import { IndexedDbArchiveSource } from './pmtilesSource'
import type { ArchiveZooms, Footprint } from '../lib/archiveCoverage'

/**
 * The archive's zoom range, or `null` where it cannot be established.
 *
 * Null covers every way of not knowing, and they are deliberately not
 * distinguished: no archive yet, a partial one whose header is not written,
 * IndexedDB unavailable, or a file too damaged to parse. Callers must treat
 * null as "do not act on coverage", never as "covers nothing" - see
 * archiveCoversZoom.
 */
export async function readArchiveZooms(idbKey: string): Promise<ArchiveZooms | null> {
  try {
    const header = await new PMTiles(new IndexedDbArchiveSource(idbKey)).getHeader()
    return { minZoom: header.minZoom, maxZoom: header.maxZoom }
  } catch {
    return null
  }
}

/**
 * The ground the archive declares it covers, or `null` where that cannot be
 * established - the same nulls as {@link readArchiveZooms}, and the same
 * rule for callers: null is "do not act on coverage", never "covers nothing".
 *
 * The header's bounds are the bounding RECTANGLE of a thin winding band, so
 * this is the outer edge of the download and not a promise about every point
 * inside it. That is the honest shape of the fact: lib/archiveCoverage.ts's
 * `coverageAt` claims "outside" only past this edge, and says nothing about
 * ground inside it.
 */
export async function readArchiveFootprint(idbKey: string): Promise<Footprint | null> {
  try {
    const header = await new PMTiles(new IndexedDbArchiveSource(idbKey)).getHeader()
    return {
      west: header.minLon,
      south: header.minLat,
      east: header.maxLon,
      north: header.maxLat,
    }
  } catch {
    return null
  }
}
