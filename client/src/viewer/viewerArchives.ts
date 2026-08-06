// Opens a dropped .pmtiles file and works out what kind of map it is
// (issue #202).
//
// The viewer takes whole archives as browser File objects - the built
// artifacts are hundreds of megabytes, GitHub Pages caps files at 100 MB,
// and a quality check does not need the bytes to go anywhere anyway. File
// reads are byte-range slices (pmtiles' FileSource), the same access
// pattern the app itself uses against IndexedDB.
//
// Classification is by evidence in the archive, not by filename: a rename
// must not change what a file renders as. MVT tiles are the vector basemap.
// Raster tiles split on the one fact that matters - terrarium-encoded
// elevation (which export_dem.py stamps into its metadata) drives hillshade,
// any other raster is a picture-of-a-map sheet (the USGS background).

import { FileSource, PMTiles, TileType, type Source } from 'pmtiles'
import type { Protocol } from 'pmtiles'
import { packageArchiveUrl } from '../map/protocol'

export type ViewerSlot = 'basemap' | 'dem' | 'raster'

/** The header fields the viewer reads, structurally typed - what
 *  PMTiles.getHeader() resolves to. */
export interface ArchiveHeader {
  tileType: number
  minZoom: number
  maxZoom: number
  minLon: number
  minLat: number
  maxLon: number
  maxLat: number
}

export interface OpenedArchive {
  slot: ViewerSlot
  /** The pmtiles:// URL a style source points at. */
  url: string
  header: ArchiveHeader
  fileName: string
  sizeBytes: number
}

export class UnsupportedArchiveError extends Error {
  constructor(tileType: number) {
    super(
      `This archive's tile type (${tileType}) is not one the viewer knows how to ` +
        `render - expected vector (MVT) or raster (PNG/WebP/JPEG) tiles.`,
    )
    this.name = 'UnsupportedArchiveError'
  }
}

/** One fixed key per slot, so re-dropping a rebuilt artifact replaces the
 *  previous one (Protocol.add indexes by key) instead of accumulating. */
export function slotKey(slot: ViewerSlot): string {
  return `viewer:${slot}`
}

/** FileSource answers getKey() with the file's NAME, which would make the
 *  style URL depend on what the download happened to be called. This pins
 *  the key to the slot and delegates the reads. */
export class SlotSource implements Source {
  private readonly inner: FileSource
  private readonly key: string

  constructor(file: File, key: string) {
    this.inner = new FileSource(file)
    this.key = key
  }

  getKey(): string {
    return this.key
  }

  getBytes(offset: number, length: number) {
    return this.inner.getBytes(offset, length)
  }
}

export function classifyArchive(
  header: ArchiveHeader,
  metadata: Record<string, unknown>,
): ViewerSlot {
  if (header.tileType === TileType.Mvt) return 'basemap'

  const raster =
    header.tileType === TileType.Png ||
    header.tileType === TileType.Webp ||
    header.tileType === TileType.Jpeg
  if (!raster) throw new UnsupportedArchiveError(header.tileType)

  return metadata.encoding === 'terrarium' ? 'dem' : 'raster'
}

/**
 * Read enough of the file to classify it, then register it on the protocol
 * under its slot's key. Two PMTiles instances on purpose: the first exists
 * only to read the header and metadata (a few KB of slices), because the
 * slot - and therefore the key the real registration needs - is not known
 * until the archive has said what it is.
 */
export async function openArchive(
  protocol: Protocol,
  file: File,
): Promise<OpenedArchive> {
  const probe = new PMTiles(new FileSource(file))
  const header = (await probe.getHeader()) as ArchiveHeader
  const metadata = ((await probe.getMetadata()) ?? {}) as Record<string, unknown>

  const slot = classifyArchive(header, metadata)
  const key = slotKey(slot)
  protocol.add(new PMTiles(new SlotSource(file, key)))

  return {
    slot,
    url: packageArchiveUrl(key),
    header,
    fileName: file.name,
    sizeBytes: file.size,
  }
}
