// What the trail is like right now, from the two places that can say.
//
// Closures and reports arrive twice - a published baseline that needs no
// backend, and a live read that overrides it - and the ATC's own notices
// arrive once. Three states, two effects and the clock that dates them, lifted
// out of App.tsx: the fetching is entirely self-contained, and what the shell
// actually does with the answers (which band goes on the map, which sentence
// goes in the header) stays in the shell, where the rest of that reasoning is.
//
// features/CONDITIONS_DELIVERY.md is the design.

import { useCallback, useEffect, useState } from 'react'
import {
  API_CONFIGURED,
  fetchClosures,
  fetchReports,
  type ClosureSummary,
  type ReportSummary,
} from './api'
import {
  UNAVAILABLE,
  itemsOf,
  withBaseline,
  withLive,
  type ConditionState,
} from './conditionState'
import {
  fetchPublishedAtcUpdates,
  fetchPublishedClosures,
  fetchPublishedReports,
} from './publishedConditions'
import type { AtcUpdate } from './atcUpdates'

export interface Conditions {
  /**
   * Null means "we have not managed to ask", not "there are none" - the two
   * draw the same map and mean opposite things on the ground (#286). Nothing
   * renders a reassuring absence from either: a clear header is what a hiker
   * sees when the way ahead is clear AND when we could not check, and the
   * status strip's sync age is what tells those apart (lib/syncAge.ts).
   */
  closures: readonly ClosureSummary[] | null
  reports: readonly ReportSummary[] | null
  /** The states behind those two lists, for the "as of" the strip prints. */
  closureState: ConditionState<ClosureSummary>
  reportState: ConditionState<ReportSummary>
  /**
   * The ATC's own notices, and deliberately NOT a `ConditionState` (#461).
   *
   * That machine exists to say which of two tiers a hiker is looking at - a
   * live backend read or a day-old published baseline - and here there is only
   * ever one: ATC publishes on their website, not through our API, so there is
   * no live tier for a baseline to be a fallback from. Wrapping it anyway would
   * put an "as of" caveat about OUR bake on data whose age is ATC's own
   * `updated_at`, the one number that matters, which travels on each row.
   */
  atcUpdates: readonly AtcUpdate[]
  /** The other half of that honesty, beside the list rather than inside the
   *  rows - it is a fact about the review, not about any one notice. */
  atcReviewedAt: Date | null
  /** When something last actually reached the server. Null until it has. */
  lastSyncedAt: Date | null
  /** Stamp that clock. Exposed because the outbox flush is the other thing
   *  that reaches the server, and one clock has to serve both. */
  markSynced(): void
}

