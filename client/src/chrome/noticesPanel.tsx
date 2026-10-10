// The trail-notices feature, owned by one file instead of by App.tsx (#327).
//
// Everything the map screen needs in order to draw an organization's notices,
// let a hiker tap one, and tell them when new ones have been posted: the two
// map collections, the tap handler, the sheet over the tapped one, the full
// list, and the "new notices" banner's count and its dismissal.
//
// TWO PUBLISHERS NOW, AND THE SEAM IS HERE (#1083). This hook is where the
// asymmetry between them lives, which is what keeps it out of App.tsx and
// MapScreen.tsx - the two files BRANCHING.md §2 measures at thirteen of the
// last twenty-three conflicting merges. The shell hands over both artifacts
// and gets back the same prop bundle it always did.
//
// The asymmetry itself is small and it is real: only ATC's rows carry a mile,
// so only ATC's rows reach `closureBands` and `atcUpdatePoints`. Everything
// below that line - the list, the banner, the count, the silence watermark -
// takes every organization's rows through lib/notices.ts. features/
// ORG_NOTICES.md §3 is why that is the honest split rather than a stopgap:
// `unplaced` is a first-class arm of the union, not a failure to place.
//
// EVERY CLUB, ONCE conditions/notices.json IS HERE (#1805, decisions 66 and
// 67). That file carries every club's notices, and a list of all of them is
// a feed, so with it the panel becomes the maintainer's rule instead: the
// notices that touch a hike planned in the next 7 days (lib/plannedNotices.ts
// says what counts as planned and what "touches" means), and an empty state
// that says why when nothing is planned - never every club. Decision 67's
// hunting areas, shooting sites and burned areas come out of the same file,
// or out of conditions/hazard_areas.json, which a phone reads whatever is
// planned (decision 84), drawn where a trail this phone holds crosses one.
// Without the file - a
// bucket the exporters still publish - everything above is exactly as it
// was. The map's A.T. bands and dots come from ATC's own file either way.
//
// A PLANNED HIKE WHOSE FILE IS NOT ON THE PHONE SAYS SO (option A of the
// maintainer's poll of 2026-10-09). A hike is planned, and lib/useConditions.ts
// has settled that this phone holds no copy of notices.json for a reason a
// connection can change (`clubNoticesMissing`: a first run with no signal, a
// file over lib/conditionsCache.ts's ceiling relaunched offline, a download
// that failed). The legend row reads "Notices for your planned hikes: not on
// this phone yet", and today's list of ATC's and NYNJTC's notices opens under
// a warning that a closure on the hike will not show here. While the first
// download is in flight, or after a 404, the panel is today's, unchanged.
//
// All of it used to live in App.tsx as three `useState`s, five `useMemo`s, one
// `useCallback` and about forty lines of JSX inside the `<MapScreen>` call -
// at roughly lines 640, 1,490 and 4,440 of a 4,706-line file, each block
// interleaved with every other feature's share of the same four things. That
// interleaving is the mechanism #327 measured: a change to ATC notices and a
// change to, say, the route builder both edit App.tsx, so the two branches
// conflict even though the features have nothing to do with each other.
//
// What makes this more than a move is the return type. The hook hands back
// exactly the `MapScreenProps` fields this feature owns, as a `Pick<>`, so
// App.tsx spreads one value and the bundle cannot drift from the screen's own
// declarations. Ownership itself is a convention rather than something the
// compiler enforces - nothing stops a second file `Pick`ing the same field -
// but it is a convention with one obvious place to check, which is more than
// a flat prop list offers.
//
// MapScreen itself is untouched: its prop list is still flat, and that is
// deliberate. Regrouping its 104 props into bundles would have rewritten
// every fixture in MapScreen.test.tsx, which is churn that hides behaviour
// rather than protecting it.

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  atcBandCandidates,
  atcPointNotices,
  atcUpdateForBandId,
  type AtcUpdate,
} from '../lib/atcUpdates'
import { atcUpdatePoints } from '../map/atcUpdateLayers'
import {
  ATC_SOURCE_KEY,
  atcUpdateAsNotice,
  newNoticeLabel,
  newNoticesSince,
  readNoticeSilence,
  silenceNewNotices,
  type TrailNotice,
} from '../lib/notices'
import { closureBands } from '../map/closureLayers'
import { viewportMiles } from '../lib/viewportMiles'
import type { BoundingBox } from '../lib/legendContents'
import type { TrailIndex } from '../lib/trailPosition'
import type { Stewards } from '../lib/stewards'
import { EMPTY_CLUB_SECTIONS, type ClubSections } from '../lib/clubSections'
import { anyHikePlanned, type DayHike } from '../lib/dayHikes'
import type { Trip } from '../lib/trips'
import { routeLines, type TrailGraphIndex } from '../lib/trailGraph'
import { resolveDayHike } from '../lib/dayHikeCard'
import { localDay } from '../lib/passedToday'
import type { HazardArea, StretchAdvisory } from '../lib/hazardAreas'
import type { Position } from '../lib/noticeGeometry'

