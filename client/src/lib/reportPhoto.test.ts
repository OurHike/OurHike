// Preparing a photo for upload (#234).
//
// jsdom has no image decoder and no canvas, so `createImageBitmap` and
// `HTMLCanvasElement` are both doubled here. That bounds what these tests can
// claim, and the bound is worth stating rather than discovering: they prove
// the ARITHMETIC and the DECISIONS - what size is asked for, which qualities
// are tried in what order, what happens when none of them fit, what is
// released - and they prove nothing at all about whether a real JPEG survives
// a real canvas. The module header says the same thing; that gap belongs to
// the real-browser layer TESTING.md plans.

import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  MAX_PHOTO_BYTES,
  MAX_PHOTO_EDGE,
  PHOTO_QUALITIES,
  PhotoUnusable,
  prepareReportPhoto,
} from './reportPhoto'

/** What the doubled canvas was asked to do, so a test can assert on it. */
interface Recorded {
  size: [number, number]
  drawn: number[][]
  qualities: number[]
  closed: number
}

/**
 * Doubles the decoder and the canvas.
 *
 * `sizes` is what each successive `toBlob` should produce, in bytes, letting a
 * test walk the quality ladder deterministically - the one thing a real
 * encoder could never be relied on to do.
 */
function stubImaging(
  bitmap: { width: number; height: number },
  sizes: number[],
): Recorded {
  const recorded: Recorded = { size: [0, 0], drawn: [], qualities: [], closed: 0 }

  vi.stubGlobal(
    'createImageBitmap',
    vi.fn(async () => ({
      ...bitmap,
      close: () => {
        recorded.closed += 1
      },
    })),
  )

  let attempt = 0
  vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
    if (tag !== 'canvas') throw new Error(`unexpected createElement(${tag})`)
    return {
      set width(value: number) {
        recorded.size[0] = value
      },
      set height(value: number) {
        recorded.size[1] = value
      },
      getContext: () => ({
        drawImage: (_source: unknown, ...box: number[]) => recorded.drawn.push(box),
      }),
      toBlob: (callback: (blob: Blob | null) => void, _type: string, quality: number) => {
        recorded.qualities.push(quality)
        const size = sizes[Math.min(attempt, sizes.length - 1)]
        attempt += 1
        callback({ size, type: 'image/jpeg' } as Blob)
      },
    } as unknown as HTMLElement
  })

  return recorded
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const A_FILE = new Blob(['not really a jpeg'])

