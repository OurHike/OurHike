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

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  API_CONFIGURED,
  fetchClosures,
  fetchDisputes,
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
  fetchPublishedDisputes,
  fetchPublishedDrought,
  fetchPublishedFieldNotes,
  fetchPublishedNynjtcAlerts,
  fetchPublishedReports,
  fetchPublishedWorkProjects,
  type OrgNotice,
  type PublishedConditions,
} from './publishedConditions'
import type { DroughtBand } from '../map/droughtLayers'
import type { AtcUpdate } from './atcUpdates'
import type { DisputeSummary } from './disputes'
import type { NoteSummary } from './fieldNotes'
import type { WorkProjectSummary } from './workProjects'

/**
 * How often the published baselines are re-read while the app is open.
 *
 * One hour, equal to the cadence .github/workflows/publish-conditions.yml's
 * cron DECLARES rather than a fraction of it. What GitHub's scheduler
 * delivers is slower, and measured rather than assumed (#1316, 2026-09-25):
 * 40 scheduled runs, 2026-09-18 16:42Z to 2026-09-25 08:10Z, all successful: median gap 4.0 h, mean 4.1 h, max 6.3 h. The maintainer accepted that cadence rather than
 * chasing it (poll, 2026-09-25), so the hour stays: it bounds how long after
 * a publish does land the phone sees it, and a re-read of bytes that have not
 * changed costs one small fetch. Exported so a test can drive it and so the
 * pairing is greppable from both ends.
 */
export const CONDITIONS_REFRESH_MS = 60 * 60 * 1000

/**
 * The shortest gap between two re-reads triggered by the app becoming visible.
 *
 * Five minutes. The hourly interval is paced against the declared cron, but
 * a return-to-foreground is not a clock tick - it is the one moment we know a
 * hiker is about to READ the thing, and the artifact may have been republished
 * several times while the screen was off. Refetching then is worth the bytes.
 *
 * Doing it on every visibility change would not be: switching to a messaging
 * app and back is a normal thing to do repeatedly, and each round trip is a
 * hiker's data and battery.
 */
export const VISIBILITY_REFRESH_MIN_MS = 5 * 60 * 1000

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
  /**
   * Places the field says are not there (#876), corroborated - null is "we
   * have not managed to ask", which must never render as "nobody disputes
   * this" (#249's distinction, again).
   */
  disputes: readonly DisputeSummary[] | null
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
   *  rows - it is a fact about the review, not about any one notice.
   *
   *  ATC's ONLY. `conditions/nynjtc_alerts.json` deliberately carries no
   *  `reviewed_at` - nobody has checked NYNJTC's page, so there is no such
   *  date, and the exporter refuses to invent one. See `orgNotices`. */
  atcReviewedAt: Date | null
  /**
   * Notices from organizations that are not the ATC (#1083).
   *
   * A second publisher through the same machinery, and the reason it is a
   * separate field rather than concatenated onto `atcUpdates` is that the two
   * artifacts are different shapes: ATC's rows carry two mile columns and
   * NYNJTC's carry features/ORG_NOTICES.md §2's publisher-agnostic row with
   * its `place` union. lib/notices.ts adapts the older one into the newer, and
   * chrome/noticesPanel.tsx is where that happens - which keeps the asymmetry
   * in one file rather than in every consumer.
   *
   * Empty rather than null when nothing comes back, for the same reason
   * `atcUpdates` is: the bucket serves a 404 while the exporter has never run,
   * and the pipeline publishes nothing rather than an empty document so that
   * "we have not looked" cannot render as "NYNJTC reports nothing".
   */
  orgNotices: readonly OrgNotice[]
  /**
   * Every club's notices, from conditions/notices.json (#1805, decision 53
   * phase D), or null when that file has not reached this phone.
   *
   * NULL IS THE ORDINARY STATE WHILE THE EXPORTERS PUBLISH: no exporter
   * writes the file, only the dbt path does, so on such a bucket it 404s and
   * the notices panel keeps reading `atcUpdates` and `orgNotices` exactly as
   * before. An EMPTY list is a different claim - the file arrived and no
   * club has a notice - and the two are kept apart for that reason.
   *
   * The map's A.T. bands and dots still come from `atcUpdates`: ATC's own
   * file, unchanged (decision 51), is what draws them.
   */
  clubNotices: readonly OrgNotice[] | null
  /** When conditions/notices.json was baked, for the panel's "as of". */
  clubNoticesGeneratedAt: Date | null
  /**
   * Whether the bucket has said it serves conditions/notices.json, though
   * this phone may not have downloaded it (decision 77): what keeps the
   * notices panel the planned-hike one on a phone with nothing planned,
   * which downloads nothing. False until a HEAD request answers 200, and
   * never set back by a 404 or a dead spot, as a held list is never taken
   * away. lib/publishedNotices.ts's `noticesListed` says why a HEAD and not
   * the manifest.
   */
  clubNoticesListed: boolean
  /**
   * Whether a hike is planned and this phone holds no copy of
   * conditions/notices.json, settled: the last planned-hike read ended with
   * nothing, for a reason a connection can change (lib/publishedNotices.ts's
   * `readPublishedNotices` lists them; never a 404). What
   * chrome/noticesPanel.tsx says to the hiker, in option A of the
   * maintainer's poll of 2026-10-09.
   *
   * FALSE UNTIL A READ SETTLES, so a phone whose first download is in flight
   * keeps today's panel, with no wording of its own for that state. Once
   * true it stays true while a retry is in flight, which is still the truth
   * (the phone holds no copy yet), and the warning does not flicker off and
   * on again. False whenever `clubNotices` holds a list.
   */
  clubNoticesMissing: boolean
  /**
   * Decision 67's hunting areas, shooting sites and burned areas, from
   * conditions/hazard_areas.json (decision 84), read whatever is planned,
   * or null when that file has not reached this phone. Like `clubNotices`,
   * never set back to null by a 404 or a dead spot, and null is "no
   * answer", never "no hazard area": chrome/noticesPanel.tsx then draws the
   * areas from notices.json if this phone holds it.
   */
  hazardFile: PublishedConditions<OrgNotice> | null
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