export function useConditions(online: boolean): Conditions {
  // One state each rather than a list plus a separate "where did this come
  // from", because the two reads race and updating two states from a race is
  // how you get fresh closures labelled stale. lib/conditionState.ts owns the
  // rule that live always wins; `closures` and `reports` stay exactly the
  // `T[] | null` every consumer already expects. Reports carry the same state
  // machine as closures (#436) - they are the warning pins, the other half of
  // what a hiker walks into.
  const [closureState, setClosureState] =
    useState<ConditionState<ClosureSummary>>(UNAVAILABLE)
  const [reportState, setReportState] =
    useState<ConditionState<ReportSummary>>(UNAVAILABLE)
  const [atcUpdates, setAtcUpdates] = useState<readonly AtcUpdate[]>([])
  const [atcReviewedAt, setAtcReviewedAt] = useState<Date | null>(null)
  // Was a state with no setter until #231 - nothing ever synced, so the status
  // strip said "never synced" on every device forever, which was true and
  // looked like a bug in the strip rather than a missing feature.
  const [lastSyncedAt, setLastSyncedAt] = useState<Date | null>(null)

  const markSynced = useCallback(() => setLastSyncedAt(new Date()), [])

  // The published baseline, fetched once and independently of the backend.
  // This is the read that makes an unreachable backend mean "day-old closures,
  // labelled as day-old" rather than the silence it used to mean.
  //
  // Gated on `online`, matching the rule the trail-line fetch already keeps -
  // "waits for signal rather than failing a fetch it knows cannot work". This
  // was written ungated first, on the theory that the service worker might hold
  // a copy; it does not. vite.config.ts precaches the app shell and the glyph
  // ranges and nothing else, because this app's offline story is IndexedDB
  // rather than cached responses. So offline there is genuinely no baseline to
  // get, and the honest state is `unavailable` - which the strip says out loud
  // instead of rendering as a clear trail.
  //
  // Losing that case matters less than it sounds: the failure this baseline
  // exists for is a backend that is down while the phone has signal, and that
  // is an online phone. Keeping a baseline across a real signal loss means
  // persisting it the way the trail lines are persisted, which is a storage
  // decision of its own rather than a line in this effect.
  //
  // NOT gated on API_CONFIGURED, though - this path has nothing to do with the
  // backend, and a build with no backend configured at all is exactly the one
  // that most needs a baseline.
  useEffect(() => {
    if (!online) return

    let cancelled = false

    void fetchPublishedClosures().then((published) => {
      if (cancelled || published === null) return
      // Functional update, because the live read may already have landed -
      // `withBaseline` is what refuses to overwrite it.
      setClosureState((current) =>
        withBaseline(current, published.items, published.generatedAt),
      )
    })

    // Reports the same way (#436). The baseline holds only public moderated
    // rows, so a signed-in reporter's own unmoderated report still needs the
    // live read - which wins whenever it lands, exactly as with closures.
    void fetchPublishedReports().then((published) => {
      if (cancelled || published === null) return
      setReportState((current) =>
        withBaseline(current, published.items, published.generatedAt),
      )
    })

    // The ATC's notices. No `withBaseline` and no race to lose: there is no
    // live read to be overwritten by, so this is a plain set. `null` covers the
    // 404 the bucket serves while nobody has reviewed the source file, and
    // leaving the list empty in that case is the point - the pipeline publishes
    // nothing rather than an empty document precisely so that "we have not
    // looked" cannot render as "ATC reports nothing".
    void fetchPublishedAtcUpdates().then((published) => {
      if (cancelled || published === null) return
      setAtcUpdates(published.items)
      setAtcReviewedAt(published.reviewedAt ?? null)
    })

    return () => {
      cancelled = true
    }
  }, [online])

  // The map's own reads (#232), deliberately not gated on an account: browsing
  // has never needed one, and the reads send a token only if there is one
  // (lib/api.ts).
  //
  // Both settle independently. A closures read that succeeds while reports
  // fails should still warn about the closure - pairing them would mean one
  // failure silencing both, and closures are the half a hiker walks into.
  useEffect(() => {
    if (!online || !API_CONFIGURED) return

    let cancelled = false
    // A read reaching the server IS a sync, and the status strip's age is the
    // only thing distinguishing "nothing reported here" from "we could not
    // ask" - so it has to move when the map data does, not only when a report
    // goes out.
    const stamp = () => {
      if (!cancelled) setLastSyncedAt(new Date())
    }

    // A read that throws leaves its state where it was - the baseline if one
    // landed, `unavailable` otherwise - and says nothing else. Being unable to
    // reach the backend is the ordinary condition out here, not an error to
    // interrupt someone over; the conditions age on the status strip is what
    // turns the state left behind into something a hiker can read.
    const leaveUnknown = () => undefined

    void fetchClosures().then((next) => {
      if (cancelled) return
      setClosureState(withLive(next))
      stamp()
    }, leaveUnknown)

    void fetchReports().then((next) => {
      if (cancelled) return
      setReportState(withLive(next))
      stamp()
    }, leaveUnknown)

    return () => {
      cancelled = true
    }
  }, [online])

  return {
    closures: itemsOf(closureState),
    reports: itemsOf(reportState),
    closureState,
    reportState,
    atcUpdates,
    atcReviewedAt,
    lastSyncedAt,
    markSynced,
  }
}
