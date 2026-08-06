// Tests for viewerArchives.ts - classifying and registering dropped
// archives. The classification tests run against REAL archive bytes: a
// minimal spec-v3 PMTiles (magic, header fields at their fixed offsets, an
// empty root directory, uncompressed JSON metadata) built by hand below, so
// openArchive is proven against the format rather than against a mock of it.

import { describe, it, expect } from 'vitest'
import { Protocol, TileType } from 'pmtiles'
import {
  SlotSource,
  UnsupportedArchiveError,
  classifyArchive,
  openArchive,
  slotKey,
} from './viewerArchives'

const HEADER = {
  tileType: TileType.Mvt,
  minZoom: 0,
  maxZoom: 14,
  minLon: -80,
  minLat: 34,
  maxLon: -68,
  maxLat: 46,
}

/** A complete, valid, empty PMTiles v3 archive. Offsets are the spec's own
 *  (mirrored by pmtiles' bytesToHeader). */
function tinyArchive({
  tileType = TileType.Mvt,
  metadata = {} as Record<string, unknown>,
} = {}): File {
  const metadataBytes = new TextEncoder().encode(JSON.stringify(metadata))
  const root = new Uint8Array([0]) // varint 0: an empty directory
  const buf = new ArrayBuffer(127 + root.length + metadataBytes.length)
  const view = new DataView(buf)
  const bytes = new Uint8Array(buf)

  bytes.set(new TextEncoder().encode('PMTiles'), 0)
  view.setUint8(7, 3) // spec version
  view.setBigUint64(8, BigInt(127), true) // root offset
  view.setBigUint64(16, BigInt(root.length), true)
  view.setBigUint64(24, BigInt(127 + root.length), true) // metadata offset
  view.setBigUint64(32, BigInt(metadataBytes.length), true)
  view.setUint8(97, 1) // internal compression: none
  view.setUint8(98, 1) // tile compression: none
  view.setUint8(99, tileType)
  view.setUint8(100, HEADER.minZoom)
  view.setUint8(101, HEADER.maxZoom)
  view.setInt32(102, HEADER.minLon * 1e7, true)
  view.setInt32(106, HEADER.minLat * 1e7, true)
  view.setInt32(110, HEADER.maxLon * 1e7, true)
  view.setInt32(114, HEADER.maxLat * 1e7, true)
  bytes.set(root, 127)
  bytes.set(metadataBytes, 127 + root.length)

  return new File([buf], 'dropped.pmtiles')
}

describe('classifyArchive', () => {
  it('vector tiles are the basemap, whatever the metadata says', () => {
    expect(classifyArchive({ ...HEADER, tileType: TileType.Mvt }, {})).toBe('basemap')
  })

  it('terrarium-encoded raster is elevation - the fact export_dem.py stamps', () => {
    const header = { ...HEADER, tileType: TileType.Webp }
    expect(classifyArchive(header, { encoding: 'terrarium' })).toBe('dem')
  })

  it('any other raster is a picture-of-a-map sheet', () => {
    expect(classifyArchive({ ...HEADER, tileType: TileType.Webp }, {})).toBe('raster')
    expect(classifyArchive({ ...HEADER, tileType: TileType.Png }, {})).toBe('raster')
  })

  it('refuses tile types the viewer cannot render, by name', () => {
    expect(() => classifyArchive({ ...HEADER, tileType: 0 }, {})).toThrow(
      UnsupportedArchiveError,
    )
  })
})

describe('SlotSource', () => {
  it('answers the slot key, not the file name - a rename must not change the style URL', async () => {
    const source = new SlotSource(tinyArchive(), slotKey('basemap'))
    expect(source.getKey()).toBe('viewer:basemap')
  })

  it('reads byte ranges from the file it wraps', async () => {
    const source = new SlotSource(tinyArchive(), slotKey('basemap'))
    const { data } = await source.getBytes(0, 7)
    expect(new TextDecoder().decode(data)).toBe('PMTiles')
  })
})

describe('openArchive', () => {
  it('classifies real archive bytes and registers them under the slot key', async () => {
    const protocol = new Protocol()

    const archive = await openArchive(protocol, tinyArchive({ tileType: TileType.Mvt }))

    expect(archive.slot).toBe('basemap')
    expect(archive.url).toBe('pmtiles://viewer:basemap')
    expect(archive.header.maxZoom).toBe(14)
    expect(archive.header.minLon).toBeCloseTo(-80)
    expect(protocol.get('viewer:basemap')).toBeDefined()
  })

  it('routes a terrarium raster to the dem slot from its own metadata', async () => {
    const protocol = new Protocol()
    const file = tinyArchive({
      tileType: TileType.Webp,
      metadata: { encoding: 'terrarium' },
    })

    const archive = await openArchive(protocol, file)

    expect(archive.slot).toBe('dem')
    expect(protocol.get('viewer:dem')).toBeDefined()
  })

  it('re-dropping a slot replaces the previous archive rather than accumulating', async () => {
    const protocol = new Protocol()

    await openArchive(protocol, tinyArchive())
    const first = protocol.get('viewer:basemap')
    await openArchive(protocol, tinyArchive())

    expect(protocol.get('viewer:basemap')).not.toBe(first)
  })
})
