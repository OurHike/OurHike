// Writes every generated POI pin out as a PNG, so the glyphs can be LOOKED at.
//
// poiIcons.ts is polygon maths, and polygon maths type-checks and passes unit
// tests while drawing something that is not a droplet. Nothing but an eye
// catches that, and jsdom cannot rasterise, so this is a dev script rather
// than a test. Run it with `npx vite-node scripts/preview-poi-pins.ts`.

import { deflateSync } from 'node:zlib'
import { mkdirSync, writeFileSync } from 'node:fs'
import { buildPoiIcons } from '../src/map/poiIcons'
import { buildAtcNoticeIcon } from '../src/map/atcNoticeMark'
import { ATC_NOTICE_ICON_ID } from '../src/lib/atcUpdateStyle'

function chunk(type: string, body: Buffer): Buffer {
  const length = Buffer.alloc(4)
  length.writeUInt32BE(body.length)
  const typed = Buffer.concat([Buffer.from(type, 'ascii'), body])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(typed))
  return Buffer.concat([length, typed, crc])
}

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  return c >>> 0
})

function crc32(buffer: Buffer): number {
  let c = 0xffffffff
  for (const byte of buffer) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function png(width: number, height: number, rgba: Uint8ClampedArray): Buffer {
  // One filter byte (0 = none) per scanline, which is what `deflate` gets fed.
  const raw = Buffer.alloc(height * (width * 4 + 1))
  for (let y = 0; y < height; y += 1) {
    raw[y * (width * 4 + 1)] = 0
    Buffer.from(rgba.buffer, y * width * 4, width * 4).copy(raw, y * (width * 4 + 1) + 1)
  }

  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(width, 0)
  ihdr.writeUInt32BE(height, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 6 // colour type: RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

/** Nearest-neighbour blow-up. A 60px badge shown at 60px is exactly the size
 *  at which a glyph that is subtly wrong looks fine, which defeats the point
 *  of looking at it. */
function upscale(
  src: Uint8ClampedArray,
  width: number,
  height: number,
  factor: number,
): Uint8ClampedArray {
  const out = new Uint8ClampedArray(width * factor * height * factor * 4)
  for (let y = 0; y < height * factor; y += 1) {
    for (let x = 0; x < width * factor; x += 1) {
      const from = (Math.floor(y / factor) * width + Math.floor(x / factor)) * 4
      const to = (y * width * factor + x) * 4
      for (let c = 0; c < 4; c += 1) out[to + c] = src[from + c]
    }
  }
  return out
}

const SCALE = 4
const outDir = process.argv[2] ?? 'poi-pin-preview'
mkdirSync(outDir, { recursive: true })

// The ATC point notice rides along, and this script is exactly why (#1071).
// Its geometry is polar maths rather than polygon maths, which fails in a
// different way and in the same place: every constant was right while the first
// render was a black disc with red spokes on it, and no unit test written
// against the SPEC could have seen that. map/atcNoticeMark.test.ts samples the
// alpha channel and would catch it now - but a number saying "the gap is 4.5px"
// is still not the same as looking at the thing.
for (const { id, image } of [
  ...buildPoiIcons(),
  { id: ATC_NOTICE_ICON_ID, image: buildAtcNoticeIcon() },
]) {
  const { width: w, height: h, data } = image
  writeFileSync(
    `${outDir}/${id}.png`,
    png(w * SCALE, h * SCALE, upscale(data, w, h, SCALE)),
  )
}

// A contact sheet, so every pin can be judged side by side rather than one
// browser tab at a time.
//
// THE CELL IS THE LARGEST ICON, NOT THE FIRST ONE. This used to be
// `icons[0].image.width` and every pin was copied as though it were that
// size, which is true of exactly the 20 plain pins that happen to sort
// first. The badge variants are not: buildPoiIcons() emits four sizes -
// 76, 116, 140 and 144 px - because a badge hangs outside the disc. Reading a
// 144px image with a 76px stride advances by the wrong amount on every row,
// so each cell sheared a little further than the last and the whole sheet
// below the third row was diagonal noise.
//
// It had been that way for as long as there have been badge variants, and
// nothing caught it, because the thing this script exists to produce is a
// picture nobody had scrolled to the bottom of. That is the same failure the
// script itself is the fix for - "polygon maths type-checks and passes unit
// tests while drawing something that is not a droplet" - one level up.
//
// Found while looking at #1197's ninth pin, which is the only reason it was
// found at all.
const icons = buildPoiIcons()
const cell = Math.max(...icons.map(({ image }) => Math.max(image.width, image.height)))
const cols = 6
const rows = Math.ceil(icons.length / cols)
const sheet = new Uint8ClampedArray(cell * cols * cell * rows * 4)

icons.forEach(({ image }, index) => {
  // Centred in its cell, so a badge that hangs off one side does not make the
  // disc itself look off-register against the row.
  const ox = (index % cols) * cell + Math.floor((cell - image.width) / 2)
  const oy = Math.floor(index / cols) * cell + Math.floor((cell - image.height) / 2)
  for (let y = 0; y < image.height; y += 1) {
    for (let x = 0; x < image.width; x += 1) {
      const from = (y * image.width + x) * 4
      const to = ((oy + y) * cell * cols + ox + x) * 4
      for (let c = 0; c < 4; c += 1) sheet[to + c] = image.data[from + c]
    }
  }
})

writeFileSync(
  `${outDir}/contact-sheet.png`,
  png(
    cell * cols * SCALE,
    cell * rows * SCALE,
    upscale(sheet, cell * cols, cell * rows, SCALE),
  ),
)
console.log(
  `Wrote ${icons.length} pins, the ATC notice mark and a contact sheet to ${outDir}/`,
)