/**
 * @param ready Whether the launch is past its first frame (#1302,
 *   lib/useAfterFirstFrame.ts). The nine published reads and the four live
 *   ones below wait for it; nothing they feed changes what the first frame
 *   is, and every line they fill renders "unknown" until they land anyway.
 *   Defaults to true so a screen or a test that mounts this hook alone
 *   behaves as before.
 * @param hikePlanned Whether the hiker has any hike planned
 *   (lib/dayHikes.ts's `anyHikePlanned`): conditions/notices.json, about
 *   2 MB gzipped, is downloaded only while it is true (decision 77), and the
 *   moment it turns true, not at the next hourly read. Defaults to true for
 *   the same reason `ready` does.
 */
export function useConditions(
  online: boolean,
  ready = true,
  hikePlanned = true,
): Conditions {
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
  // Disputes ride the same two tiers as the notes they are computed from,
  // and get the same state machine for the same reason: a live read wins
  // whenever it lands, and until one does the baseline is what a hiker has.
  const [disputeState, setDisputeState] =
    useState<ConditionState<DisputeSummary>>(UNAVAILABLE)
  const [atcUpdates, setAtcUpdates] = useState<readonly AtcUpdate[]>([])
  const [orgNotices, setOrgNotices] = useState<readonly OrgNotice[]>([])
  const [clubNotices, setClubNotices] = useState<PublishedConditions<OrgNotice> | null>(
    null,
  )
  const [clubNoticesListed, setClubNoticesListed] = useState(false)
  const [clubNoticesMissing, setClubNoticesMissing] = useState(false)
  const [hazardFile, setHazardFile] = useState<PublishedConditions<OrgNotice> | null>(
    null,
  )
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
  // An hour, matching the cron's declared cadence rather than beating it. A
  // shorter interval would spend a hiker's battery and data re-reading bytes
  // that cannot have changed; a longer one would add its own delay on top of
  // the publish's. The two numbers are a pair, and moving one without the
  // other is the mistake this comment exists to prevent. The pair is the
  // DECLARED cadence: the bake actually lands about every four hours
  // (measured, see CONDITIONS_REFRESH_MS), so a closure verified just after a
  // run can take ~6 h to reach this clock, which the maintainer accepted.
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

  // AND AGAIN THE MOMENT THE PHONE COMES BACK OUT OF A POCKET, because the
  // interval above does not survive that.
  //
  // A backgrounded tab has its timers throttled hard and a backgrounded PWA
  // may have them suspended outright - that is the browser doing its job for
  // the battery, not a bug. What it means here is that the hourly re-read
  // silently stops while the screen is off, so the state a hiker sees on
  // waking their phone is whatever was fetched before they put it away. On a
  // surface carrying ATC's closures, four hours in a pocket is exactly when
  // the answer is most likely to have changed and least likely to have been
  // re-read.
  //
  // Throttled to `VISIBILITY_REFRESH_MIN_MS`, because app-switching is not
  // rare: without it, flicking between the map and a messaging app would
  // refetch every baseline each time, on a hiker's data.
  const lastReadAt = useRef(0)
  useEffect(() => {
    if (!online) return
    const onVisible = () => {
      if (document.visibilityState !== 'visible') return
      const now = Date.now()
      if (now - lastReadAt.current < VISIBILITY_REFRESH_MIN_MS) return
      lastReadAt.current = now
      setRefreshCount((count) => count + 1)
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
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
    if (!ready) return
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

    // NYNJTC's alerts (#1083). Same posture as ATC's above and for the same
    // reason - they publish on their own site, not through our API - and no
    // `reviewedAt` to read, because that artifact deliberately carries none.
    // Nobody has checked NYNJTC's page, so every row ships `unreviewed` and
    // the list says so rather than the app implying a review nobody did.
    void fetchPublishedNynjtcAlerts(undefined, how).then((published) => {
      if (cancelled || published === null) return
      setOrgNotices(published.items)
    })

    // The volunteer workdays (#760). Reviewed-file data like the ATC
    // notices, so a plain set - and the generated_at travels because the
    // 48-hour opportunity ceiling is judged against it.
    void fetchPublishedDisputes(undefined, how).then((published) => {
      if (cancelled || published === null) return
      setDisputeState((current) =>
        withBaseline(current, published.items, published.generatedAt),
      )
    })

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
  }, [online, refreshCount, ready])

  // Every club's notices in one file (#1805), in an effect of its own so
  // that planning a hike reads it at once without re-reading the rest.
  // DOWNLOADED ONLY WHILE A HIKE IS PLANNED (decision 77): it is about 2 MB
  // gzipped, and only the planned-hike panel and the areas drawn for it read
  // it. With nothing planned, lib/publishedNotices.ts's readPublishedNotices
  // reads the copy this phone kept, if any, and asks the bucket with a HEAD
  // whether it serves the file at all, so the panel stays the planned-hike
  // one. A null keeps whatever this phone already holds: a 404 on a bucket
  // the exporters publish is the ordinary state, and a dead spot must not
  // take a held list away. The reader comes in behind import(), for the
  // launch budget (lib/publishedNotices.ts says why); a chunk that cannot
  // load reads as no file, exactly as a 404 does.
  //
  // THE HAZARD AREAS RIDE THE SAME EFFECT, PLANNED OR NOT (decision 84):
  // conditions/hazard_areas.json is read on each run of this effect - at
  // launch, on each refresh and visibility read, as notices.json was before
  // decision 77, and once more when planning changes - with the same rule
  // that a null keeps what this phone holds. ON A PROMISE OF ITS OWN: at a
  // weak-signal trailhead the areas waited behind a planned hike's download
  // of notices.json (UA's was 11,811,546 bytes on 2026-10-09), or behind the
  // HEAD with nothing planned.
  useEffect(() => {
    if (!ready) return
    let cancelled = false
    const reader = import('./publishedNotices')
    void reader
      .then(({ readPublishedNotices }) => readPublishedNotices(hikePlanned, { online }))
      .then(
        ({ published, listed, missing }) => {
          if (cancelled) return
          if (published !== null) setClubNotices(published)
          if (listed) setClubNoticesListed(true)
          // Every settled read answers it, and only a settled one: a read
          // in flight leaves the last answer standing (see the field). If
          // publishedNotices.ts's chunk cannot load, the rejection handler
          // below sets nothing, so the panel keeps the last answer too.
          setClubNoticesMissing(missing)
        },
        () => undefined,
      )
    void reader
      .then(({ fetchPublishedHazardAreas }) => fetchPublishedHazardAreas({ online }))
      .then(
        (hazards) => {
          if (!cancelled && hazards !== null) setHazardFile(hazards)
        },
        () => undefined,
      )
    return () => {
      cancelled = true
    }
  }, [online, refreshCount, ready, hikePlanned])

  // The map's own reads (#232), deliberately not gated on an account: browsing
  // has never needed one, and the reads send a token only if there is one
  // (lib/api.ts).
  //
  // Both settle independently. A closures read that succeeds while reports
  // fails should still warn about the closure - pairing them would mean one
  // failure silencing both, and closures are the half a hiker walks into.
  useEffect(() => {
    if (!ready || !online || !API_CONFIGURED) return

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

    // Disputes (#876). Its own read rather than something derived from the
    // notes above, and that is the design rather than an extra request:
    // corroboration counts distinct ACCOUNTS, and the notes on this phone
    // carry no `reporter_id` to count. The verdict is computed where the
    // identities are and travels as a count.
    void fetchDisputes().then((next) => {
      if (cancelled) return
      setDisputeState(withLive(next))
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
  }, [online, refreshCount, ready])

  return {
    closures: itemsOf(closureState),
    reports: itemsOf(reportState),
    notes: itemsOf(noteState),
    disputes: itemsOf(disputeState),
    closureState,
    reportState,
    noteState,
    atcUpdates,
    atcReviewedAt,
    orgNotices,
    clubNotices: clubNotices?.items ?? null,
    clubNoticesGeneratedAt: clubNotices?.generatedAt ?? null,
    clubNoticesListed,
    clubNoticesMissing: clubNotices === null && clubNoticesMissing,
    hazardFile,
    drought,
    droughtWeek,
    workProjects,
    workProjectsGeneratedAt,
    lastSyncedAt,
    markSynced,
  }
}
