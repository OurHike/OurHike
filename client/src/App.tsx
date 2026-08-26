// The app shell: what screen is showing, and where its data comes from.
//
// There is no router. Every screen is reached from the tab bar or from a flow
// that owns its own back-out, so URLs would be a second navigation model to
// keep in sync with the first for no gain a hiker would notice - and the
// service worker precaches one document either way.
//
// Two tabs, Trail and More (chrome/tabs.ts). Downloads was a third until
// 2026-08-05 and is now a window this file opens over whichever of them is
// showing - see screens/DownloadsDialog.tsx for why, and `downloadsWindow`
// below for what goes in it.
//
// Sign-in reaches the reporting flow through stepAfterSaving() (lib/
// contributionFlow.ts), and only ever after the report is already in the
// outbox. That ordering is the promise the flow exists to keep: someone asked
// to authenticate on a ridge with one bar can decline, or simply fail, and
// still have what they wrote.
//
// This used to be deliberately unwired, on the grounds that provider buttons
// which cannot authenticate would break exactly that promise. They can now -
// there is a real Supabase project (features/AUTHENTICATION.md), and Supabase
// Auth is what a hiker signs in to, not this project's own backend.
//
// Queued reports now send too (#231): useOutboxSync below flushes the outbox
// once there is both a connection and an account. Saving is still what the
// flow GUARANTEES, and that ordering has not moved - sending is what happens
// afterwards, if it can, and a build with no VITE_API_BASE_URL simply never
// gets that far.
//
// Which providers appear is a build-time answer (lib/supabase.ts's
// ENABLED_PROVIDERS), because a button whose credentials do not exist yet
// reaches an error page rather than an account.
//
// Identity - trail name and reporter type - is still not collected here.
// stepAfterSaving() reports when it is wanted and there is no screen for it,
// so that step ends the flow the way it already ended, with the report
// queued.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MapScreen } from './chrome/MapScreen'
import type { PoiDetail } from './chrome/PoiCard'
import { TabBar } from './chrome/TabBar'
import { ErrorBoundary, ScreenFailed } from './chrome/ErrorBoundary'
import type { TabId } from './chrome/tabs'
import { Downloads } from './screens/Downloads'
import {
  hikingDetailOptions,
  noDetailOptions,
  rasterDetailOptions,
} from './screens/DetailPicker'
import { DownloadsDialog } from './screens/DownloadsDialog'
import { More, type StuckReport } from './screens/More'
import { Moderation } from './screens/Moderation'
import { InstallPrompt } from './screens/InstallPrompt'
import {
  ENTRY_CARD_MAX_VIEWPORT_FRACTION,
  Onboarding,
  type OnboardingResult,
} from './screens/Onboarding'
import { ClosureForm, type ClosureFormSubmission } from './screens/ClosureForm'
import { closureDraft } from './lib/closureDraft'
import { disputeFor } from './lib/disputes'
import { useWorkdayPanel } from './chrome/workdayPanel'
import type { DisputePoint } from './map/disputeLayers'
import { ReportForm, type ReportFormSubmission } from './screens/ReportForm'
import { ReportTypePicker, type ReportTypeId } from './screens/ReportTypePicker'
import { CORRIDOR_ARCHIVE_URL } from './map/protocol'
import { DATA_CONFIGURED } from './lib/config'
import {
  forgetPreferencesSync,
  loadPreferences,
  savePreferences,
} from './lib/preferences'
import { usePreferencesSync } from './lib/usePreferencesSync'
import { useTripsSync } from './lib/useTripsSync'
import {
  setSyncEnabled,
  summariseSync,
  syncEnabled,
  type SyncStatus,
} from './lib/syncStatus'
import { tripSyncState } from './lib/tripSyncState'
import { preferencesSyncState } from './lib/preferences'
import { forgetTripSync } from './lib/tripsSync'
import { forgetDayHikeSync } from './lib/dayHikesSync'
import { RemovedPoiCard } from './chrome/RemovedPoiCard'
import { resolvePoiId, tombstoneFor } from './lib/poiIdentity'
import { buildAccountArchive, downloadArchive } from './lib/accountArchive'
import { deleteAccount, type DeletionReceipt } from './lib/api'
import {
  DEFAULT_PREFERENCES,
  type BackgroundSource,
  type HikingDetailLevel,
  type ReporterType,
  type UserPreferences,
} from './lib/userPreferences'
import {
  detailLevelForZoom,
  getDownloadDetail,
  type DetailLevel,
} from './lib/downloadDetail'
import { useArchiveDownloads } from './lib/useArchiveDownload'
import { useDrawnPoiCounts } from './lib/useDrawnPoiCounts'
import { useAvailableBytes } from './lib/useAvailableBytes'
import { useArchiveZooms } from './lib/useArchiveZooms'
import { archiveCoversZoom } from './lib/archiveCoverage'
import { HEALTHY, type LiveSourceHealth, type SourceReport } from './map/liveSourceHealth'
import {
  backgroundProblem,
  forgetPackages,
  rememberNotDrawing,
  sheetNotDrawing,
} from './lib/backgroundHealth'
import {
  BASEMAP_PACKAGE,
  CORRIDOR_BACKGROUND_PACKAGE,
  HIKING_SHEET,
  offeredPackages,
  offeredSheets,
  offlineBackgroundAvailable,
  packageArtifactKey,
  packageDownloadUrl,
  packageSizeBytes,
  sheetSizeBytes,
  USGS_SHEET,
  withdrawnSheets,
  type BackgroundSheet,
} from './lib/packages'
import { combineBackgroundStatus } from './lib/backgroundStatus'
import { activeDownload } from './lib/downloadActivity'
import { useClock } from './lib/useClock'
import { useOnline } from './lib/useOnline'
import { useDataSaver } from './lib/useDataSaver'
import { backgroundOverride, effectiveBackground } from './lib/dataSaver'
import { useFinePointer } from './lib/useFinePointer'
import { useTheme } from './lib/useTheme'
import { useDesktop } from './lib/useDesktop'
import { useInstallPrompt } from './lib/useInstallPrompt'
import { useAppUpdate, UPDATE_CHECK_MS } from './lib/useAppUpdate'
import { readCamera, writeCamera } from './lib/cameraMemory'
import { useGeolocation } from './lib/useGeolocation'
import { positionLine } from './lib/positionLine'
import { naismithMinutes } from './lib/naismith'
import {
  locateOnTrail,
  mileOnTrail,
  trailPointAtMile,
  trailSlice,
} from './lib/trailPosition'
import type { StoredPoi } from './lib/trailData'
import { useTrailData } from './lib/useTrailData'
import { ribbonWindow } from './lib/elevationProfile'
import { ribbonLanes, ribbonView } from './lib/ribbonView'
import { viewportMiles } from './lib/viewportMiles'
import { anchoredClientMile, anchoredMile, type MileAnchor } from './lib/route'
import { type ViaStop } from './lib/dayPlanner'
import type { ChartStretch } from './chrome/ElevationChart'
import { type RouteStopChoice } from './chrome/RouteStopPicker'
import { useRouteBuilderPanel, type ViaStopLike } from './chrome/routeBuilderPanel'
import {
  insertZeroAfter,
  removeDay,
  togglePinned,
  toggleResupply,
  type HikePlan,
  type PlanTarget,
  type RestRhythm,
} from './lib/plan'
import {
  EMPTY_STORE,
  addGroup,
  addHike,
  addToGroup,
  addTrip,
  loadTrips,
  openTrip,
  openTripOf,
  removeFromGroup,
  removeGroup,
  removeTrip,
  renameGroup,
  renameTrip,
  saveTrips,
  updateTrip,
  type TripStore,
} from './lib/trips'
import { hikeFromTrips, hikeOfTrip, recordedPlan } from './lib/hikes'
import { GroupScreen } from './screens/GroupScreen'
import { TripList } from './screens/TripList'
import { PlanScreen } from './screens/Plan'
import { PlanKindSheet } from './chrome/PlanKindSheet'
import { DayHikePickBar } from './chrome/DayHikePickBar'
import {
  canCloseLoop,
  draftStatus,
  EMPTY_DRAFT,
  loopDraft,
  tapAt,
  undoTap,
  type DayHikeDraft,
} from './lib/dayHikeDraft'
import { routeGeometry, type TrailGraphIndex } from './lib/trailGraph'
import {
  attachTrailGraphElevation,
  attachTrailGraphGeometry,
  fetchTrailGraphElevation,
  fetchTrailGraphGeometry,
} from './lib/trailGraphData'
import { orgLabelFrom } from './lib/stewards'
import {
  EMPTY_DAY_HIKES,
  loadDayHikes,
  saveDayHikes,
  type DayHike,
  type DayHikeStore,
} from './lib/dayHikes'
import { useDayHikesSync } from './lib/useDayHikesSync'
import { dayHikeBailOuts, resolveDayHike } from './lib/dayHikeCard'
import { dayHikesNearHere } from './lib/dayHikeShelf'
import { DayHikeCard } from './screens/DayHikeCard'
import { DayHikesHere } from './chrome/DayHikesHere'
import type { PlanMode } from './screens/PlanHome'
import type { DayHikeDrawing } from './map/dayHikeLayers'
import { PlanTargetSheet } from './screens/PlanTargetSheet'
import { startTracking, trackDirection, type DirectionTracker } from './lib/hikeDirection'
import { beginContribution, stepAfterSaving } from './lib/contributionFlow'
import { useModerator } from './lib/useModerator'
import { hasStatedReporterType, signReportAs } from './lib/reporterIdentity'
import { IdentitySetup } from './screens/IdentitySetup'
import { SignInPrompt, type AuthProvider } from './screens/SignInPrompt'
import { EmailSignIn } from './screens/EmailSignIn'
import { ENABLED_PROVIDERS } from './lib/supabase'
import { TRAILS } from './lib/trails'
import { useAccount } from './lib/useAuth'
import {
  sendMagicLink,
  signInWithEmail,
  signInWithProvider,
  signOut,
  signUpWithEmail,
} from './lib/auth'
import {
  enqueueAppFailure,
  enqueueClosure,
  listQueued,
  removeQueued,
  retryQueued,
  type AppFailureDraft,
  type FlushResult,
} from './lib/outbox'
import { AppFailureReport } from './screens/AppFailureReport'
import { useOutboxSync, syncOutbox } from './lib/outboxSync'
import { conditionsAgeLabel, worstOf } from './lib/conditionState'
import { useConditions } from './lib/useConditions'
import { enqueueFieldNote } from './lib/outbox'
import type { FieldNoteDraft, NoteSummary } from './lib/fieldNotes'
import { rollupByPoi } from './lib/noteRollup'
import { pinConditionFor, stalenessPresentation } from './lib/stalenessDisplay'
import { stalenessTier } from './lib/staleness'
import {
  advanceToday,
  localDay,
  passedPlaces,
  readPassedToday,
  writePassedToday,
  type PassedToday,
} from './lib/passedToday'
import { NOTE_SCOPED_TYPES } from './lib/fieldNotes'
import { Volunteer } from './screens/Volunteer'
import { VolunteerHours } from './screens/VolunteerHours'
import { enqueueVolunteerHours } from './lib/outbox'
import { fetchMyVolunteerHours } from './lib/api'
import type { VolunteerHoursDraft, VolunteerHoursSummary } from './lib/volunteerHours'
import type { FieldNoteContext, ReportAnchor } from './chrome/FieldNoteSection'
import { closureBanner, closureLanes, type RankedClosure } from './lib/closureBanner'
import { projectClosures } from './lib/closureProjection'
import { atcUpdateBanner, atcUpdateLanes, type RankedAtcUpdate } from './lib/atcUpdates'
import { useAtcNoticesPanel } from './chrome/atcNoticesPanel'
import {
  useWaypointFiltersPanel,
  type UpdatePreferences,
} from './chrome/waypointFiltersPanel'
import { POI_PIN_MIN_ZOOM } from './map/poiLayers'
import { useTappedLinePanel } from './chrome/tappedLinePanel'
import { readStoredPace, writeStoredPace, type PaceProfile } from './lib/pace'
import {
  MAX_FIX_GAP_MILES,
  readWalked,
  recordStep,
  writeWalked,
  type MileRange,
} from './lib/walkedMiles'
import { clubRunAtMile, clubTimeline } from './lib/clubSections'
import { HikePicker } from './screens/HikePicker'
import {
  clearPlannedHike,
  hikeSummary,
  loadPlannedHike,
  plannedDirection,
  savePlannedHike,
  type PlannedHike,
} from './lib/plannedHike'
import { closureBands } from './map/closureLayers'
import { corridorWithHighlights, EMPTY_CORRIDOR } from './map/corridorLayers'
import {
  isSeriousWarning,
  placeAll,
  routeBannerText,
  warningsOnRoute,
} from './lib/seriousWarnings'
import type { BoundingBox, MapPoint } from './lib/legendContents'
import type { SearchablePoi } from './lib/searchPoi'
import { siteRoster } from './map/poiSites'
import './App.css'
// Last, and entirely inside media queries - see the file header. Nothing in it
// can match a phone, which is how the WEBSITE.md §8 constraint is kept
// structurally rather than by review.
import './desktop.css'

// OurHike hikes one trail today - see lib/trails.ts for why this is a lookup
// and not just a string.
const TRAIL_NAME = TRAILS.AT.name
const TRAIL_LOGO = TRAILS.AT.logo

// Sync and export are rendered and do nothing: what they need is the backend,
// which is Phase 2 (ROADMAP.md). They share one placeholder rather than
// getting an identical empty arrow each.
//
// Sign in and sign out used to be here too. They are real now - Supabase Auth
// is a separate service from this project's backend, so signing in never
// needed that backend to exist, only a project to sign in to.
// The whole trail, Springer to Katahdin, as the opening view. Taken from the
// published topo archive's own header bounds, so it frames exactly the ground
// the map actually covers rather than a hand-typed guess.
//
// Opening on the entire corridor rather than a point on it because before there
// is a GPS fix the app genuinely does not know where the hiker is, and Harpers
// Ferry - the previous default - is a confident-looking answer to that question
// that is wrong for everyone not standing in Harpers Ferry. A view of the whole
// trail says "somewhere on this" honestly.
//
// And it stays that view. The first fix used to zoom the camera to it, which
// takes the map away from anyone reading it - planning a resupply, looking at a
// stretch two states north - for no reason beyond the phone having worked out
// where they are. The camera is the hiker's from the first frame; the locate
// control (map/mapChrome.ts) is how they ask to be taken to themselves, and it
// is a tap away in the thumb zone.
const CORRIDOR_BOUNDS: [[number, number], [number, number]] = [
  [-84.73, 34.2],
  [-68.3, 46.34],
]

const EMPTY_BBOX: BoundingBox = { west: 0, south: 0, east: 0, north: 0 }

/** Where a search result lands. Only ever zooms IN: someone already at 16
 *  looking at a spring does not want to be pulled back out to see a shelter. */
const SEARCH_RESULT_ZOOM = 14

interface Camera {
  center: [number, number]
  zoom: number
}

/**
 * One stored POI as the waypoint card takes it.
 *
 * Built from both arrays on purpose: the POI itself carries the geometry and the
 * provenance, and `searchablePois` has already paid for the `locateOnTrail()`
 * call that places it on the trail, so the mile in the card is the same number
 * search puts on the same POI rather than a second computation that could
 * disagree with it.
 *
 * One function because there are two callers and the tapped waypoint is in both
 * of them: it is the card's subject, and it is also the anchor chip of its own
 * site's strip (#526). Two spots computing this shape is two spots that can put
 * two different miles on one card.
 */
function cardDetail(poi: StoredPoi, searchable: readonly SearchablePoi[]): PoiDetail {
  return { ...poi, mile: searchable.find((candidate) => candidate.id === poi.id)?.mile }
}

type ReportingState =
  | null
  | { step: 'pick'; anchor?: ReportAnchor }
  | { step: 'form'; type: ReportTypeId; anchor?: ReportAnchor }

// Sign-in is its own flow rather than another step of the reporting one,
// because it is reachable from two places that want different things back:
// finishing a contribution, and the account row in Settings. Conflating them
// would mean the Settings path inheriting the report flow's copy, which
// promises that a report is already saved - true in one case and not the
// other.
type AuthFlowState = null | { screen: 'choose' | 'email'; afterReport: boolean }

/** A saved day hike's default name: its longest leg's trail, or a plain
 *  fallback. The hiker renames it; this is what the row says until they do. */
function dayHikeName(route: {
  legs: Array<{ name: string | null; miles: number }>
}): string {
  const longest = [...route.legs].sort((a, b) => b.miles - a.miles)[0]
  return longest?.name !== null && longest?.name !== undefined
    ? `${longest.name} day hike`
    : 'Day hike'
}

