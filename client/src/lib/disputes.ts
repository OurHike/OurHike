// Places the field says are not there (#876, features/FIELD_NOTES.md §4).
//
// The one place this app genuinely contradicts upstream on upstream's own
// ground: ATC says there is a spring here, and there is no spring here.
//
// WHAT IS HERE AND WHAT IS NOT
//
// The corroboration rule is NOT here, and that is the load-bearing division.
// It turns on distinct ACCOUNTS, and `NoteSummary` withholds `reporter_id`
// from everyone but the author and a moderator (§6, #252) - so the rule runs
// on the server, where the identities are, and a verdict travels
// (`backend/app/core/disputes.py`). What this module owns is what a hiker
// reads: the shape of that verdict, and the sentence the card prints.
//
// WHY IT IS A SENTENCE AND NOT ONLY A PIN
//
// WIREFRAMES.md §11's rule is that the visual channel never carries the
// meaning alone, and §4 names the exact sentence it wants: "2 hikers reported
// this missing, most recently 4 days ago". A dashed pin says *something* is
// unusual about a place; only the words say which of two very different
// things it is - never verified to exist, or verified and now gone.

/** One place, reported missing - `DisputeOut` on the wire. */
export interface DisputeSummary {
  poi_id: string
  /** Distinct ACCOUNTS inside the decay window, not notes: two notes from
   *  one person is one observation, and the card prints this number. */
  accounts: number
  /** ISO timestamp of the most recent disputing observation. */
  latest_at: string
  /** True when a maintainer whose assignment covers that mile is among
   *  them - a different sentence, and a stronger one. */
  maintainer_said: boolean
}

const DAY_MS = 24 * 60 * 60 * 1000

/** "today", "yesterday", "4 days ago" - noteRollup.ts's own phrasing, shared
 *  deliberately: two surfaces ageing the same observation in different words
 *  is a hiker reading two claims where there is one. */
function age(latest: Date, now: Date): string {
  const days = Math.floor((now.getTime() - latest.getTime()) / DAY_MS)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  return `${days} days ago`
}

/**
 * What the card says about a disputed place, or null when nothing does.
 *
 * Three sentences rather than one, and the difference between them is the
 * whole reason this is a function rather than a template:
 *
 * - **A maintainer's word is named as a maintainer's.** "The maintainer for
 *   this stretch" is a different claim from "2 hikers", and flattening them
 *   into a count would throw away the strongest evidence this feature can
 *   receive.
 * - **An unverified place gets a hedge the others do not.** FIELD_NOTES.md
 *   §4 leaves open whether `not_found` should be offered at all on a
 *   `confidence: low` POI, on the grounds that a hiker may be reporting the
 *   data's known weakness rather than a change on the ground. It is offered
 *   (lib/fieldNotes.ts says why), and this is where that weaker claim is
 *   said out loud instead of being counted as if it were the same thing.
 */
export function disputeSentence(
  dispute: DisputeSummary | null,
  now: Date,
  options: { unverified?: boolean } = {},
): string | null {
  if (dispute === null) return null

  const when = age(new Date(dispute.latest_at), now)

  if (dispute.maintainer_said) {
    return `The maintainer for this stretch reported this missing, ${when}.`
  }

  const who =
    dispute.accounts === 1
      ? '1 hiker reported this missing'
      : `${dispute.accounts} hikers reported this missing`

  if (options.unverified === true) {
    // The place upstream never confirmed either. Both facts, in one
    // sentence, because either alone misleads: "reported missing" implies it
    // was there, and "never verified" implies nobody has looked.
    return `${who}, most recently ${when}. This one was never confirmed to exist.`
  }

  return `${who}, most recently ${when}.`
}

/** The disputes for one place, from the map's working set. A plain lookup
 *  rather than a hook: the card is rendered inside a list and a hook per row
 *  would be a request per row. */
export function disputeFor(
  disputes: readonly DisputeSummary[] | null,
  poiId: string,
): DisputeSummary | null {
  return disputes?.find((dispute) => dispute.poi_id === poiId) ?? null
}
