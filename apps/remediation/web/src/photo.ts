// What a photo is turned into before it leaves the phone (#1910).
//
// Drawn onto a canvas and encoded again as JPEG. That does two things: it
// shrinks a 12-megapixel original to at most PHOTO_LONG_SIDE pixels, under the
// photo bucket's 3 MB limit, and it drops the EXIF block, which is where a
// phone keeps the GPS position it was taken at, the time, and the device.
// It is the only redraw a photo gets: it goes from here to a public Storage
// bucket with no server in between (apps/remediation/db/README.md), so this step
// is not optional.

/** `@unvalidated`: enough to see debris and trampled ground on a phone screen;
 *  a reviewer comparing before and after is what would say if it is too little. */
export const PHOTO_LONG_SIDE = 2048
export const PHOTO_QUALITY = 0.85

export async function prepareForUpload(file: Blob): Promise<Blob> {
  // 'from-image' applies the EXIF orientation while the pixels are drawn, so the
  // photo stays upright after the tag that said which way was up is gone.
  const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
  const scale = Math.min(1, PHOTO_LONG_SIDE / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  const context = canvas.getContext('2d')
  if (!context) throw new Error('This browser cannot prepare photos.')
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()
  return await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob(
      (blob) =>
        blob ? resolve(blob) : reject(new Error('The photo could not be prepared.')),
      'image/jpeg',
      PHOTO_QUALITY,
    ),
  )
}
