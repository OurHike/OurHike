// The heavy half of photoScreen.ts - see that file for the contract this
// module lives under (flag never blocks, every failure is null). Nothing
// imports this statically: the TensorFlow.js runtime it pulls in is the
// single largest dependency in the app, and it belongs to the share sheet
// alone.
//
// Two detectors over one tfjs runtime:
//
// - **BlazeFace** answers "is there a face". Its weights are vendored under
//   public/models/blazeface/ (see the README there) - the exact bytes the
//   npm package would have fetched from TensorFlow Hub, served from our own
//   origin so the check works at a shelter with no signal once the browser
//   has cached them.
// - **nsfwjs MobileNetV2** answers "is there nudity". Its weights are under
//   public/models/nsfw/, extracted byte-for-byte from the nsfwjs 4.3.0 npm
//   package's own bundled model (scripts/extract-nsfw-model.mjs rebuilds
//   them; the package's bundled-import path is unusable here because its
//   loader calls Buffer.from, a Node API no browser has). Loaded through
//   nsfwjs/core rather than the nsfwjs root, which is what keeps the
//   package's other two models - 35MB of InceptionV3 and MobileNetV2Mid -
//   out of the build entirely.
//
// Both models load lazily on first use and stay loaded; a failed load
// clears the slot so coming back into signal can try again instead of
// caching the failure forever.

import * as blazeface from '@tensorflow-models/blazeface'
import { load as loadNsfwModel, type NSFWJS } from 'nsfwjs/core'
import { looksLikeNudity, type ScreenFinding } from './photoScreen'

// The nudity decision rule and its threshold live in photoScreen.ts
// (looksLikeNudity) so they are testable without this module's TensorFlow
// runtime. The face rule is BlazeFace's own default score threshold (0.75)
// deciding what counts as a face, and any face at all is the finding - no
// minimum size, because a small face is still somebody who was not asked.
// @unvalidated the same way the nudity threshold is; the same future corpus
// settles both.

let nsfwSlot: Promise<NSFWJS> | undefined
let faceSlot: Promise<blazeface.BlazeFaceModel> | undefined

function modelUrl(path: string): string {
  // BASE_URL ends with '/' (vite.config.ts requires it of VITE_BASE_PATH).
  return `${import.meta.env.BASE_URL}models/${path}`
}

function nsfwModel(): Promise<NSFWJS> {
  nsfwSlot ??= loadNsfwModel(modelUrl('nsfw/model.json'), {}).catch((error: unknown) => {
    nsfwSlot = undefined
    throw error
  })
  return nsfwSlot
}

function faceModel(): Promise<blazeface.BlazeFaceModel> {
  faceSlot ??= blazeface
    .load({ modelUrl: modelUrl('blazeface/model.json') })
    .catch((error: unknown) => {
      faceSlot = undefined
      throw error
    })
  return faceSlot
}

/** Decode the stored JPEG to pixels once, for both detectors. */
async function pixels(blob: Blob): Promise<ImageData> {
  const bitmap = await createImageBitmap(blob)
  try {
    const canvas = document.createElement('canvas')
    canvas.width = bitmap.width
    canvas.height = bitmap.height
    const context = canvas.getContext('2d')
    if (context === null) throw new Error('no 2d context to decode the photo into')
    context.drawImage(bitmap, 0, 0)
    return context.getImageData(0, 0, bitmap.width, bitmap.height)
  } finally {
    bitmap.close()
  }
}

async function nudityIn(image: ImageData): Promise<boolean> {
  const model = await nsfwModel()
  return looksLikeNudity(await model.classify(image))
}

async function facesIn(image: ImageData): Promise<number> {
  const model = await faceModel()
  const found = await model.estimateFaces(image, false)
  return found.length
}

/** Both checks over one decode. Each detector fails alone - a phone that
 *  cannot load one model can still run the other - and a check that fails
 *  reports nothing, per the seam's contract. */
export async function screenBlob(blob: Blob): Promise<ScreenFinding> {
  const image = await pixels(blob)
  const [nudity, faces] = await Promise.all([
    nudityIn(image).catch(() => false),
    facesIn(image).catch(() => 0),
  ])
  if (nudity) return { flag: 'nudity', faces }
  if (faces > 0) return { flag: 'faces', faces }
  return null
}
