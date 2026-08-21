// The published conditions, kept on the phone (#447).
//
// `fetchPublished*` is gated on `online`, and rightly: vite.config.ts
// precaches the app shell and the glyph ranges and nothing else, so a request
// fired with no signal is pure waste and App.trailData.test.tsx asserts this
// app does not fire one. The consequence was that the baseline helped in one
// failure and not the other:
//
//   backend down, phone has signal  ->  baseline, labelled with its age
//   phone has no signal             ->  "Trail conditions unavailable"
//
// The second row is the one a hiker on the trail is actually in. So the fix
// is not to remove the gate - it is to keep the last artifact that DID
// arrive, which is what this module does.
//
// WHERE, AND WHY NOT localStorage
//
// IndexedDB through `idb-keyval`, beside the outbox and the archive, because
// this app's offline story is already IndexedDB and `localStorage` is
// synchronous on the main thread - #448 moved a hash fold off that thread for
// exactly this reason, and a few hundred KB of JSON parsed there at startup
// would be the same mistake in a smaller coat.
//
// ONE KEY PER ARTIFACT, WHICH IS THE PART WORTH READING
//
// Six artifacts arrive concurrently. A single record holding all six would
// make every arrival a read-modify-write over one key, which is precisely the
// hazard #288 found in the outbox: two writes interleave between the `get`
// and the `set` and the loser vanishes. `idb-keyval`'s `set` is one
// transaction over one key, so writing them separately means the race cannot
// happen rather than being handled.
//
// WHAT THIS DELIBERATELY DOES NOT DO
//
// It does not expire anything. A stored baseline is served however old it is,
// carrying its own `generated_at`, and `conditionState.ts` labels it exactly
// as it labels a fresh one - see `recallPublished` for the argument.

import { del, get, set } from 'idb-keyval'

/** One artifact as it was received, with its dates in the form they arrived
 *  in. Stored as the raw document rather than the parsed shape so that the
 *  same validation runs on the way back out - a stored document is no more
 *  trustworthy than a fetched one, and less recently checked. */
export interface CachedConditions {
  /** The document exactly as `fetchPublished` parsed it from the bucket. */
  document: Record<string, unknown>
  /** When this phone stored it. Not shown to anybody: the age a hiker reads
   *  is the bake's `generated_at`, which is a fact about the data, while
   *  this is a fact about the download. Kept for debugging and for a future
   *  eviction rule that needs to know which copy is oldest. */
  storedAt: string
}

/** Namespaced like the outbox's `ourhike:outbox`, and suffixed with the
 *  artifact's own bucket key so the two never collide. */
export function conditionsCacheKey(key: string): string {
  return `ourhike:conditions:${key}`
}

/**
 * The most bytes one stored artifact may occupy.
 *
 * @unvalidated 2 MB is picked, not measured. The real artifacts are far
 * smaller - closures, reports and notes are a few hundred rows of short JSON
 * - so this is not a budget anybody is spending, it is a ceiling that stops a
 * pathological bake (a runaway export, a bucket serving the wrong file) from
 * growing into the space a hiker's 1.18 GB archive lives in. What would
 * settle it: the actual size distribution of `conditions/*.json` across a
 * month of publishes, which nothing records today. Until then it is set high
 * enough that no real artifact can reach it and low enough that six of them
 * together are noise beside one downloaded map.
 */
export const MAX_CACHED_BYTES = 2 * 1024 * 1024

/**
 * Keep this artifact for the next time the phone has no signal.
 *
 * **Never throws, and never blocks the caller.** A read that reached the
 * bucket has already succeeded; failing to write a copy of it must not turn
 * that into a failure. A private-mode browser with no IndexedDB, a full disk,
 * or a quota refusal all end the same way here - the fetch's answer stands
 * and the next offline session simply has nothing kept, which is exactly
 * where this app was before.
 */
export async function rememberPublished(
  key: string,
  document: Record<string, unknown>,
  storedAt: Date = new Date(),
): Promise<void> {
  try {
    const serialised = JSON.stringify(document)
    if (serialised.length > MAX_CACHED_BYTES) {
      // Dropped rather than truncated: half a JSON document is not a
      // smaller baseline, it is an unparseable one, and the copy already
      // stored is better than that. Clearing is deliberate too - a stored
      // copy that this build now refuses to refresh would age silently.
      await del(conditionsCacheKey(key))
      return
    }

    const cached: CachedConditions = { document, storedAt: storedAt.toISOString() }
    await set(conditionsCacheKey(key), cached)
  } catch {
    // See the docstring: a failure to keep a copy is not a failure to read.
  }
}

/**
 * The last artifact under this key that reached this phone, or null.
 *
 * **No expiry, and that is a decision rather than an omission (#447 asks for
 * it by name).** A stored baseline could be weeks old, and `closureAgeLabel`
 * will say "Conditions as of 34d ago". Three reasons that is the right thing
 * to show:
 *
 * - **A closure outlives the artifact that describes it.** A relocation, a
 *   bridge rebuild, a storm-damaged section - these are measured in seasons.
 *   A month-old closure list is, in the ordinary case, still true.
 * - **The age is already carried and already rendered.** `generated_at`
 *   travels with the document, `conditionState.ts` keeps the tier, and the
 *   status strip prints it. Nothing here can render as fresh.
 * - **A ceiling replaces something with nothing.** Past it, a hiker would see
 *   "Trail conditions unavailable" while the phone holds a month-old list of
 *   closures that are probably still shut. That is a worse answer, and it is
 *   the answer this issue exists to stop giving.
 *
 * The artifacts that genuinely expire keep their own rules and are untouched:
 * `workProjects.ts` stops calling a workday an opportunity past 48 hours, and
 * the drought bands carry the week they describe.
 */
export async function recallPublished(key: string): Promise<CachedConditions | null> {
  try {
    const cached = await get<CachedConditions>(conditionsCacheKey(key))
    if (cached === undefined) return null
    // Shape-checked rather than trusted: this came out of a store an older
    // build wrote, and a document that is not an object would otherwise
    // reach the same parser that validates network bytes as if it were one.
    if (typeof cached.document !== 'object' || cached.document === null) return null
    return cached
  } catch {
    return null
  }
}
