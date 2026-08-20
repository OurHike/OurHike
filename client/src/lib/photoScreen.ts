// The on-device look at a photo before it is offered to everyone (#837):
// does it show a face, does it show nudity. Run when the share sheet opens,
// entirely on the phone - the photo never leaves to be looked at, which is
// the property the whole feature stands on.
//
// This file is the seam and nothing else. The detectors - a TensorFlow.js
// runtime, BlazeFace, and nsfwjs's MobileNetV2 - cost megabytes, so they
// live in photoScreenEngine.ts behind a dynamic import: a hiker who never
// shares a photo never downloads a face detector, and the app shell's
// precache never carries one (vite.config.ts excludes the engine's chunk by
// name).
//
// **The check never decides anything, and its absence must cost nothing.**
// That is the #570 posture (flag, never block) made mechanical: a finding
// here only adds friction copy to the share sheet and a `flagged` value to
// the queued share - the backend sorts its queue by it, and holds only the
// nudity case until one human glance. So every failure path - offline
// before the engine chunk ever arrived, a browser without WebGL, a decode
// error, the models simply wrong - resolves to null, which is exactly the
// state every share was in before this shipped: report-driven, human-judged.
// A screen that could fail closed would be a block wearing a flag's name.

/** What the screen found: nudity (outranks faces - it is the one finding
 *  with a hold behind it), or how many faces. Null is "nothing found OR
 *  could not look" - deliberately one value, because the queued share must
 *  not distinguish them (see above). */
export type ScreenFinding = { flag: 'nudity' | 'faces'; faces: number } | null

// @unvalidated - a prior, not a measurement, because the corpus that would
// validate it (photos hikers actually share) does not exist yet. What would
// settle it: once shares exist, count the moderation queue's nudity flags a
// human judged pointless, and the reported photos the screen said nothing
// about. The lean is deliberate and matches the share sheet's own copy ("it
// is often wrong about that"): a false flag costs one human glance and a
// short hold, a miss costs nudity live on a card until somebody reports it.
export const NUDITY_MIN_PROBABILITY = 0.3

/** The nudity decision over nsfwjs's five class scores (they sum to 1).
 *  Porn and Hentai are the two that mean nudity on a waypoint card; Sexy is
 *  excluded on purpose - hikers in shorts at a swimming hole live there all
 *  summer. Summed rather than any-one-over, and the threshold set under a
 *  majority, because the model splits probability across its classes -
 *  demanding 0.5 from a single class in practice demands near-certainty.
 *  Pure and exported so the rule is testable without a TensorFlow runtime;
 *  photoScreenEngine.ts is its only production caller. */
export function looksLikeNudity(
  predictions: ReadonlyArray<{ className: string; probability: number }>,
): boolean {
  let probability = 0
  for (const prediction of predictions) {
    if (prediction.className === 'Porn' || prediction.className === 'Hentai') {
      probability += prediction.probability
    }
  }
  return probability >= NUDITY_MIN_PROBABILITY
}

export async function screenPhoto(blob: Blob): Promise<ScreenFinding> {
  try {
    const { screenBlob } = await import('./photoScreenEngine')
    return await screenBlob(blob)
  } catch {
    return null
  }
}