describe('prepareReportPhoto', () => {
  it('shrinks the long edge to the bound and keeps the aspect ratio', async () => {
    const recorded = stubImaging({ width: 4032, height: 3024 }, [400_000])

    await prepareReportPhoto(A_FILE)

    // 4032 is the long edge, so the scale is 1600/4032 and the short edge
    // follows it. Asserting both is what catches a scale applied to one axis.
    expect(recorded.size[0]).toBe(MAX_PHOTO_EDGE)
    expect(recorded.size[1]).toBe(Math.round((3024 * MAX_PHOTO_EDGE) / 4032))
    expect(recorded.drawn).toEqual([[0, 0, MAX_PHOTO_EDGE, recorded.size[1]]])
  })

  it('bounds the HEIGHT when the photo is portrait', async () => {
    // The same arithmetic with the axes swapped, and a separate case because
    // `Math.max` over the wrong axis passes the landscape test above.
    const recorded = stubImaging({ width: 3024, height: 4032 }, [400_000])

    await prepareReportPhoto(A_FILE)

    expect(recorded.size[1]).toBe(MAX_PHOTO_EDGE)
    expect(recorded.size[0]).toBe(Math.round((3024 * MAX_PHOTO_EDGE) / 4032))
  })

  it('never enlarges a photo that is already small', async () => {
    // Upscaling would add bytes to send in exchange for nothing to look at.
    const recorded = stubImaging({ width: 800, height: 600 }, [40_000])

    await prepareReportPhoto(A_FILE)

    expect(recorded.size).toEqual([800, 600])
  })

  it('re-encodes even a small photo, because that is the EXIF answer', async () => {
    // The tempting optimisation is to pass a small file through untouched.
    // It would ship the GPS coordinates inside it - see the module header.
    const recorded = stubImaging({ width: 640, height: 480 }, [30_000])

    const prepared = await prepareReportPhoto(A_FILE)

    expect(recorded.qualities.length).toBeGreaterThan(0)
    expect(prepared.size).toBe(30_000)
  })

  it('asks the decoder to apply the orientation tag', async () => {
    // Without this a canvas strip turns every portrait photo sideways: the
    // pixels are unrotated and the tag that said so is gone.
    stubImaging({ width: 100, height: 100 }, [1000])

    await prepareReportPhoto(A_FILE)

    expect(createImageBitmap).toHaveBeenCalledWith(A_FILE, {
      imageOrientation: 'from-image',
    })
  })

  it('stops at the first quality that fits', async () => {
    const recorded = stubImaging({ width: 2000, height: 2000 }, [MAX_PHOTO_BYTES - 1])

    await prepareReportPhoto(A_FILE)

    expect(recorded.qualities).toEqual([PHOTO_QUALITIES[0]])
  })

  it('walks down the ladder while the result is still too big', async () => {
    const recorded = stubImaging({ width: 2000, height: 2000 }, [
      MAX_PHOTO_BYTES + 1,
      MAX_PHOTO_BYTES + 1,
      MAX_PHOTO_BYTES - 1,
    ])

    const prepared = await prepareReportPhoto(A_FILE)

    expect(recorded.qualities).toEqual(PHOTO_QUALITIES)
    expect(prepared.size).toBeLessThanOrEqual(MAX_PHOTO_BYTES)
  })

  it('accepts a photo that lands exactly on the limit', async () => {
    // The boundary the server also treats as acceptable
    // (backend/app/core/photos.py compares with >, not >=).
    const recorded = stubImaging({ width: 2000, height: 2000 }, [MAX_PHOTO_BYTES])

    await expect(prepareReportPhoto(A_FILE)).resolves.toBeDefined()
    expect(recorded.qualities).toEqual([PHOTO_QUALITIES[0]])
  })

  it('refuses, in words a hiker can act on, when nothing on the ladder fits', async () => {
    stubImaging({ width: 2000, height: 2000 }, [MAX_PHOTO_BYTES + 1])

    await expect(prepareReportPhoto(A_FILE)).rejects.toThrow(PhotoUnusable)
    await expect(prepareReportPhoto(A_FILE)).rejects.toThrow(/taking another/i)
  })

  it('refuses a file the browser cannot decode', async () => {
    // A HEIC on a browser without the codec, a truncated download, a PDF
    // renamed. The picker filters by extension and extensions lie.
    vi.stubGlobal(
      'createImageBitmap',
      vi.fn(async () => {
        throw new Error('unsupported')
      }),
    )

    await expect(prepareReportPhoto(A_FILE)).rejects.toThrow(PhotoUnusable)
  })

  it('releases the decoded bitmap even when the photo is refused', async () => {
    // A decoded bitmap is the full uncompressed image - tens of megabytes.
    // The hiker who tries three photos in a row is the one who notices.
    const recorded = stubImaging({ width: 2000, height: 2000 }, [MAX_PHOTO_BYTES + 1])

    await expect(prepareReportPhoto(A_FILE)).rejects.toThrow(PhotoUnusable)

    expect(recorded.closed).toBe(1)
  })

  it('releases the decoded bitmap on the happy path too', async () => {
    const recorded = stubImaging({ width: 1000, height: 1000 }, [10_000])

    await prepareReportPhoto(A_FILE)

    expect(recorded.closed).toBe(1)
  })
})