/** lib/noticeSelection.ts, once loaded: kept at module scope so a remount
 *  after the first load has it on its first render. */
type NoticeSelection = typeof import('../lib/noticeSelection')
let loadedSelection: NoticeSelection | null = null

/** The routing lib/noticeSelection.ts is handed, from modules the first
 *  frame already holds. */
const ROUTING = { resolveDayHike, routeLines }

function noAdvisories(): StretchAdvisory[] {
  return []
}
import type { MapScreenProps } from './MapScreen'
import {
  HazardAreaSheet,
  NoticeList,
  OrgNoticeSheet,
  PlannedNoticeList,
} from '../screens/deferred'

/**
 * The `MapScreenProps` fields this feature owns.
 *
 * A `Pick<>` rather than a hand-written interface so it cannot drift from the
 * screen's own declarations - the prose explaining each of these lives on
 * `MapScreenProps`, where the component that renders them can be read beside
 * it, and is deliberately not copied here.
 */
export type NoticesMapProps = Pick<
  MapScreenProps,
  | 'atcUpdates'
  | 'atcUpdatePoints'
  | 'onSelectAtcUpdate'
  | 'atcUpdateSheet'
  | 'noticeCount'
  | 'onOpenNotices'
  | 'noticeList'
  | 'newNoticeCount'
  | 'newNoticeLabel'
  | 'noticeRowLabel'
  | 'hazardAreas'
  | 'onSelectHazardArea'
  | 'hazardAreaSheet'
>

/** No hazard area, as one shared reference for a phone with neither
 *  conditions/notices.json nor hazard_areas.json - a fresh array per render would re-push the
 *  map's source on every one. */
const NO_HAZARD_AREAS: readonly HazardArea[] = []

export interface NoticesPanel {
  /** Spread into `<MapScreen>`. */
  mapScreen: NoticesMapProps
  /**
   * Whether a hiker has one of this feature's sheets open.
   *
   * Returned separately rather than folded into `mapScreen` because it is not
   * a prop: the shell reads it to decide whether a service-worker update may
   * restart the page under somebody (lib/useAppUpdate.ts). Only the tapped
   * sheet counts, exactly as it did in App.tsx - the notice list is a list a
   * hiker can reopen, and the banner is not a screen at all.
   */
  sheetOpen: boolean
  /**
   * Decision 67's areas the map is drawing (#1805), for the tapped line's
   * card, which prints an area's advisory on the stretch inside it
   * (chrome/tappedLinePanel.tsx). Returned beside `mapScreen` rather than in
   * it because it is that panel's input, not this screen's.
   */
  hazardAreas: readonly HazardArea[]
  /** The advisories for a tapped place on a trail: each drawn area it is
   *  inside or beside. Always a function, answering none until the rule has
   *  loaded and none on a phone with neither file that carries the areas. */
  hazardAdvisoriesAt: (at: Position) => StretchAdvisory[]
}