function App() {
  // Two pieces of state rather than one nullable, because null only ever meant
  // "not read off the phone yet" - and saying that with a boolean keeps the
  // preferences themselves always a whole object. That removes an unreachable
  // null check from every reader below, including one inside updatePreferences
  // that no caller could ever satisfy: nothing renders, and so nothing can
  // change a preference, until the load has finished.
  //
  // Starting from DEFAULT_PREFERENCES rather than a placeholder is not a
  // behaviour change: the two values anything read before the load completes
  // (location_permission_requested, max_background_zoom) were already falling
  // back to exactly these defaults.
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_PREFERENCES)
  const [preferencesLoaded, setPreferencesLoaded] = useState(false)
  const [activeTab, setActiveTab] = useState<TabId>('trail')
  // The download window (screens/DownloadsDialog.tsx), which replaced the tab
  // it used to be. Held here rather than on either screen because it opens
  // over both of them, from the one background picker they share.
  const [downloadsOpen, setDownloadsOpen] = useState(false)
  /**
   * Which background sources are known NOT to be drawing - remembered here
   * rather than on the map screen, because the downloads window outlives that
   * screen (#334) and is where a hiker acts on it.
   *
   * Remembered, not mirrored, and lib/backgroundHealth.ts's
   * `rememberNotDrawing` owns the whole rule: a source that has drawn clears
   * itself, a source that errored without ever drawing sets itself, and a
   * source that has done neither leaves this alone. That last clause is what
   * carries a real failure across the teardown a trip to the More tab costs,
   * and the first is what stops a transient error condemning a good archive
   * for the rest of the session - #352, which is the shape this state should
   * have had from the start.
   */
  const [notDrawing, setNotDrawing] = useState<LiveSourceHealth>(HEALTHY)
  const [legendOpen, setLegendOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  // The tapped pin, held as an id rather than as the POI itself. Everything the
  // card shows is derived below, so a POI that changes underneath - a fresh
  // download, or the hiker deleting the one they had - is described correctly
  // or closes itself, instead of the card going on showing a copy of data the
  // app no longer holds.
  const [selectedPoiId, setSelectedPoiId] = useState<string | null>(null)
  const [bbox, setBbox] = useState<BoundingBox>(EMPTY_BBOX)
  /**
   * The hiker has driven the map themselves, so the elevation ribbon follows
   * the viewport rather than their GPS fix (#910 review, "always in sync").
   *
   * A gesture sets it; the ribbon's own "Back to me" clears it. Deliberately
   * NOT cleared by a new fix arriving: a hiker who panned to next week's
   * section does not want the ribbon yanked back every few seconds by the
   * watch, which is the whole reason this is a latch rather than a comparison
   * of the fix against the viewport.
   */
  const [mapTaken, setMapTaken] = useState(false)

  const [reporting, setReporting] = useState<ReportingState>(null)
  /**
   * Whether the app-failure report is open (#848).
   *
   * Its own flag rather than a step on `ReportingState`, because it is not a
   * report: nothing about it is drawn on the map, nothing moderates it, and
   * it does not go through the sign-in and reporter-type questions
   * `handleSubmitReport` asks. Sharing the state would have meant sharing
   * those.
   */
  const [reportingFailure, setReportingFailure] = useState(false)
  /**
   * Whether the closure form is open (#832).
   *
   * Its own flag rather than a step on `ReportingState`, for the reason the
   * flag above has one: a closure is not a report type. It has its own
   * table, two ends instead of a fix, and no `reporter_type` - so putting it
   * on `ReportingState` would have meant widening a union that describes
   * something else, and answering the reporter-type question for a record
   * with nowhere to put the answer.
   */
  const [reportingClosure, setReportingClosure] = useState(false)
  const [authFlow, setAuthFlow] = useState<AuthFlowState>(null)
  /**
   * The day hike being built (#978, frame `1j`), or null when that builder
   * is closed. A SIBLING of the route draft, not a third arm on it:
   * DayHikeDraft is already the whole state and carries its own undo, so it
   * needs neither `history` nor the `withStops` funnel. Exclusivity matters
   * because the derived values below (the chart selection, the ribbon) key
   * off `routeBuilder.draftLive` - `routeDraft` itself lives in
   * chrome/routeBuilderPanel.tsx since #991 - and would answer for the A.T.
   * while somebody built in Harriman.
   *
   * EXCLUSIVITY RUNS BOTH WAYS AGAIN (#997). It was written as though it
   * did and implemented in one direction: `openDayHike` cleared the route
   * draft, nothing cleared the day hike, so a route builder opened over one
   * held a draft that neither the map tap nor `routeSheet` would show,
   * because both answer for the day hike first. `sweepForBuilder` clears it
   * now, and every route-builder door passes through there.
   */
  const [dayHike, setDayHike] = useState<DayHikeDraft | null>(null)
  /** Frame `1i`'s door - "What are you planning?" - over the Plan tab. */
  const [planKindOpen, setPlanKindOpen] = useState(false)
  /**
   * The graph with its edge vertices attached, once the lazy geometry fetch
   * lands - or null while only the routing half is here. Taps and routing
   * work on the bare index meanwhile (chord projection, stated in
   * lib/trailGraph.ts); the drawn highlight waits for real vertices, because
   * a chord across a switchback is a picture of a trail that does not exist.
   */
  const [dayHikeIndex, setDayHikeIndex] = useState<TrailGraphIndex | null>(null)
  /** The SAVED day hikes (#976) - loaded once, written through saveDayHikes,
   *  and fed to the account sync exactly as tripStore is. */
  const [dayHikeStore, setDayHikeStore] = useState<DayHikeStore>(EMPTY_DAY_HIKES)
  /** Frame `1l` as a review (#980): Done builds the record and the card holds
   *  it; only "Save this day hike" commits it to the store. The draft stays
   *  alive underneath, so "Back to the map" is a real return, not a rebuild. */
  const [dayHikeReview, setDayHikeReview] = useState<DayHike | null>(null)
  /**
   * A date set on the review card, before there is a record to keep it on.
   *
   * Its own state because the review record is NOT durable: "Back to the
   * map" clears it (the draft underneath is what survives), and pressing
   * Done again rebuilds the record from the draft. A date typed before that
   * round trip lived only on the discarded record, so it vanished with no
   * warning - on the one field the list, the split and the trailhead door
   * all read. Cleared with the draft, never outliving it.
   */
  const [dayHikeDraftDate, setDayHikeDraftDate] = useState<string | null>(null)
  /**
   * Which home the Plan tab shows (#1008): the day-hike room or the trips
   * room. Null until the hiker (or the trailhead door) picks one, so the
   * default can be derived from stores that load after mount - a useState
   * initialiser here would run against empty stores and freeze the wrong
   * answer.
   */
  const [planMode, setPlanMode] = useState<PlanMode | null>(null)
  /**
   * Whether the Plan tab shows the full day-hike list (frame D7).
   *
   * Held here rather than inside PlanScreen because the map's trailhead door
   * offers "All your day hikes ›" from another tab entirely, and PlanScreen
   * is rebuilt on every tab switch - state local to it is always false on
   * arrival, so that control would have landed one screen short of what it
   * named.
   *
   * Lifting it bought that door its destination and took on the cost every
   * lifted flag has: it now OUTLIVES the tab switch that used to clear it,
   * and `Plan.tsx` reads it before it reads the mode. `enterTripsRoom` below
   * is what pays that cost back.
   */
  const [dayListOpen, setDayListOpen] = useState(false)
  /**
   * Landing in the trips room, from every door that puts a hiker there.
   *
   * ONE FUNCTION RATHER THAN A MIRROR LINE IN EACH DOOR, for the reason
   * `sweepForBuilder` gives about its own: a rule copied into four openers is
   * the same fix today and the same bug at the fifth. Three things have to be
   * true to actually arrive, and each of them was a separate defect when the
   * doors said only the first:
   *
   * - `planMode` is 'trips'. The mode is sticky by design - it is the hiker's
   *   own pick - so a door that makes a TRIP the subject has to say so, or a
   *   hiker who once tapped the chip lands on a room their new trip is not in.
   * - The day-hike list is closed. `Plan.tsx` tests `dayListOpen` BEFORE the
   *   mode, so a list left open from an earlier visit wins over the trips room
   *   outright: the trip that was just laid out never appears, and the screen
   *   that greets the hiker is the day-hike list wearing the day band.
   * - Any open day-hike card is put away. It docks over up to 85% of the
   *   screen, and a day-hike surface floating over the trips room is the exact
   *   "which mode am I in" confusion this split exists to end.
   *
   * The close is a read-modify-write that marks the sync ledger, so it is
   * guarded on there being something to close - inside, against the loaded
   * store, which is what keeps this callback stable and lets the doors below
   * list it as a dependency.
   */
  const enterTripsRoom = useCallback(() => {
    setPlanMode('trips')
    setDayListOpen(false)
    void loadDayHikes().then((store) => {
      if (store.openId === null) return
      const next = { ...store, openId: null }
      setDayHikeStore(next)
      return saveDayHikes(next)
    })
  }, [])
  /**
   * The trailhead door (frame D8), put away - by the hikes it was offering
   * rather than outright.
   *
   * A plain boolean would be wrong for the case that actually happens: drive
   * to a second trailhead in one session and the door for a DIFFERENT hike
   * would stay silenced by a dismissal aimed at the first. Holding the ids
   * means "no thanks" applies to what was asked, and a hike the hiker has
   * not said no to still gets to ask once.
   */
  const [hikesHereDismissed, setHikesHereDismissed] = useState<readonly string[]>([])
  /**
   * The desktop chart's own settled selection - a measurement, nothing more
   * - read only while no route draft is open (PR #885 review). With a draft
   * open the chart's selection IS the draft's stretch, derived below, so
   * the two instruments cannot disagree; this one is cleared when a draft
   * opens so a stale measurement does not resurface when it closes.
   */
  const [freeChartStretch, setFreeChartStretch] = useState<ChartStretch | null>(null)
  /** Which way the chart's free measurement reads. The route's direction,
   *  when a draft is open, comes from the draft itself. */
  const [freeChartSouth, setFreeChartSouth] = useState(false)
  /**
   * Every trip the hiker has kept, and which one the Plan tab is showing
   * (#787). This replaced a single `HikePlan` state: the plan below is
   * DERIVED from the open trip, so every handler that edits a plan keeps
   * working unchanged and there is exactly one place a trip's plan lives.
   */
  const [tripStore, setTripStore] = useState<TripStore>(EMPTY_STORE)
  /** Whether the trip switcher is showing over the Plan tab. */
  const [tripsOpen, setTripsOpen] = useState(false)
  /**
   * The target sheet's subject: which route to lay days over - its stops in
   * walk order, destinations included - or null while the sheet is closed.
   * Opened from the route builder's "Break into days" and from the
   * timeline's target button - the same sheet, so the two entrances cannot
   * drift apart.
   */
  const [targetRequest, setTargetRequest] = useState<null | {
    route: ViaStop[]
    initialTarget?: PlanTarget
    initialStartDate?: string
    initialRhythm?: RestRhythm
    /** Set when the sheet was opened over an existing trip, so laying out
     *  re-lays that trip rather than keeping a second copy of it (#787). */
    tripId?: string
  }>(null)
  /**
   * Whether the identity screen is showing (#233).
   *
   * `stepAfterSaving()` has reported this step since the flow was designed and
   * there was no screen to show for it, so the branch did nothing and every
   * report went out signed `thru`. screens/IdentitySetup.tsx was built and
   * tested for exactly this and imported by nothing.
   */
  const [collectingIdentity, setCollectingIdentity] = useState(false)
  /**
   * Whether this session has already asked. Skipping is allowed and does NOT
   * write a reporter type - inventing one is the bug being closed - so
   * without this a hiker who skips is asked again on their very next report.
   * Once per session is the balance: never nagging, and never silently
   * deciding they are a day hiker because they closed a screen.
   */
  const identityAsked = useRef(false)
  // Null until a stored session is read, and null forever if nobody signs in.
  // Signed out is the state every screen already works in, so this gates
  // nothing.
  const account = useAccount()
  const [queuedCount, setQueuedCount] = useState(0)
  const [stuckReports, setStuckReports] = useState<StuckReport[]>([])

  // What the hiker SAID they are doing, as against what the GPS works out
  // below. Null is the ordinary state rather than an incomplete setup (#335).
  const [hike, setHike] = useState<PlannedHike | null>(null)
  const [pickingHike, setPickingHike] = useState(false)
  // Whether the moderation queue is open, and whether it may be. The role is
  // read once per sign-in (lib/useModerator.ts) and decides only whether the
  // entry point exists - the backend gates every call regardless (#235).
  const [moderating, setModerating] = useState(false)
  const isModerator = useModerator(account !== null)

  const [direction, setDirection] = useState<DirectionTracker | null>(null)
  // The live map is state rather than a ref because effects have to run when
  // it appears. It appears more than once: the map screen unmounts whenever
  // another tab is showing, so every trip through More builds a new one. The
  // download no longer costs one - that is a window over this screen, not a
  // tab beside it.
  const [map, setMap] = useState<MapLibreMap | null>(null)
  // Where the camera was left, so a rebuilt map opens where the hiker left it
  // instead of snapping back to the whole corridor.
  //
  // Seeded from session storage (#311). A service-worker update restarts the
  // page, and while that now waits for a moment nobody is watching
  // (lib/useAppUpdate.ts), the restart still forgets the view - so a hiker who
  // put the phone away reading a junction took it out again looking at the
  // whole trail. Null on a fresh tab, which is the corridor, deliberately.
  const [camera, setCamera] = useState<Camera | null>(() => readCamera())

  const now = useClock()
  const online = useOnline()

  // What the trail is like right now - closures, reports, the ATC's own
  // notices - and when something last reached the server. See
  // lib/useConditions.ts for the two tiers behind the first two.
  const {
    closures,
    reports,
    notes,
    disputes,
    closureState,
    reportState,
    atcUpdates,
    atcReviewedAt,
    drought,
    droughtWeek,
    workProjects,
    workProjectsGeneratedAt,
    lastSyncedAt,
    markSynced,
  } = useConditions(online)

  /**
   * This phone's own just-written notes, echoed locally (FIELD_NOTES.md).
   *
   * A tapped "dry" freshens the pin for THIS hiker immediately - the tap is
   * the newest observation there is, and waiting for it to round-trip
   * through a backend that may be days of walking away would render their
   * own answer as somebody else's staleness. Session-lived on purpose: the
   * durable copy is the outbox item, and once it flushes the ordinary
   * live/baseline reads carry it back like anyone else's.
   */
  const [localNotes, setLocalNotes] = useState<readonly NoteSummary[]>([])

  // The working set the roll-up reads: what the wire said, with this phone's
  // own unsent notes in front. Null still means "we could not ask" - a local
  // echo is real data, so it upgrades null to a list of one.
  const allNotes = useMemo(() => {
    if (notes === null) return localNotes.length === 0 ? null : localNotes
    return localNotes.length === 0 ? notes : [...localNotes, ...notes]
  }, [notes, localNotes])

  // Per-place roll-ups (FIELD_NOTES.md §3), recomputed at render time from
  // whatever notes are held - never stored, the derive-don't-duplicate rule.
  const noteRollups = useMemo(() => rollupByPoi(allNotes ?? [], now), [allNotes, now])

  // Which ring each waypoint wears (#256's consumer, #759's nudge). The
  // policy lives in lib/stalenessDisplay.ts; this just binds it to the
  // roll-up above, and MapView hands it to the source rebuild.
  const pinCondition = useMemo(
    () => pinConditionFor((poiId) => noteRollups.get(poiId)?.lastConfirmedAt ?? null),
    [noteRollups],
  )

  /**
   * First run: the three entry steps are showing over the map (#721).
   *
   * Read here rather than beside the render below, because it decides what the
   * shell does as well as what it draws: the steps are a card over the map, and
   * the only thing behind them is the trail line, so the POIs are held back
   * until they are gone (#857, and see useTrailData's TrailDataOptions).
   *
   * True until the phone's own preferences have been read, which is the same
   * answer a first run gives and the safe one for a returning hiker - nothing
   * renders during that window either way (`preferencesLoaded` below), and the
   * read that follows fills the map in.
   */
  const entering = !preferences.onboarding_completed

  // The centerline, the POIs, the elevation profile, and the fetch that puts
  // them on the phone - see lib/useTrailData.ts. Everything below reads these;
  // nothing else writes them.
  const {
    trailIndex,
    pois,
    spurs,
    elevation,
    clubSections,
    stewards,
    highlights,
    retiredPois,
    trailsUrl,
    overviewTrailsUrl,
    nearbyTrailsUrl,
    graphIndex,
    haveTrailLines,
    error: dataError,
    ensure: ensureTrailData,
  } = useTrailData(online, { centerlineOnly: entering })

  /**
   * Closure miles, re-read against the release this phone is holding (#674).
   *
   * One funnel, before anything reads a closure's miles, because there is no
   * such thing as half the app using the projected pair. `lib/closureBanner`
   * decides whether a hiker is standing inside a closed stretch and
   * `closureBands` draws where it is; those two disagreeing about where a
   * closure starts is exactly the failure mode a shared source removes.
   *
   * A no-op on every closure authored before #832's form, which is still
   * most of them: with no geometry `projectClosures` returns the array it
   * was given and these memos do not re-run. Closures filed from this app
   * now carry their two points, so the projection has started doing real
   * work on real rows — and `lib/closureProjection.ts`'s `@unvalidated`
   * tolerance, which had nothing to measure while nothing wrote geometry,
   * now has data coming that could settle it.
   */
  const placedClosures = useMemo(
    () =>
      closures === null || trailIndex === null
        ? closures
        : projectClosures(closures, trailIndex),
    [closures, trailIndex],
  )

  /**
   * The map's source observations, folded in; its withdrawals, dropped.
   *
   * A withdrawal is a map saying it no longer speaks for anything, which is
   * not evidence about the archive on the phone - dropping it here is what
   * lets the failure survive the walk to the More tab. Everything else is
   * `rememberNotDrawing`'s decision. Stable across renders, as MapViewProps
   * requires of this handler.
   */
  const recordSourceHealth = useCallback((report: SourceReport) => {
    if (report.withdrawn) return
    setNotDrawing((remembered) => rememberNotDrawing(remembered, report))
  }, [])
  // Read here rather than inside the map, so the settings screen and the canvas
  // are answering from the same value - a row that says "live" over a map
  // drawing the archive would be the exact mismatch this feature exists to
  // avoid.
  const saveData = useDataSaver()
  // Decides whether the map gets zoom buttons - see lib/useFinePointer.ts.
  // Read here rather than inside MapView so the whole map screen answers from
  // one value.
  const finePointer = useFinePointer()
  // Resolves 'auto' against the OS, writes `data-theme` for the stylesheets,
  // and hands back what actually got drawn - which the map needs as a prop,
  // because a WebGL canvas cannot read a CSS variable (map/style.ts's
  // attachMapAppearance).
  //
  // Called above the `preferencesLoaded` gate below, like every other hook
  // here: it runs on DEFAULT_PREFERENCES for the tick before the phone's own
  // answer lands, and that default is 'auto' - the same thing main.tsx already
  // stamped on the document before React started.
  /** The hiker's own pace (#880). Read from its OWN key rather than from
   *  preferences, which is a sync target - PERSONALIZED_PACE.md §4 keeps a
   *  pace profile off the wire even once an account exists. State rather than
   *  a bare read so the Pace screen can change it and every estimate follows. */
  /** The hiker's own pace (#880). Its own local key rather than a preference:
   *  PERSONALIZED_PACE.md §4 keeps a pace profile off the wire even once an
   *  account exists, and `UserPreferences` is a whole-blob sync target. */
  const [pace, setPace] = useState<PaceProfile>(() => readStoredPace())

  const handleChangePace = useCallback((next: PaceProfile) => {
    // Written through readPace's clamp, so nothing out of range is stored even
    // if a control is ever wired to a wider range than the estimator allows.
    writeStoredPace(next)
    setPace(readStoredPace())
  }, [])

  const resolvedTheme = useTheme(preferences.theme)
  // Whether this is the big-screen layout - and, for the download, whether the
  // machine is one that goes up a mountain. See handleOnboardingComplete.
  const isDesktop = useDesktop()
  const install = useInstallPrompt()
  useEffect(() => {
    void loadPreferences().then(
      (stored) => {
        setPreferences(stored)
        setPreferencesLoaded(true)
      },
      // A storage read that rejects - private browsing, an evicted database -
      // must not keep the gate below closed: `preferencesLoaded` false renders
      // NOTHING, and a rejection here left the app a permanently blank page
      // with the map a tick away the whole time. Defaults are the honest
      // fallback; the preferences another session stored are unreachable
      // either way.
      () => setPreferencesLoaded(true),
    )
  }, [])

  // Nothing waits on this. A hike changes what the banners can say and
  // nothing about whether the app renders, so unlike preferences it gets no
  // `loaded` gate: a hiker who set one two states ago has their banners a tick
  // later, and one who never did is already in the state this resolves to.
  // A rejected read leaves it null for the same reason - null is what "no
  // hike" already means everywhere.
  useEffect(() => {
    void loadPlannedHike().then(setHike, () => setHike(null))
  }, [])

  // The trips, on the same contract: a rejected or invalid read leaves an
  // empty store, which is what "no plans" already means everywhere. This is
  // also where a phone upgrading from the single-plan build has its plan
  // migrated - see lib/trips.ts.
  useEffect(() => {
    void loadTrips().then(setTripStore, () => setTripStore(EMPTY_STORE))
  }, [])

  // Two facts, not one number. A report waiting for signal resolves itself;
  // a report the server refused never will, and showing them as one count is
  // what let a phone with a wrong clock say "waiting to send" forever (#243).
  const refreshOutbox = useCallback(async () => {
    const queue = await listQueued()
    setQueuedCount(queue.filter((item) => item.failure === undefined).length)
    setStuckReports(
      queue
        .filter((item) => item.failure !== undefined)
        .map((item) => ({ id: item.id, reason: item.failure!.reason })),
    )
  }, [])

  // Re-read after either thing that can add to the queue closes. `reporting`
  // is the condition report; `reportingFailure` is the app-failure report
  // (#848), and leaving it out would have left the "waiting to send" count
  // stale for exactly the report a hiker most wants to see acknowledged.
  useEffect(() => {
    void refreshOutbox()
  }, [reporting, reportingFailure, refreshOutbox])

  // Sending is the one thing that waits for signal. Everything else a hiker
  // does - writing the report, reading the map - already happened offline.
  //
  // Keyed on having an account as well as a connection because a report can be
  // written before signing in: the flow saves first and asks about identity
  // afterwards (lib/contributionFlow.ts), so the queue can hold reports that
  // no token could have sent yet. Signing in later is a second, equally valid
  // moment to try.
  const handleSynced = useCallback(
    ({ sent, stuck }: FlushResult) => {
      // Only on a real delivery. Stamping the clock after a flush that sent
      // nothing would make "synced just now" mean "we had signal", which is
      // the opposite of what the strip is for (lib/syncAge.ts).
      if (sent > 0) markSynced()
      // Refreshed even when nothing was sent, because a flush that only
      // discovered a refusal still changed what the hiker needs to see -
      // that is the whole point of the stuck state.
      if (sent > 0 || stuck > 0) void refreshOutbox()
    },
    [refreshOutbox, markSynced],
  )

  // Written through to the phone before the state moves, so a hiker who sets
  // a hike and immediately kills the app has it on the next launch. The same
  // order updatePreferences uses, and for the same reason.
  const handleSaveHike = useCallback(async (next: PlannedHike) => {
    await savePlannedHike(next)
    setHike(next)
    setPickingHike(false)
  }, [])

  const handleClearHike = useCallback(async () => {
    await clearPlannedHike()
    setHike(null)
    setPickingHike(false)
  }, [])

  useOutboxSync(online && account !== null, handleSynced)

  /**
   * Clears the refusal and sends, now - the escape hatch for a cause the
   * hiker has just fixed.
   *
   * The flush is the part that was missing (#266). Clearing the failure on
   * its own only relabels the report: the sole flush trigger is
   * useOutboxSync's effect, whose deps are both referentially stable, and
   * outboxSync is "deliberately not on a timer" - so on a steady connection
   * nothing ran, and the screen swapped "could not be sent" plus its reason
   * for "waiting to send" at the exact moment nothing was going to try. That
   * is the lie this whole feature exists to remove, told by the button meant
   * to fix it.
   *
   * refreshOutbox runs in `finally` rather than after the flush, because the
   * failure has been cleared either way - a retry with no signal has to leave
   * the report reading as waiting, not as refused.
   */
  const handleRetryReport = useCallback(
    (id: string) => {
      void retryQueued(id)
        .then(() => syncOutbox())
        .then((result) => {
          if (result !== null && result.sent > 0) markSynced()
        })
        .finally(() => void refreshOutbox())
    },
    [refreshOutbox, markSynced],
  )

  const handleDiscardReport = useCallback(
    (id: string) => {
      void removeQueued(id).then(refreshOutbox)
    },
    [refreshOutbox],
  )

  const locationAllowed = preferences.location_permission_requested
  const gps = useGeolocation(locationAllowed)

  const detailLevel: DetailLevel = detailLevelForZoom(preferences.max_background_zoom)
  // The hiking sheet's own level (#276) - a separate dial from the USGS
  // raster's tier above, because the two sheets' choices must never share one.
  const hikingLevel = preferences.hiking_detail_level
  // Feet or metres, for every screen and the canvas alike (#619, lib/units.ts).
  // Read once here and handed down, the same way the resolved theme is: two
  // reads of one preference is how a banner in miles ends up over a map in
  // kilometres.
  const units = preferences.unit_system

  // Every sheet this build can hold bytes for (#237), and every archive
  // behind them (#192). One flat download store underneath - the per-sheet
  // grouping is a fact about what a card shows, not about how bytes are held.
  //
  // A WITHDRAWN sheet is in here, and has to be. It is not on offer any more
  // (lib/packages.ts, #855), but a phone that took it before the withdrawal
  // is still holding it, and every one of those bytes is reachable only
  // through a registered request: the status the card reads, the header
  // `useArchiveZooms` asks for, and the delete. Registering one starts
  // nothing on its own - `useArchiveDownloads` transfers only when something
  // asks it to.
  const catalogSheets = useMemo(() => [...offeredSheets(), ...withdrawnSheets()], [])
  const downloadRequests = useMemo(
    () =>
      catalogSheets
        .flatMap((sheet) => offeredPackages(sheet))
        .map((pkg) => ({
          packageKey: pkg.idbKey,
          url: packageDownloadUrl(pkg, detailLevel, hikingLevel),
          artifactKey: packageArtifactKey(pkg, detailLevel, hikingLevel),
        })),
    [catalogSheets, detailLevel, hikingLevel],
  )
  const {
    statusFor: archiveStatusFor,
    errorFor: archiveErrorFor,
    statusesKnown: archivesRead,
    start: startPackage,
    startAll: startPackages,
    remove: removePackage,
    persistence: archivePersistence,
  } = useArchiveDownloads(downloadRequests)

  /**
   * The sheets that get a card in the download window - which is not the same
   * list as the one above (#855).
   *
   * An offered sheet is always here. A WITHDRAWN one is here only while this
   * phone has bytes of it, and that is the whole rule: a hiker who downloaded
   * the USGS raster before it was withdrawn still has up to 1.2 GB of it, and
   * the card is the only place to get that space back. A hiker who never took
   * it is never shown a map they can no longer have.
   *
   * BYTES, not "finished". A transfer stopped at 90% is several hundred
   * megabytes in IndexedDB and the card is where its Resume lives; dropping
   * it at `downloaded` would leave those bytes with no screen that mentions
   * them. The two states that mean this phone holds nothing are excluded, and
   * they are opposite in kind - `not-downloaded` never started, `evicted` was
   * reclaimed by the OS (#190) - but the answer to "is there anything here to
   * finish or free" is no for both.
   *
   * The card needs no notion of withdrawal to render correctly, and is not
   * given one: DownloadCard offers Download in `not-downloaded` and Delete in
   * `downloaded`, so a sheet that reaches this list arrives already showing
   * the only buttons that still make sense.
   *
   * Downstream of `archiveStatusFor` on purpose, which is why the catalog
   * above is a separate memo: the requests have to be registered before there
   * is any status to filter on.
   */
  const backgroundSheets = useMemo(
    () =>
      catalogSheets.filter(
        (sheet) =>
          sheet.withdrawn !== true ||
          offeredPackages(sheet).some((pkg) => {
            const { state } = archiveStatusFor(pkg.idbKey)
            return state !== 'not-downloaded' && state !== 'evicted'
          }),
      ),
    [catalogSheets, archiveStatusFor],
  )

  // What the phone can still hold, so a level it cannot is greyed where it is
  // chosen rather than refused after the tap (#555). Re-read after a delete
  // below: freeing space is the app's own printed remedy, and #554 measured
  // that the browser's accounting may never notice on its own.
  const { bytes: availableBytes, refresh: refreshAvailableBytes } = useAvailableBytes()

  /** One sheet as one state, however many archives are behind it. */
  const sheetStatus = useCallback(
    (sheet: BackgroundSheet) =>
      combineBackgroundStatus(
        offeredPackages(sheet).map((pkg) => ({
          status: archiveStatusFor(pkg.idbKey),
          sizeBytes: packageSizeBytes(pkg, detailLevel, hikingLevel),
        })),
      ),
    [archiveStatusFor, detailLevel, hikingLevel],
  )

  /** The first of this sheet's archives with something to report. One card
   *  per sheet, so one message - and the archives are not something a hiker
   *  was told about, so naming which of them failed would explain nothing.
   *  Per sheet rather than global, so one sheet's failure can never render
   *  on the other's card. */
  const sheetError = useCallback(
    (sheet: BackgroundSheet) =>
      offeredPackages(sheet)
        .map((pkg) => archiveErrorFor(pkg.idbKey))
        .find(Boolean) ?? null,
    [archiveErrorFor],
  )

  // Whether the corridor raster specifically is on the phone. Asked about
  // that archive rather than about the background as a whole, because it is
  // the archive the offline background is DRAWN from - archiveZooms reads its
  // header, and effectiveBackground decides against its presence.
  const archiveStatus = archiveStatusFor(CORRIDOR_BACKGROUND_PACKAGE.idbKey)

  // Whether there is a corridor on this phone at all. Only a FINISHED archive
  // counts: a partial one is bytes in IndexedDB that the PMTiles source cannot
  // read, so treating "downloading" or "failed" as downloaded would honour an
  // offline background against an archive that draws nothing - the exact state
  // effectiveBackground exists to keep a hiker out of.
  const archiveDownloaded = archiveStatus.state === 'downloaded'

  // Whether "downloaded only" is still a background anyone here can choose
  // (#855). Read from the catalog rather than worked out here, so this and
  // Settings' copy of the same picker cannot come to different answers - and
  // so it agrees by construction with the card `backgroundSheets` decides on
  // above, which is the same question about the same sheet.
  const offlineBackground = offlineBackgroundAvailable(archiveDownloaded)

  // Whether ANY sheet's archive is here - what words the DownloadsLink
  // ("choose" vs "change"). Distinct from archiveDownloaded since #237: the
  // hiking sheet downloading without the USGS raster is now a normal phone.
  const anySheetDownloaded = backgroundSheets.some((sheet) =>
    offeredPackages(sheet).some(
      (pkg) => archiveStatusFor(pkg.idbKey).state === 'downloaded',
    ),
  )

  /**
   * Which sheets are in the step BEFORE their transfer - fetching the trail
   * data that has to land first (`ensureTrailData`).
   *
   * State, and rendered, because it used to be neither. The canary is 12.3 MB
   * of trails.geojson, and until it finished nothing on the card changed at
   * all: the button a hiker had just pressed sat there unchanged, no status,
   * no figure, for as long as that took on their connection. The download had
   * genuinely started; the app simply had no way to say so, which is the same
   * complaint the footer bar exists to answer, one step earlier in the flow.
   *
   * Per sheet rather than one flag because the card that reports it is per
   * sheet - and the trail data being shared is exactly why two sheets tapped
   * together can both be in this step off one fetch.
   */
  const [preparingSheets, setPreparingSheets] = useState<readonly string[]>([])

  // What is arriving right now, across every sheet, for the link that says so
  // (lib/downloadActivity.ts). Decided here rather than on either screen for
  // the reason the transfer itself lives here: the download outlives the
  // window it was started from and has to be reportable from the map and from
  // Settings alike, which are never both mounted. Off the SHEET statuses the
  // cards already render, so the footer's figure and the card's cannot
  // disagree about the same download.
  const downloadActivity = activeDownload(
    backgroundSheets.map(sheetStatus),
    preparingSheets.length > 0,
  )

  // Whether the hiking sheet's TILES are on the phone - the basemap package
  // alone, not the sheet as a whole. The DEM beside it is the same sheet's
  // terrain, and a missing hillshade is not what makes a background fail to
  // draw. Read by the status strip to tell "your download is not drawing"
  // from "you have no download" (lib/backgroundHealth.ts, #314).
  const hikingSheetDownloaded =
    archiveStatusFor(BASEMAP_PACKAGE.idbKey).state === 'downloaded'

  // What the archive on this phone actually covers, read from its own header
  // rather than assumed from the pipeline's constants (#216). Null until a
  // finished archive exists to ask, and null again if it is deleted.
  const archiveZooms = useArchiveZooms(
    CORRIDOR_BACKGROUND_PACKAGE.idbKey,
    archiveDownloaded,
  )

  // A fix moves no camera - see CORRIDOR_BOUNDS. It is read for everything
  // else: the mile below, the direction of travel, the elevation ribbon.
  const fix = useMemo(() => {
    if (trailIndex === null || gps.status !== 'located') return null
    return locateOnTrail(trailIndex, gps.at)
  }, [trailIndex, gps])

  /**
   * Which miles this hiker has actually walked (#598's `visited`).
   *
   * The maintainer's rule, 2026-08-19: two fixes count as walking between them
   * when they are no more than half a mile apart. lib/walkedMiles.ts holds the
   * gate and the arithmetic; this is only the pair of fixes it needs.
   *
   * NOTHING IS UPLOADED, and that is the design rather than an omission.
   * features/EVENTING.md rule 2 forbids geography in the event pipe - "no
   * coordinates, no mile, no segment id, no POI id, no region" - and the rule
   * above needs none of it, because the phone is asking about its own fixes.
   * What is kept is the ANSWER (mile intervals, merged) and never the evidence:
   * no coordinates, no timestamps, no ordering, so what sits on the device
   * cannot be replayed into a route down the corridor the way a fix log can.
   *
   * A count ACROSS hikers - the popularity number `visited` was first posed as
   * - is a different feature and needs an explicit, dated decision about rule 2
   * before anybody builds it. This is not that, and does not become it.
   */
  const [walked, setWalked] = useState<MileRange[]>(() => readWalked())
  const previousWalkedMile = useRef<number | null>(null)

  // Today's slice of the same record (lib/passedToday.ts), for the Volunteer
  // tab's "places you passed today" - the one surface DATA_NUDGES.md calls
  // genuinely new (#759). Same fixes, same gate, one extra local date.
  const [passedToday, setPassedToday] = useState<PassedToday>(() =>
    readPassedToday(new Date()),
  )

  useEffect(() => {
    const mile = fix?.mile ?? null
    if (mile === null) return
    const previous = previousWalkedMile.current
    previousWalkedMile.current = mile
    // The gate lives in recordStep and is checked here too, so a refused pair
    // costs no render at all - `watchPosition` fires often, and a state update
    // per fix that changed nothing would re-run every memo on this screen.
    if (previous === null || Math.abs(mile - previous) > MAX_FIX_GAP_MILES) return
    setWalked((current) => recordStep(current, previous, mile))
    setPassedToday((current) => advanceToday(current, new Date(), previous, mile))
  }, [fix?.mile])

  // Persisted in its own effect rather than inside the updater above: React
  // may call a state updater twice, and a writer that runs twice is a writer
  // in the wrong place.
  useEffect(() => {
    writeWalked(walked)
  }, [walked])

  useEffect(() => {
    writePassedToday(passedToday)
  }, [passedToday])

  useEffect(() => {
    if (fix === null) return
    setDirection((previous) =>
      previous === null ? startTracking(fix.mile) : trackDirection(previous, fix.mile),
    )
  }, [fix])

  /**
   * Which way this hiker is walking, from whichever source knows.
   *
   * OBSERVATION WINS, and the plan fills the gap it leaves. `hikeDirection.ts`
   * waits for a quarter mile of movement before it will commit - deliberately,
   * so a GPS wandering under tree cover at a lunch stop does not flip the
   * header - and until then a declared hike is the only thing that can answer
   * the question at all. That quarter mile is exactly the stretch a hiker
   * leaving a trailhead walks with no banner (#335).
   *
   * The ordering is worth being deliberate about, because the two can
   * disagree: somebody who said NOBO and is measurably walking south is
   * either turned around or has changed their mind, and this app cannot tell
   * which. Trusting the plan over the observation would redefine "ahead" as
   * the way they are NOT going and warn about closures behind them, which is
   * the worse of the two failures. Telling them they are walking the wrong
   * way is the wrong-way alert's job (#93, #247), not this line's.
   */
  const heading =
    direction?.direction ?? (hike === null ? undefined : plannedDirection(hike))

  /**
   * The closure a hiker is about to walk into, in one line, or null.
   *
   * Needs a mile and a closure list; the direction goes down as whatever is
   * known, undefined included. "Ahead" is meaningless before the app knows
   * which way someone is walking - a guess would put a NOBO hiker's closure
   * behind them - but standing INSIDE a closure needs no direction at all,
   * and direction takes a quarter mile of walking to establish
   * (lib/hikeDirection.ts). Gating the whole banner on it kept the app
   * silent for exactly the first quarter mile of a closed section, which is
   * where the warning matters most. closureBanner.ts owns that split.
   */
  const { closureAhead, advisoryAhead } = useMemo(() => {
    if (fix === null) return { closureAhead: null, advisoryAhead: null }

    // Two sources compete for each line: OurHike's verified closures and the
    // ATC's own notices (#461). Nearest wins, which is the rule the two lane
    // functions already apply WITHIN their own list - "the closure two hundred
    // miles north is not the one that changes what they do next" - extended
    // across both rather than replaced by a precedence between the sources.
    // Neither deserves one: an ATC notice is authoritative about the trail they
    // maintain, and a verified closure was checked by a moderator, so ranking
    // them would be inventing a claim about which organisation is more right.
    // Which one is in front of the hiker is a fact, and it is the fact that
    // decides what they do next.
    //
    // The winner is then written in its OWN voice - "Trail closed 2.1 mi
    // ahead" for ours, "ATC · Closure 2.1 mi ahead · <their headline>" for
    // theirs. That is the whole of #461's requirement in the one place a
    // hiker reads without tapping anything.
    //
    // TWO LINES, NOT ONE (#485). A closure that is a stretch of trail and an
    // advisory that is a region answer different questions - "what do I do next"
    // against "what country am I in" - so they do not compete. Ranked together,
    // standing inside a 398-mile advisory scored 0 and buried the nine-mile
    // closure three miles ahead for 398 miles of walking. The rule is written
    // once per source (`closureLanes`, `atcUpdateLanes`) and the source tie is
    // broken here, the same way, for each lane.
    const closureLane = closureLanes(placedClosures ?? [], fix.mile, heading)
    const atcLane = atcUpdateLanes(atcUpdates, fix.mile, heading)

    // Whichever source the hiker reaches first, in that source's own voice.
    // `<=` keeps ours first on an exact tie, which is arbitrary and has to be
    // something; it matters only when both name the same mile.
    const pick = (
      closure: RankedClosure | null,
      atc: RankedAtcUpdate | null,
    ): string | null => {
      if (closure !== null && (atc === null || closure.distance <= atc.distance)) {
        return closureBanner(closure.closure, fix.mile, heading, units)
      }
      if (atc !== null) return atcUpdateBanner(atc.update, fix.mile, heading, units)
      return null
    }

    return {
      closureAhead: pick(closureLane.specific, atcLane.specific),
      advisoryAhead: pick(closureLane.broad, atcLane.broad),
    }
  }, [placedClosures, atcUpdates, fix, heading, units])

  /**
   * Serious warnings between here and the end of the trail, counted.
   *
   * Placing them is `placeAll`'s job (#244), which snaps lat/lon against this
   * same trail index where it can and falls back to the mile the reporting
   * phone recorded where it cannot - the case that used to be uncountable, a
   * report filed against a POI with no coordinates.
   *
   * `severity` filtering is `warningsOnRoute`'s job, so a report that a
   * moderator has not escalated cannot reach this line.
   */
  const warningsAhead = useMemo(() => {
    if (
      reports === null ||
      trailIndex === null ||
      fix === null ||
      heading === undefined
    ) {
      return null
    }

    const placed = placeAll(reports, trailIndex)

    // Where the ROUTE ends, which is the phrase the banner uses. A declared
    // hike answers it exactly; without one the terminus is as far as "ahead"
    // can honestly go, and "on your route" quietly means the two thousand
    // miles between here and Katahdin (#335).
    //
    // Clamped to the direction actually being walked. A hiker heading north
    // who declared a southbound hike would otherwise get a range running
    // backwards past them, and `warningsOnRoute` normalises it into a count of
    // everything BEHIND them - a banner about warnings they have already
    // passed. Falling back to the terminus in that case says less and says it
    // truthfully.
    const declaredEnd = hike === null ? null : hike.endMile
    const terminus = heading === 'NOBO' ? trailIndex.totalMiles : 0
    const routeEnd =
      declaredEnd !== null &&
      (heading === 'NOBO' ? declaredEnd >= fix.mile : declaredEnd <= fix.mile)
        ? declaredEnd
        : terminus

    return routeBannerText(
      warningsOnRoute(placed, { fromMile: fix.mile, toMile: routeEnd }).length,
    )
  }, [reports, trailIndex, fix, heading, hike])

  /**
   * The same closures on the canvas: a barred red band along each closed
   * stretch (lib/closureStyle.ts).
   *
   * Needs the centerline index and nothing else - no GPS fix, no direction.
   * That is the difference from `closureAhead` above and the reason they are
   * two memos rather than one: "ahead" is a claim about a hiker, and drawing
   * a closed stretch of trail is a claim about the trail. A closure should be
   * on the map from the moment it is known, including for someone who has not
   * started walking and has no direction yet.
   */
  const closureBandsOnMap = useMemo(() => {
    if (placedClosures === null || trailIndex === null) return []
    return closureBands(placedClosures, trailIndex)
  }, [placedClosures, trailIndex])

  /**
   * Who maintains which stretch, as the corridor view draws it (#598).
   *
   * Needs the centerline index for the same reason the closure bands do: the
   * published artifact carries mile ranges and no geometry, so `trailSlice`
   * is what turns "miles 1,013.4 to 1,015.2" into a line. Everything the map
   * draws from it stops at the seam - see map/corridorLayers.ts.
   *
   * Not gated on a GPS fix or on a hike, deliberately, in the same way the
   * closure bands are not: who looks after a stretch of trail is a fact about
   * the trail, and the corridor view is what somebody at a kitchen table is
   * looking at before they have either.
   */
  const corridorOnMap = useMemo(() => {
    if (trailIndex === null) return EMPTY_CORRIDOR
    return corridorWithHighlights(clubSections, highlights, trailIndex)
  }, [clubSections, highlights, trailIndex])

  /**
   * The ATC's notices: bands, dots, the tapped sheet, the full list and the
   * "new alerts" banner - chrome/atcNoticesPanel.tsx owns all of it (#327).
   *
   * What is left here is the header's one line, which is a different
   * question: `atcUpdateLanes` below ranks an ATC notice against a closure
   * for the single sentence a walking hiker gets, and that comparison is the
   * shell's precisely because neither feature can make it alone.
   */
  const atc = useAtcNoticesPanel({
    updates: atcUpdates,
    reviewedAt: atcReviewedAt,
    trailIndex,
    now,
  })

  /**
   * Serious warnings as points, straight from the report's own lat/lon.
   *
   * No `locateOnTrail` here, unlike `warningsAhead`, which needs a mile to
   * decide what is on the route. A pin goes where the report was written -
   * including the ones a few hundred feet off trail, which `locateOnTrail`
   * still places and which a hiker is better off seeing at their real
   * position than snapped onto the centerline.
   */
  const warningPins = useMemo(() => {
    if (reports === null) return []
    return reports.flatMap((report) => {
      if (!isSeriousWarning(report) || report.lat === null || report.lon === null) {
        return []
      }
      return [{ id: report.id, lon: report.lon, lat: report.lat }]
    })
  }, [reports])

  // Built from the POIs alone. The mile is added where the centerline index
  // exists and simply omitted where it does not - searching for a shelter by
  // name needs no geometry, and gating the whole list on the index meant a
  // missing one silently emptied search while 800-odd POIs sat in memory.
  //
  // `mileOnTrail` rather than `locateOnTrail` (#717). This memo wants the mile
  // and reads nothing else, and `locateOnTrail` pays for a second search over
  // the whole tread to answer a question about GPS fixes that a POI never
  // asks. Measured 2026-08-15 on x86 over the corridor's 2,837 POIs: 975 ms in
  // one synchronous memo, about half of it that discarded scan - and this runs
  // on the launch after the trail index lands, which is the same moment the
  // map is being built.
  const searchablePois: SearchablePoi[] = useMemo(
    () =>
      pois.map((poi) => ({
        id: poi.id,
        name: poi.name,
        type: poi.type,
        mile:
          trailIndex === null
            ? undefined
            : (mileOnTrail(trailIndex, { lon: poi.lon, lat: poi.lat }) ?? undefined),
      })),
    [pois, trailIndex],
  )

  // What the tapped pin's card says - see cardDetail for why it is assembled
  // from both arrays rather than from the POI alone.
  const selectedPoi: PoiDetail | null = useMemo(() => {
    if (selectedPoiId === null) return null
    const poi = pois.find((candidate) => candidate.id === selectedPoiId)
    if (poi === undefined) return null
    return cardDetail(poi, searchablePois)
  }, [selectedPoiId, pois, searchablePois])

  /**
   * The card for a selected waypoint that no longer exists (#831).
   *
   * features/POI_IDENTITY.md §4's fourth existence state, and what it replaces
   * is not an error message — it is nothing at all. `selectedPoi` above finds
   * no live POI for a retired id and hands the map screen null, so a hiker
   * whose photos are anchored to a water point the ATC dropped last September
   * taps it and the app appears to ignore them.
   *
   * ONLY REACHED WHEN THE LIVE LOOKUP FAILS, which is what makes this free on
   * every ordinary tap: a pin the map drew is a live row by construction, so
   * `selectedPoi` answers first and this memo returns null without touching
   * the tombstones.
   *
   * Resolved here rather than in the card because only the shell holds the
   * live waypoints, and the successor's NAME is what the card needs — "merged
   * into Rocky Run Shelters" is a sentence a hiker can act on where an id is
   * not. `resolvePoiId` is handed the live set as its predicate for the reason
   * lib/poiIdentity.ts gives: the tombstones alone cannot tell a live id from
   * one this project has never heard of, and those are different answers.
   *
   * NOTHING SELECTS A RETIRED ID YET, AND THAT IS WORTH SAYING OUT LOUD.
   *
   * Every route into `handleSelectPoi` today hands it an id that came from the
   * live waypoints: a map tap (the pins are built from `poi_*.geojson`, which
   * carries live rows by an invariant three consumers enforce), a search
   * result, and the passed-places list (derived by mile from those same
   * waypoints). So this memo returns null on every selection the app can
   * currently make, and the card below has never been drawn in anger.
   *
   * It is here rather than deferred because it is the half that has to exist
   * first. The anchors that will reach it are the ones #831 names — a hiker's
   * private photos and `PlanStop.poiId`, whose own comment says it is "kept so
   * a later feature can follow the reference" — and each of those is a
   * feature that cannot be built until there is somewhere for a followed
   * reference to land. Written down rather than left for a reader to
   * discover, per CLAUDE.md, and flagged in the pull request.
   */
  const removedPoi = useMemo(() => {
    if (selectedPoiId === null || selectedPoi !== null) return null
    const tombstone = tombstoneFor(retiredPois, selectedPoiId)
    if (tombstone === undefined) return null
    const successorId = resolvePoiId(retiredPois, selectedPoiId, (id) =>
      pois.some((candidate) => candidate.id === id),
    )
    const successor =
      successorId === null
        ? undefined
        : pois.find((candidate) => candidate.id === successorId)
    return { tombstone, successor }
  }, [selectedPoiId, selectedPoi, retiredPois, pois])

  /**
   * Every part of the tapped waypoint's site, anchor first, for the card's chip
   * strip (#526). Empty for a POI that is in no site, which is most of them and
   * all of them on a phone that downloaded before #523.
   *
   * Built here rather than in the card for the same reason `selectedPoi` is: the
   * card is handed one waypoint, and the shell is the only layer holding the
   * others. It goes through the same `cardDetail` as the anchor above, which is
   * what stops one card showing two different miles for the same POI - the
   * anchor appears in both of these.
   */
  const selectedSite: readonly PoiDetail[] = useMemo(() => {
    if (selectedPoiId === null) return []
    return siteRoster(pois, selectedPoiId).map((part) => cardDetail(part, searchablePois))
  }, [selectedPoiId, pois, searchablePois])

  /**
   * The corridor read end to end, in mile order.
   *
   * Memoised because it is rebuilt from the published artifact and read on
   * every tap - and because `clubTimeline` sorts, which is not free to redo
   * on each render of a screen a hiker pans around.
   */
  const clubRuns = useMemo(() => clubTimeline(clubSections), [clubSections])

  /**
   * Below the seam, a tap on the trail asks a different question.
   *
   * "Who maintains this?" is what the map is ABOUT down here
   * (features/CORRIDOR_VIEW.md), so the club sheet takes the tap and the
   * blaze sheet stands down; above the seam the hiker is navigating and the
   * line's own facts are what they asked for. One tap path either way - this
   * chooses which sentences it produces, and never shows both.
   *
   * `camera === null` IS below the seam: that is the opening view, fitted to
   * CORRIDOR_BOUNDS, which lands near z4.9 on a phone.
   */
  const belowSeam = camera === null || camera.zoom < POI_PIN_MIN_ZOOM

  /**
   * Who maintains the trail the hiker is looking at, for the legend (#598).
   *
   * From the camera's centre rather than from a GPS fix, deliberately: this
   * answers "who looks after what is on my screen", which is a question
   * somebody planning at a kitchen table has as much as somebody standing on
   * the trail - and it is the only version of the question that has an answer
   * before the phone knows where it is.
   *
   * Omitted below the seam, where the map is already drawing the attribution
   * and the legend would be repeating the screen back at the hiker.
   *
   * The FULL name, where features/CORRIDOR_VIEW.md's mock-up showed the
   * acronym. Above the seam nothing is tappable to expand "PATC" into anything
   * - the club sections are not drawn up here - so an acronym would be a
   * four-letter word with no way to find out what it means.
   */
  const maintainerLine: string | null = useMemo(() => {
    if (belowSeam || camera === null || trailIndex === null) return null
    const mile = mileOnTrail(trailIndex, {
      lon: camera.center[0],
      lat: camera.center[1],
    })
    if (mile === null) return null
    const run = clubRunAtMile(clubRuns, mile)
    if (run === null) return null
    // The unattributed miles get a sentence of their own rather than silence:
    // 38.5 miles of the trail are like this, and "we do not know" is the
    // answer OurHikeValues.md #4 asks for over a blank.
    return run.club === null
      ? 'Maintaining club not recorded along here.'
      : `Maintained by the ${run.club.name}.`
  }, [belowSeam, camera, trailIndex, clubRuns])

  /** Closes the legend. A named callback rather than an inline arrow because
   *  the tapped-line feature holds it too - any tap that opens a sheet puts
   *  the legend away - and a new function each render would have re-made that
   *  feature's handlers on every one. */
  const closeLegend = useCallback(() => setLegendOpen(false), [])

  /**
   * A tap on the trail, on a maintaining club's stretch, or on a highlight
   * mark, and the one sheet that answers it - chrome/tappedLinePanel.tsx owns
   * all three (#327).
   *
   * `belowSeam` and `clubRuns` are passed in rather than derived there
   * because `maintainerLine` above reads the same two answers, and two
   * derivations of one question is the disagreement this file's own comments
   * keep refusing elsewhere.
   */
  const line = useTappedLinePanel({
    spurs,
    pois,
    units,
    trailName: TRAIL_NAME,
    pace,
    walked,
    trailIndex,
    belowSeam,
    clubSections,
    clubRuns,
    highlights,
    elevation,
    onCloseLegend: closeLegend,
  })

  /**
   * The disputed places, joined to where they are (#876).
   *
   * The join is the shell's because neither half can do it: the verdict comes
   * from the server, which holds no coordinates (it has no POI table at all -
   * `poi_id` is a soft reference into a published artifact), and the POI
   * export knows nothing about notes. This is the one place both are in hand.
   *
   * A dispute whose POI this phone does not hold draws nothing rather than
   * drawing somewhere - the same rule the rest of this file keeps about 0,0.
   */
  const disputedPoints: DisputePoint[] = useMemo(() => {
    if (disputes === null || disputes.length === 0) return []
    const disputed = new Set(disputes.map((dispute) => dispute.poi_id))
    return pois
      .filter((poi) => disputed.has(poi.id))
      .map((poi) => ({ poiId: poi.id, lon: poi.lon, lat: poi.lat }))
  }, [disputes, pois])

  const viewportPoints: MapPoint[] = useMemo(
    () =>
      pois.map((poi) => ({
        id: poi.id,
        type: poi.type,
        lat: poi.lat,
        lon: poi.lon,
        confidence: poi.confidence,
        // Carried through so the map can draw one pin per site (#524). Spread
        // conditionally rather than assigned as possibly-undefined, so a POI
        // from a pre-#523 download has no site keys at all rather than keys
        // holding undefined - which `composeSites` reads identically, but which
        // would show up in a snapshot as a claim about a site.
        ...(poi.siteId !== undefined ? { siteId: poi.siteId } : {}),
        ...(poi.siteRole !== undefined ? { siteRole: poi.siteRole } : {}),
      })),
    [pois],
  )

  // The elevation ribbon and the waypoint lanes (WIREFRAMES.md §1.3, §1.4),
  // which need three things at once: a published profile, a GPS fix, and that
  // fix landing on the centerline. Any one missing and both are omitted rather
  // than stubbed - see MapScreenProps. An empty ribbon reads as "nothing ahead
  // of you", which is a far worse claim than not drawing one.
  //
  // Both share a single window, computed once here. They are one visual block
  // in the wireframe and a hiker reads a pin as sitting under the part of the
  // profile it belongs to, which is only true while the two agree about what
  // stretch of trail they are showing. That also means no profile costs the
  // lanes as well - the only way to have no profile is a data release built
  // before pipeline/export_elevation.py existed, and a second window source for
  // that case would be a code path nothing exercises.
  //
  // features/ELEVATION_PROFILE.md has the window and the climb decisions.
  //
  // Only the WINDOW is settled here. What the ribbon finally draws is one of
  // four things now (#910) and is decided in lib/ribbonView.ts, further down
  // where the route draft and the map viewport are also in scope; this window
  // is handed to it, and to the lanes below, so the two cannot disagree about
  // which stretch they are showing.
  const fixWindow = useMemo(
    () =>
      elevation === null || fix === null
        ? null
        : ribbonWindow(elevation, fix.mile, direction?.direction),
    [elevation, fix, direction],
  )

  /** The lanes' copy of the tier styling (#759's "highest-value surface"):
   *  the same roll-up the pin rings read, through the same policy module. One
   *  callback whichever domain the ribbon settles on, because a spring that is
   *  stale in the field is stale on a plan, and a second lookup would be a
   *  second chance to disagree about it. */
  const laneStaleness = useCallback(
    (poiId: string, poiType: string) =>
      stalenessPresentation(
        poiType,
        stalenessTier(noteRollups.get(poiId)?.lastConfirmedAt ?? null),
      ),
    [noteRollups],
  )

  /**
   * Every POI whose position is known on BOTH mile scales (#755) - the
   * published pipeline mile (#753) and the client index's own, which
   * `searchablePois` has already paid `mileOnTrail` for. Zipped by index:
   * that memo maps over `pois` one to one.
   *
   * Empty on a download that predates #753, which is `anchoredMile`'s cue to
   * refuse - see lib/route.ts for the honest fallback that follows.
   */
  /**
   * How long the trail is, on the pipeline's own axis - the far end of the
   * "how far" slider (#804).
   *
   * Read off the published elevation profile's last sample rather than
   * hardcoded, which keeps it true when the trail is re-measured and keeps
   * it right for a second trail (value #7: nothing here assumes the AT).
   * Null on a download with no profile, where the slider falls back and the
   * typed field still takes anything.
   */
  const trailMiles = useMemo(() => {
    if (elevation === null || elevation.distanceMi.length === 0) return null
    return elevation.distanceMi[elevation.distanceMi.length - 1]
  }, [elevation])

  const mileAnchors: MileAnchor[] = useMemo(
    () =>
      pois.flatMap((poi, i) => {
        const clientMile = searchablePois[i]?.mile
        return poi.mile !== undefined && clientMile !== undefined
          ? [{ mile: poi.mile, clientMile }]
          : []
      }),
    [pois, searchablePois],
  )

  // Where the hiker is on the pipeline's own mile axis, for the entrance's
  // "where I am" door and "call it a day where you are". Null without a fix
  // - and null without anchors, because a client-scale mile compared against
  // pipeline-scale boundaries is the exact mixed measurement lib/route.ts
  // exists to prevent.
  const gpsPlanMile = useMemo(() => {
    if (fix === null) return null
    return anchoredMile(fix.mile, mileAnchors)
  }, [fix, mileAnchors])

  /** The volunteer workdays on the map and the sheet over a tapped one -
   *  chrome/workdayPanel.tsx owns both (#327). Placed here rather than beside
   *  the other map features because the sheet quotes `gpsPlanMile`, which is
   *  what the Volunteer tab's own "trail mi away" measures. */
  const workday = useWorkdayPanel({
    projects: workProjects,
    generatedAt: workProjectsGeneratedAt,
    now,
    gpsPlanMile,
  })

  // What a reload would destroy right now (#311). Every one of these is React
  // state that no storage carries: a report being written, a window or sheet
  // the hiker opened, a sign-in half done. The update waits for all of them to
  // be put away AND for the page to be hidden - see lib/useAppUpdate.ts.
  //
  // The camera is deliberately NOT in this list. It is kept across the reload
  // instead (lib/cameraMemory.ts), because holding an update for as long as
  // someone is looking at a map would hold it for the whole hike.
  //
  // THIS LIST DRIFTED, and #657's audit caught it: every modal added since
  // #311 forgot to join, so a pending reload could eat a half-typed trail
  // name. The four that were missing are marked below. There is no mechanism
  // stopping the next one from being forgotten the same way - a test cannot
  // ask "is this every modal", because only a reader knows which pieces of
  // state are worth a hiker's work - so the honest guard is this paragraph
  // and the rule it states: **anything that holds something a hiker typed,
  // or that they opened and would have to find again, belongs here.**
  const updateWouldCost =
    reporting !== null ||
    authFlow !== null ||
    downloadsOpen ||
    legendOpen ||
    searchOpen ||
    selectedPoiId !== null ||
    // The trail-name prompt (#233): a half-typed name is exactly the case
    // #311 was about, and it was the one missing.
    collectingIdentity ||
    // Two numbers being entered, and a screen that replaced More rather than
    // covering it - reloading would land the hiker somewhere else entirely.
    pickingHike ||
    // A moderator part-way through a queue, whose place in it is state.
    moderating ||
    // The app-failure form (#848), which is somebody typing about the app
    // having nearly got them lost - the last draft in this app worth losing.
    reportingFailure ||
    // The sheets: each is something the hiker opened and would have to find
    // on the map again. Each feature answers for its own now (#327) - which
    // is why this list sits below the panel hooks rather than up among the
    // `useState`s, and why a feature that grows a second sheet widens its own
    // `sheetOpen` instead of this line.
    atc.sheetOpen ||
    workday.sheetOpen
  useAppUpdate(UPDATE_CHECK_MS, { hold: updateWouldCost })

  /**
   * The trip the Plan tab is showing, and its plan (#787). Everything below
   * that says `plan` reads this - deriving it keeps one copy of a trip's
   * plan in the store, so an edit cannot land on a stale duplicate.
   */
  const currentTrip = useMemo(() => openTripOf(tripStore), [tripStore])
  /**
   * The hike the Plan tab can zoom out to (#790).
   *
   * The open trip's own hike, or - when it belongs to none - the hike, if
   * there is exactly one. Two hikes and no trip to disambiguate them is a
   * choice nobody has been asked to make, so nothing is guessed: the zoom
   * is simply not offered until a trip says which hike is meant.
   */
  const currentHike = useMemo(() => {
    const owning =
      currentTrip === null ? null : hikeOfTrip(tripStore.hikes, currentTrip.id)
    if (owning !== null) return owning
    return tripStore.hikes.length === 1 ? tripStore.hikes[0] : null
  }, [currentTrip, tripStore.hikes])
  const plan = currentTrip?.plan ?? null

  /** Every POI that can BE a stop: its published pipeline mile is known.
   *  Empty on a pre-#753 download - the entrance's cue to refuse. */
  const routeStopChoices: RouteStopChoice[] = useMemo(
    () =>
      pois.flatMap((poi) =>
        poi.mile === undefined
          ? []
          : [
              {
                id: poi.id,
                name: poi.name,
                type: poi.type,
                mile: poi.mile,
                // Carried so the picker can tell a town from an outfitter,
                // which are the same poi_type (#802).
                ...(poi.source === undefined ? {} : { source: poi.source }),
              },
            ],
      ),
    [pois],
  )

  /**
   * Every write to the trip store runs through here: apply, persist,
   * fire-and-forget. The in-memory store is the truth the screens render
   * either way - the same contract the single plan had.
   */
  const applyTripStore = useCallback((edit: (current: TripStore) => TripStore) => {
    setTripStore((current) => {
      const next = edit(current)
      if (next !== current) void saveTrips(next)
      return next
    })
  }, [])

  /**
   * Keep a drafted stretch as ground already walked (#789).
   *
   * The same two ends the builder just described, said in the past tense -
   * which is why this door is there rather than behind a second way to name
   * two places. Every day in the record is walked on arrival, so it feeds
   * the roll-up and #791's gaps exactly as a walked trip does; `recorded`
   * marks the provenance, so no screen prints a remembered 300-mile stretch
   * as if somebody walked it in a day.
   *
   * The builder hands over the stops and closes itself, so what is left
   * here is the part that was always the shell's: the trip store, and where
   * the hiker lands afterwards.
   */
  const handleRecordWalked = useCallback(
    (stops: readonly ViaStopLike[]) => {
      const plan = recordedPlan(stops.map((stop) => ({ ...stop, resupply: false })))
      applyTripStore((store) => addTrip(store, plan, undefined, true))
      // The trips room, because a trip is what just happened (#1008).
      enterTripsRoom()
      setActiveTab('plan')
    },
    [applyTripStore, enterTripsRoom],
  )

  /**
   * The one-thing-open-at-a-time rule the legend, the search and the
   * waypoint card already keep between them. It is the shell's because the
   * things being closed are, and it is stable so the builder's own handlers
   * can list it as a dependency rather than close over a first-render copy.
   *
   * THE DAY HIKE CLOSES HERE, and this is the whole of #997's fix. The rule
   * was written as "each opener clears the other" and implemented in one
   * direction: `openDayHike` cleared the route draft, nothing cleared the
   * day hike. Both surfaces the two modes share - the map tap and
   * `routeSheet` - answer for the day hike first, so a route builder opened
   * on top of one held a live draft that nobody could see or reach.
   *
   * ONE PLACE RATHER THAN TWO, which is what makes it stay fixed. Every door
   * that opens a route draft from nothing passes through here: the panel's
   * `openRouteBuilderFrom` (so "start on the map", #790's gap door and
   * #791's plan-from-here) calls it as `onOpenBuilder`, and
   * `handlePlanChartStretch` calls it directly rather than keeping the copy
   * of these lines it used to. A mirror line in each opener would have been
   * the same fix today and the same bug again at the next door.
   *
   * Symmetric with `openDayHike`, deliberately: that door already discards a
   * route draft without asking, and a rule that discards in one direction
   * and refuses in the other is what made this confusing in the first place.
   * The alternative - refuse, and send the hiker back to the day hike, which
   * is what `openPlanKind` does - is the kinder behaviour and a different
   * decision; #997 records it.
   */
  const sweepForBuilder = useCallback(() => {
    setActiveTab('trail')
    setSelectedPoiId(null)
    setLegendOpen(false)
    setSearchOpen(false)
    setTargetRequest(null)
    // Both halves of the day-hike surface: the draft (#997) and frame `1l`'s
    // review card over it - a review outliving its cleared draft would sit
    // over the route builder describing a walk that no longer exists.
    setDayHikeReview(null)
    setDayHike(null)
    setDayHikeDraftDate(null)
    // A route being built IS the trip room's subject, so the Plan tab is set
    // to it now rather than when the route becomes a trip. Without this the
    // mode a hiker last picked outlives the thing they are actually doing:
    // build a route after a visit to the day room and the Plan tab still
    // opens on Day hikes, where the one primary button is "Plan a day hike"
    // - and that button reaches this same sweep, discarding the route.
    setPlanMode('trips')
  }, [])
  const clearFreeChartStretch = useCallback(() => setFreeChartStretch(null), [])

  // The route builder (#991), the fourth of these. Its state, its twenty-odd
  // handlers and the ~100 lines of JSX behind three `MapScreenProps` fields
  // all live in chrome/routeBuilderPanel.tsx now; what is left here is the
  // seam, which is this call, the chart cluster below it, and the two places
  // the day-hike builder has to be told about (the map tap and the sweep).
  const routeBuilder = useRouteBuilderPanel({
    trailIndex,
    mileAnchors,
    pois,
    elevation,
    pace,
    units,
    routeStopChoices,
    gpsPlanMile,
    gpsClientMile: fix?.mile ?? null,
    trailMiles,
    targetOpen: targetRequest !== null,
    setTargetRequest,
    onRecordWalked: handleRecordWalked,
    onOpenBuilder: sweepForBuilder,
    clearFreeChartStretch,
  })
  // Destructured, and the reason is memoisation rather than brevity: the
  // hook returns a fresh object every render, so a `[routeBuilder]` dep
  // would rebuild the chart's whole prop bundle on every keystroke anywhere
  // in this shell. Each field below is either a value or a `useCallback`,
  // and several are STABLER than what they replaced - `draftLive` flips when
  // a draft opens or closes, where the old `routeDraft` dep changed on every
  // edit to one.
  const {
    draftLive,
    draftStretch,
    draftSouth,
    restretchToMiles,
    toggleDraftDirection,
    openFromMiles,
    closeRouteBuilder,
  } = routeBuilder
  /**
   * A tap on the map, while either builder is open.
   *
   * THE DAY HIKE'S TAP, first and before anything the route builder does: a
   * day hike routes over the junction graph, not the A.T. index, and a phone
   * can hold one without the other. tapAt owns the refusal - a tap off every
   * maintained line places nothing and sets the sentence the bar shows.
   *
   * Everything after it is the route builder's and lives in its own file
   * now (#991), so this delegates rather than deciding. The precedence is
   * unchanged and stays here, in the shell, because it is a fact about two
   * features rather than about either one.
   */
  const handleMapTap = useCallback(
    (at: { lon: number; lat: number }) => {
      if (dayHike !== null) {
        // While frame `1l`'s card reviews the route, the map underneath is a
        // picture, not a control: a tap that edited the draft would desync
        // the card from the ground it is describing.
        if (dayHikeReview !== null) return
        const graphForTaps = dayHikeIndex ?? graphIndex
        if (graphForTaps === null) return
        setDayHike((draft) => (draft === null ? draft : tapAt(graphForTaps, draft, at)))
        return
      }
      routeBuilder.mapScreen.onRouteTap?.(at)
    },
    [dayHike, dayHikeReview, dayHikeIndex, graphIndex, routeBuilder],
  )
  // Opening the day-hike builder repeats the route builder's sweep rather
  // than sharing one. That was argued when this door was written - "the
  // one-thing-open rule is each opener's own responsibility", and a shared
  // helper acquires a caller that does not want all six lines - and it asked
  // to be revisited when a third door repeated it.
  //
  // A THIRD DOOR DID, and repeating cost exactly what the note feared in the
  // other direction: #997. The route builder's two openers now share
  // `sweepForBuilder`, because the line that fixes #997 has to be in every
  // door that opens a route draft and was worth writing once. This one still
  // stands apart, and that is a real difference rather than an oversight -
  // its list is not the same list. It clears `planKindOpen` (the sheet it was
  // opened from) and seeds a draft; `sweepForBuilder` clears the day hike,
  // which this door is creating. Merging them would need a parameter, and a
  // sweep with a mode flag is not a shared rule.
  const openDayHike = useCallback(() => {
    setActiveTab('trail')
    setSelectedPoiId(null)
    setLegendOpen(false)
    setSearchOpen(false)
    setTargetRequest(null)
    setFreeChartStretch(null)
    routeBuilder.closeRouteBuilder()
    setPlanKindOpen(false)
    // Re-entering the builder puts the review away: the taps are live again,
    // and a card reviewing a snapshot of a draft being edited would lie.
    setDayHikeReview(null)
    setDayHike((draft) => draft ?? EMPTY_DRAFT)
    // The mirror of `sweepForBuilder`'s last line, and for the same reason:
    // the draft a hiker is building is what the Plan tab is about.
    setPlanMode('day')
  }, [routeBuilder])

  const handleDayHikeCancel = useCallback(() => {
    setDayHikeReview(null)
    setDayHike(null)
    setDayHikeDraftDate(null)
  }, [])

  // Derived once per state change, not per render - draftStatus runs the
  // router and App re-renders on the GPS clock.
  const dayHikeStatus = useMemo(() => {
    if (dayHike === null) return null
    const graphForTaps = dayHikeIndex ?? graphIndex
    if (graphForTaps === null) return null
    return draftStatus(graphForTaps, dayHike)
  }, [dayHike, dayHikeIndex, graphIndex])

  // What the builder bar prints as ≈time, and the one place it is derived.
  //
  // Naismith takes ascent and no descent - structurally, so a call site cannot
  // wire descent in without changing its signature first (lib/naismith.ts).
  // The climb comes off the route, which priced it from the same walked metres
  // its legs are priced from, so the time and the miles cannot disagree about
  // how much of an edge was walked.
  //
  // Null whenever the walk cannot be priced: no elevation on this phone, or an
  // edge of it nobody has measured. The bar supports printing no time, and
  // that is the honest output - an over-read dead band on rolling terrain
  // over-states time, which is the safe direction, but zero would understate
  // it, which is not.
  const dayHikeWalkingMinutes = useMemo(() => {
    if (dayHikeStatus === null || dayHikeStatus.kind !== 'routed') return null
    const climb = dayHikeStatus.route.climb
    if (climb === null) return null
    return naismithMinutes({
      distanceMi: dayHikeStatus.route.miles,
      ascentFt: climb.gainFt,
    })
  }, [dayHikeStatus])

  const dayHikeDrawing = useMemo<DayHikeDrawing | null>(() => {
    if (dayHike === null) return null
    const points = dayHike.points.map((point, index) => ({
      lon: point.at.lon,
      lat: point.at.lat,
      label: String(index + 1),
    }))
    // The highlight waits for real vertices (dayHikeIndex): routeGeometry
    // refuses chord drawing itself, so before the geometry lands this is
    // points only - the taps are the hiker's own work and draw immediately.
    if (
      dayHikeIndex === null ||
      dayHikeStatus === null ||
      dayHikeStatus.kind !== 'routed'
    ) {
      return { lines: [], points }
    }
    const first = dayHike.points[0]
    const last = dayHike.looped
      ? dayHike.points[0]
      : dayHike.points[dayHike.points.length - 1]
    const lines =
      routeGeometry(dayHikeIndex.graph, dayHikeStatus.route.edgeIndices, first, last) ??
      []
    return { lines, points }
  }, [dayHike, dayHikeIndex, dayHikeStatus])

  const dayHikeOrgLabel = useMemo(() => orgLabelFrom(stewards), [stewards])

  /**
   * Done: the draft becomes a saved DayHike and the builder closes.
   *
   * ENDS ARE STORED AS COORDINATES, NEVER AS GraphPoint.edgeIndex - the
   * index is positional into an array the pipeline compacts in input order,
   * so a republished graph would silently shift a saved hike onto a
   * different trail. A coordinate re-resolves against whatever graph the
   * phone holds. poiId stays null until the finished-hike card's join
   * (#980); the field exists now so the shape needs no migration.
   */
  const handleDayHikeDone = useCallback(() => {
    if (dayHike === null || dayHikeStatus === null || dayHikeStatus.kind !== 'routed') {
      return
    }
    const route = dayHikeStatus.route
    const hike: DayHike = {
      id: crypto.randomUUID(),
      name: dayHikeName(route),
      // Whatever the hiker set on a review card before "Back to the map"
      // discarded it - see dayHikeDraftDate.
      date: dayHikeDraftDate,
      segments: [
        dayHike.points.map((point) => ({
          coord: [point.at.lon, point.at.lat] as [number, number],
          poiId: null,
        })),
      ],
      figures: {
        miles: route.miles,
        legs: route.legs.map((leg) => ({
          name: leg.name,
          source: leg.source,
          blaze_color: leg.blaze_color,
          miles: leg.miles,
        })),
      },
      looped: dayHike.looped,
      recorded: 'planned',
    }
    // Done no longer saves: it hands the record to frame `1l`'s card, and
    // "Save this day hike" there is the commit (#980). The draft stays live
    // underneath so closing the card returns to the builder mid-thought.
    setDayHikeReview(hike)
  }, [dayHike, dayHikeStatus, dayHikeDraftDate])

  const handleDayHikeSave = useCallback(() => {
    if (dayHikeReview === null) return
    const hike = dayHikeReview
    // saveDayHikes records the sync ledger itself (read-before-write, so the
    // edit travels as the hiker's own act) - nothing to record here. The
    // store is re-read rather than trusted to React state so a save landing
    // from the sync between renders is never overwritten. openId stays null:
    // nothing is on screen once the card closes, and the card defines what
    // that pointer means now.
    void loadDayHikes().then((store) => {
      const next = { hikes: [...store.hikes, hike], openId: null }
      setDayHikeStore(next)
      return saveDayHikes(next)
    })
    setDayHikeReview(null)
    setDayHike(null)
    setDayHikeDraftDate(null)
  }, [dayHikeReview])

  /** Open a saved hike's card from the Plan tab. Written through the store
   *  because that is where `openId` lives - held in the one document so the
   *  pointer cannot outlive the hike it names. */
  const handleOpenDayHike = useCallback((id: string) => {
    void loadDayHikes().then((store) => {
      const next = {
        ...store,
        openId: store.hikes.some((hike) => hike.id === id) ? id : null,
      }
      setDayHikeStore(next)
      return saveDayHikes(next)
    })
  }, [])

  const handleDayHikeCardClose = useCallback(() => {
    if (dayHikeReview !== null) {
      // The review's close is "Back to the map": the draft is still there.
      setDayHikeReview(null)
      return
    }
    void loadDayHikes().then((store) => {
      const next = { ...store, openId: null }
      setDayHikeStore(next)
      return saveDayHikes(next)
    })
  }, [dayHikeReview])

  const handleDeleteDayHike = useCallback((id: string) => {
    // The filter IS the delete; saveDayHikes' before/after diff records it
    // in the sync ledger as the hiker's own act, tombstone and all.
    void loadDayHikes().then((store) => {
      const next = { hikes: store.hikes.filter((hike) => hike.id !== id), openId: null }
      setDayHikeStore(next)
      return saveDayHikes(next)
    })
  }, [])

  /** Date a saved hike (#1008) - the same read-modify-write every other
   *  store edit takes, so a sync landing between renders is never lost. */
  const handleSetDayHikeDate = useCallback((id: string, date: string | null) => {
    void loadDayHikes().then((store) => {
      const next = {
        ...store,
        hikes: store.hikes.map((hike) => (hike.id === id ? { ...hike, date } : hike)),
      }
      setDayHikeStore(next)
      return saveDayHikes(next)
    })
  }, [])

  /** The hike a card is showing: the unsaved review outranks the store's
   *  open one - they cannot both be on screen, and the review is newer. */
  const cardDayHike =
    dayHikeReview ??
    (dayHikeStore.openId !== null
      ? (dayHikeStore.hikes.find((hike) => hike.id === dayHikeStore.openId) ?? null)
      : null)

  // Derived once per state change, not per render, for dayHikeStatus's
  // reason: resolution runs the router per tapped pair and App re-renders
  // on the GPS clock.
  const cardResolution = useMemo(() => {
    if (cardDayHike === null) return null
    const graph = dayHikeIndex ?? graphIndex
    if (graph === null) return null
    return resolveDayHike(graph, cardDayHike)
  }, [cardDayHike, dayHikeIndex, graphIndex])

  const cardBailOuts = useMemo(() => {
    if (cardResolution === null) return []
    const graph = dayHikeIndex ?? graphIndex
    if (graph === null) return []
    return dayHikeBailOuts(graph, cardResolution)
  }, [cardResolution, dayHikeIndex, graphIndex])

  const dayHikeCardNode =
    cardDayHike !== null ? (
      <DayHikeCard
        hike={cardDayHike}
        resolved={cardResolution}
        bailOuts={cardBailOuts}
        stewards={stewards}
        units={units}
        networkAvailable={graphIndex !== null}
        mode={dayHikeReview !== null ? 'review' : 'saved'}
        onSave={handleDayHikeSave}
        onClose={handleDayHikeCardClose}
        onDelete={() => handleDeleteDayHike(cardDayHike.id)}
        onSetDate={(date) => {
          if (dayHikeReview === null) {
            handleSetDayHikeDate(cardDayHike.id, date)
            return
          }
          // Pre-save it rides the review record AND the draft-scoped state,
          // so a trip back to the map to re-check the route does not throw
          // it away.
          setDayHikeReview({ ...dayHikeReview, date })
          setDayHikeDraftDate(date)
        }}
      />
    ) : null

  /**
   * Which Plan home to show (#1008): the hiker's own last pick wins; until
   * they make one, the day side when a day-hike card is open or day hikes
   * are all they have, the trips side otherwise.
   */
  const effectivePlanMode: PlanMode =
    planMode ??
    (cardDayHike !== null
      ? 'day'
      : tripStore.trips.length > 0 || tripStore.hikes.length > 0
        ? 'trips'
        : dayHikeStore.hikes.length > 0
          ? 'day'
          : 'trips')

  /**
   * The switch chip. Crossing into the trips room is the same arrival as any
   * other door's, so it lands the same way - see `enterTripsRoom`. Switching
   * back to the day room needs none of that: the list and the card it would
   * close are that room's own furniture.
   */
  const handleSwitchPlanMode = useCallback(
    (mode: PlanMode) => {
      if (mode === 'trips') {
        enterTripsRoom()
        return
      }
      setPlanMode(mode)
    },
    [enterTripsRoom],
  )

  /** The trailhead door's candidates (frame D8): saved starts near the fix,
   *  less the ones this session has already been told no about. */
  const hikesNearHere = useMemo(() => {
    if (gps.status !== 'located') return []
    return dayHikesNearHere(dayHikeStore.hikes, gps.at).filter(
      (entry) => !hikesHereDismissed.includes(entry.hike.id),
    )
  }, [gps, dayHikeStore.hikes, hikesHereDismissed])

  /**
   * Whether something a hiker ASKED for already has the map's lower third.
   *
   * The door is the only occupant of that space nobody asked for - every
   * other one is the answer to a tap. The builders it defers to could never
   * collide with these, because opening a builder suppresses the taps that
   * raise them; the door renders in exactly the state where those taps are
   * live, so it is the first surface here that can land on top of one. z-index
   * does not settle it either: these are siblings at the same level, and the
   * routeSheet slot is the LAST child of the canvas, so equal z-index means
   * the door wins on DOM order.
   */
  const lowerThirdTaken =
    selectedPoiId !== null ||
    line.mapScreen.lineSheet != null ||
    atc.mapScreen.atcUpdateSheet != null ||
    atc.mapScreen.atcNoticeList != null ||
    workday.mapScreen.workdaySheet != null

  const dayHikesHereNode =
    hikesNearHere.length > 0 && !lowerThirdTaken ? (
      <DayHikesHere
        near={hikesNearHere}
        units={units}
        // lib/passedToday.ts's own helper rather than a second copy of the
        // idiom - it already spells the phone's LOCAL calendar day as
        // YYYY-MM-DD, which is the store's date shape and the right clock
        // here: "that's today" is a claim about the hiker's morning, not
        // UTC's.
        today={localDay(now)}
        onOpen={(id) => {
          handleOpenDayHike(id)
          setPlanMode('day')
          setDayListOpen(false)
          setActiveTab('plan')
        }}
        onAll={() => {
          setPlanMode('day')
          setDayListOpen(true)
          setActiveTab('plan')
        }}
        onDismiss={() =>
          setHikesHereDismissed((dismissed) => [
            ...dismissed,
            ...hikesNearHere.map((entry) => entry.hike.id),
          ])
        }
      />
    ) : null

  // The two heavy halves of the graph - each edge's vertices and its climb
  // (#1011) - fetched the first time the builder opens and attached onto a NEW
  // index (lib/trailGraphData.ts). Keyed on the mode being open rather than on
  // launch: with the whole A.T. in the graph these are by far the heavier
  // artifacts, and a launch that never opens the door should never pay for
  // them.
  //
  // INDEPENDENT OF EACH OTHER ON PURPOSE. Either can 404 on a release exported
  // before it existed, and neither absence should take the other down: without
  // geometry the highlight is refused and the walk still prices; without
  // elevation the walk still draws and the climb goes unsaid. Both are states
  // the surfaces below already know how to say.
  //
  // BOTH DOORS, NOT JUST THE BUILDER. A saved card opens from the Plan tab
  // with no draft in hand, so keying this on `dayHike` alone left the one
  // surface a hiker returns to resolving against the routing-only graph -
  // no vertices to draw and, since #1011, no climb to print. Either door
  // opening is what these are needed for.
  useEffect(() => {
    if (
      (dayHike === null && cardDayHike === null) ||
      graphIndex === null ||
      dayHikeIndex !== null
    ) {
      return
    }

    const controller = new AbortController()
    let wanted = true

    const edgeCount = graphIndex.graph.edges.length
    void Promise.all([
      fetchTrailGraphGeometry(edgeCount, controller.signal),
      fetchTrailGraphElevation(edgeCount, controller.signal),
    ]).then(([geometry, elevation]) => {
      if (!wanted) return
      let next = graphIndex
      if (geometry !== null) next = attachTrailGraphGeometry(next, geometry)
      if (elevation !== null) next = attachTrailGraphElevation(next, elevation)
      // Unchanged means both 404'd - leave dayHikeIndex null so the builder
      // keeps routing on the graph it already has.
      if (next !== graphIndex) setDayHikeIndex(next)
    })

    return () => {
      wanted = false
      controller.abort()
    }
  }, [dayHike, cardDayHike, graphIndex, dayHikeIndex])

  // The Plan tab's one primary action (#805). A live draft goes BACK to its
  // builder - the door is for starting, never a toll gate on the way back to
  // your own route (openRouteBuilderFrom's rule, kept here for both modes).
  const openPlanKind = useCallback(() => {
    if (dayHike !== null) {
      setActiveTab('trail')
      return
    }
    if (routeBuilder.draftLive) {
      routeBuilder.openRouteBuilder()
      return
    }
    setPlanKindOpen(true)
  }, [dayHike, routeBuilder])

  /**
   * The trail inside the map's viewport, on the pipeline's axis - the "always
   * in sync" half of the #910 review.
   *
   * Null until the hiker has taken the map themselves (`mapTaken`), which is
   * what keeps a shell-driven camera move - the opening fit, a jump after a
   * download - from quietly pulling the ribbon off the hiker. Null too on a
   * pre-#753 download, where there are no anchors to carry the client index's
   * miles onto the profile's axis, and a span measured on one scale and drawn
   * against the other would be wrong by the drift between them.
   */
  const mapStretch = useMemo(() => {
    if (!mapTaken || trailIndex === null) return null
    const span = viewportMiles(trailIndex, bbox)
    if (span === null) return null
    const startMile = anchoredMile(span.startMile, mileAnchors)
    const endMile = anchoredMile(span.endMile, mileAnchors)
    if (startMile === null || endMile === null) return null
    return { startMile, endMile }
  }, [mapTaken, trailIndex, bbox, mileAnchors])

  /**
   * The one ribbon the phone draws, whichever of the four it turns out to be
   * (lib/ribbonView.ts holds the precedence and the reasoning).
   *
   * Computed unconditionally rather than behind `isDesktop`, and the cost is
   * worth naming rather than waving at: above the breakpoint MapScreen draws
   * the chart and never the ribbon, so a desk pays one envelope pass over the
   * domain and throws it away. That pass is the same decimation the chart
   * itself makes, memoised on the same span, and it re-runs only when the span
   * moves. Gating it would mean subscribing the shell to `useDesktop()`'s
   * media query for nothing else.
   */
  const ribbon = useMemo(
    () =>
      ribbonView({
        profile: elevation,
        planStretch: draftStretch,
        mapStretch,
        fixClientMile: fix?.mile ?? null,
        fixPlanMile: gpsPlanMile,
        fixWindow,
        ...(direction?.direction === undefined ? {} : { direction: direction.direction }),
      }),
    [elevation, draftStretch, mapStretch, fix, gpsPlanMile, fixWindow, direction],
  )

  /**
   * The three lanes under whichever ribbon won (#913) - the same
   * WIREFRAMES.md §1.4 lanes, over the ground the ribbon is actually showing
   * rather than only over the fix window.
   *
   * Both POI lists go in because the axis depends on the domain and
   * lib/ribbonView.ts is where that rule belongs: `ahead` is windowed on the
   * client index, so its pins come from `searchablePois`, which has already
   * paid `locateOnTrail()` for every POI; every other domain is a
   * pipeline-axis span, so its pins come from the published mile on `pois`
   * (#753). Deciding that here would put the trap in the caller.
   */
  const waypoints = useMemo(() => {
    const lanes = ribbonLanes(ribbon, {
      onPipelineAxis: pois,
      onClientAxis: searchablePois,
    })
    return lanes === undefined ? undefined : { ...lanes, stalenessFor: laneStaleness }
  }, [ribbon, pois, searchablePois, laneStaleness])

  const chartSelection = draftLive ? draftStretch : freeChartStretch
  const chartSouth = draftSouth ?? freeChartSouth

  /**
   * A drag settled on the chart. With no draft open it is a measurement and
   * nothing more; with one open it re-stretches the route (the review's
   * "overriding what was selected"). A null - a click - changes no route:
   * clearing one is the builder's close button, and the chart already
   * refuses to send it.
   *
   * `draftLive` is what picks the branch, rather than anything the builder
   * reports back from the call: a state updater runs at render, so a seam
   * that answered "did I act?" would answer it a render too late.
   */
  const handleChartStretch = useCallback(
    (stretch: ChartStretch | null) => {
      if (!draftLive) {
        setFreeChartStretch(stretch)
        return
      }
      if (stretch === null) return
      restretchToMiles(stretch.startMile, stretch.endMile)
    },
    [draftLive, restretchToMiles],
  )

  /** The chart's direction toggle turns the ROUTE around while one is being
   *  built - reversing the stops, which is what walking it the other way
   *  means - and is a display choice only while measuring. */
  const handleChartSouth = useCallback(() => {
    if (!draftLive) {
      setFreeChartSouth((was) => !was)
      return
    }
    toggleDraftDirection()
  }, [draftLive, toggleDraftDirection])

  /** "Plan this stretch": the measured selection becomes a route - ends at
   *  its ends, walked the way the figures were just reading. */
  const handlePlanChartStretch = useCallback(() => {
    if (freeChartStretch === null) return
    // THE sweep, not a copy of it (#997). This handler used to repeat four
    // of its five lines inline, which is how the day-hike clear could have
    // been added to one opener and missed here. The one line it did not
    // repeat - setActiveTab('trail') - is a no-op on this path rather than a
    // difference: the chart is a MapScreen prop, and App returns early for
    // every other tab, so nothing reaches here from anywhere else.
    sweepForBuilder()
    setFreeChartStretch(null)
    openFromMiles(freeChartStretch.startMile, freeChartStretch.endMile, freeChartSouth)
  }, [freeChartStretch, freeChartSouth, openFromMiles, sweepForBuilder])

  // The desktop's full elevation chart (#135). Unlike the ribbon it needs no
  // fix - a desk has none - only the published profile; the fix, when one
  // exists, rides along on the profile's own axis (gpsPlanMile above). The
  // two converters are how chart focus reaches the map: a profile-axis mile
  // crosses to the client index's scale through the POI anchors
  // (lib/route.ts), then trailPointAtMile / trailSlice turn it into
  // geometry. No anchors (a pre-#753 download) costs the map linkage and
  // nothing else - the chart still draws and measures.
  //
  // The selection and direction ride down CONTROLLED (PR #885 review): the
  // route draft's stretch while the builder is open, the free measurement
  // otherwise - so a stop entered in the builder selects on the chart, and
  // a drag on the chart re-stretches the route.
  const desktopChart = useMemo(() => {
    if (elevation === null) return undefined
    const mileToCoordinate = (mile: number): [number, number] | null => {
      if (trailIndex === null) return null
      const clientMile = anchoredClientMile(mile, mileAnchors)
      if (clientMile === null) return null
      return trailPointAtMile(trailIndex, clientMile)
    }
    const stretchToRuns = (startMile: number, endMile: number) => {
      if (trailIndex === null) return []
      const from = anchoredClientMile(startMile, mileAnchors)
      const to = anchoredClientMile(endMile, mileAnchors)
      if (from === null || to === null) return []
      return trailSlice(trailIndex, from, to)
    }
    return {
      profile: elevation,
      currentMile: gpsPlanMile,
      mileToCoordinate,
      stretchToRuns,
      selection: chartSelection,
      southbound: chartSouth,
      selectionFromPlan: draftLive,
      onSelectStretch: handleChartStretch,
      onToggleSouthbound: handleChartSouth,
      onPlanStretch: handlePlanChartStretch,
      wholeTrailBounds: CORRIDOR_BOUNDS,
      // The hiker's own pace rides down too (#886): the chart and the route
      // builder share a selection, so they must price it the same way.
      pace,
    }
  }, [
    elevation,
    trailIndex,
    mileAnchors,
    gpsPlanMile,
    chartSelection,
    chartSouth,
    draftLive,
    handleChartStretch,
    handleChartSouth,
    handlePlanChartStretch,
    pace,
  ])

  // Re-targeting an existing plan runs the same sheet over the plan's own
  // route, seeded with what it aimed at last time. The route is the ends
  // PLUS every pinned boundary: a pin is the promise that replanning goes
  // around this day, not through it (#758's rule), and a wholesale re-lay
  // is replanning - so a booked hostel or an added destination survives a
  // target change, and everything the generator chose is re-chosen. Refused
  // once anything is walked: the past is a record a re-lay would overwrite,
  // and re-planning what remains is the cascade's job (#758). The screen
  // hides the button in that state; this guard is the belt to that
  // suspender.
  const handleChangeTarget = useCallback(() => {
    if (plan === null || plan.stops.length < 2) return
    if (plan.days.some((day) => day.walked === true)) return
    const kept = [
      plan.stops[0],
      ...plan.days.flatMap((day, index) => (day.pinned ? [plan.stops[index + 1]] : [])),
      plan.stops[plan.stops.length - 1],
    ]
    // A pinned final day would list the last stop twice.
    const route = kept.filter((stop, index) => index === 0 || stop !== kept[index - 1])
    setTargetRequest({
      route: route.map((stop) => ({
        mile: stop.mile,
        ...(stop.name === undefined ? {} : { name: stop.name }),
        ...(stop.poiId === undefined ? {} : { poiId: stop.poiId }),
      })),
      initialTarget: plan.target,
      ...(plan.days[0]?.date === undefined
        ? {}
        : { initialStartDate: plan.days[0].date }),
      // A re-lay keeps the rest rhythm rather than dropping it (#798).
      ...(plan.rhythm === undefined ? {} : { initialRhythm: plan.rhythm }),
      ...(currentTrip === null ? {} : { tripId: currentTrip.id }),
    })
  }, [plan, currentTrip])

  /**
   * Laying days out either KEEPS A NEW TRIP or re-lays the one already open,
   * and the difference is which door the sheet came through: the route
   * builder makes a trip that did not exist, while the timeline's "change
   * target" re-lays a trip that does. Without the distinction, re-targeting
   * would silently leave the old version behind as a second trip - which is
   * the bug this whole issue is about, arriving from the other side.
   */
  const handleLayOut = useCallback(
    (next: HikePlan) => {
      const tripId = targetRequest?.tripId ?? null
      applyTripStore((store) =>
        tripId === null ? addTrip(store, next) : updateTrip(store, tripId, next),
      )
      setTargetRequest(null)
      closeRouteBuilder()
      // Laid-out days are a trip: land in the room that shows them.
      enterTripsRoom()
      setActiveTab('plan')
    },
    [targetRequest, applyTripStore, closeRouteBuilder, enterTripsRoom],
  )

  // Every timeline edit runs through here, against whichever trip is open.
  // Keeps the no-plan case inert exactly as before.
  const applyPlanEdit = useCallback(
    (edit: (current: HikePlan) => HikePlan) => {
      applyTripStore((store) => {
        const trip = openTripOf(store)
        if (trip === null) return store
        const next = edit(trip.plan)
        return next === trip.plan ? store : updateTrip(store, trip.id, next)
      })
    },
    [applyTripStore],
  )

  /** Delete the open trip - not every trip. The Plan tab's own button says
   *  "Delete plan", and a hiker with four kept trips must not lose the other
   *  three to it. */
  const handleDeletePlan = useCallback(() => {
    applyTripStore((store) =>
      store.openId === null ? store : removeTrip(store, store.openId),
    )
  }, [applyTripStore])

  // The cascade (#758) hands back whole re-planned plans rather than edits.
  const handleReplacePlan = useCallback(
    (next: HikePlan) => {
      applyTripStore((store) => {
        const trip = openTripOf(store)
        return trip === null ? store : updateTrip(store, trip.id, next)
      })
    },
    [applyTripStore],
  )

  const handleOpenTrip = useCallback(
    (id: string) => {
      applyTripStore((store) => openTrip(store, id))
      setTripsOpen(false)
      enterTripsRoom()
      setActiveTab('plan')
    },
    [applyTripStore, enterTripsRoom],
  )

  const handleRenameTrip = useCallback(
    (id: string, name: string) => applyTripStore((store) => renameTrip(store, id, name)),
    [applyTripStore],
  )

  const handleRemoveTrip = useCallback(
    (id: string) => applyTripStore((store) => removeTrip(store, id)),
    [applyTripStore],
  )

  /**
   * Group every kept trip into one hike (#788), over the ground they
   * already cover. The "I have a history" door: a section hiker with four
   * trips gets a hike without retyping any of it, and the ends carry the
   * stops' own references so a relocation moves the hike rather than
   * silently resizing it.
   *
   * Named for the ground rather than asked for: naming is a rename away,
   * and a dialog before the thing exists is a dialog nobody reads.
   */
  const handleGroupIntoHike = useCallback(() => {
    applyTripStore((store) => {
      const hike = hikeFromTrips(store.trips, 'My hike')
      return hike === null ? store : addHike(store, hike)
    })
  }, [applyTripStore])

  // The hiker's own buckets (#800). A trip stays in every other group it is
  // in - which is the whole difference from a hike, of which it has one.
  const [openGroupId, setOpenGroupId] = useState<string | null>(null)

  const handleNewGroup = useCallback(
    (name: string) => applyTripStore((store) => addGroup(store, name)),
    [applyTripStore],
  )

  const handleAddToGroup = useCallback(
    (groupId: string, tripId: string) =>
      applyTripStore((store) => addToGroup(store, groupId, tripId)),
    [applyTripStore],
  )

  const handleRemoveFromGroup = useCallback(
    (groupId: string, tripId: string) =>
      applyTripStore((store) => removeFromGroup(store, groupId, tripId)),
    [applyTripStore],
  )

  const handleRenameGroup = useCallback(
    (groupId: string, name: string) =>
      applyTripStore((store) => renameGroup(store, groupId, name)),
    [applyTripStore],
  )

  const handleRemoveGroup = useCallback(
    (groupId: string) => {
      applyTripStore((store) => removeGroup(store, groupId))
      setOpenGroupId(null)
    },
    [applyTripStore],
  )

  const openGroup = tripStore.groups.find((group) => group.id === openGroupId) ?? null

  const targetSheet =
    targetRequest === null ? null : (
      <PlanTargetSheet
        route={targetRequest.route}
        pois={pois}
        elevation={elevation}
        units={units}
        pace={pace}
        {...(targetRequest.initialTarget === undefined
          ? {}
          : { initialTarget: targetRequest.initialTarget })}
        {...(targetRequest.initialRhythm === undefined
          ? {}
          : { initialRhythm: targetRequest.initialRhythm })}
        {...(targetRequest.initialStartDate === undefined
          ? {}
          : { initialStartDate: targetRequest.initialStartDate })}
        onCancel={() => setTargetRequest(null)}
        onLayOut={handleLayOut}
      />
    )

  // Zoomed out past what the download covers (#216).
  //
  // Read off the DRAWN background rather than the choice: with Data Saver on,
  // a hiker who picked the live sheet is looking at the archive too, and the
  // gap is just as blank for them. `camera` is null until the first moveend,
  // so nothing is claimed before the map has reported a zoom.
  const belowArchiveZoom =
    effectiveBackground(preferences.background_source, saveData, archiveDownloaded) ===
      'usgs_topo_offline' &&
    camera !== null &&
    !archiveCoversZoom(archiveZooms, camera.zoom)

  /**
   * Write preferences to the phone, and do not let the failure be silent (#315).
   *
   * `void savePreferences(next)` was the shape at both call sites, which is
   * the failure mode #891 already shipped once: a rejection nobody catches is
   * QUIETER than a log while reading like the error is taken seriously. Here
   * it costs more than a lost toggle. `onboarding_completed` is a preference,
   * so a phone whose IndexedDB write fails — private mode, a full quota, a
   * store the browser has decided to evict — finishes first run, comes back,
   * and is shown first run again. Every launch. With no explanation, and no
   * reason for the hiker to suspect anything other than the app being broken.
   *
   * PARTIAL, AND WORTH SAYING SO. This makes the failure legible in a bug
   * report (lib/bugReport.ts collects console output) rather than telling the
   * hiker anything. The honest surface is a sentence on screen — "this phone
   * would not save your settings" — and that is a screen this change does not
   * add. #315 records it as still open.
   */
  const persistPreferences = useCallback((next: UserPreferences) => {
    void savePreferences(next).catch((error: unknown) => {
      console.error(
        'Could not save preferences to this phone. Settings will not survive a ' +
          'relaunch, and first run will be shown again because onboarding_completed ' +
          'is one of them.',
        error,
      )
    })
  }, [])

  /**
   * Writes a preference and persists it.
   *
   * Accepts a function as well as a patch, and the function form is what a
   * TOGGLE needs: it reads the current value inside the update rather than
   * closing over this render's copy, so a fast double-tap cannot land two
   * flips on one stale value. The drought toggle used to reach past this
   * helper to `setPreferences` for exactly that reason, which left two ways
   * to write a preference and only one of them going through here.
   */
  const updatePreferences: UpdatePreferences = useCallback(
    (patch) => {
      setPreferences((current) => {
        const next = {
          ...current,
          ...(typeof patch === 'function' ? patch(current) : patch),
        }
        persistPreferences(next)
        return next
      })
    },
    [persistPreferences],
  )

  /**
   * The legend's three filters - which categories are drawn, whether
   * unconfirmed places are, and the drought tint - owned by
   * chrome/waypointFiltersPanel.tsx (#327).
   */
  const filters = useWaypointFiltersPanel({
    preferences,
    updatePreferences,
    drought,
    droughtWeek,
  })

  /**
   * Opens the download window, and clears whatever else was open over the map.
   *
   * One thing open at a time, the same rule the legend and the waypoint card
   * already keep. Both of those announce themselves as modal dialogs on a
   * phone, and so does this - leaving one behind would put a screen-reader
   * user inside a dialog with a second one on top of it. On a desktop the
   * legend is a permanent panel and closing it is a no-op, which is the right
   * answer there too.
   */
  const openDownloads = useCallback(() => {
    setDownloadsOpen(true)
    setLegendOpen(false)
    setSelectedPoiId(null)
  }, [])

  /**
   * The background choice, and the one case where making it does something
   * else as well.
   *
   * Choosing "downloaded only" with nothing downloaded is a request for a map
   * this phone does not have. The preference is still saved - it takes effect
   * the moment an archive lands, and lib/dataSaver.ts draws the live sheet
   * meanwhile so nobody is left holding blank paper - but saving it silently
   * would answer a hiker's "show me my download" with a note explaining that
   * there isn't one. The window that fixes it opens instead.
   *
   * Here rather than inside BackgroundPicker because both pickers - the
   * legend's and Settings' - are the same component, and a rule about what a
   * choice MEANS belongs to the shell that owns the download, not to the
   * control that reports the choice.
   *
   * THE SECOND HALF CANNOT FIRE TODAY, and is kept anyway (#855). With the
   * USGS sheet withdrawn the picker offers "downloaded only" exactly where it
   * can be honoured - on a phone that already holds the archive - so the
   * branch below is unreachable from any screen: either the choice is
   * unavailable, or it is available and `archiveDownloaded` is already true.
   * It is the rule for when the sheet returns, and deleting it would leave
   * whoever un-withdraws that sheet with a silent choice that answers "show
   * me my download" by storing a preference and saying nothing.
   */
  const handleChangeBackground = useCallback(
    (background_source: BackgroundSource) => {
      updatePreferences({ background_source })
      if (background_source === 'usgs_topo_offline' && !archiveDownloaded) {
        openDownloads()
      }
    },
    [updatePreferences, archiveDownloaded, openDownloads],
  )

  const handleOnboardingComplete = useCallback(
    ({ hikingDetailLevel, locationRequested }: OnboardingResult) => {
      // The choice made is the choice written (#277): onboarding's download
      // step speaks the hiking sheet now, so the hiking sheet's preference
      // is what it sets. The USGS raster's tier keeps its default until its
      // own card is used.
      updatePreferences({
        onboarding_completed: true,
        download_choice_made: true,
        location_permission_requested: locationRequested,
        hiking_detail_level: hikingDetailLevel,
      })
      // The download window, over the map rather than instead of it. The
      // choice just made is a download that has not started, so the window is
      // still what someone leaving onboarding needs; what has changed is that
      // it no longer costs them the first sight of the map to see it.
      //
      // NOT ON A DESKTOP (WEBSITE.md §6, "Download UX"). A laptop has signal,
      // and the assumption worth making about it is the one it is almost
      // always right about: this connection is not being metered by the mile.
      // The live sheet is already the default background, so a browser that
      // never opens this window still gets the whole trail drawn - the
      // download buys it nothing it does not already have, and 314 MB is a
      // real cost to put in front of someone before they have seen the map.
      //
      // It is withheld, not removed, and that distinction is the whole of the
      // rule. The legend is a permanent panel above 900px, and DownloadsLink
      // sits in it, so "Choose what to download" is on screen the entire time
      // - more visible than the phone's, where the legend has to be opened
      // first. Someone setting up a cabin machine, or a laptop that is coming
      // along, is one click away and was never told no.
      if (!isDesktop) openDownloads()
    },
    [updatePreferences, openDownloads, isDesktop],
  )

  /** One sheet: every archive it is made of, in one tap. Archives already on
   *  the phone are left alone rather than re-fetched. */
  const handleDownloadSheet = useCallback(
    async (sheet: BackgroundSheet) => {
      const missing = offeredPackages(sheet)
        .map((pkg) => pkg.idbKey)
        .filter((key) => archiveStatusFor(key).state !== 'downloaded')
      if (missing.length === 0) return

      // Said before the wait rather than after it, which is the point: this
      // is the first thing the tap does and it used to be the silent thing.
      setPreparingSheets((current) =>
        current.includes(sheet.id) ? current : [...current, sheet.id],
      )
      try {
        if (!(await ensureTrailData())) return
      } finally {
        // In `finally` so a refused canary puts the card back to a state with
        // a button in it. Leaving this sheet "preparing" after a failure
        // would be a phone claiming to be working with nothing in flight -
        // and the error the catch above set would have nothing to sit under.
        setPreparingSheets((current) => current.filter((id) => id !== sheet.id))
      }

      // Whatever these sources did to the LAST copy of these bytes is not true
      // of the one now arriving. Scoped to `missing` rather than to the whole
      // sheet (#352): fetching the DEM half of the hiking sheet says nothing
      // about the basemap beside it, and clearing that flag withdrew a "No
      // live map" that was still true.
      setNotDrawing((current) => forgetPackages(current, missing))
      await startPackages(missing)
    },
    [archiveStatusFor, ensureTrailData, startPackages],
  )

  /** Resume, which skips the trail-data step: those bytes are already here,
   *  and the point of resuming is not to spend signal twice. */
  const handleResumeSheet = useCallback(
    async (sheet: BackgroundSheet) => {
      const resuming = offeredPackages(sheet)
        .filter((pkg) => archiveStatusFor(pkg.idbKey).state !== 'downloaded')
        .map((pkg) => pkg.idbKey)
      // The same clear the download path makes, and its absence here was a
      // real defect (#352): a transfer that drops leaves the source erroring
      // for the ordinary reason that nothing is downloaded yet, and the
      // resume that completes then inherited that flag - so a byte-correct
      // archive was announced as damaged the moment it finished.
      setNotDrawing((current) => forgetPackages(current, resuming))
      await Promise.all(resuming.map((key) => startPackage(key)))
    },
    [archiveStatusFor, startPackage],
  )

  /** Deleting a sheet deletes that sheet: every archive behind it, and
   *  nothing else - not the other sheet, which is the acceptance line #237
   *  wrote down ("delete it without touching the background they navigate
   *  by"), and not the trail's own data.
   *
   *  The trail data deliberately stays. It belongs to the trail rather than
   *  to the map under it, it is a rounding error against what is being
   *  reclaimed, and it is downloaded by default anyway - so taking it would
   *  strip the trail line off the screen only for the next launch with
   *  signal to fetch it again. */
  const handleDeleteSheet = useCallback(
    async (sheet: BackgroundSheet) => {
      await Promise.all(offeredPackages(sheet).map((pkg) => removePackage(pkg.idbKey)))
      // The moment a greyed rung should come back (#555). Awaited before this
      // rather than fired alongside it, so the re-read sees the space the
      // delete released instead of racing it.
      refreshAvailableBytes()
    },
    [removePackage, refreshAvailableBytes],
  )

  // Every move is also where the camera would have to be put back, so this is
  // the one place that remembers it. Reading the map rather than deriving a
  // centre from the bounding box keeps a round trip through another tab exact:
  // re-fitting a box adds its padding again each time, so the view would creep
  // outwards with every visit to Downloads.
  const handleViewportChange = useCallback(
    (next: BoundingBox, fromGesture: boolean) => {
      setBbox(next)
      // Only the hiker's own pan or pinch takes the ribbon off them (#910).
      // Every camera move the SHELL makes - the opening fit, a jump to a
      // search result, the ribbon's own framing buttons - arrives here with
      // no originalEvent and leaves the latch alone.
      if (fromGesture) setMapTaken(true)
      if (map === null) return
      const centre = map.getCenter()
      const settled: Camera = { center: [centre.lng, centre.lat], zoom: map.getZoom() }
      setCamera(settled)
      // Written on every settled move rather than on unload: a page being
      // replaced by a new service worker gets no reliable last word, and
      // `moveend` is already the one place that knows where the view came to
      // rest (#311).
      writeCamera(settled)
    },
    [map],
  )

  /**
   * Put the map back on the hiker, and the ribbon back on their ten miles
   * (#910 review).
   *
   * The other half of the `mapTaken` latch: a gesture sets it, this clears it.
   * The camera move is a `jumpTo` rather than a gesture, so it does not
   * immediately re-arm the latch it is clearing - and the zoom is left alone,
   * because "back to me" is a claim about where the map is centred, not about
   * how far in the hiker wanted to be.
   */
  const handleBackToMe = useCallback(() => {
    setMapTaken(false)
    if (map === null || gps.status !== 'located') return
    map.jumpTo({ center: [gps.at.lon, gps.at.lat] })
  }, [map, gps])

  const handleMapReady = useCallback((next: MapLibreMap | null) => setMap(next), [])

  // How many of the waypoints in view the map actually drew (#528). Measured on
  // `idle` rather than derived, because the collision engine decides it and only
  // MapLibre knows what it decided - see lib/useDrawnPoiCounts.ts.
  const {
    counts: drawnPoiCounts,
    belowPoiZoom,
    ghostedTrailsDrawn,
  } = useDrawnPoiCounts(map)

  // One thing open at a time. The waypoint card floats by its pin rather than
  // at the bottom where the legend sits, but the rule survives the move: two
  // dialogs at once means a screen-reader user in one with the other still
  // announcing itself, and a hiker mid-walk should have one thing to dismiss,
  // not a stack. The desktop legend is a permanent panel and does not close.
  //
  // Null is a tap on bare map - the card's tap-elsewhere-to-dismiss, which
  // every map card teaches. It only clears the selection: closing the LEGEND
  // from a stray tap on the map above it would punish a miss twice.
  const handleSelectPoi = useCallback((id: string | null) => {
    setSelectedPoiId(id)
    if (id !== null) setLegendOpen(false)
  }, [])

  const handleOpenLegend = useCallback(() => {
    setLegendOpen(true)
    setSelectedPoiId(null)
  }, [])

  const handleClosePoi = useCallback(() => setSelectedPoiId(null), [])

  /**
   * Queue a closure and send it if there is anything to send it with (#832).
   *
   * The geometry is captured HERE rather than in the form, because this is
   * where the trail index lives - and it has to be captured now rather than
   * at flush time or later. A mile is a reading against one measurement of
   * the centerline; converting it to a point afterwards needs the release
   * the closure was authored against, and pipeline/DATA_RELEASES.md prunes a
   * release 90 days after it is superseded. The conversion stops being
   * possible long before the closure stops mattering.
   *
   * Saved to the outbox FIRST, like every other contribution: everything
   * after that line can fail without costing somebody the closure they just
   * walked up to. The sign-in step follows rather than precedes for the same
   * reason - `POST /closures` needs an account, but a hiker standing at a
   * washout should not meet a sign-in wall before their report is safe.
   *
   * No reporter-type question: a closure carries no `reporter_type`, so
   * asking would collect an answer with nowhere to put it.
   */
  const handleSubmitClosure = useCallback(
    async ({ authoredAt, ...fields }: ClosureFormSubmission) => {
      await enqueueClosure(closureDraft(fields, trailIndex), authoredAt)
      setReportingClosure(false)

      // Explicitly, for #640's reason: useOutboxSync fires on a CHANGE to
      // `online` or the account, and filing this changes neither.
      void syncOutbox().then((result) => {
        if (result !== null && result.sent > 0) markSynced()
      })
      if (account === null) setAuthFlow({ screen: 'choose', afterReport: true })
    },
    [account, markSynced, trailIndex],
  )

  /**
   * Ask who is reporting, at most once a session and never twice over.
   *
   * Called from both paths that reach the step: straight after a report when
   * there is nothing to sign in to, and after the sign-in flow closes for a
   * hiker who was sent there first. contributionFlow.ts puts the account
   * ahead of the identity, and this keeps that order without letting it
   * SWALLOW the question - a hiker who declines the account still files
   * reports, and every one of them carries a reporter type.
   */
  const askForIdentity = useCallback(() => {
    if (identityAsked.current) return
    if (hasStatedReporterType(preferences.reporter_type)) return
    identityAsked.current = true
    setCollectingIdentity(true)
  }, [preferences.reporter_type])

  const handleSubmitReport = useCallback(
    async ({ authoredAt, photo, ...draft }: ReportFormSubmission) => {
      // Saved first, always, and before authentication is so much as
      // mentioned. Everything below this line can fail without costing the
      // hiker what they just wrote - the photo included, which is why it is
      // pulled out of the draft here and stored as bytes beside it (#234).
      await beginContribution(draft, authoredAt, photo)
      setReporting(null)

      const next = stepAfterSaving({
        hasAccount: account !== null,
        // The reporter type, not the trail name, is what says this screen has
        // been answered: it is the field every report must carry, and the
        // trail name beside it may legitimately be left blank (#233).
        hasIdentity: hasStatedReporterType(preferences.reporter_type),
      })
      // Sent now, explicitly (#640). useOutboxSync cannot do it: its effect
      // fires when `online` or the account CHANGES, and a signed-in hiker
      // with signal changes neither by submitting - the same steady-state gap
      // #266 closed for "Try again", on the other path that needed it. This
      // comment used to say the hook "is already watching"; that sentence was
      // what kept the gap open. When the next step is sign-in there is no
      // account yet and syncOutbox declines on its own - the flush after
      // signing in belongs to the hook, because an account arriving is the
      // change it does watch. Not awaited: a send standing between someone
      // and the map they were reading would be a network round trip in the
      // way, and a failure lands in the outbox exactly as it always did.
      void syncOutbox().then((result) => {
        if (result !== null && result.sent > 0) markSynced()
      })
      if (next === 'sign-in') setAuthFlow({ screen: 'choose', afterReport: true })
      else if (next === 'identity') askForIdentity()
    },
    [account, preferences.reporter_type, askForIdentity, markSynced],
  )

  /**
   * Queue an app-failure report and send it if there is anything to send it
   * with (#848).
   *
   * Shorter than `handleSubmitReport` above by exactly the things this report
   * does not need. No sign-in step: the endpoint takes no account, because a
   * hiker whose app just failed may never have made one. No reporter-type
   * question: nothing about this is attributed to a kind of hiker. What it
   * keeps is the part that matters out here - saved to the outbox FIRST, so
   * everything after this line can fail without costing them what they wrote.
   *
   * The screen is not closed here. It shows its own acknowledgement, and
   * closes when the hiker presses Done - somebody who has just described
   * being lost should be told what happens next rather than dropped back on
   * the map.
   */
  const handleSubmitAppFailure = useCallback(
    async (draft: AppFailureDraft, authoredAt: Date) => {
      await enqueueAppFailure(draft, authoredAt)

      // Explicitly, for the reason #640 gives about the report path:
      // useOutboxSync fires on a CHANGE to `online` or the account, and
      // filing this changes neither. Not awaited - a network round trip must
      // not stand between somebody and the acknowledgement.
      void syncOutbox().then((result) => {
        if (result !== null && result.sent > 0) markSynced()
      })
    },
    [markSynced],
  )

  /**
   * Queue a field note (FIELD_NOTES.md, #759's card surface), echo it
   * locally, and walk the same after-saving steps a report walks.
   *
   * Saved first, exactly as handleSubmitReport: everything below the
   * enqueue can fail without costing the hiker their tap. The local echo is
   * what freshens their own pin immediately - see `localNotes` above.
   */
  const handleAddFieldNote = useCallback(
    async (draft: FieldNoteDraft, photo?: Blob) => {
      const item = await enqueueFieldNote(draft, undefined, photo)

      setLocalNotes((current) => [
        {
          id: item.id,
          poi_id: draft.poi_id ?? null,
          lat: draft.lat ?? null,
          lon: draft.lon ?? null,
          mile: draft.mile ?? null,
          observation: draft.observation ?? null,
          note: draft.note ?? null,
          observed_at: item.authoredAt,
          reporter_type: draft.reporter_type,
          // The local echo carries no photo URL, and that is honest rather
          // than a gap (#879): the bytes are still on this phone, and the
          // only URL that exists is one the server mints after the upload
          // lands. The card shows the note now and the picture once it has
          // actually gone - which is the same order the queue sends them in.
          photo_url: null,
        },
        ...current,
      ])

      // Explicitly, for #640's reason on the report path: useOutboxSync
      // fires on a CHANGE to `online` or the account, and a signed-in hiker
      // with signal changes neither by tapping.
      void syncOutbox().then((result) => {
        if (result !== null && result.sent > 0) markSynced()
      })

      const next = stepAfterSaving({
        hasAccount: account !== null,
        hasIdentity: hasStatedReporterType(preferences.reporter_type),
      })
      if (next === 'sign-in') setAuthFlow({ screen: 'choose', afterReport: true })
      else if (next === 'identity') askForIdentity()
    },
    [account, preferences.reporter_type, askForIdentity, markSynced],
  )

  /**
   * A report that starts from a place card carries the place (FIELD_NOTES.md
   * step 1): the escalation after a problem-shaped tap, and the card's own
   * "report a problem here". With a type it goes straight to the form -
   * `damaged` names shelter_repair - and without one it opens the picker,
   * because no report type is "a dry spring" and pre-picking a wrong one
   * would file a flooding report about the absence of water.
   */
  const handleReportFromPoi = useCallback(
    (anchor: ReportAnchor, type?: 'shelter_repair') => {
      setSelectedPoiId(null)
      setReporting(
        type === undefined ? { step: 'pick', anchor } : { step: 'form', type, anchor },
      )
    },
    [],
  )

  /**
   * The conditions section's whole world, built once per change of its
   * inputs so the card is not re-rendered by every unrelated shell state.
   */
  const noteContext: FieldNoteContext = useMemo(
    () => ({
      notesFor: (poiId: string) => {
        if (allNotes === null) return null
        return allNotes
          .filter((note) => note.poi_id === poiId)
          .sort(
            (a, b) =>
              new Date(b.observed_at).getTime() - new Date(a.observed_at).getTime(),
          )
      },
      reporterType: preferences.reporter_type,
      contributeConditions: preferences.contribute_conditions,
      // The corroborated verdict for this place (#876). Null covers both
      // "nobody disputes it" and "we could not ask", and the card treats
      // them the same on purpose: neither is a claim worth printing, and
      // only the first is a claim at all.
      disputeFor: (poiId: string) => disputeFor(disputes, poiId),
      onAddNote: (draft: FieldNoteDraft, photo?: Blob) =>
        void handleAddFieldNote(draft, photo),
      onReportProblem: handleReportFromPoi,
      now,
    }),
    [
      allNotes,
      disputes,
      preferences.reporter_type,
      preferences.contribute_conditions,
      handleAddFieldNote,
      handleReportFromPoi,
      now,
    ],
  )

  /**
   * The hours logbook (#761): what the backend holds, fetched when the
   * Volunteer tab is actually open - a private record read by one screen
   * does not earn a fetch on every launch - plus this phone's own unsent
   * records echoed locally, the same immediately-real contract the field
   * notes keep. Null until either exists.
   */
  const [myHours, setMyHours] = useState<VolunteerHoursSummary[] | null>(null)
  const [localHours, setLocalHours] = useState<readonly VolunteerHoursSummary[]>([])

  useEffect(() => {
    if (!online || account === null || activeTab !== 'volunteer') return
    let cancelled = false
    fetchMyVolunteerHours().then(
      (records) => {
        if (!cancelled) setMyHours(records)
      },
      // Unreachable backend, unconfigured build, expired session - all the
      // ordinary conditions out here. The logbook keeps whatever it had.
      () => undefined,
    )
    return () => {
      cancelled = true
    }
  }, [online, account, activeTab])

  const hoursRecords = useMemo(() => {
    if (myHours === null && localHours.length === 0) return null
    const fetched = myHours ?? []
    const fetchedIds = new Set(fetched.map((record) => record.id))
    // The echo wins only until the server copy arrives under the same id -
    // then the server's state (a club may have confirmed it) is the record.
    return [
      ...localHours.filter((record) => !fetchedIds.has(record.id)),
      ...fetched,
    ].sort((a, b) => b.worked_on.localeCompare(a.worked_on) || a.id.localeCompare(b.id))
  }, [myHours, localHours])

  /** Queue a day's hours - saved first, echoed at once, sign-in asked after
   *  (contributionFlow.ts's ordering, the same walk every write takes). */
  const handleLogHours = useCallback(
    async (draft: VolunteerHoursDraft) => {
      const item = await enqueueVolunteerHours(draft)

      setLocalHours((current) => [
        {
          id: item.id,
          club_id: draft.club_id ?? null,
          worked_on: draft.worked_on,
          hours: draft.hours,
          work_project_id: draft.work_project_id ?? null,
          activity: draft.activity,
          note: draft.note ?? null,
          mile: draft.mile ?? null,
          lat: draft.lat ?? null,
          lon: draft.lon ?? null,
          state: 'claimed',
          confirmed_at: null,
          recorded_at: item.authoredAt,
        },
        ...current,
      ])

      void syncOutbox().then((result) => {
        if (result !== null && result.sent > 0) markSynced()
      })

      const next = stepAfterSaving({
        hasAccount: account !== null,
        hasIdentity: hasStatedReporterType(preferences.reporter_type),
      })
      if (next === 'sign-in') setAuthFlow({ screen: 'choose', afterReport: true })
    },
    [account, preferences.reporter_type, markSynced],
  )

  /**
   * Today's walked-past water, shelters, campsites and resupply, oldest mile
   * first - the Volunteer tab's list (lib/passedToday.ts). Names come from
   * the same searchable index every other list reads.
   */
  const passedPlacesToday = useMemo(
    () =>
      passedPlaces(
        passedToday.ranges,
        searchablePois.flatMap((poi) =>
          poi.mile === undefined
            ? []
            : [{ id: poi.id, name: poi.name, type: poi.type, mile: poi.mile }],
        ),
        NOTE_SCOPED_TYPES,
      ),
    [passedToday.ranges, searchablePois],
  )

  /**
   * A tap on a passed place opens its card, on the map, framed - the exact
   * behaviour a search result has (#527), because the list is a second way
   * to name a place, not a second kind of screen.
   */
  const handleOpenPassedPlace = useCallback(
    (id: string) => {
      setActiveTab('trail')
      handleSelectPoi(id)
      const found = pois.find((candidate) => candidate.id === id)
      if (found !== undefined && map !== null) {
        map.jumpTo({
          center: [found.lon, found.lat],
          zoom: Math.max(map.getZoom(), SEARCH_RESULT_ZOOM),
        })
      }
    },
    [pois, map, handleSelectPoi],
  )

  /** Answered: both fields land together, which is what the screen collects.
   *  An empty trail name is stored as null rather than as "", so Settings can
   *  keep saying "Not set" rather than showing a blank. */
  const handleSaveIdentity = useCallback(
    ({ trailName, reporterType }: { trailName: string; reporterType: ReporterType }) => {
      updatePreferences({
        trail_name: trailName.trim() === '' ? null : trailName.trim(),
        reporter_type: reporterType,
      })
      setCollectingIdentity(false)
    },
    [updatePreferences],
  )

  const handleChooseProvider = useCallback((provider: AuthProvider) => {
    if (provider === 'email') {
      setAuthFlow((current) =>
        current === null ? null : { screen: 'email', afterReport: current.afterReport },
      )
      return
    }
    // An OAuth round trip leaves the page. If it returns with a session,
    // useAccount's subscription is what notices - there is nothing to await
    // here, and no state worth setting on the way out.
    void signInWithProvider(provider)
  }, [])

  /**
   * Build the archive and hand it to the browser (#895).
   *
   * The device half is read here rather than passed down because App is the
   * only thing that knows the stores exist; the screen owns the button and
   * the spinner, and nothing else.
   */
  /**
   * That this device has just deleted its account.
   *
   * Only here to keep the receipt on screen. Signing out is what makes the
   * app's own state honest afterwards, and it takes `account` to null - which
   * is the gate the section renders behind, so without this flag the panel
   * unmounts in the same tick as the deletion it was about to report. Not
   * persisted: it describes this render, not this device.
   */
  const [accountDeleted, setAccountDeleted] = useState(false)

  const handleExportAccount = useCallback(async () => {
    downloadArchive(await buildAccountArchive())
  }, [])

  /**
   * Delete the account, then make this device stop acting like it has one.
   *
   * The order is the whole of it. `deleteAccount` first, because if it
   * throws, nothing local should have changed and the hiker's next press is
   * an ordinary retry. Only once the server has answered does this device
   * forget its sync ledgers and sign out.
   *
   * WHAT THIS DELIBERATELY DOES NOT DO IS WIPE THE PHONE
   *
   * The trips, the planned hike and the preferences stay in IndexedDB, and
   * the screen says so. They are this device's copy and always were - phase
   * D's off switch makes the same promise in the other direction ("It does
   * not delete anything, anywhere"), and a server-side deletion that also
   * silently destroyed a hiker's local planning would be this app taking a
   * decision that was never asked of it. Uninstalling is what removes those,
   * and that is the sentence on the screen.
   *
   * The ledgers DO go, for the reason `handleSignOut` gives at more length:
   * `since` and `seen` are claims about an account this device no longer
   * has, and left in place they would make the next sign-in - possibly by
   * somebody else on a shared handset - look like a device that had already
   * synced, and upload one person's plans into another person's account.
   */
  const handleDeleteAccount = useCallback(async (): Promise<DeletionReceipt> => {
    const receipt = await deleteAccount()
    setAccountDeleted(true)
    await forgetPreferencesSync()
    await forgetTripSync()
    await forgetDayHikeSync()
    await signOut()
    return receipt
  }, [])

  const handleSignOut = useCallback(async () => {
    await signOut()
    // The preferences stay - they are this phone's, and a hiker who signs
    // out should not watch their theme revert. What goes is the claim to
    // have synced with an account this device no longer has (#891): leaving
    // it would let the NEXT sign-in, possibly by somebody else on a shared
    // handset, look like a device that had already synced, and take this
    // one's settings for their account rather than the other way round.
    await forgetPreferencesSync()
    // The trips stay - they are this device's - but `since` and `seen` are
    // claims about an account this device no longer has. Left in place they
    // would make the next sign-in, possibly by somebody else on a shared
    // handset, look like a device that had already synced, and upload one
    // person's plans into another person's account as ordinary edits (#892).
    await forgetTripSync()
    // And the day hikes' own ledger, for exactly the same reason (#1035).
    // It landed with its own store (#976) and its own forget function, and
    // that function was never called from here - so a day hike's segments,
    // which are the coordinates somebody tapped, were the one thing a shared
    // handset still carried across a sign-out.
    await forgetDayHikeSync()
  }, [])

  /**
   * The account's preferences arriving, on a device that had none of them.
   *
   * Written straight to state and NOT through `updatePreferences`: that one
   * marks the blob dirty, which would have this device push back what it
   * just pulled on every launch for ever. `adoptPreferences` has already
   * put these in IndexedDB with the account's own stamp.
   */
  const handleAdoptPreferences = useCallback((synced: UserPreferences) => {
    setPreferences(synced)
  }, [])

  /**
   * Whether this handset syncs at all (#894), and what it has to report.
   *
   * The flag is device-local on purpose - lib/syncStatus.ts has the reason:
   * a hiker who stops syncing their laptop has not asked their phone to
   * stop, so a synced setting would travel to exactly the devices it is
   * meant to exclude.
   *
   * `syncTick` is what re-reads the two ledgers. They live in IndexedDB
   * rather than in React state, so nothing re-renders when they change -
   * and a "what has reached your account" panel that did not notice a sync
   * completing would be the confidently-wrong surface this whole phase
   * exists to replace.
   */
  const [syncOn, setSyncOn] = useState(true)
  const [syncTick, setSyncTick] = useState(0)
  const [syncSummary, setSyncSummary] = useState<SyncStatus | null>(null)

  useEffect(() => {
    void syncEnabled().then(setSyncOn, () => setSyncOn(true))
  }, [])

  useEffect(() => {
    let live = true
    void Promise.all([tripSyncState(), preferencesSyncState()]).then(
      ([trips, prefs]) => {
        if (live) setSyncSummary(summariseSync(tripStore, trips, prefs))
      },
      // A ledger that cannot be read is not "everything is safe". Left null,
      // the section does not render at all, which is honest: this screen
      // would rather say nothing than say the reassuring thing on no
      // evidence.
      () => {
        if (live) setSyncSummary(null)
      },
    )
    return () => {
      live = false
    }
  }, [tripStore, preferences, syncTick])

  const handleToggleSync = useCallback((next: boolean) => {
    setSyncOn(next)
    void setSyncEnabled(next)
  }, [])

  // Bumped when a sync lands, so the panel re-reads the ledgers.
  const noteSyncRan = useCallback(() => setSyncTick((tick) => tick + 1), [])

  usePreferencesSync(
    preferences,
    account !== null && syncOn,
    handleAdoptPreferences,
    noteSyncRan,
  )

  /**
   * The account's trips arriving, merged with this device's (#892).
   *
   * Written straight to state and NOT through anything that saves: the
   * reconciliation has already written IndexedDB through `adoptTrips`,
   * which deliberately does not mark the store as changed here - otherwise
   * this device would push back what it just pulled on every sync.
   */
  const handleAdoptTrips = useCallback((merged: TripStore) => {
    setTripStore(merged)
  }, [])

  useTripsSync(tripStore, account !== null && syncOn, handleAdoptTrips, noteSyncRan)

  useEffect(() => {
    let wanted = true
    void loadDayHikes().then((store) => {
      if (wanted) setDayHikeStore(store)
    })
    return () => {
      wanted = false
    }
  }, [])

  // The day hikes' own exchange (#976, decided 2026-08-25: sync from day
  // one) - its own ledger and endpoint, never trips': a day-hike id in the
  // trips ledger would upload as a tombstone no synced_trips row matches, a
  // silent no-op that looks like a working sync.
  const handleAdoptDayHikes = useCallback((merged: DayHikeStore) => {
    // Reconciliation already wrote IndexedDB through adoptDayHikes - the
    // same do-not-mark rule handleAdoptTrips explains.
    setDayHikeStore(merged)
  }, [])

  useDayHikesSync(
    dayHikeStore,
    account !== null && syncOn,
    handleAdoptDayHikes,
    noteSyncRan,
  )

  // Signing in ends the sign-in flow, whichever way it completed - an email
  // form resolving in this tab, or a provider redirect landing back on a
  // freshly loaded page. Watching the account rather than the call site is
  // what makes those two the same event here.
  useEffect(() => {
    if (account !== null) setAuthFlow(null)
  }, [account])

  /**
   * Signing in hands on to the step it was standing in front of (#233).
   *
   * contributionFlow.ts puts the account first because a trail name belongs
   * to a profile, so this is where the identity question actually becomes
   * askable. Only on a SUCCESSFUL sign-in: someone who backed out has just
   * declined one question, and answering that with a second one is how an app
   * teaches people to dismiss whatever it puts in front of them. They can
   * still say who they are in Settings, which is where it is editable now.
   */
  useEffect(() => {
    if (account !== null && authFlow?.afterReport === true) askForIdentity()
  }, [account, authFlow, askForIdentity])

  // Nothing renders until the phone has answered about itself: its stored
  // preferences, so a returning hiker never sees a flash of the first-run
  // onboarding, and what is in its archive store, so the map is built around
  // the right background the first time (App.mapLifecycle.test.tsx).
  //
  // The second half is the same argument as the first, one screen further in.
  // `archiveStatusFor` answers "not downloaded" for a package it has not read
  // yet, which is the same answer it gives for one that genuinely is not
  // there - and effectiveBackground() below turns that into "draw the live
  // sheet". So a phone WITH the corridor on it used to open on the live sheet,
  // start pulling vector and DEM tiles over the network, and then throw the
  // whole map away and rebuild it around the archive when the read landed a
  // beat later. A blink, a re-frame, and roughly 2 MB of somebody's data
  // allowance spent on a background they had already downloaded their way out
  // of - which is precisely the spend lib/dataSaver.ts exists to prevent.
  //
  // Both reads start on mount and run in parallel, so what this waits for is
  // the slower of the two rather than their sum, and both are IndexedDB reads
  // of small things - an object of preferences, and blob HANDLES whose bytes
  // are not touched. Neither can hang the app open: loadPreferences() falls
  // back to defaults if it rejects, and every path through the archive read,
  // including its catch, sets a status.
  if (!preferencesLoaded || !archivesRead) return null

  /**
   * Where the opening view has room to be, which during first run is not the
   * whole canvas.
   *
   * The corridor was always fitted to the full map, and the entry card then
   * covered up to 78% of it - so the first thing a hiker saw was the Maine end
   * of the trail wedged into the corner above the card, while the sentence next
   * to it said "the whole trail's topo map lives on your phone". The fit was
   * right and the framing was wrong, which is why this is padding rather than a
   * different camera: CORRIDOR_BOUNDS still says show all of it, and this says
   * where "all of it" has to fit.
   *
   * Expressed as a fraction of the viewport rather than in pixels because the
   * card is (`ENTRY_CARD_MAX_VIEWPORT_FRACTION`), so the two move together on a
   * short screen and a tall one alike. The left/right/top insets stay the plain
   * breathing room every fitted box gets.
   */
  const entryFitPadding = entering
    ? {
        top: 24,
        bottom: Math.round(
          (globalThis.innerHeight ?? 0) * ENTRY_CARD_MAX_VIEWPORT_FRACTION,
        ),
        left: 24,
        right: 24,
      }
    : undefined

  // First run is rendered by the MAIN RETURN below, not by a branch here, and
  // that is #721's whole fix.
  //
  // The three entry steps used to be an opaque screen, so the first thing
  // OurHike showed anyone was a page about a map instead of the map. Every
  // sentence on those steps - the whole trail lives on your phone, pick how
  // much detail, here is why we want your location - is a claim about a thing
  // that is right there and was being described rather than shown.
  // WIREFRAMES.md §5 already asked for this on the location step ("an overlay
  // on top of the already-downloading map, so the reason is visible"); it is
  // the same argument on all three, so the map is behind all three.
  //
  // That was built as a SECOND `<MapView>`, in a branch that returned before
  // the map screen ever rendered. It drew the right thing and cost a whole map:
  // React reconciles by position, so when `onboarding_completed` flipped, the
  // entry tree unmounted, `MapView`'s cleanup dropped the WebGL context, and
  // the map screen built another one from scratch. Measured on a 4x-throttled
  // phone profile: two WebGL contexts, and 1,230 ms of blocking work across
  // seven long tasks at the exact moment the steps were dismissed - on a main
  // thread that had just finished the launch fetch.
  //
  // The comment here used to justify that as "the same price a trip through
  // the More tab already pays". It is not the same price. A trip through More
  // is something a hiker chose and can avoid; this landed on every hiker once,
  // at the end of the flow whose entire job is the first impression.
  //
  // So the map stays where it is and the CHROME changes around it: the map
  // screen renders throughout, with `entering` hiding everything but its canvas
  // and making the subtree `inert` (chrome/MapScreen.tsx). Nothing about what a
  // hiker sees behind the steps has changed - still the canvas and nothing
  // else, still untouchable, still credited - and there is now one map.

  if (authFlow !== null) {
    if (authFlow.screen === 'email') {
      return (
        <EmailSignIn
          onMagicLink={sendMagicLink}
          onSignIn={signInWithEmail}
          onSignUp={signUpWithEmail}
          onCancel={() => setAuthFlow(null)}
        />
      )
    }

    return (
      <SignInPrompt
        providers={ENABLED_PROVIDERS}
        reportSaved={authFlow.afterReport}
        // #315: Google and Apple are a full off-origin navigation, so
        // offline they take the hiker out of the app and away from the map
        // rather than merely failing. The screen holds those two and says so.
        online={online}
        onSignIn={handleChooseProvider}
        onCancel={() => setAuthFlow(null)}
      />
    )
  }

  // After the report is saved and after sign-in, which is the order
  // contributionFlow.ts insists on: a trail name belongs to a profile, so
  // asking first collects something with nowhere to put it (#233).
  if (collectingIdentity) {
    return (
      <IdentitySetup
        onSave={handleSaveIdentity}
        onSkip={() => setCollectingIdentity(false)}
      />
    )
  }

  // Before the report screens below and after the auth ones above, which is
  // the order this file already keeps: a full-screen flow renders instead of
  // the map. Nothing here is gated on an account, deliberately - see
  // handleSubmitAppFailure.
  if (reportingFailure) {
    return (
      <AppFailureReport
        online={online}
        onSubmit={(draft, authoredAt) => void handleSubmitAppFailure(draft, authoredAt)}
        onClose={() => setReportingFailure(false)}
      />
    )
  }

  if (reportingClosure) {
    return (
      <ClosureForm
        // The snapped mile the header is already showing, or null when there
        // is no fix or it could not be placed on the centerline. Never zero:
        // mi 0.0 is Springer Mountain, not "we do not know".
        hereMile={fix?.mile ?? null}
        online={online}
        onSubmit={(submission) => void handleSubmitClosure(submission)}
        onCancel={() => setReportingClosure(false)}
      />
    )
  }

  if (reporting !== null) {
    if (reporting.step === 'pick') {
      const anchor = reporting.anchor
      return (
        <ReportTypePicker
          // The anchor rides through the pick (FIELD_NOTES.md step 1): a
          // report that started from a place card stays about that place
          // whichever type gets chosen.
          onPick={(type) =>
            setReporting(
              anchor === undefined
                ? { step: 'form', type }
                : { step: 'form', type, anchor },
            )
          }
          // A closure leaves the report flow rather than continuing it: it
          // is a different record with a different form (#832).
          onReportClosure={() => {
            setReporting(null)
            setReportingClosure(true)
          }}
          onCancel={() => setReporting(null)}
        />
      )
    }

    return (
      <ReportForm
        type={reporting.type}
        trailName={preferences.trail_name}
        // The stored answer, or the floor when nobody has said (#233). It was
        // a hardcoded "thru" here and in More below, so every report in the
        // queue claimed to be from a thru-hiker - see lib/reporterIdentity.ts
        // for why the fallback is the weakest claim rather than that one.
        reporterType={signReportAs(preferences.reporter_type)}
        // Anchored reports carry the PLACE (FIELD_NOTES.md step 1): the
        // POI's own coordinates and mile, which need no GPS fix - it is the
        // place being reported on, not the hiker's position. Un-anchored
        // ones keep the fix: null with no fix, rather than 0,0 - a real
        // place in the Atlantic a maintainer cannot tell from a missing
        // location. The mile is separately unknown when the fix is off the
        // centerline or the trail index has not been downloaded yet.
        location={
          reporting.anchor !== undefined
            ? {
                lat: reporting.anchor.lat,
                lon: reporting.anchor.lon,
                ...(reporting.anchor.mile !== undefined
                  ? { mile: reporting.anchor.mile }
                  : {}),
              }
            : gps.status === 'located'
              ? { lat: gps.at.lat, lon: gps.at.lon, mile: fix?.mile }
              : null
        }
        poiId={reporting.anchor?.poiId}
        online={online}
        onSubmit={(submission) => void handleSubmitReport(submission)}
        onCancel={() => setReporting(null)}
      />
    )
  }

  // Rendered beside whichever screen is showing rather than instead of it -
  // it is a window over the app, and the map or Settings behind it is still
  // there. Built once here so the two branches below cannot drift into two
  // slightly different downloads.
  //
  // The notices come with it. They are about this download and nothing else,
  // and the tab that used to carry them is gone; leaving them on a screen
  // would mean an archive that failed at 4 AM announcing itself over the map
  // for the rest of the walk.
  const downloadsWindow = downloadsOpen && (
    <DownloadsDialog onClose={() => setDownloadsOpen(false)}>
      {!DATA_CONFIGURED && (
        // Written for the hiker who hits it, even though the condition is a
        // builder's mistake: an env var name in a role="alert" reads as
        // gibberish to the one person guaranteed to be shown it. Whoever
        // builds the app finds VITE_DATA_BASE_URL through lib/config.ts.
        <p role="alert" className="app__notice">
          This copy of the app was built without a place to download maps from, so
          downloading cannot work. That is a fault in the app itself — not your phone, and
          not your signal.
        </p>
      )}
      {dataError !== null && (
        <p role="alert" className="app__notice">
          {dataError.message}
          {/* The same one story the download card tells for a refused
              archive: nothing kept, nothing here to resume, a fresh
              download is the fix (#238). */}
          {dataError.kind === 'hash-mismatch' &&
            ' Downloading again fetches a fresh copy from the start.'}
        </p>
      )}
      <InstallPrompt
        platform={install.platform}
        canPrompt={install.canPrompt}
        onInstall={install.install}
      />
      <Downloads
        sheets={backgroundSheets.map((sheet) => ({
          id: sheet.id,
          title: sheet.title,
          summary: sheet.summary,
          status: sheetStatus(sheet),
          sizeBytes: sheetSizeBytes(sheet, detailLevel, hikingLevel),
          error: sheetError(sheet),
          // Answered against the card's OWN status, not a second reading of
          // what is downloaded: this notice exists to contradict a card that
          // says the download finished, so it has to be about the same claim
          // that card is making (lib/backgroundHealth.ts).
          notDrawing: sheetNotDrawing(
            notDrawing,
            sheet,
            sheetStatus(sheet).state === 'downloaded',
          ),
          // The step before this sheet's transfer, so the tap has something
          // to show for itself while the canary is in flight.
          preparing: preparingSheets.includes(sheet.id),
          // Each sheet's picker carries its own level set and writes its own
          // preference (#276) - the USGS raster's tiers and the hiking
          // sheet's cuts are separate dials. The `as` casts are safe because
          // DetailPicker only ever emits ids from the options handed to it.
          detail:
            sheet.id === USGS_SHEET.id
              ? {
                  options: rasterDetailOptions(),
                  value: detailLevel,
                  name: 'usgs-detail',
                  availableBytes,
                  onChange: (level: string) =>
                    updatePreferences({
                      max_background_zoom: getDownloadDetail(level as DetailLevel).zoom,
                    }),
                }
              : sheet.id === HIKING_SHEET.id
                ? {
                    options: hikingDetailOptions(),
                    value: hikingLevel,
                    name: 'hiking-detail',
                    availableBytes,
                    onChange: (level: string) =>
                      updatePreferences({
                        hiking_detail_level: level as HikingDetailLevel,
                      }),
                  }
                : // A sheet nobody has wired a dial for yet: the ladder,
                  // greyed, rather than a card shaped unlike its neighbours
                  // (#298).
                  {
                    options: noDetailOptions(),
                    value: '',
                    onChange: () => undefined,
                  },
          onStart: () => void handleDownloadSheet(sheet),
          onResume: () => void handleResumeSheet(sheet),
          onDelete: () => void handleDeleteSheet(sheet),
        }))}
        persistence={archivePersistence}
      />
    </DownloadsDialog>
  )

  if (activeTab === 'more') {
    // Its own boundary for the same reason the map has one, with the roles
    // reversed: a throw anywhere in Settings used to escape to the ROOT
    // boundary, which has no tab bar and no reset - one bad stored value
    // rendering More was a permanently dead app. Caught here, the tab bar
    // survives underneath and the map stays one tap away, which is the only
    // recovery that matters on a trail.
    return (
      <>
        <div className="app__screen">
          <div>
            {/* No resetKey: this boundary only renders while activeTab is
                'more', so leaving the tab unmounts it and clears the error -
                a resetKey={activeTab} here could never change while mounted
                (#175). */}
            <ErrorBoundary fallback={() => <ScreenFailed what="This screen" />}>
              {moderating ? (
                // Replaces More rather than covering it, for the same reason
                // HikePicker does: it is reached from here and nowhere else,
                // so there is nothing behind it worth keeping visible.
                <Moderation onClose={() => setModerating(false)} />
              ) : pickingHike ? (
                // Replaces More rather than covering it. The picker is reached
                // from here and nowhere else, so there is nothing behind it
                // worth keeping visible - and a screen needs no backdrop, no
                // focus trap and no Escape handler to get half right.
                <HikePicker
                  hike={hike}
                  trailMiles={trailIndex?.totalMiles ?? null}
                  units={units}
                  onSave={(next) => void handleSaveHike(next)}
                  onClear={() => void handleClearHike()}
                  onClose={() => setPickingHike(false)}
                />
              ) : (
                // Neither `onSync` nor `onExport` is passed, and that is the
                // change rather than an omission (#657): both were bound to
                // `notYet` and rendered as live buttons that did nothing.
                // DataSettings draws "Later" when it has no handler, which is
                // the standard the same file already keeps for "Roads &
                // walkability".
                <More
                  stewards={stewards}
                  account={account}
                  onSignIn={() => setAuthFlow({ screen: 'choose', afterReport: false })}
                  onSignOut={() => void handleSignOut()}
                  preferences={preferences}
                  onChange={updatePreferences}
                  onChangeBackground={handleChangeBackground}
                  pace={pace}
                  onChangePace={handleChangePace}
                  lastSyncedAt={lastSyncedAt}
                  syncStatus={syncSummary ?? undefined}
                  syncEnabled={syncOn}
                  onToggleSync={handleToggleSync}
                  onExportAccount={handleExportAccount}
                  onDeleteAccount={handleDeleteAccount}
                  accountDeleted={accountDeleted}
                  now={now}
                  dataSaver={saveData}
                  archiveDownloaded={archiveDownloaded}
                  hasDownload={anySheetDownloaded}
                  downloadActivity={downloadActivity}
                  onOpenDownloads={openDownloads}
                  hikeSummary={hike === null ? null : hikeSummary(hike)}
                  onEditHike={() => setPickingHike(true)}
                  onStartReport={() => setReporting({ step: 'pick' })}
                  onReportFailure={() => setReportingFailure(true)}
                  onOpenModeration={isModerator ? () => setModerating(true) : undefined}
                  queuedReportCount={queuedCount}
                  stuckReports={stuckReports}
                  onRetryReport={handleRetryReport}
                  onDiscardReport={handleDiscardReport}
                />
              )}
            </ErrorBoundary>
          </div>
          <TabBar active={activeTab} onSelect={setActiveTab} />
        </div>
        {downloadsWindow}
      </>
    )
  }

  if (activeTab === 'plan') {
    return (
      <>
        <div className="app__screen">
          <div>
            {/* Its own boundary like More's, and for More's reason: a throw
                in the timeline must not cost the map, and the tab bar
                underneath is the way back. */}
            <ErrorBoundary fallback={() => <ScreenFailed what="This screen" />}>
              <PlanScreen
                plan={plan}
                elevation={elevation}
                kindSheet={
                  planKindOpen ? (
                    <PlanKindSheet
                      networkAvailable={graphIndex !== null}
                      walkedAvailable={false}
                      onPickDayHike={openDayHike}
                      onPickTrip={() => {
                        setPlanKindOpen(false)
                        routeBuilder.openRouteBuilder()
                      }}
                      onPickWalked={() => setPlanKindOpen(false)}
                      onClose={() => setPlanKindOpen(false)}
                    />
                  ) : null
                }
                pois={pois}
                gpsMile={gpsPlanMile}
                units={units}
                pace={pace}
                draftLive={routeBuilder.draftLive || dayHike !== null}
                // WHICH builder holds it, not merely that one does: each
                // room offers a way back to its own draft and its own
                // action otherwise. The day hike wins a tie for the reason
                // the map tap does - the two are exclusive (#997), and this
                // is the same precedence stated once more.
                draftKind={
                  dayHike !== null ? 'day' : routeBuilder.draftLive ? 'trip' : null
                }
                dayListOpen={dayListOpen}
                onDayListOpen={setDayListOpen}
                dayHikes={dayHikeStore.hikes}
                onOpenDayHike={handleOpenDayHike}
                {...(dayHikeReview === null && dayHikeCardNode !== null
                  ? { dayHikeCard: dayHikeCardNode }
                  : {})}
                onStartOnMap={openPlanKind}
                onNewDayHike={openDayHike}
                onNewTrip={routeBuilder.openRouteBuilder}
                networkAvailable={graphIndex !== null}
                gpsAt={gps.status === 'located' ? gps.at : null}
                mode={effectivePlanMode}
                onSwitchMode={handleSwitchPlanMode}
                onChangeTarget={handleChangeTarget}
                onInsertZeroAfter={(index) =>
                  applyPlanEdit((current) => insertZeroAfter(current, index))
                }
                onRemoveDay={(index) =>
                  applyPlanEdit((current) => removeDay(current, index))
                }
                onTogglePinned={(index) =>
                  applyPlanEdit((current) => togglePinned(current, index))
                }
                // The stop a day ends at is boundary index + 1 - the plan's
                // own storage shape (lib/plan.ts).
                onToggleEndResupply={(index) =>
                  applyPlanEdit((current) => toggleResupply(current, index + 1))
                }
                onReplacePlan={handleReplacePlan}
                onDeletePlan={handleDeletePlan}
                tripName={currentTrip?.name ?? null}
                openTripId={tripStore.openId}
                tripCount={tripStore.trips.length}
                hike={currentHike}
                trips={tripStore.trips}
                onOpenTrip={handleOpenTrip}
                hikes={tripStore.hikes}
                groups={tripStore.groups}
                onOpenGroup={setOpenGroupId}
                onPlanGap={routeBuilder.handlePlanGap}
                onPlanFrom={routeBuilder.handlePlanFrom}
                onOpenTrips={() => setTripsOpen(true)}
                {...(targetSheet === null ? {} : { targetSheet })}
                {...(openGroup !== null
                  ? {
                      // A group replaces the switcher rather than stacking
                      // over it - one thing open at a time, the rule every
                      // other sheet in this shell keeps.
                      tripList: (
                        <GroupScreen
                          group={openGroup}
                          trips={tripStore.trips}
                          units={units}
                          onOpenTrip={(id) => {
                            setOpenGroupId(null)
                            handleOpenTrip(id)
                          }}
                          onAddTrip={(tripId) => handleAddToGroup(openGroup.id, tripId)}
                          onRemoveTrip={(tripId) =>
                            handleRemoveFromGroup(openGroup.id, tripId)
                          }
                          onRename={(name) => handleRenameGroup(openGroup.id, name)}
                          onRemove={() => handleRemoveGroup(openGroup.id)}
                          onClose={() => setOpenGroupId(null)}
                        />
                      ),
                    }
                  : {})}
                {...(tripsOpen && openGroup === null
                  ? {
                      tripList: (
                        <TripList
                          trips={tripStore.trips}
                          openId={tripStore.openId}
                          hikes={tripStore.hikes}
                          pois={pois}
                          elevation={elevation}
                          units={units}
                          onOpen={handleOpenTrip}
                          onRename={handleRenameTrip}
                          onRemove={handleRemoveTrip}
                          onNew={() => {
                            setTripsOpen(false)
                            routeBuilder.openRouteBuilder()
                          }}
                          onGroupIntoHike={handleGroupIntoHike}
                          groups={tripStore.groups}
                          onOpenGroup={setOpenGroupId}
                          onNewGroup={handleNewGroup}
                          onClose={() => setTripsOpen(false)}
                        />
                      ),
                    }
                  : {})}
              />
            </ErrorBoundary>
          </div>
          <TabBar active={activeTab} onSelect={setActiveTab} />
        </div>
        {downloadsWindow}
      </>
    )
  }

  if (activeTab === 'volunteer') {
    return (
      <>
        <div className="app__screen">
          <div>
            {/* Its own boundary like More's and Plan's, for their shared
                reason: a throw here must not cost the map, and the tab bar
                underneath is the way back. */}
            <ErrorBoundary fallback={() => <ScreenFailed what="This screen" />}>
              <Volunteer
                contributeConditions={preferences.contribute_conditions}
                onToggleContribute={(next) =>
                  updatePreferences({ contribute_conditions: next })
                }
                passedToday={passedPlacesToday}
                onOpenPlace={handleOpenPassedPlace}
                units={units}
                opportunities={workProjects}
                opportunitiesAsOf={workProjectsGeneratedAt}
                gpsMile={fix?.mile ?? null}
                now={now}
              >
                <VolunteerHours
                  records={hoursRecords}
                  onLog={(draft) => void handleLogHours(draft)}
                  now={now}
                />
              </Volunteer>
            </ErrorBoundary>
          </div>
          <TabBar active={activeTab} onSelect={setActiveTab} />
        </div>
        {downloadsWindow}
      </>
    )
  }

  // The map is both the likeliest thing in this app to throw - WebGL, a GPS
  // watcher, byte-range reads against an archive that can be 1.18 GB, and a
  // pile of MapLibre attach/detach lifecycle - and the worst thing to lose,
  // since it is what someone is looking at when they do not recognise where
  // they are. Its own boundary keeps a map failure from costing More as well,
  // and the tab bar below the fallback is the way back to it.
  //
  // The download window is outside the boundary on purpose. It is the one
  // thing that can put a map back on a phone that has none, so it has to
  // survive the map falling over - and it is already open, over the failure,
  // whenever the map threw while someone was in it.
  return (
    <>
      <ErrorBoundary
        resetKey={activeTab}
        fallback={() => (
          <div className="app__screen">
            <ScreenFailed what="The map" />
            <TabBar active={activeTab} onSelect={setActiveTab} />
          </div>
        )}
      >
        <MapScreen
          // First run (#721). Hides everything but the canvas and makes the
          // whole subtree inert, so the steps below are drawn over the map
          // rather than over a second copy of it.
          entering={entering}
          topoArchiveUrl={CORRIDOR_ARCHIVE_URL}
          trailsUrl={trailsUrl}
          overviewTrailsUrl={overviewTrailsUrl}
          nearbyTrailsUrl={nearbyTrailsUrl}
          background={effectiveBackground(
            preferences.background_source,
            saveData,
            archiveDownloaded,
          )}
          // Same inputs, same module, one line apart - so the strip cannot say
          // the background was overridden while the canvas draws the one that
          // was chosen, which is the mismatch dataSaver.ts exists to stop.
          backgroundOverride={backgroundOverride(
            preferences.background_source,
            saveData,
            archiveDownloaded,
          )}
          // The CHOICE, not the outcome above: the picker in the legend shows
          // and writes what the hiker asked for, and the override note beside it
          // explains any gap between that and what is drawn.
          backgroundChoice={preferences.background_source}
          onChangeBackground={handleChangeBackground}
          // And whether that choice still exists to make (#855). False on a
          // phone with no raster archive, which is every phone that did not
          // take one before the sheet was withdrawn.
          offlineBackgroundAvailable={offlineBackground}
          // The link at the foot of the legend, and the wording it gets. This
          // is the only way to the download from the map now that the tab is
          // gone - which is why it is carried, and not why it is given room.
          onOpenDownloads={openDownloads}
          hasDownload={anySheetDownloaded}
          // The bar on that same link. This is the only place a download in
          // flight is visible from the map, and the map is where a hiker who
          // shut the window is standing.
          downloadActivity={downloadActivity}
          // Narrower than the line above on purpose: the credit corner names
          // the USGS survey only while there are USGS tiles on the phone to
          // draw, and a hiking-sheet-only download has none.
          hasRasterArchive={archiveDownloaded}
          hasNearbyTrails={nearbyTrailsUrl !== null}
          // Decided here rather than on the screen (#334): the same failing
          // source has to reach the downloads window, which opens over the
          // More tab where the map screen is not rendered at all. What the
          // sources reported and what is on the phone mean nothing apart, so
          // they are joined once, in one place, and both screens read the
          // same answer. The DEM is deliberately not an input - an outage
          // there costs relief and contours on a sheet that still draws.
          backgroundProblem={backgroundProblem({
            sources: notDrawing,
            online,
            rasterArchiveDownloaded: archiveDownloaded,
            hikingSheetDownloaded,
          })}
          onLiveSourceHealth={recordSourceHealth}
          belowArchiveZoom={belowArchiveZoom}
          // Only once something has actually gone wrong, not merely because
          // the lines have not arrived yet. A first launch spends a few
          // seconds with no trail on the map in the ordinary case, and a flag
          // that fired during it would be crying wolf on every cold start -
          // which is how a flag stops being read. `dataError` is what turns
          // "not yet" into "not coming".
          trailLinesMissing={!haveTrailLines && dataError !== null}
          // For the opening camera only - MapView keeps it out of the zooms
          // the download has no tiles for.
          archiveZooms={archiveZooms}
          trailName={TRAIL_NAME}
          trailLogo={TRAIL_LOGO}
          // One sentence rather than a number, decided in one place
          // (lib/positionLine.ts): the header used to say "Looking for GPS…"
          // for six different situations, three of which never resolve (#312).
          position={positionLine({
            gps,
            enabled: locationAllowed,
            mile: fix?.mile,
            direction: direction?.direction,
            trailReady: trailIndex !== null,
          })}
          // Which also decides whether the map offers its locate control -
          // attaching it regardless was a second high-accuracy watch and a
          // permission prompt behind this preference's back.
          locationEnabled={locationAllowed}
          closureAhead={closureAhead}
          advisoryAhead={advisoryAhead}
          warningsAhead={warningsAhead}
          closures={closureBandsOnMap}
          corridor={corridorOnMap}
          maintainerLine={maintainerLine}
          disputes={disputedPoints}
          // Three features, three files, three lines (#327). Each spread is
          // exactly the `MapScreenProps` fields that feature owns - a
          // `Pick<>` on the screen's own type, so the compiler refuses a
          // second owner for any of them and a change to one of these
          // features never reaches this file at all.
          {...atc.mapScreen}
          {...line.mapScreen}
          {...workday.mapScreen}
          // The route builder's three, from the same kind of hook (#991).
          {...routeBuilder.mapScreen}
          dayHikeDrawing={dayHikeDrawing}
          // Two things sit OVER the builder's own surface, and both are the
          // shell's: the break-into-days sheet, and the day-hike builder.
          // The precedence between them is unchanged - target, then day
          // hike, then whatever the route builder wanted to show.
          onRouteTap={
            targetRequest !== null ||
            (dayHike === null && routeBuilder.mapScreen.onRouteTap === undefined)
              ? undefined
              : handleMapTap
          }
          routeSheet={
            targetRequest !== null ? (
              targetSheet
            ) : dayHikeReview !== null ? (
              // Frame `1l` as a review, in the same slot the bar held - one
              // surface continuing, with Save as its one primary action.
              dayHikeCardNode
            ) : dayHike !== null ? (
              <DayHikePickBar
                draft={dayHike}
                status={dayHikeStatus ?? { kind: 'empty' }}
                units={units}
                orgLabel={dayHikeOrgLabel}
                // Priced from the graph's own per-edge climb (#1011). Still
                // null - and the bar still prints no time - whenever this
                // phone holds no elevation artifact or the walk crosses an
                // edge nobody measured: ascentFt: 0 would price a climb in
                // Harriman at zero, a flat-ground claim on real ground.
                walkingMinutes={dayHikeWalkingMinutes}
                onUndo={() =>
                  setDayHike((draft) => (draft === null ? draft : undoTap(draft)))
                }
                onCloseLoop={() =>
                  setDayHike((draft) => (draft === null ? draft : loopDraft(draft)))
                }
                onDone={handleDayHikeDone}
                onCancel={handleDayHikeCancel}
                canCloseLoop={dayHike !== null && canCloseLoop(dayHike)}
              />
            ) : (
              // The trailhead door (frame D8) takes the slot only when
              // nothing else wants it - a door must never cover a builder.
              (routeBuilder.mapScreen.routeSheet ?? dayHikesHereNode)
            )
          }
          warnings={warningPins}
          time={now}
          online={online}
          hasGpsFix={gps.status === 'located'}
          lastSyncedAt={lastSyncedAt}
          conditionsAge={conditionsAgeLabel(worstOf(closureState, reportState), now)}
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          onOpenLegend={handleOpenLegend}
          onOpenSearch={() => setSearchOpen(true)}
          legendOpen={legendOpen}
          onCloseLegend={closeLegend}
          searchOpen={searchOpen}
          onCloseSearch={() => setSearchOpen(false)}
          searchablePois={searchablePois}
          onSelectSearchResult={(poi) => {
            const found = pois.find((p) => p.id === poi.id)
            // AND OPEN ITS CARD (§3 of #527). Moving the camera was the whole of
            // what selecting a result did, which broke the moment sites landed:
            // `composeSites` removes a folded member from the source, so
            // searching "Mt. Algo Shelter Privy" centred the map on a coordinate
            // with NO PIN on it - the privy rides the shelter's pin ~42 m away -
            // and then said nothing. The search found it and the map denied it.
            //
            // Selecting it is what makes the card open, and the card is where
            // the answer is: PoiCard opens on whichever part the shell asked for
            // (`shown = site.find(...) ?? poi`), so this lands on the PRIVY's
            // chip with the rest of the site beside it, rather than on the
            // shelter. Nothing here special-cases a member - passing the id that
            // was searched for is what makes it right.
            handleSelectPoi(poi.id)
            // Centring alone left the zoom wherever it was, which from the opening
            // view of the whole corridor meant tapping a result moved the map by a
            // few pixels and looked like nothing happened at all.
            // The miss is unreachable, and kept for the type checker: every result
            // the sheet can offer was built by mapping this same `pois` array, and
            // the sheet only exists on the map screen, so `found` is always there
            // and `map` is never null. Ignored for coverage rather than covered -
            // no input produces a search result pointing at a POI the app does not
            // hold, or a tap on a sheet that is not rendered.
            /* v8 ignore start */
            if (found !== undefined && map !== null) {
              map.jumpTo({
                center: [found.lon, found.lat],
                zoom: Math.max(map.getZoom(), SEARCH_RESULT_ZOOM),
              })
            }
            /* v8 ignore stop */
            setSearchOpen(false)
          }}
          bbox={bbox}
          // Which of the four the ribbon is showing is lib/ribbonView.ts's
          // decision, made above. The LANES follow it (#913): one window for
          // both, from that same decision, so a pin always sits under the
          // ground it names - and dropped entirely, rather than re-windowed
          // or emptied, on the domains where a pill would stand for more
          // trail than a place (lib/ribbonView.ts has the arithmetic).
          elevation={ribbon}
          chart={desktopChart}
          waypoints={waypoints}
          onRibbonBackToMe={gps.status === 'located' ? handleBackToMe : undefined}
          viewportPoints={viewportPoints}
          ghostedTrailsDrawn={ghostedTrailsDrawn}
          drawnCounts={drawnPoiCounts}
          belowPoiZoom={belowPoiZoom}
          {...filters.mapScreen}
          selectedPoi={selectedPoi}
          selectedSite={selectedSite}
          removedPoiCard={
            removedPoi === null ? undefined : (
              <RemovedPoiCard
                tombstone={removedPoi.tombstone}
                successorName={removedPoi.successor?.name}
                onOpenSuccessor={
                  removedPoi.successor === undefined
                    ? undefined
                    : () => handleSelectPoi(removedPoi.successor?.id ?? null)
                }
                onClose={handleClosePoi}
              />
            )
          }
          noteContext={noteContext}
          pinCondition={pinCondition}
          onSelectPoi={handleSelectPoi}
          onClosePoi={handleClosePoi}
          // WIREFRAMES.md §1.5: zoom buttons are web-only. Nothing was passing
          // this, so `showZoomButtons` sat on its default of false everywhere and
          // a browser with a mouse had no visible way to zoom at all.
          showZoomButtons={finePointer}
          // The canvas is WebGL and cannot read the `data-theme` attribute the
          // rest of the app follows, so the resolved answer goes down as a prop
          // - see map/style.ts's attachMapAppearance. The style, red-light and
          // detail preferences ride the same road for the same reason.
          theme={resolvedTheme}
          themeChoice={preferences.theme}
          mapStyle={preferences.map_style}
          redLight={preferences.red_light_enabled}
          detail={preferences.layer_detail_level}
          // And the same road for the same reason: the contour interval, the
          // summit labels, the scale bar and the elevation ribbon's three
          // labels all answer from this one value (#619). The machinery on the
          // map side has been there since the contours were built - what was
          // missing was anybody passing the preference into it.
          units={units}
          // The corridor is the opening view only. Once there is a camera to put
          // back, it wins: `bounds` would otherwise re-frame the entire trail
          // every time the map screen came back from another tab.
          center={camera?.center}
          zoom={camera?.zoom}
          bounds={camera === null ? CORRIDOR_BOUNDS : undefined}
          boundsPadding={entryFitPadding}
          onViewportChange={handleViewportChange}
          onMapReady={handleMapReady}
        />
      </ErrorBoundary>
      {/* The entry steps, over the map screen rather than instead of it
          (#721). A sibling of the boundary, not a child: they are the way out
          of first run, so a map that throws mid-onboarding must not take them
          down with it - the same argument that keeps the download window
          outside it.

          Last in the fragment, so they stack over everything the map screen
          draws. There is nothing else to compete with them - `entering` has
          hidden the chrome and made the whole screen inert - and the download
          window below cannot be open yet, because the only thing that opens it
          is finishing these steps. */}
      {entering && <Onboarding onComplete={handleOnboardingComplete} />}
      {downloadsWindow}
    </>
  )
}

export default App
