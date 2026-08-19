import { describe, it, expect } from 'vitest'
import { exifCaptureDate } from './exifDate'

// The fixtures are built by hand, byte by byte, because that is the honest
// way to test a binary parser: a real camera JPEG checked into the repo
// would prove one camera's layout, and the failure modes worth catching -
// wrong endianness handled, offsets off the end refused, an unset clock's
// "0000:00:00" rejected - need fixtures that hold exactly one deviation.

/** A TIFF body holding the given tags, in either byte order. */
function tiffBody(
  little: boolean,
  options: {
    dateTimeOriginal?: string
    ifd0DateTime?: string
    exifPointerPastEnd?: boolean
  } = {},
): number[] {
  const out: number[] = []
  const u16 = (value: number) =>
    little ? out.push(value & 0xff, value >> 8) : out.push(value >> 8, value & 0xff)
  const u32 = (value: number) => {
    const bytes = [
      (value >>> 24) & 0xff,
      (value >>> 16) & 0xff,
      (value >>> 8) & 0xff,
      value & 0xff,
    ]
    out.push(...(little ? bytes.reverse() : bytes))
  }

  // TIFF header: byte order, 42, offset of IFD0 (immediately after: 8).
  out.push(...(little ? [0x49, 0x49] : [0x4d, 0x4d]))
  u16(42)
  u32(8)

  // Layout, all offsets relative to the TIFF header:
  //   8              IFD0: up to 2 entries + next-IFD pointer
  //   afterIfd0      Exif sub-IFD when dateTimeOriginal is present
  //   then           the ASCII date values
  const ifd0Entries: (() => void)[] = []
  const values: number[] = []
  const ifd0Count =
    (options.dateTimeOriginal !== undefined || options.exifPointerPastEnd ? 1 : 0) +
    (options.ifd0DateTime !== undefined ? 1 : 0)
  const afterIfd0 = 8 + 2 + ifd0Count * 12 + 4
  const exifIfdSize = options.dateTimeOriginal !== undefined ? 2 + 12 + 4 : 0
  let valueAt = afterIfd0 + exifIfdSize

  const asciiEntry = (tag: number, text: string) => {
    const bytes = [...text].map((c) => c.charCodeAt(0))
    bytes.push(0)
    const at = valueAt
    values.push(...bytes)
    valueAt += bytes.length
    return () => {
      u16(tag)
      u16(2) // ASCII
      u32(bytes.length)
      u32(at)
    }
  }

  let originalEntry: (() => void) | null = null
  if (options.dateTimeOriginal !== undefined) {
    originalEntry = asciiEntry(0x9003, options.dateTimeOriginal)
    ifd0Entries.push(() => {
      u16(0x8769)
      u16(4) // LONG
      u32(1)
      u32(afterIfd0)
    })
  }
  if (options.exifPointerPastEnd) {
    ifd0Entries.push(() => {
      u16(0x8769)
      u16(4)
      u32(1)
      u32(0xffff) // far past the segment: must be refused, not read
    })
  }
  if (options.ifd0DateTime !== undefined) {
    ifd0Entries.push(asciiEntry(0x0132, options.ifd0DateTime))
  }

  u16(ifd0Entries.length)
  for (const entry of ifd0Entries) entry()
  u32(0) // no next IFD

  if (originalEntry !== null) {
    u16(1)
    originalEntry()
    u32(0)
  }

  out.push(...values)
  return out
}

/** A minimal JPEG: SOI, the given APP1 payload, SOS. */
function jpegWith(app1Payload: number[]): Blob {
  const preamble = [0x45, 0x78, 0x69, 0x66, 0x00, 0x00] // "Exif\0\0"
  const segment = [...preamble, ...app1Payload]
  const length = segment.length + 2
  const bytes = [
    0xff,
    0xd8, // SOI
    0xff,
    0xe1,
    (length >> 8) & 0xff,
    length & 0xff,
    ...segment,
    0xff,
    0xda,
    0x00,
    0x02, // SOS: image data from here
  ]
  return new Blob([new Uint8Array(bytes)])
}

describe('exifCaptureDate', () => {
  it('reads DateTimeOriginal from a little-endian EXIF block', async () => {
    const file = jpegWith(tiffBody(true, { dateTimeOriginal: '2026:06:18 14:03:22' }))
    await expect(exifCaptureDate(file)).resolves.toBe('2026-06-18')
  })

  it('reads DateTimeOriginal from a big-endian EXIF block', async () => {
    const file = jpegWith(tiffBody(false, { dateTimeOriginal: '2024:11:02 08:00:00' }))
    await expect(exifCaptureDate(file)).resolves.toBe('2024-11-02')
  })

  it('prefers the shutter time over IFD0 DateTime when both exist', async () => {
    const file = jpegWith(
      tiffBody(true, {
        dateTimeOriginal: '2025:07:04 12:00:00',
        ifd0DateTime: '2026:01:01 00:00:00',
      }),
    )
    await expect(exifCaptureDate(file)).resolves.toBe('2025-07-04')
  })

  it('falls back to IFD0 DateTime when there is no Exif sub-IFD', async () => {
    const file = jpegWith(tiffBody(true, { ifd0DateTime: '2023:09:30 19:45:01' }))
    await expect(exifCaptureDate(file)).resolves.toBe('2023-09-30')
  })

  it("rejects an unset camera clock's zero date", async () => {
    const file = jpegWith(tiffBody(true, { dateTimeOriginal: '0000:00:00 00:00:00' }))
    await expect(exifCaptureDate(file)).resolves.toBeNull()
  })

  it('refuses a sub-IFD pointer past the end of the segment', async () => {
    const file = jpegWith(tiffBody(true, { exifPointerPastEnd: true }))
    await expect(exifCaptureDate(file)).resolves.toBeNull()
  })

  it('returns null for a JPEG with no EXIF at all', async () => {
    const bytes = [0xff, 0xd8, 0xff, 0xda, 0x00, 0x02]
    await expect(exifCaptureDate(new Blob([new Uint8Array(bytes)]))).resolves.toBeNull()
  })

  it('returns null for a file that is not a JPEG', async () => {
    await expect(exifCaptureDate(new Blob(['not a jpeg']))).resolves.toBeNull()
  })

  it('returns null for an empty file', async () => {
    await expect(exifCaptureDate(new Blob([]))).resolves.toBeNull()
  })
})