export interface NoticesInput {
  /** Every ATC notice the app holds (lib/useConditions.ts). The only rows that
   *  carry a mile, and therefore the only ones the map can place. */
  updates: readonly AtcUpdate[]
  /** Every notice from an organization that is not the ATC. All `unplaced`
   *  today, which is the honest state rather than a gap - see
   *  features/ORG_NOTICES.md §3. */
  orgNotices: readonly TrailNotice[]
  /** When a person last checked ATC's reviewed file against ATC's page.
   *
   *  ATC's ONLY, and deliberately not a map: `conditions/nynjtc_alerts.json`
   *  carries no `reviewed_at` at all, and that absence is load-bearing rather
   *  than an omission - nobody has checked NYNJTC's page, so there is no such
   *  date, and inventing one would claim a review that did not happen. The
   *  list turns this into the map it renders from, so the two states stay
   *  distinguishable. */
  reviewedAt: Date | null
  /** The published registry - where every organization's name comes from
   *  (features/ORG_NOTICES.md §6). Empty is ordinary; see lib/stewards.ts. */
  stewards: Stewards
  /** The centerline, or null before it has loaded - nothing is placed without it. */
  trailIndex: TrailIndex | null
  /**
   * What the map is currently showing, which is what the list is scoped to.
   *
   * The hiker's own frame rather than the app's: a thru-hiker in Connecticut
   * scrolling past nine Georgia notices to reach the one nine miles ahead is
   * the problem the scoping solves. Turned into a mile span here, because
   * `lib/viewportMiles.ts` already answers exactly that question for the
   * legend and a second answer to it would be a second thing to keep true.
   */
  bbox: BoundingBox
  /** The shell's clock, so the "new notices" window moves with it. */
  now: Date
  /**
   * Every club's notices from conditions/notices.json (#1805, decision 53
   * phase D), or null when that file has not reached this phone.
   *
   * NULL KEEPS TODAY'S PANEL: the two files above, NoticeList, the extent
   * scoping. Present, the panel becomes decision 66's - the notices that
   * touch a hike planned in the next 7 days (lib/plannedNotices.ts) - and
   * decision 67's hazard areas draw. The map's A.T. bands and dots come
   * from `updates` either way.
   */
  clubNotices?: readonly TrailNotice[] | null
  /** When conditions/notices.json was baked. */
  clubNoticesGeneratedAt?: Date | null
  /**
   * Whether the bucket serves conditions/notices.json though this phone has
   * not downloaded it (lib/useConditions.ts): decision 77 downloads it only
   * once a hike is planned. With it and nothing planned, the panel is still
   * decision 66's, saying no hike is planned, and never the list above. With
   * a hike planned it counts for nothing: a planned hike's notices come only
   * from the file, never from its absence.
   */
  clubNoticesListed?: boolean
  /**
   * Whether lib/useConditions.ts has settled that this phone holds no copy
   * of conditions/notices.json for a planned hike, for a reason a connection
   * can change (its `clubNoticesMissing`). With a hike planned and the file
   * absent, the legend row and the top of today's list then say so, in the
   * words the maintainer chose (option A of the poll of 2026-10-09); the
   * list itself is today's. Counts for nothing once the file is here, or
   * with nothing planned.
   */
  clubNoticesMissing?: boolean
  /**
   * conditions/hazard_areas.json (decision 84), read whatever is planned,
   * or null when it has not reached this phone. Decision 67's areas draw
   * from it, or from `clubNotices` when that file is the newer of the two
   * or this one is missing (lib/noticeSelection.ts's `hazardView`), so a
   * phone with no hike planned still draws them and none draws twice.
   */
  hazardFile?: { items: readonly TrailNotice[]; generatedAt: Date } | null
  /** The hiker's long-hike plans (lib/trips.ts). */
  trips?: readonly Trip[]
  /** The hiker's day hikes (lib/dayHikes.ts). */
  dayHikes?: readonly DayHike[]
  /** The trail graph this phone holds, or null: what routes a day hike and
   *  what decision 67's areas are checked against beside the A.T. */
  graph?: TrailGraphIndex | null
  /** ATC's club sections (lib/clubSections.ts): which club maintains each
   *  A.T. mile, for a long hike's clubs. */
  clubSections?: ClubSections
}

const NO_TRIPS: readonly Trip[] = []
const NO_DAY_HIKES: readonly DayHike[] = []

