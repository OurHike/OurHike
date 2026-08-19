// The capture date of a photo, read from the original file's EXIF - the one
// piece of metadata this app keeps on purpose.
//
// reportPhoto.ts re-encodes every picked photo through a canvas precisely so
// that the stored JPEG is a new file that never carried EXIF: no GPS, no
// device, no tag that survives because nobody knew to look for it. The
// capture date is the single exception POI_PHOTOS.md carves out - "capture
// date is kept... it is what the card prints, and the honesty rule needs it" -
// and the re-encode is exactly what destroys it. So the date is read HERE,
// from the original bytes, before the canvas sees them, and travels beside
// the re-encoded blob rather than inside it.
//
// Reading EXIF locally is allowed by the privacy rule as restated in
// POI_PHOTOS.md: "the location never leaves the phone", not "never read it".
// This module narrows further and never even parses the GPS tags - it walks
// to the two date tags and stops.
//
// Hand-rolled rather than a dependency, and small on purpose: a JPEG is
// SOI + marker segments, EXIF is an APP1 segment holding a TIFF structure,
// and a date is an ASCII tag in IFD0 or the Exif sub-IFD. Every offset is
// bounds-checked and every failure returns null, because "no date" is an
// ordinary answer this feature already handles - the photo is then dated by
// the day it was added, which is the doc's stated fallback.

/** Tags this module reads, and the only ones. */
const TAG_EXIF_IFD_POINTER = 0x8769
const TAG_DATE_TIME_ORIGINAL = 0x9003 // Exif sub-IFD: when the shutter fired
const TAG_DATE_TIME = 0x0132 // IFD0: file modification, the weaker fallback

/** How much of the file is worth reading. APP1 must precede the image data,
 *  and the EXIF spec caps any APP1 segment at 64 KB; 256 KB covers a maker
 *  that pads the header without ever pulling a whole camera file into
 *  memory for two tags. */
const HEAD_BYTES = 256 * 1024

/**
 * "YYYY-MM-DD" from the file's EXIF, or null.
 *
 * Null for anything that is not a JPEG with a parseable, plausible date -
 * HEIC, PNG, a screenshot, a truncated download, a camera that wrote
 * "0000:00:00". The caller falls back to the date the photo was added, so
 * null is a fallback path, never an error.
 */
export async function exifCaptureDate(file: Blob): Promise<string | null> {
  let head: ArrayBuffer
  try {
    head = await file.slice(0, HEAD_BYTES).arrayBuffer()
  } catch {
    return null
  }
  const bytes = new DataView(head)

  // SOI, then marker segments until the entropy-coded data starts.
  if (bytes.byteLength < 4 || bytes.getUint16(0) !== 0xffd8) return null
  let offset = 2
  while (offset + 4 <= bytes.byteLength) {
    if (bytes.getUint8(offset) !== 0xff) return null
    const marker = bytes.getUint8(offset + 1)
    // SOS or EOI: image data from here on, no APP1 was found.
    if (marker === 0xda || marker === 0xd9) return null
    const length = bytes.getUint16(offset + 2)
    if (length < 2) return null
    if (marker === 0xe1) {
      const date = dateFromApp1(bytes, offset + 4, length - 2)
      if (date !== null) return date
      // An APP1 that is XMP rather than EXIF: keep walking.
    }
    offset += 2 + length
  }
  return null
}

/** The date out of one APP1 segment, or null when it is not EXIF/TIFF. */
function dateFromApp1(bytes: DataView, start: number, length: number): string | null {
  // "Exif\0\0" preamble, then the TIFF header the offsets are relative to.
  if (length < 14 || start + length > bytes.byteLength) return null
  if (
    bytes.getUint8(start) !== 0x45 || // E
    bytes.getUint8(start + 1) !== 0x78 || // x
    bytes.getUint8(start + 2) !== 0x69 || // i
    bytes.getUint8(start + 3) !== 0x66 || // f
    bytes.getUint16(start + 4) !== 0
  ) {
    return null
  }
  const tiff = start + 6
  const end = start + length
  const order = bytes.getUint16(tiff)
  const little = order === 0x4949 // "II"; "MM" is big-endian
  if (!little && order !== 0x4d4d) return null
  if (bytes.getUint16(tiff + 2, little) !== 42) return null

  const ifd0 = tiff + bytes.getUint32(tiff + 4, little)

  // DateTimeOriginal in the Exif sub-IFD is the shutter time and wins;
  // IFD0's DateTime is "file changed" and is only better than nothing.
  const exifPointer = tagValueOffset(bytes, end, ifd0, TAG_EXIF_IFD_POINTER, little)
  if (exifPointer !== null) {
    const original = asciiTag(
      bytes,
      tiff,
      end,
      tiff + exifPointer,
      TAG_DATE_TIME_ORIGINAL,
      little,
    )
    const date = parseExifDate(original)
    if (date !== null) return date
  }
  return parseExifDate(asciiTag(bytes, tiff, end, ifd0, TAG_DATE_TIME, little))
}

/** Walk one IFD for a LONG tag's value (the sub-IFD pointer). */
function tagValueOffset(
  bytes: DataView,
  end: number,
  ifd: number,
  tag: number,
  little: boolean,
): number | null {
  const entry = findEntry(bytes, end, ifd, tag, little)
  if (entry === null) return null
  return bytes.getUint32(entry + 8, little)
}

/** Walk one IFD for an ASCII tag's text. */
function asciiTag(
  bytes: DataView,
  tiff: number,
  end: number,
  ifd: number,
  tag: number,
  little: boolean,
): string | null {
  const entry = findEntry(bytes, end, ifd, tag, little)
  if (entry === null) return null
  if (bytes.getUint16(entry + 2, little) !== 2) return null // ASCII
  const count = bytes.getUint32(entry + 4, little)
  // An EXIF date is exactly 20 bytes with its NUL; anything much longer is
  // not a date and anything shorter cannot hold one.
  if (count < 11 || count > 32) return null
  // Values over 4 bytes live at an offset; a date always does.
  const at = tiff + bytes.getUint32(entry + 8, little)
  if (at < 0 || at + count > end) return null
  let text = ''
  for (let i = 0; i < count; i += 1) {
    const c = bytes.getUint8(at + i)
    if (c === 0) break
    text += String.fromCharCode(c)
  }
  return text
}

/** The 12-byte entry for a tag inside one IFD, or null. */
function findEntry(
  bytes: DataView,
  end: number,
  ifd: number,
  tag: number,
  little: boolean,
): number | null {
  if (ifd < 0 || ifd + 2 > end) return null
  const entries = bytes.getUint16(ifd, little)
  for (let i = 0; i < entries; i += 1) {
    const entry = ifd + 2 + i * 12
    if (entry + 12 > end) return null
    if (bytes.getUint16(entry, little) === tag) return entry
  }
  return null
}

/**
 * "YYYY-MM-DD" out of EXIF's "YYYY:MM:DD HH:MM:SS", or null.
 *
 * Validated rather than trusted: cameras really do write "0000:00:00
 * 00:00:00" for an unset clock, and a card printing "Jan 0000" would be the
 * honesty rule mocking itself. Bounds are sanity, not certification - a
 * wrong-but-plausible camera clock is the hiker's own clock problem, the
 * same as it is for any photo app.
 */
function parseExifDate(text: string | null): string | null {
  if (text === null) return null
  const match = /^(\d{4}):(\d{2}):(\d{2})\b/.exec(text)
  if (match === null) return null
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  if (year < 1900 || month < 1 || month > 12 || day < 1 || day > 31) return null
  return `${match[1]}-${match[2]}-${match[3]}`
}
