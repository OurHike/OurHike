// Turning a phone photo into something that can be sent from a ridge (#234).
//
// Three things have to happen to a picture between the camera roll and the
// moderation queue, and they are not independent - doing them in one pass is
// most of why this module exists.
//
// WHY IT IS RE-ENCODED RATHER THAN UPLOADED
//
// A modern phone photo is several megabytes. The backend refuses anything
// over 2 MB (backend/app/core/photos.py) and it is right to: this app sizes
// its own corridor downloads carefully because hikers are on metered
// connections with one bar, and an upload is that same connection in the
// other direction, on the battery that has to reach the next town. So the
// image is drawn onto a canvas at a bounded size and encoded again.
//
// WHY THAT IS ALSO THE EXIF ANSWER
//
// A phone photo carries EXIF: GPS coordinates, a timestamp, often the device.
// A `bad_hikers` report is routed `internal_only` precisely because it
// concerns a person, and shipping the reporter's exact position inside the
// image file would undo that quietly, in a place nobody would think to look.
//
// The honest description of what happens here is NOT that the tags are
// removed. A canvas holds pixels and nothing else, so the JPEG that comes out
// of it is a new file that never had them - there is no stripping step to get
// wrong, and no tag that survives because this module did not know to look for
// it. That is the reason to re-encode rather than to edit the original's
// headers, even for a photo already small enough to send.
//
// The one thing a canvas does throw away that matters is the orientation tag,
// which is why decoding asks for `imageOrientation: 'from-image'`: the bitmap
// arrives already rotated, so the pixels are the right way up and the tag that
// used to say so is not needed. Without it, stripping EXIF would silently turn
// every portrait photo sideways.
//
// WHAT IS NOT TESTED HERE, AND CANNOT BE
//
// jsdom has no canvas and no image decoder, so every test in this file feeds
// the real code a doubled `createImageBitmap` and a doubled canvas. What that
// proves is the arithmetic and the decisions - the scale factor, the quality
// ladder, the refusal - and what it cannot prove is that a real JPEG from a
// real phone comes out the other side. That gap is the same one TESTING.md
// item 19 describes for the map, and it belongs to the real-browser smoke
// layer that document already plans.

/**
 * The longest edge the stored photo may have.
 *
 * 1600 px is chosen against the job the photo has to do: a moderator deciding
 * whether a bridge is really out, on a laptop, from a card that is a few
 * hundred pixels wide. It is generous for that and still roughly a tenth of
 * the pixels a current phone camera produces.
 */
export const MAX_PHOTO_EDGE = 1600

/**
 * The server's limit, restated so the client can refuse locally.
 *
 * Deliberately duplicated from `backend/app/core/photos.py` rather than
 * fetched: the whole point is to know the answer with no signal. If the two
 * ever disagree the server wins and the upload is refused, which is a bug
 * worth having loudly rather than a size worth guessing at.
 */
export const MAX_PHOTO_BYTES = 2 * 1024 * 1024

/**
 * JPEG qualities to try, in order, stopping at the first that fits.
 *
 * A ladder rather than one number because the size a quality produces depends
 * on the picture: dense forest at 0.75 can outweigh a bare ridge at 0.9. The
 * bottom rung is deliberately low - a blurry photo of a washed-out bridge is
 * worth more to a maintainer than no photo, and this is the last step before
 * refusing outright.
 */
export const PHOTO_QUALITIES = [0.75, 0.6, 0.45]

export const PHOTO_CONTENT_TYPE = 'image/jpeg'

/**
 * A photo that cannot be made sendable.
 *
 * The message is shown to a hiker verbatim, so it reads like a sentence and
 * says what they can do - which is to take another one, because there is
 * nothing about this failure they can fix on the file they have.
 */
export class PhotoUnusable extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'PhotoUnusable'
  }
}

/** A canvas 2D target, narrowed to what this module actually uses so a test
 *  double does not have to implement the whole DOM interface. */
interface DrawTarget {
  width: number
  height: number
  getContext(id: '2d'): { drawImage(source: ImageBitmap, ...box: number[]): void } | null
  toBlob(callback: (blob: Blob | null) => void, type: string, quality: number): void
}

function canvasOf(width: number, height: number): DrawTarget {
  // A real `<canvas>` rather than an OffscreenCanvas, and that is a
  // compatibility choice rather than an oversight: this runs on whatever
  // phone a hiker owns, `toBlob` has been everywhere for a decade, and
  // `OffscreenCanvas.convertToBlob` arrived in Safari only recently. Nothing
  // here is slow enough to need a worker.
  const canvas = document.createElement('canvas') as unknown as DrawTarget
  canvas.width = width
  canvas.height = height
  return canvas
}

/** Promisified `toBlob`, which is callback-shaped and can yield null. */
async function encode(canvas: DrawTarget, quality: number): Promise<Blob | null> {
  return new Promise((resolve) => {
    canvas.toBlob(resolve, PHOTO_CONTENT_TYPE, quality)
  })
}

/**
 * A JPEG under the server's limit, with no metadata, the right way up.
 *
 * Throws `PhotoUnusable` for a file that cannot be decoded at all and for one
 * that will not fit at the lowest quality on the ladder. Both are conditions
 * the hiker has to know about at the moment they pick the file - which is why
 * this runs then, and not during a flush that may happen days later with the
 * phone in a pocket.
 */
export async function prepareReportPhoto(file: Blob): Promise<Blob> {
  let bitmap: ImageBitmap
  try {
    // `from-image` is what makes the strip safe - see the header. Browsers
    // that do not know the option ignore it, which is the pre-existing
    // behaviour rather than a new failure.
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
  } catch {
    // A HEIC on a browser that cannot decode it, a truncated download, a file
    // that is not an image at all. The picker's `accept` filters by extension
    // and extensions lie.
    throw new PhotoUnusable('That file could not be read as a photo. Try taking another.')
  }

  try {
    // Never upscales: `Math.min(1, …)` means a photo already smaller than the
    // bound is re-encoded at its own size rather than blown up, which would
    // add bytes to send in exchange for nothing to look at.
    const scale = Math.min(1, MAX_PHOTO_EDGE / Math.max(bitmap.width, bitmap.height))
    const width = Math.max(1, Math.round(bitmap.width * scale))
    const height = Math.max(1, Math.round(bitmap.height * scale))

    const canvas = canvasOf(width, height)
    const context = canvas.getContext('2d')
    if (context === null) {
      throw new PhotoUnusable(
        'This device could not process the photo. Try taking another.',
      )
    }
    context.drawImage(bitmap, 0, 0, width, height)

    for (const quality of PHOTO_QUALITIES) {
      const encoded = await encode(canvas, quality)
      if (encoded !== null && encoded.size <= MAX_PHOTO_BYTES) return encoded
    }

    throw new PhotoUnusable(
      'That photo is too large to send, even shrunk. Try taking another.',
    )
  } finally {
    // Released whichever way this exits. A decoded bitmap holds the full
    // uncompressed image - tens of megabytes for a current phone camera - and
    // a hiker who tries three photos in a row on a device with no memory to
    // spare is the case that notices.
    bitmap.close()
  }
}