export function useNoticesPanel({
  updates,
  orgNotices,
  reviewedAt,
  stewards,
  trailIndex,
  bbox,
  now,
  clubNotices = null,
  clubNoticesGeneratedAt = null,
  clubNoticesListed = false,
  clubNoticesMissing = false,
  hazardFile = null,
  trips = NO_TRIPS,
  dayHikes = NO_DAY_HIKES,
  graph = null,
  clubSections = EMPTY_CLUB_SECTIONS,
}: NoticesInput): NoticesPanel {
  const [selectedBandId, setSelectedBandId] = useState<string | null>(null)
  /** The tapped hazard area, by notice id (#1805). */
  const [selectedHazardId, setSelectedHazardId] = useState<string | null>(null)
  /**
   * Whether the full list of notices is open.
   *
   * Separate from `selectedBandId` rather than a third state of it. The two
   * answer different questions - "which one did they tap" and "did they ask to
   * read all of them" - and a hiker who opens the list, taps a band behind it
   * and closes that sheet should find the list still where they left it.
   */
  const [noticesOpen, setNoticesOpen] = useState(false)
  /**
   * The newest edit the hiker has already silenced on this phone, PER
   * ORGANIZATION - lib/notices.ts's watermarks, read once at mount and written
   * back every time silencing happens.
   *
   * A version counter rather than the dates themselves. The dates live in
   * localStorage and `readNoticeSilence` is the only reader; holding a copy
   * here would mean keeping two truths in step for no gain, while a counter
   * that changes on every write is exactly enough to re-run the memo below.
   *
   * ONE KEY PER ORGANIZATION IS THE POINT. There was one shared key until
   * #1083, so a hiker dismissing ATC's banner would have silenced NYNJTC's too
   * - for notices they had never been shown. A watermark records what somebody
   * has SEEN, and nobody sees one organization's notices by dismissing
   * another's.
   */
  const [silenceVersion, setSilenceVersion] = useState(0)

  /**
   * The ATC's notices as bands, through exactly the same geometry.
   *
   * `atcBandCandidates` adapts each update into the shared `Closure` shape and
   * `closureBands` does the rest, so an ATC update inherits `trailSlice`'s
   * centerline placement and `isBroadAdvisory`'s length ceiling without either
   * being reimplemented - which is what #461 means by the geometry path
   * needing no new code, and what keeps ATC's 398-mile Helene advisory from
   * painting a fifth of the trail (#462).
   *
   * The candidate filter is where the two differ: only ATC categories that
   * mean the trail itself is obstructed become a band, because barrier tape
   * says "go around" and a notice about a closed car park does not. The rest
   * keep the banner, exactly as an over-long advisory does.
   */
  const bandsOnMap = useMemo(() => {
    if (trailIndex === null) return []
    return closureBands(atcBandCandidates(updates), trailIndex)
  }, [updates, trailIndex])

  /**
   * The same notices that name one mile rather than a stretch, as dots.
   *
   * Not filtered by `obstructsTheTrail`, unlike the bands. A dot makes no
   * claim about passability - it says the ATC has posted something here - so a
   * bear warning and a closed shelter both belong on the map, and neither is
   * the barrier a band would have made them.
   */
  const pointsOnMap = useMemo(() => {
    if (trailIndex === null) return []
    return atcUpdatePoints(atcPointNotices(updates), trailIndex)
  }, [updates, trailIndex])

  /** The tapped update, resolved from the band id the map reported. */
  const selectedUpdate = useMemo(() => {
    if (selectedBandId === null) return null
    return atcUpdateForBandId(updates, selectedBandId)
  }, [updates, selectedBandId])

  /**
   * Which notices the canvas is ACTUALLY drawing, by band id.
   *
   * Read off the two collections above rather than re-derived from the
   * updates, and that is the whole point of computing it here. The filters
   * (`atcBandCandidates`, `atcPointNotices`) say what this build INTENDS to
   * draw; `closureBands` and `atcUpdatePoints` then drop anything whose mile
   * falls outside this build's centerline, which no predicate over an
   * `AtcUpdate` can know. AtcNoticeList tells a hiker which notices have no
   * mark to look for, and it can only be honest about that from the truth.
   */
  const drawnIds = useMemo(
    () =>
      new Set<string>([
        ...bandsOnMap.map((band) => band.id),
        ...pointsOnMap.map((point) => point.id),
      ]),
    [bandsOnMap, pointsOnMap],
  )

  /**
   * Every notice the app holds, from every publisher, in one list.
   *
   * ATC's rows are adapted rather than the other way round, because ATC's
   * artifact is the older one: `pipeline/export_atc_updates.py` still writes
   * `atc_id` and two mile columns, while `export_nynjtc_alerts.py` already
   * writes the publisher-agnostic row features/ORG_NOTICES.md §2 specifies.
   *
   * ATC FIRST, deliberately. The order here is the order the banner names
   * organizations in, and the A.T. is the trail this app is holding.
   */
  const legacyNotices = useMemo<TrailNotice[]>(
    () => [...updates.map(atcUpdateAsNotice), ...orgNotices],
    [updates, orgNotices],
  )

  /**
   * Decision 66's panel (#1805): each hike planned in the next 7 days and
   * the notices that touch it, or why there is none. Only with
   * conditions/notices.json, or with the bucket serving it and nothing
   * planned; otherwise the panel stays today's.
   *
   * Keyed on the calendar day rather than the clock, so a minute's tick does
   * not re-run the geometry: the window only moves at midnight.
   */
  /**
   * The rule and the geometry (lib/noticeSelection.ts), imported when the
   * panel first becomes decision 66's and not before: the launch budget's
   * reason, which that module's header gives. Until it has loaded, such a
   * phone shows the planned-hike row with nothing counted yet,
   * never today's list of everything - which would flash the old panel for a
   * moment on every launch.
   */
  const [selection, setSelection] = useState<NoticeSelection | null>(loadedSelection)

  const hikePlanned = anyHikePlanned(trips, dayHikes)
  /** Whether the panel is decision 66's: conditions/notices.json is on the
   *  phone, whether or not its rule has finished loading - or the bucket
   *  serves it and nothing is planned, so decision 77 downloaded nothing. */
  const clubMode = clubNotices !== null || (clubNoticesListed && !hikePlanned)
  /** Whether today's list is shown to a hiker with a hike planned whose
   *  notices this phone does not hold, and has to say so first. */
  const plannedMissing = clubNotices === null && hikePlanned && clubNoticesMissing

  // Also for the hazard areas' own file alone (decision 84): a phone with
  // nothing planned and no notices.json still draws them. An import that
  // fails (a stale precache, no signal) is asked for again when the next
  // notices or hazard file lands: App holds this hook for the app's life.
  const wantsSelection = clubMode || hazardFile !== null
  useEffect(() => {
    if (!wantsSelection || selection !== null) return
    let live = true
    void import('../lib/noticeSelection').then(
      (module) => {
        loadedSelection = module
        if (live) setSelection(module)
      },
      () => undefined,
    )
    return () => {
      live = false
    }
  }, [wantsSelection, selection, clubNotices, hazardFile])

  const today = localDay(now)
  const view = useMemo(
    () =>
      !clubMode || selection === null
        ? null
        : selection.plannedView({
            notices: clubNotices ?? [],
            trips,
            dayHikes,
            today,
            trailIndex,
            graph,
            routing: ROUTING,
            clubSections,
            stewards,
          }),
    [
      clubMode,
      clubNotices,
      selection,
      trips,
      dayHikes,
      today,
      trailIndex,
      graph,
      clubSections,
      stewards,
    ],
  )
  const planned = view?.planned ?? null

  /**
   * Decision 67's areas a trail on this phone runs through (#1805), drawn
   * under the trail, from conditions/hazard_areas.json or notices.json,
   * whichever lib/noticeSelection.ts's `hazardView` takes (decision 84); an
   * area no held trail meets is not drawn (lib/hazardAreas.ts).
   */
  const hazards = useMemo(
    () =>
      selection === null
        ? null
        : selection.hazardView(
            clubNotices,
            clubNoticesGeneratedAt,
            hazardFile,
            trailIndex,
            graph,
          ),
    [clubNotices, clubNoticesGeneratedAt, hazardFile, selection, trailIndex, graph],
  )
  const hazardAreas = hazards?.areas ?? NO_HAZARD_AREAS
  const hazardAdvisoriesAt = hazards?.advisoriesAt ?? noAdvisories

  const selectedHazard = useMemo(
    () =>
      selectedHazardId === null
        ? null
        : (hazardAreas.find((area) => area.notice.notice_id === selectedHazardId)
            ?.notice ?? null),
    [hazardAreas, selectedHazardId],
  )

  /**
   * What the "new notices" dot counts and opening the list silences. With
   * the planned-hike panel that is exactly what the panel shows, which is
   * what #1155 — Opening the notices list silences notices it did not show
   * asked of the old list: a hiker is never told of news the list will not
   * show them, nor silenced on it.
   */
  const allNotices = useMemo<TrailNotice[]>(
    () => (!clubMode ? legacyNotices : (view?.shown ?? [])),
    [clubMode, view, legacyNotices],
  )

  /**
   * What the bottom "new notices" banner has to say, or null (#687).
   *
   * Independent of every filter above - `atcBandCandidates`, `atcPointNotices`
   * and the lane functions all decide what belongs on the MAP or in the
   * header's one line, and none of that is "has an organization posted
   * something recently". A notice the map cannot place and the header will
   * never mention (behind the hiker, over the band ceiling, or `unplaced`
   * altogether) is still new, and still worth this banner - chrome/
   * NoticeList.tsx is the same argument for the full list.
   *
   * ONE BANNER ACROSS ORGANIZATIONS rather than one each. features/
   * ORG_NOTICES.md §5 calls the banner "a scarce surface rather than a record"
   * and §9 leaves open "how many notice sources the banner can carry before it
   * stops being a warning and becomes a feed". A second banner is more chrome
   * this screen doesn't have room for, so the count merges and the list keeps
   * every row.
   */
  const newNotices = useMemo(
    // silenceVersion is not read inside - it is the dependency that re-runs
    // this after a dismissal writes new watermarks. See its declaration.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    () =>
      view === null
        ? newNoticesSince(allNotices, now, readNoticeSilence)
        : view.newSince(now, readNoticeSilence),
    [allNotices, now, silenceVersion, view],
  )

  const silenceNotices = useCallback(() => {
    if (newNotices === null) return
    // One dismissal, N watermarks: what a hiker dismisses is what they were
    // shown, and they were shown a count that spans organizations.
    silenceNewNotices(newNotices)
    setSilenceVersion((version) => version + 1)
  }, [newNotices])

  const openNotices = useCallback(() => {
    setNoticesOpen(true)
    // Opening the full list is a hiker having looked - and since 2026-09-10
    // the only way to silence, the banner's own dismiss having gone with the
    // banner (MapScreen.tsx's `newNoticeCount`) - see silenceNotices above.
    //
    // THAT PREMISE STOPPED HOLDING WHEN THE LIST BECAME SCOPED, and this is
    // written down rather than fixed here because the fix is a product call
    // nobody has made. `silenceNotices` writes a watermark over `allNotices`,
    // while `NoticeList` renders `scopedNotices(...)` - so a notice edited 30
    // hours ago, outside the stretch on screen, not drawn and not inside the
    // 24-hour always-shown window is counted by the banner, HIDDEN behind
    // "Show N more", and silenced by this call. The hiker is told there is
    // news, opens the list, is not shown that notice, and is never told again.
    //
    // Two things make it worse rather than better than it sounds. The
    // watermark is per organization and per newest edit, so silencing one
    // unseen notice silences every older one from that org. And `extent` is
    // deliberately null until `noticesOpen` is true, so even computing the
    // shown set here would see "nothing scoped" and silence everything
    // anyway - the honest fix has to silence on what the list ACTUALLY
    // rendered, which means the list reporting it, which is a change to a
    // safety surface and not a cleanup.
    //
    // Filed as #1155 — Opening the notices list silences notices it did not
    // show, which carries the reproduction and the two questions that have to
    // be answered first. Until one is, this errs toward
    // silencing too much, which is the wrong direction for a surface that
    // carries closures: "NEVER silently dropped" is lib/notices.ts's own rule
    // for the list and this call is the hole in it.
    silenceNotices()
  }, [silenceNotices])

  /**
   * When each organization's notices were last checked by a person, as the
   * list needs it.
   *
   * Present-with-a-value, present-with-null and ABSENT are three different
   * claims and the list renders three different sentences - see
   * NoticeListProps.reviewedAt. ATC's key is always present because somebody
   * does review that file; NYNJTC's is never added, because nobody reviews
   * theirs and saying "we cannot tell when" would be a softer lie than the
   * truth.
   */
  const reviewedBySource = useMemo(
    () => new Map<string, Date | null>([[ATC_SOURCE_KEY, reviewedAt]]),
    [reviewedAt],
  )

  /**
   * The stretch of trail on screen, or null with no centerline and null when
   * the viewport holds no trail at all. Both scope nothing, which is the
   * conservative direction: showing every notice is what this screen did
   * before the rule existed.
   *
   * ONLY WHILE THE LIST IS OPEN, and that guard is load-bearing rather than
   * tidy. `viewportMiles` walks the centerline's latitude buckets and `bbox`
   * changes on every pan and zoom, so computing this unconditionally would
   * make every map movement pay for a screen almost nobody has open. Measured
   * here rather than reasoned about: without the guard, App.mapOverlays.test's
   * first case went from passing to timing out at 5s on two runs in three.
   *
   * The list is the only reader, so a closed list needs no answer.
   */
  const extent = useMemo(
    () => (!noticesOpen || trailIndex === null ? null : viewportMiles(trailIndex, bbox)),
    [noticesOpen, trailIndex, bbox],
  )

  const mapScreen = useMemo<NoticesMapProps>(
    () => ({
      atcUpdates: bandsOnMap,
      atcUpdatePoints: pointsOnMap,
      onSelectAtcUpdate: setSelectedBandId,
      atcUpdateSheet:
        selectedUpdate === null ? null : (
          <OrgNoticeSheet
            update={selectedUpdate}
            reviewedAt={reviewedAt}
            stewards={stewards}
            onClose={() => setSelectedBandId(null)}
          />
        ),
      noticeCount: allNotices.length,
      onOpenNotices: openNotices,
      newNoticeCount: newNotices?.count ?? 0,
      newNoticeLabel:
        newNotices === null ? undefined : newNoticeLabel(newNotices, stewards),
      // The maintainer's words for a planned hike's missing notices (option
      // A of the poll of 2026-10-09): set, the legend shows the row however
      // few notices the phone holds, so a first run with no signal still
      // reaches the sentence saying why.
      noticeRowLabel: plannedMissing
        ? 'Notices for your planned hikes: not on this phone yet'
        : !clubMode
          ? undefined
          : allNotices.length === 0
            ? 'Notices for your planned hikes'
            : `Notices for your planned hikes (${allNotices.length})`,
      hazardAreas,
      onSelectHazardArea: setSelectedHazardId,
      hazardAreaSheet:
        selectedHazard === null ? null : (
          <HazardAreaSheet
            notice={selectedHazard}
            stewards={stewards}
            onClose={() => setSelectedHazardId(null)}
          />
        ),
      noticeList: !noticesOpen ? null : clubMode ? (
        planned === null ? null : (
          <PlannedNoticeList
            planned={planned}
            stewards={stewards}
            generatedAt={clubNoticesGeneratedAt}
            onClose={() => setNoticesOpen(false)}
          />
        )
      ) : (
        <NoticeList
          notices={allNotices}
          drawnIds={drawnIds}
          reviewedAt={reviewedBySource}
          stewards={stewards}
          extent={extent}
          now={now}
          plannedNoticesMissing={plannedMissing}
          onClose={() => setNoticesOpen(false)}
        />
      ),
    }),
    [
      bandsOnMap,
      pointsOnMap,
      selectedUpdate,
      reviewedAt,
      reviewedBySource,
      stewards,
      extent,
      now,
      allNotices,
      openNotices,
      newNotices,
      noticesOpen,
      drawnIds,
      planned,
      clubMode,
      plannedMissing,
      hazardAreas,
      selectedHazard,
      clubNoticesGeneratedAt,
    ],
  )

  return {
    mapScreen,
    sheetOpen: selectedBandId !== null || selectedHazard !== null,
    hazardAreas,
    hazardAdvisoriesAt,
  }
}
