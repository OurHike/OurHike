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
  fetchFieldNotes,
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
  fetchPublishedDrought,
  fetchPublishedFieldNotes,
  fetchPublishedReports,
  fetchPublishedWorkProjects,
} from './publishedConditions'
import type { DroughtBand } from '../map/droughtLayers'
import type { AtcUpdate } from './atcUpdates'
import type { NoteSummary } from './fieldNotes'
import type { WorkProjectSummary } from './workProjects'

/**
 * How often the published baselines are re-read while the app is open.
 *
 * One hour, deliberately equal to the pipeline's publish cadence
 * (.github/workflows/publish-conditions.yml) rather than a fraction of it.
 * Exported so a test can drive it and so the pairing is greppable from both
 * ends.
 */
export const CONDITIONS_REFRESH_MS = 60 * 60 * 1000

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
  /**
   * Visible field notes - the map's working set, each place's most recent
   * few (features/FIELD_NOTES.md §3's roll-up input). Null carries the same
   * distinction as `closures`: "we have not managed to ask" is not "nobody
   * has said anything", and only the second may render a spring as merely
   * unconfirmed.
   */
  notes: readonly NoteSummary[] | null
  /** The states behind those lists, for the "as of" the strip prints. */
  closureState: ConditionState<ClosureSummary>
  reportState: ConditionState<ReportSummary>
  noteState: ConditionState<NoteSummary>
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
  /**
   * This week's drought bands, and the week they describe (#720).
   *
   * Empty rather than null when there is nothing: unlike a closure, an
   * absent drought band is not ambiguous. The pipeline publishes an empty
   * band set for a trail with no drought on it precisely so that "no
   * drought" and "we could not ask" stay distinguishable - the second one
   * leaves `droughtWeek` null, and the map draws nothing in both cases
   * because there is nothing to draw either way.
   */
  drought: readonly DroughtBand[]
  /** The Tuesday-to-Monday week those bands describe, or null if none
   *  arrived. NOT the bake's clock - see publishedConditions.ts. */
  droughtWeek: { start: Date; end: Date } | null
  /**
   * The volunteer workdays (#760), and the bake's own clock beside them -
   * the first data in this app that EXPIRES, so the age is not decoration:
   * lib/workProjects.ts turns it into "stop calling these opportunities"
   * past 48 hours. Null until an artifact has been read; like the ATC
   * notices there is no live tier for this to be a baseline OF.
   */
  workProjects: readonly WorkProjectSummary[] | null
  workProjectsGeneratedAt: Date | null
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
  const [noteState, setNoteState] = useState<ConditionState<NoteSummary>>(UNAVAILABLE)
  const [atcUpdates, setAtcUpdates] = useState<readonly AtcUpdate[]>([])
  const [atcReviewedAt, setAtcReviewedAt] = useState<Date | null>(null)
  const [drought, setDrought] = useState<readonly DroughtBand[]>([])
  const [droughtWeek, setDroughtWeek] = useState<{ start: Date; end: Date } | null>(null)
  const [workProjects, setWorkProjects] = useState<readonly WorkProjectSummary[] | null>(
    null,
  )
  const [workProjectsGeneratedAt, setWorkProjectsGeneratedAt] = useState<Date | null>(
    null,
  )
  // Was a state with no setter until #231 - nothing ever synced, so the status
  // strip said "never synced" on every device forever, which was true and
  // looked like a bug in the strip rather than a missing feature.
  const [lastSyncedAt, setLastSyncedAt] = useState<Date | null>(null)

  const markSynced = useCallback(() => setLastSyncedAt(new Date()), [])

  // WHY THERE IS A CLOCK HERE AT ALL (#720).
  //
  // Both reads below used to run once per online transition, so a hiker who
  // opened the app in the morning and kept signal still had the morning's
  // closures at dusk. That was survivable while the pipeline published once a
  // day - the artifact could not be newer than what they already had. It
  // stopped being survivable when publishing moved to hourly: without this,
  // the whole cadence change would land in the bucket and reach nobody.
  //
  // An hour, matching the publish cadence rather than beating it. A shorter
  // interval would spend a hiker's battery and data re-reading bytes that
  // cannot have changed; a longer one would make the hourly publish pointless
  // for the phone it is for. The two numbers are a pair, and moving one
  // without the other is the mistake this comment exists to prevent.
  //
  // Every read this drives is cheap and cancellable, and each one leaves its
  // state exactly where it was on failure - so a wake-up in a dead spot costs
  // one failed fetch and changes nothing on screen.
  const [refreshCount, setRefreshCount] = useState(0)
  useEffect(() => {
    if (!online) return
    const timer = setInterval(
      () => setRefreshCount((count) => count + 1),
      CONDITIONS_REFRESH_MS,
    )
    return () => clearInterval(timer)
  }, [online])

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
  // **That gate is now a routing decision rather than a dead end (#447).**
  // The effect still fires no request without signal - `{ online }` travels
  // to `fetchPublished`, which skips the fetch entirely - but it now reads
  // the copy this phone kept the last time an artifact arrived. So the
  // second row of that table stops being "Trail conditions unavailable" on a
  // phone that is holding a perfectly good, perfectly datable closure list,
  // and the fetch-that-cannot-work is still never fired.
  //
  // NOT gated on API_CONFIGURED, though - this path has nothing to do with the
  // backend, and a build with no backend configured at all is exactly the one
  // that most needs a baseline.
  useEffect(() => {
    let cancelled = false
    // Named once rather than repeated six times: every read below wants the
    // same routing, and a read that quietly disagreed would be the one that
    // fires a request in a dead spot.
    const how = { online }

    void fetchPublishedClosures(undefined, how).then((published) => {
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
    void fetchPublishedReports(undefined, how).then((published) => {
      if (cancelled || published === null) return
      setReportState((current) =>
        withBaseline(current, published.items, published.generatedAt),
      )
    })

    // Field notes ride the same two-tier read as reports (FIELD_NOTES.md
    // §6): the baseline is what a hiker has when the backend is down, and
    // the live read wins whenever it lands.
    void fetchPublishedFieldNotes(undefined, how).then((published) => {
      if (cancelled || published === null) return
      setNoteState((current) =>
        withBaseline(current, published.items, published.generatedAt),
      )
    })

    // The ATC's notices. No `withBaseline` and no race to lose: there is no
    // live read to be overwritten by, so this is a plain set. `null` covers the
    // 404 the bucket serves while nobody has reviewed the source file, and
    // leaving the list empty in that case is the point - the pipeline publishes
    // nothing rather than an empty document precisely so that "we have not
    // looked" cannot render as "ATC reports nothing".
    void fetchPublishedAtcUpdates(undefined, how).then((published) => {
      if (cancelled || published === null) return
      setAtcUpdates(published.items)
      setAtcReviewedAt(published.reviewedAt ?? null)
    })

    // The volunteer workdays (#760). Reviewed-file data like the ATC
    // notices, so a plain set - and the generated_at travels because the
    // 48-hour opportunity ceiling is judged against it.
    void fetchPublishedWorkProjects(undefined, how).then((published) => {
      if (cancelled || published === null) return
      setWorkProjects(published.items)
      setWorkProjectsGeneratedAt(published.generatedAt)
    })

    // The drought bands (#720). No `withBaseline` and no race, like the ATC
    // notices: there is no live endpoint behind this, so the published
    // artifact is the only tier there is.
    void fetchPublishedDrought(undefined, how).then((published) => {
      if (cancelled || published === null) return
      setDrought(
        published.items.map((feature) => ({
          dm: feature.properties.dm,
          label: feature.properties.label,
          trailMiles: feature.properties.trail_miles,
          geometry: feature.geometry,
        })),
      )
      setDroughtWeek(published.validWeek ?? null)
    })

    return () => {
      cancelled = true
    }
  }, [online, refreshCount])

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

    void fetchFieldNotes().then((next) => {
      if (cancelled) return
      setNoteState(withLive(next))
      stamp()
    }, leaveUnknown)

    return () => {
      cancelled = true
    }
    // `refreshCount` drives this one too. The baseline read above is what
    // makes an unreachable backend survivable; this is the read that makes a
    // reachable one current, and a hiker with signal all afternoon should get
    // the closure a moderator verified at lunchtime rather than whatever the
    // backend said when the app opened.
  }, [online, refreshCount])

  return {
    closures: itemsOf(closureState),
    reports: itemsOf(reportState),
    notes: itemsOf(noteState),
    closureState,
    reportState,
    noteState,
    atcUpdates,
    atcReviewedAt,
    drought,
    droughtWeek,
    workProjects,
    workProjectsGeneratedAt,
    lastSyncedAt,
    markSynced,
  }
}
