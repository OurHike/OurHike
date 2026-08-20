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
import { ReportForm, type ReportFormSubmission } from './screens/ReportForm'
import { ReportTypePicker, type ReportTypeId } from './screens/ReportTypePicker'
import { CORRIDOR_ARCHIVE_URL } from './map/protocol'
import { DATA_CONFIGURED } from './lib/config'
import { loadPreferences, savePreferences } from './lib/preferences'
import {
  hiddenTypesFrom,
  onlyType,
  showAllTypes,
  toggleType,
} from './lib/waypointVisibility'
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
import {
  locateOnTrail,
  mileOnTrail,
  trailPointAtMile,
  trailSlice,
} from './lib/trailPosition'
import type { StoredPoi } from './lib/trailData'
import { useTrailData } from './lib/useTrailData'
import { ribbonSamples, ribbonWindow } from './lib/elevationProfile'
import {
  anchoredClientMile,
  anchoredMile,
  insertRoutePoint,
  legFigures,
  mileAtWalkingMinutes,
  routeDirection,
  routeLegs,
  type MileAnchor,
} from './lib/route'
import { DEFAULT_WALKING_HOURS, nearestStopBeyond, type ViaStop } from './lib/dayPlanner'
import { RouteEntranceSheet, type EntranceEnd } from './chrome/RouteEntranceSheet'
import { RouteStopsPanel, type RouteLegDisplay } from './chrome/RouteStopsPanel'
import { RouteStopPicker, type RouteStopChoice } from './chrome/RouteStopPicker'
import { RouteMapPickBar } from './chrome/RouteMapPickBar'
import type { RouteDrawing } from './map/routeLayers'
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
import { nearestStop } from './lib/cascade'
import {
  hikeFromTrips,
  hikeOfTrip,
  recordedPlan,
  type HikePiece,
  type PlaceRef,
} from './lib/hikes'
import { GroupScreen } from './screens/GroupScreen'
import { TripList } from './screens/TripList'
import { PlanScreen } from './screens/Plan'
import { PlanTargetSheet } from './screens/PlanTargetSheet'
import { stopLabel } from './lib/planDisplay'
import { upcomingClimb } from './lib/upcomingClimb'
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
import {
  atcBandCandidates,
  atcPointNotices,
  atcUpdateBanner,
  atcUpdateForBandId,
  atcUpdateLanes,
  type RankedAtcUpdate,
} from './lib/atcUpdates'
import { atcUpdatePoints } from './map/atcUpdateLayers'
import {
  atcAlertsSince,
  readAtcAlertSilence,
  writeAtcAlertSilence,
} from './lib/atcAlertsBanner'
import { AtcUpdateSheet } from './chrome/AtcUpdateSheet'
import { POI_PIN_MIN_ZOOM } from './map/poiLayers'
import { ClubSheet } from './chrome/ClubSheet'
import { LineSheet } from './chrome/LineSheet'
import { buildClubDetail, type ClubDetail } from './lib/clubDetail'
import { HighlightSheet } from './chrome/HighlightSheet'
import { buildHighlightDetail, type HighlightDetail } from './lib/highlightDetail'
import { readStoredPace, writeStoredPace, type PaceProfile } from './lib/pace'
import {
  MAX_FIX_GAP_MILES,
  readWalked,
  recordStep,
  writeWalked,
  type MileRange,
} from './lib/walkedMiles'
import { clubRunAtMile, clubTimeline } from './lib/clubSections'
import { buildLineDetail, type LineDetail } from './lib/lineDetail'
import type { TappedLine } from './map/lineTaps'
import { AtcNoticeList } from './chrome/AtcNoticeList'
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
const notYet = () => undefined

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

/**
 * A dropped route point (#755), on both mile scales at once.
 *
 * `mile` is the pipeline's axis - what every figure is computed and printed
 * on. `clientMile` is the centerline index's own scale, kept solely because
 * drawing goes through trailSlice/trailPointAtMile, which live there. See
 * lib/route.ts's header for why the two are never compared.
 *
 * `seq` is drop order, for undo: an inserted point lands mid-array, so "the
 * last point I dropped" and "the last point of the route" are different
 * points, and undo means the former.
 */
interface RouteDraftStop {
  mile: number
  /** Null for a stop no tap and no anchor could place on the client scale -
   *  it still plans and prices honestly (those run on `mile`), it just
   *  cannot be drawn. */
  clientMile: number | null
  name?: string
  poiId?: string
}

/**
 * The route builder's two screens (the chosen "route by destination" flow):
 * the ENTRANCE asks where from and how far or how long; "Use this stretch"
 * lands the resolved pair on the EDITOR, where every stop is a field and
 * destinations join between the ends. The draft survives tab switches -
 * the Plan tab reopens the editor rather than tolling the entrance again -
 * and dies only at the close button or when a plan is laid out of it.
 */
type RouteDraftState =
  | {
      phase: 'entrance'
      start: RouteDraftStop | null
      /** The far end when the hiker NAMED one (#804). With both ends fixed
       *  the entrance stops asking how far and states it. */
      fixedEnd: RouteDraftStop | null
      ask: 'far' | 'long'
      miles: number
      days: number
      south: boolean
    }
  | { phase: 'editor'; stops: RouteDraftStop[] }

/** Which slot of the draft a picked stop lands in. */
/** A place the app already knows, as a stop the route builder can open on.
 *  The client mile is re-derived from the anchors rather than carried,
 *  because a PlaceRef only ever holds the pipeline's axis (lib/hikes.ts). */
function draftStopFor(place: PlaceRef, anchors: readonly MileAnchor[]): RouteDraftStop {
  return {
    mile: place.mile,
    clientMile: anchoredClientMile(place.mile, anchors),
    ...(place.name === undefined ? {} : { name: place.name }),
    ...(place.poiId === undefined ? {} : { poiId: place.poiId }),
  }
}

type StopSlot =
  | { kind: 'start' }
  | { kind: 'end' }
  | { kind: 'replace'; index: number }
  | { kind: 'add' }

/** The stop picker, when it is up: the slot being filled, whether the hiker
 *  went on to the map to fill it, and whether the last map tap was refused
 *  (off the corridor - cleared by the next accepted tap). */
type StopPickState = { slot: StopSlot; onMap: boolean; refusedTap: boolean }

// Sign-in is its own flow rather than another step of the reporting one,
// because it is reachable from two places that want different things back:
// finishing a contribution, and the account row in Settings. Conflating them
// would mean the Settings path inheriting the report flow's copy, which
// promises that a report is already saved - true in one case and not the
// other.
type AuthFlowState = null | { screen: 'choose' | 'email'; afterReport: boolean }

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
  // Derived from the STORED preference rather than held in a `useState` (#530).
  // `waypoint_types_shown` had been declared in the preferences model, in the
  // backend schema and in IDENTITY_AND_PRIVACY.md's canonical model since long
  // before this control, and was read by nothing - so hiding privies lasted
  // until the next reload and never reached an account.
  const hiddenTypes = useMemo(
    () => hiddenTypesFrom(preferences.waypoint_types_shown),
    [preferences.waypoint_types_shown],
  )
  // The legend's "Verified?" filter. Off by default: an unconfirmed spring is
  // still the best information anyone has about that spring, and a first run
  // that quietly withheld it would be the app deciding for a hiker what they
  // are allowed to know about. Ephemeral, exactly like hiddenTypes - both are
  // #530's problem, not this one's.
  const [verifiedOnly, setVerifiedOnly] = useState(false)
  const [bbox, setBbox] = useState<BoundingBox>(EMPTY_BBOX)

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
  const [authFlow, setAuthFlow] = useState<AuthFlowState>(null)
  /**
   * The route being built (#755), or null when the builder is closed. Held
   * here and not persisted: a draft is a sketch, and the thing worth keeping
   * - the plan - is what "Break into days" produces from it (#756).
   */
  const [routeDraft, setRouteDraft] = useState<RouteDraftState | null>(null)
  /** The last trail tap the entrance refused as too far off the corridor -
   *  cleared by the next accepted one (#801). */
  const [entranceRefusedTap, setEntranceRefusedTap] = useState(false)
  /** The stop picker over the draft, or null while every field rests. */
  const [stopPick, setStopPick] = useState<StopPickState | null>(null)
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
  const [selectedAtcBandId, setSelectedAtcBandId] = useState<string | null>(null)
  /** The tapped trail line's published facts, or null (#134). The map
   *  reports them (map/lineTaps.ts); what they mean - the spur record, the
   *  destination's name - is resolved here, where the data is. */
  const [selectedLine, setSelectedLine] = useState<TappedLine | null>(null)
  const [selectedHighlightId, setSelectedHighlightId] = useState<string | null>(null)
  /**
   * Whether the full list of ATC notices is open.
   *
   * Separate from `selectedAtcBandId` rather than a third state of it. The two
   * answer different questions - "which one did they tap" and "did they ask to
   * read all of them" - and a hiker who opens the list, taps a band behind it
   * and closes that sheet should find the list still where they left it.
   */
  const [atcNoticesOpen, setAtcNoticesOpen] = useState(false)
  /** The newest ATC edit the hiker has already silenced on this phone, or
   *  null - lib/atcAlertsBanner.ts's watermark, read once at mount and
   *  written back every time silencing happens. */
  const [atcAlertSilence, setAtcAlertSilence] = useState<Date | null>(() =>
    readAtcAlertSilence(),
  )

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
    highlights,
    trailsUrl,
    overviewTrailsUrl,
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
   * A no-op on every closure today — nothing writes closure geometry yet, so
   * `projectClosures` returns the array it was given and these memos do not
   * re-run. It is here so that the day a closure IS authored with geometry,
   * the projection is already the path rather than a second change to make.
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
  // What a reload would destroy right now (#311). Every one of these is React
  // state that no storage carries: a report being written, a window or sheet
  // the hiker opened, a sign-in half done. The update waits for all of them to
  // be put away AND for the page to be hidden - see lib/useAppUpdate.ts.
  //
  // The camera is deliberately NOT in this list. It is kept across the reload
  // instead (lib/cameraMemory.ts), because holding an update for as long as
  // someone is looking at a map would hold it for the whole hike.
  const updateWouldCost =
    reporting !== null ||
    authFlow !== null ||
    downloadsOpen ||
    legendOpen ||
    searchOpen ||
    selectedPoiId !== null
  useAppUpdate(UPDATE_CHECK_MS, { hold: updateWouldCost })

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
   * mean the trail itself is obstructed become a band, because a barred band
   * says "go around" and a notice about a closed car park does not. The rest
   * keep the banner, exactly as an over-long advisory does.
   */
  const atcBandsOnMap = useMemo(() => {
    if (trailIndex === null) return []
    return closureBands(atcBandCandidates(atcUpdates), trailIndex)
  }, [atcUpdates, trailIndex])

  /**
   * The same notices that name one mile rather than a stretch, as dots.
   *
   * Not filtered by `obstructsTheTrail`, unlike the bands. A dot makes no
   * claim about passability - it says the ATC has posted something here - so a
   * bear warning and a closed shelter both belong on the map, and neither is
   * the barrier a band would have made them.
   */
  const atcPointsOnMap = useMemo(() => {
    if (trailIndex === null) return []
    return atcUpdatePoints(atcPointNotices(atcUpdates), trailIndex)
  }, [atcUpdates, trailIndex])

  /** The tapped update, resolved from the band id the map reported. */
  const selectedAtcUpdate = useMemo(() => {
    if (selectedAtcBandId === null) return null
    return atcUpdateForBandId(atcUpdates, selectedAtcBandId)
  }, [atcUpdates, selectedAtcBandId])

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
  const atcDrawnIds = useMemo(
    () =>
      new Set<string>([
        ...atcBandsOnMap.map((band) => band.id),
        ...atcPointsOnMap.map((point) => point.id),
      ]),
    [atcBandsOnMap, atcPointsOnMap],
  )

  /**
   * What the bottom "new alerts" banner has to say, or null (#687).
   *
   * Independent of every filter above - `atcBandCandidates`, `atcPointNotices`
   * and the lane functions all decide what belongs on the MAP or in the
   * header's one line, and none of that is "has ATC posted something
   * recently". An update the map cannot place and the header will never
   * mention (behind the hiker, over the band ceiling) is still new, and
   * still worth this banner - `chrome/AtcNoticeList.tsx` is the same
   * argument for the full list.
   */
  const newAtcAlerts = useMemo(
    () => atcAlertsSince(atcUpdates, now, atcAlertSilence),
    [atcUpdates, now, atcAlertSilence],
  )

  /**
   * Marks every currently-new edit as seen. Wired to both the bottom
   * banner's own dismiss and to opening the full list (onOpenAtcNotices
   * below) - whichever way a hiker actually looked, the banner has done its
   * job and should not return until ATC posts something after this mark.
   */
  const silenceAtcAlerts = useCallback(() => {
    if (newAtcAlerts === null) return
    writeAtcAlertSilence(newAtcAlerts.newestAt)
    setAtcAlertSilence(newAtcAlerts.newestAt)
  }, [newAtcAlerts])

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
   * The tapped line's sheet content (#134), resolved here for the reason
   * `selectedPoi` is: the map reports what was drawn, and the shell is what
   * holds the spur records, the POI a spur leads to, and the hiker's units.
   */
  const selectedLineDetail: LineDetail | null = useMemo(() => {
    if (selectedLine === null) return null
    return buildLineDetail(selectedLine, spurs, pois, units, TRAIL_NAME, pace)
  }, [selectedLine, spurs, pois, units, pace])

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

  const selectedClubDetail: ClubDetail | null = useMemo(() => {
    if (!belowSeam || selectedLine === null || trailIndex === null) return null
    // The tapped point is already snapped to the line (map/lineTaps.ts), so
    // this is asking "which mile is that vertex" rather than "is the thumb
    // near the trail" - which at this zoom it need not be.
    const mile = mileOnTrail(trailIndex, {
      lon: selectedLine.at[0],
      lat: selectedLine.at[1],
    })
    if (mile === null) return null
    return buildClubDetail(clubSections, clubRuns, mile, units, walked)
  }, [belowSeam, selectedLine, trailIndex, clubSections, clubRuns, units, walked])

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

  /**
   * The tapped highlight's sheet content (#858).
   *
   * Resolved here for the reason the club sheet is: the map reports which
   * mark was touched, and the shell is what holds the records, the elevation
   * profile the numbers are derived from, the hiker's units and what they
   * have walked.
   */
  const selectedHighlightDetail: HighlightDetail | null = useMemo(() => {
    if (selectedHighlightId === null) return null
    const highlight = highlights.find((entry) => entry.id === selectedHighlightId)
    if (highlight === undefined) return null
    return buildHighlightDetail(highlight, elevation, units, walked, pace)
  }, [selectedHighlightId, highlights, elevation, units, walked, pace])

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
  const ribbon = useMemo(() => {
    if (elevation === null || fix === null) return undefined

    const window = ribbonWindow(elevation, fix.mile, direction?.direction)
    const samples = ribbonSamples(elevation, window)
    // A window that is entirely DEM coverage gap. Rare, and the honest state
    // is the same as having no profile at all.
    if (samples.length === 0) return undefined

    return {
      window,
      props: {
        samples,
        currentMile: fix.mile,
        upcomingClimb: upcomingClimb(elevation, window, fix.mile, direction?.direction),
      },
    }
  }, [elevation, fix, direction])

  // Built from searchablePois rather than from `pois` again, because that memo
  // has already paid for the locateOnTrail() call over every POI and the lanes
  // want exactly the mile it produced. A POI the centerline index cannot place
  // has no position on a mile axis, so it is left out of the lanes rather than
  // guessed onto one.
  const waypoints = useMemo(() => {
    if (ribbon === undefined) return undefined

    return {
      points: searchablePois.flatMap((poi) =>
        poi.mile === undefined ? [] : [{ id: poi.id, type: poi.type, mile: poi.mile }],
      ),
      startMile: ribbon.window.startMile,
      endMile: ribbon.window.endMile,
      // The lanes' copy of the tier styling (#759's "highest-value surface"):
      // the same roll-up the pin rings read, through the same policy module.
      stalenessFor: (poiId: string, poiType: string) =>
        stalenessPresentation(
          poiType,
          stalenessTier(noteRollups.get(poiId)?.lastConfirmedAt ?? null),
        ),
    }
  }, [ribbon, searchablePois, noteRollups])

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
   * The entrance's resolved far end: the raw answer to "how far" (start plus
   * the asked-for miles) or "how long" (the reach of days x the default
   * walking target, priced by mileAtWalkingMinutes so it cannot disagree
   * with the card), SNAPPED to the nearest real place to sleep past the
   * start. The bare clamped mile when no such place lies that way - shown
   * as exactly that - and null when even that leaves no trail.
   */
  const entranceEnd = useMemo(() => {
    if (routeDraft === null || routeDraft.phase !== 'entrance') return null
    if (routeDraft.start === null) return null
    const { start, ask, miles, days, south } = routeDraft

    const raw =
      ask === 'long' && elevation !== null
        ? mileAtWalkingMinutes(
            elevation,
            start.mile,
            days * DEFAULT_WALKING_HOURS * 60,
            south ? 'SOBO' : 'NOBO',
            pace,
          )
        : start.mile + (south ? -miles : miles)
    const reachMi = Math.abs(raw - start.mile)

    const snapped = nearestStopBeyond(pois, start.mile, raw)
    if (snapped !== null) {
      return {
        reachMi,
        kind: snapped.kind === 'terminus' ? undefined : snapped.kind,
        stop: {
          mile: snapped.mile,
          clientMile: anchoredClientMile(snapped.mile, mileAnchors),
          ...(snapped.name === undefined ? {} : { name: snapped.name }),
          ...(snapped.poiId === undefined ? {} : { poiId: snapped.poiId }),
        } satisfies RouteDraftStop,
      }
    }

    let low = Infinity
    let high = -Infinity
    for (const choice of routeStopChoices) {
      if (choice.mile < low) low = choice.mile
      if (choice.mile > high) high = choice.mile
    }
    if (low > high) return null
    const clamped = Math.min(high, Math.max(low, raw))
    if (clamped === start.mile) return null
    return {
      reachMi,
      kind: undefined,
      stop: {
        mile: clamped,
        clientMile: anchoredClientMile(clamped, mileAnchors),
      } satisfies RouteDraftStop,
    }
  }, [routeDraft, elevation, pois, routeStopChoices, mileAnchors])

  /**
   * A door's answer lands in the slot being filled. The one resolver every
   * door funnels through: a stop born from arithmetic (a snap, a distance)
   * arrives without a client mile and gets one from the inverse anchor
   * here, so the drawing below never has to know where a stop came from.
   */
  const applyPickedStop = useCallback(
    (picked: {
      mile: number
      clientMile?: number | null
      name?: string
      poiId?: string
    }) => {
      if (stopPick === null) return
      const slot = stopPick.slot
      const stop: RouteDraftStop = {
        mile: picked.mile,
        clientMile: picked.clientMile ?? anchoredClientMile(picked.mile, mileAnchors),
        ...(picked.name === undefined ? {} : { name: picked.name }),
        ...(picked.poiId === undefined ? {} : { poiId: picked.poiId }),
      }
      setRouteDraft((draft) => {
        if (draft === null) return draft
        if (slot.kind === 'start') {
          return draft.phase === 'entrance' ? { ...draft, start: stop } : draft
        }
        if (slot.kind === 'end') {
          return draft.phase === 'entrance' ? { ...draft, fixedEnd: stop } : draft
        }
        if (draft.phase !== 'editor') return draft
        if (slot.kind === 'add') {
          // Trail order IS least-added-distance order on a monotonic route,
          // so the tap builder's placement rule serves the add row unchanged
          // - between the ends when the stop is between them, extending the
          // route when it is past one.
          return { ...draft, stops: insertRoutePoint(draft.stops, stop) }
        }
        // A replacement that lands exactly on another stop's mile would fold
        // two stops into a zero-length leg - refused the way insertRoutePoint
        // refuses a re-tap: nothing changes.
        if (draft.stops.some((s, i) => i !== slot.index && s.mile === stop.mile)) {
          return draft
        }
        return {
          ...draft,
          stops: draft.stops.map((s, i) => (i === slot.index ? stop : s)),
        }
      })
      setStopPick(null)
    },
    [stopPick, mileAnchors],
  )

  // A map tap while the picker's map door is open (and only then - one tap,
  // one interpreter). Snapped by the centerline index - the one job
  // locateOnTrail keeps under HIKE_PLANNING.md Finding 2 - then carried onto
  // the pipeline's axis by the nearest anchor, so every figure slices the
  // profile at miles that mean what the display says. A tap the index
  // refuses (>3 mi off the corridor) sets a flag the bar explains, rather
  // than silently doing nothing.
  // eslint-disable-next-line react-hooks/exhaustive-deps -- listed below
  const handleStopMapTap = useCallback(
    (at: { lon: number; lat: number }) => {
      if (trailIndex === null) return
      // NO BUTTON FIRST (#801). With the entrance open and no picker over
      // it, a tap on the trail sets the START - there is nothing else this
      // screen is choosing, so nothing needs disambiguating, and a start
      // already set is moved rather than a question being asked.
      if (stopPick === null) {
        if (routeDraft === null || routeDraft.phase !== 'entrance') return
        const located = locateOnTrail(trailIndex, at)
        if (located === null) {
          setEntranceRefusedTap(true)
          return
        }
        setEntranceRefusedTap(false)
        const clientMile = located.mile
        const snapped = nearestStop(
          pois,
          anchoredMile(clientMile, mileAnchors) ?? clientMile,
        )
        setRouteDraft((draft) =>
          draft === null || draft.phase !== 'entrance'
            ? draft
            : {
                ...draft,
                start: {
                  mile:
                    snapped?.mile ?? anchoredMile(clientMile, mileAnchors) ?? clientMile,
                  clientMile,
                  ...(snapped?.name === undefined ? {} : { name: snapped.name }),
                  ...(snapped?.poiId === undefined ? {} : { poiId: snapped.poiId }),
                },
              },
        )
        return
      }
      if (!stopPick.onMap) return
      const located = locateOnTrail(trailIndex, at)
      if (located === null) {
        setStopPick({ ...stopPick, refusedTap: true })
        return
      }
      const clientMile = located.mile
      // The ?? is totality, not a path: without anchors the entrance has
      // already refused, so no tap reaches here to need the fallback.
      applyPickedStop({
        mile: anchoredMile(clientMile, mileAnchors) ?? clientMile,
        clientMile,
      })
    },
    [stopPick, trailIndex, mileAnchors, applyPickedStop, routeDraft, pois],
  )

  const handleRouteCancel = useCallback(() => {
    setRouteDraft(null)
    setStopPick(null)
  }, [])

  // What the canvas draws for the draft: the centerline's own geometry
  // between consecutive stops (trailSlice never bridges a part gap), and
  // the stops snapped back onto the line. Client miles throughout - this is
  // the drawing, and the drawing is the one consumer that scale exists for.
  // On the entrance the stretch grows as the slider moves: start alone,
  // then start to the resolved end.
  const routeDrawing: RouteDrawing | null = useMemo(() => {
    if (routeDraft === null || trailIndex === null) return null
    const stops: RouteDraftStop[] =
      routeDraft.phase === 'editor'
        ? routeDraft.stops
        : routeDraft.start === null
          ? []
          : entranceEnd === null
            ? [routeDraft.start]
            : [routeDraft.start, entranceEnd.stop]
    return {
      legs: stops.slice(1).flatMap((to, i) => {
        const from = stops[i]
        if (from.clientMile === null || to.clientMile === null) return []
        return [trailSlice(trailIndex, from.clientMile, to.clientMile)]
      }),
      points: stops.flatMap((stop, i) => {
        if (stop.clientMile === null) return []
        const at = trailPointAtMile(trailIndex, stop.clientMile)
        if (at === null) return []
        const role: 'start' | 'via' | 'end' =
          i === 0 ? 'start' : i === stops.length - 1 ? 'end' : 'via'
        return [{ lon: at[0], lat: at[1], role }]
      }),
    }
  }, [routeDraft, entranceEnd, trailIndex])

  // The editor's figures, on the pipeline miles. Null climb and time on a
  // download with no profile: the distance is still a fact, and the surface
  // says why the rest is missing rather than printing a time that quietly
  // ignored every climb (see RouteLegDisplay).
  const routeLegDisplays: RouteLegDisplay[] = useMemo(() => {
    if (routeDraft === null || routeDraft.phase !== 'editor') return []
    return routeLegs(routeDraft.stops).map(({ from, to }) =>
      elevation === null
        ? {
            distanceMi: Math.abs(to.mile - from.mile),
            ascentFt: null,
            descentFt: null,
            minutes: null,
          }
        : legFigures(elevation, from.mile, to.mile, pace),
    )
  }, [routeDraft, elevation])

  // Opening the builder is a map act: it lands on the trail tab with
  // everything else closed - the same one-thing-open-at-a-time rule the
  // legend, the search and the waypoint card already keep between them.
  // A draft already in progress reopens where it stood - the entrance is
  // for starting, never a toll gate on the way back to your own route.
  const openRouteBuilderFrom = useCallback(
    (start: RouteDraftStop | null, south?: boolean) => {
      setActiveTab('trail')
      setSelectedPoiId(null)
      setLegendOpen(false)
      setSearchOpen(false)
      setTargetRequest(null)
      setRouteDraft((draft) => {
        if (draft === null) {
          return {
            phase: 'entrance',
            start,
            fixedEnd: null,
            // The mockup's own opening answers - a mid-length section,
            // walked the way most of this trail is walked. Both are one
            // drag from anything else.
            ask: 'far',
            miles: 45,
            days: 3,
            south: south ?? false,
          }
        }
        // A suggested start fills an entrance that has none yet, and never
        // overwrites a route the hiker is already editing: their own draft
        // outranks a starting point this app proposed.
        if (start === null || draft.phase !== 'entrance') return draft
        return { ...draft, start, ...(south === undefined ? {} : { south }) }
      })
    },
    [],
  )

  const openRouteBuilder = useCallback(
    () => openRouteBuilderFrom(null),
    [openRouteBuilderFrom],
  )

  /**
   * Start a route at the beginning of a stretch nobody has walked (#790's
   * gap row).
   *
   * The gap's low end and nothing else: how far, which way and where it
   * really ends are the entrance's questions, and answering them from the
   * gap's own length would put a 554-mile "trip" in front of a hiker who
   * asked to plan a week. Choosing WHICH gap and how much of it fits the
   * days somebody has is **#791 - What's left**.
   */
  const handlePlanGap = useCallback(
    (gap: Extract<HikePiece, { kind: 'gap' }>) => {
      // A gap row starts at its low end, walking on up the trail. "What's
      // left" (#791) is where BOTH ends are offered, because that is the
      // screen where choosing between them is the question being asked.
      openRouteBuilderFrom(draftStopFor(gap.from, mileAnchors), false)
    },
    [openRouteBuilderFrom, mileAnchors],
  )

  /**
   * Plan from one end of a gap, walking toward the other (#791).
   *
   * The direction is DERIVED from the pair rather than stored anywhere: a
   * hiker who picked the high end is walking south, which is exactly what
   * the entrance's own toggle means. Nothing new is kept, and a
   * flip-flopper's third trip going the other way needs no new concept.
   */
  const handlePlanFrom = useCallback(
    (start: PlaceRef, toward: PlaceRef) => {
      openRouteBuilderFrom(draftStopFor(start, mileAnchors), toward.mile < start.mile)
    },
    [openRouteBuilderFrom, mileAnchors],
  )

  /** One field of the entrance changes; everything else stands. */
  const patchEntrance = useCallback(
    (patch: Partial<Extract<RouteDraftState, { phase: 'entrance' }>>) => {
      setRouteDraft((draft) =>
        draft !== null && draft.phase === 'entrance' ? { ...draft, ...patch } : draft,
      )
    },
    [],
  )

  const handlePickStart = useCallback(
    (door: 'gps' | 'search' | 'map') => {
      if (door === 'gps') {
        if (fix === null || gpsPlanMile === null) return
        const start: RouteDraftStop = { mile: gpsPlanMile, clientMile: fix.mile }
        setRouteDraft((draft) =>
          draft !== null && draft.phase === 'entrance' ? { ...draft, start } : draft,
        )
        return
      }
      setStopPick({ slot: { kind: 'start' }, onMap: door === 'map', refusedTap: false })
    },
    [fix, gpsPlanMile],
  )

  const handleUseStretch = useCallback(() => {
    if (routeDraft === null || routeDraft.phase !== 'entrance') return
    if (routeDraft.start === null) return
    // A named end wins over a resolved one: the hiker said where they are
    // going, so nothing snaps it to whatever the "how far" answer reached
    // (#804).
    const end = routeDraft.fixedEnd ?? entranceEnd?.stop ?? null
    if (end === null) return
    setRouteDraft({ phase: 'editor', stops: [routeDraft.start, end] })
  }, [routeDraft, entranceEnd])

  const handleEditStop = useCallback((index: number) => {
    setStopPick({ slot: { kind: 'replace', index }, onMap: false, refusedTap: false })
  }, [])

  const handleAddStop = useCallback(() => {
    setStopPick({ slot: { kind: 'add' }, onMap: false, refusedTap: false })
  }, [])

  // Only a destination between the ends can be removed - a route needs its
  // ends, and either end is changed by picking a different stop instead.
  const handleRemoveStop = useCallback(() => {
    if (stopPick === null || stopPick.slot.kind !== 'replace') return
    const index = stopPick.slot.index
    setRouteDraft((draft) => {
      if (draft === null || draft.phase !== 'editor') return draft
      if (index <= 0 || index >= draft.stops.length - 1) return draft
      return { ...draft, stops: draft.stops.filter((_, i) => i !== index) }
    })
    setStopPick(null)
  }, [stopPick])

  /** The stop before the slot being filled - what the picker's distance
   *  door measures from. The add row measures from the current end,
   *  extending the route the way "and then on to..." extends a hike;
   *  a stop the least-added-distance placement then puts BETWEEN the ends
   *  lands there instead, same rule either way. */
  const pickPrevious = useMemo(() => {
    if (stopPick === null || routeDraft === null) return null
    // The entrance's own two slots measure from nothing: a start has no
    // previous stop, and a named end is a destination rather than a
    // distance from one (#804).
    if (stopPick.slot.kind === 'start' || stopPick.slot.kind === 'end') return null
    if (routeDraft.phase !== 'editor') return null
    const stops = routeDraft.stops
    const anchor =
      stopPick.slot.kind === 'add'
        ? stops[stops.length - 1]
        : stopPick.slot.index > 0
          ? stops[stopPick.slot.index - 1]
          : null
    if (anchor === null || anchor === undefined) return null
    return { mile: anchor.mile, label: stopLabel(anchor) }
  }, [stopPick, routeDraft])

  /** Which way the distance door walks: the draft's own direction. */
  const pickSouth = useMemo(() => {
    if (routeDraft === null) return false
    if (routeDraft.phase === 'entrance') return routeDraft.south
    return routeDirection(routeDraft.stops) === 'SOBO'
  }, [routeDraft])

  const handleBreakIntoDays = useCallback(() => {
    if (routeDraft === null || routeDraft.phase !== 'editor') return
    if (routeDraft.stops.length < 2) return
    setTargetRequest({
      route: routeDraft.stops.map(({ mile, name, poiId }) => ({
        mile,
        ...(name === undefined ? {} : { name }),
        ...(poiId === undefined ? {} : { poiId }),
      })),
    })
  }, [routeDraft])

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
      setRouteDraft(null)
      setActiveTab('plan')
    },
    [targetRequest, applyTripStore],
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
      setActiveTab('plan')
    },
    [applyTripStore],
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
  /**
   * Keep the drafted stretch as ground already walked (#789).
   *
   * The same two ends the builder just described, said in the past tense -
   * which is why this door is here rather than behind a second way to name
   * two places. Every day in the record is walked on arrival, so it feeds
   * the roll-up and #791's gaps exactly as a walked trip does; `recorded`
   * marks the provenance, so no screen prints a remembered 300-mile stretch
   * as if somebody walked it in a day.
   */
  const handleRecordWalked = useCallback(() => {
    if (routeDraft === null || routeDraft.phase !== 'editor') return
    if (routeDraft.stops.length < 2) return
    const stops = routeDraft.stops.map(({ mile, name, poiId }) => ({
      mile,
      ...(name === undefined ? {} : { name }),
      ...(poiId === undefined ? {} : { poiId }),
      resupply: false,
    }))
    const plan = recordedPlan(stops)
    applyTripStore((store) => addTrip(store, plan, undefined, true))
    setRouteDraft(null)
    setStopPick(null)
    setActiveTab('plan')
  }, [routeDraft, applyTripStore])

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

  const updatePreferences = useCallback((patch: Partial<UserPreferences>) => {
    setPreferences((current) => {
      const next = { ...current, ...patch }
      void savePreferences(next)
      return next
    })
  }, [])

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

  /**
   * The drought wash on or off (#720).
   *
   * A stored preference rather than a `useState`, and that is the whole
   * point: `hiddenTypes` learned this lesson the hard way (#530) - the
   * legend's category toggles wrote to a state that died on reload, so
   * hiding privies lasted until the next launch and never reached an
   * account. A background tint somebody turned off should stay off.
   */
  const handleToggleDrought = useCallback(() => {
    // Reads the current value inside the functional update rather than
    // closing over `preferences`, so the callback has no dependency on the
    // thing it toggles - the same shape `updatePreferences` already uses, and
    // the reason a fast double-tap cannot land two flips on one stale value.
    setPreferences((current) => {
      const next = { ...current, drought_layer_shown: !current.drought_layer_shown }
      void savePreferences(next)
      return next
    })
  }, [])

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
    (next: BoundingBox) => {
      setBbox(next)
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

  const handleMapReady = useCallback((next: MapLibreMap | null) => setMap(next), [])

  // How many of the waypoints in view the map actually drew (#528). Measured on
  // `idle` rather than derived, because the collision engine decides it and only
  // MapLibre knows what it decided - see lib/useDrawnPoiCounts.ts.
  const { counts: drawnPoiCounts, belowPoiZoom } = useDrawnPoiCounts(map)

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

  // The line taps report on every click, nulls included, exactly as the POI
  // taps do - the null is the tap-elsewhere dismissal, and it also fires
  // when a tap lands on a pin or an ATC notice (map/lineTaps.ts yields to
  // both), which is what keeps this sheet from stacking under theirs.
  // A tapped mark closes the legend the way a tapped line does, and clears
  // the line selection so the two sheets can never both be open.
  const handleSelectHighlight = useCallback((id: string | null) => {
    setSelectedHighlightId(id)
    if (id !== null) {
      setLegendOpen(false)
      setSelectedLine(null)
    }
  }, [])

  const handleSelectLine = useCallback((line: TappedLine | null) => {
    setSelectedLine(line)
    if (line !== null) setLegendOpen(false)
  }, [])

  const handleOpenLegend = useCallback(() => {
    setLegendOpen(true)
    setSelectedPoiId(null)
  }, [])

  const handleClosePoi = useCallback(() => setSelectedPoiId(null), [])

  // Through the same `updatePreferences` path every other map preference uses,
  // so this one persists and syncs like the rest of them rather than being the
  // one control that forgets (#530).
  const handleToggleType = useCallback(
    (type: string) => {
      updatePreferences({
        waypoint_types_shown: toggleType(preferences.waypoint_types_shown, type),
      })
    },
    [preferences.waypoint_types_shown, updatePreferences],
  )

  /** One tap to show a single category - the control this issue is worth
   *  building for. At a crowded zoom it is the difference between four water
   *  pins drawn and forty, and it answers "where is the next water" in two taps
   *  rather than by zooming in and panning along the trail. */
  const handleOnlyType = useCallback(
    (type: string) => updatePreferences({ waypoint_types_shown: onlyType(type) }),
    [updatePreferences],
  )

  /** The way out, which is what makes persisting the filter honest. */
  const handleShowAllTypes = useCallback(
    () => updatePreferences({ waypoint_types_shown: showAllTypes() }),
    [updatePreferences],
  )

  const handleToggleVerifiedOnly = useCallback(() => {
    setVerifiedOnly((current) => !current)
  }, [])

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
    async (draft: FieldNoteDraft) => {
      const item = await enqueueFieldNote(draft)

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
      onAddNote: (draft: FieldNoteDraft) => void handleAddFieldNote(draft),
      onReportProblem: handleReportFromPoi,
      now,
    }),
    [
      allNotes,
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

  const handleSignOut = useCallback(async () => {
    await signOut()
  }, [])

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
                <More
                  account={account}
                  onSignIn={() => setAuthFlow({ screen: 'choose', afterReport: false })}
                  onSignOut={() => void handleSignOut()}
                  preferences={preferences}
                  onChange={updatePreferences}
                  onChangeBackground={handleChangeBackground}
                  pace={pace}
                  onChangePace={handleChangePace}
                  lastSyncedAt={lastSyncedAt}
                  onSync={notYet}
                  onExport={notYet}
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
                pois={pois}
                gpsMile={gpsPlanMile}
                units={units}
                pace={pace}
                draftLive={routeDraft !== null}
                onStartOnMap={openRouteBuilder}
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
                onPlanGap={handlePlanGap}
                onPlanFrom={handlePlanFrom}
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
                            openRouteBuilder()
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
          onSelectHighlight={handleSelectHighlight}
          maintainerLine={maintainerLine}
          atcUpdates={atcBandsOnMap}
          atcUpdatePoints={atcPointsOnMap}
          onSelectAtcUpdate={setSelectedAtcBandId}
          atcUpdateSheet={
            selectedAtcUpdate === null ? null : (
              <AtcUpdateSheet
                update={selectedAtcUpdate}
                reviewedAt={atcReviewedAt}
                onClose={() => setSelectedAtcBandId(null)}
              />
            )
          }
          onSelectLine={handleSelectLine}
          lineSheet={
            // A tapped highlight wins over both: it is a small, aimed-at mark
            // sitting ON the corridor, the same rule map/lineTaps.ts applies
            // when a pin beats the line under it.
            selectedHighlightDetail !== null ? (
              <HighlightSheet
                detail={selectedHighlightDetail}
                onClose={() => setSelectedHighlightId(null)}
              />
            ) : // The club sheet wins below the seam, and the two never stack:
            // one tap asks one question, and which question it is depends on
            // what the map is showing.
            selectedClubDetail !== null ? (
              <ClubSheet
                detail={selectedClubDetail}
                onClose={() => setSelectedLine(null)}
              />
            ) : selectedLineDetail === null ? null : (
              <LineSheet
                detail={selectedLineDetail}
                onClose={() => setSelectedLine(null)}
              />
            )
          }
          atcNoticeCount={atcUpdates.length}
          onOpenAtcNotices={() => {
            setAtcNoticesOpen(true)
            // Opening the full list is a hiker having looked, exactly as
            // much as tapping the bottom banner's own dismiss is - see
            // silenceAtcAlerts above.
            silenceAtcAlerts()
          }}
          newAtcAlertCount={newAtcAlerts?.count ?? 0}
          onSilenceNewAtcAlerts={silenceAtcAlerts}
          atcNoticeList={
            atcNoticesOpen ? (
              <AtcNoticeList
                updates={atcUpdates}
                drawnIds={atcDrawnIds}
                reviewedAt={atcReviewedAt}
                onClose={() => setAtcNoticesOpen(false)}
              />
            ) : null
          }
          routeDrawing={routeDrawing}
          // Defined for the whole builder session so a stray tap can never
          // fall through to a waypoint card underneath - but the handler
          // only ACTS while the picker's map door is open (one tap, one
          // interpreter). Suppressed while the target sheet is up: the
          // sheet covers the surface that would explain the tap.
          onRouteTap={
            routeDraft === null || targetRequest !== null ? undefined : handleStopMapTap
          }
          routeSheet={
            targetRequest !== null ? (
              targetSheet
            ) : stopPick !== null && stopPick.onMap ? (
              <RouteMapPickBar
                refusedTap={stopPick.refusedTap}
                units={units}
                onCancel={() =>
                  setStopPick({ ...stopPick, onMap: false, refusedTap: false })
                }
              />
            ) : stopPick !== null ? (
              <RouteStopPicker
                choices={routeStopChoices}
                pois={pois}
                previous={pickPrevious}
                south={pickSouth}
                removable={
                  stopPick.slot.kind === 'replace' &&
                  routeDraft !== null &&
                  routeDraft.phase === 'editor' &&
                  stopPick.slot.index > 0 &&
                  stopPick.slot.index < routeDraft.stops.length - 1
                }
                units={units}
                onPick={applyPickedStop}
                onMapPick={() => setStopPick({ ...stopPick, onMap: true })}
                onRemove={handleRemoveStop}
                onClose={() => setStopPick(null)}
              />
            ) : routeDraft === null ? null : routeDraft.phase === 'entrance' ? (
              <RouteEntranceSheet
                start={routeDraft.start}
                ask={routeDraft.ask}
                miles={routeDraft.miles}
                days={routeDraft.days}
                south={routeDraft.south}
                end={
                  entranceEnd === null
                    ? null
                    : ({
                        mile: entranceEnd.stop.mile,
                        ...(entranceEnd.stop.name === undefined
                          ? {}
                          : { name: entranceEnd.stop.name }),
                        ...(entranceEnd.kind === undefined
                          ? {}
                          : { kind: entranceEnd.kind }),
                      } satisfies EntranceEnd)
                }
                reachMi={
                  routeDraft.ask === 'long' ? (entranceEnd?.reachMi ?? null) : null
                }
                hoursTarget={DEFAULT_WALKING_HOURS}
                daysUsable={elevation !== null}
                gpsUsable={fix !== null && gpsPlanMile !== null}
                refused={routeStopChoices.length === 0}
                units={units}
                onAsk={(ask) => patchEntrance({ ask })}
                onMiles={(miles) => patchEntrance({ miles })}
                onDays={(days) => patchEntrance({ days })}
                onSouth={(south) => patchEntrance({ south })}
                onPickStart={handlePickStart}
                onPickEnd={() =>
                  setStopPick({ slot: { kind: 'end' }, onMap: false, refusedTap: false })
                }
                onClearEnd={() =>
                  setRouteDraft((draft) =>
                    draft !== null && draft.phase === 'entrance'
                      ? { ...draft, fixedEnd: null }
                      : draft,
                  )
                }
                fixedEnd={routeDraft.fixedEnd}
                refusedTap={entranceRefusedTap}
                trailMiles={trailMiles}
                onUse={handleUseStretch}
                onClose={handleRouteCancel}
              />
            ) : (
              <RouteStopsPanel
                stops={routeDraft.stops}
                legs={routeLegDisplays}
                direction={routeDirection(routeDraft.stops)}
                units={units}
                onEditStop={handleEditStop}
                onAddStop={handleAddStop}
                onBreakIntoDays={handleBreakIntoDays}
                onRecordWalked={handleRecordWalked}
                onClose={handleRouteCancel}
              />
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
          onCloseLegend={() => setLegendOpen(false)}
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
          elevation={ribbon?.props}
          waypoints={waypoints}
          viewportPoints={viewportPoints}
          blazeCounts={[]}
          drawnCounts={drawnPoiCounts}
          belowPoiZoom={belowPoiZoom}
          hiddenTypes={hiddenTypes}
          onToggleType={handleToggleType}
          onOnlyType={handleOnlyType}
          onShowAllTypes={handleShowAllTypes}
          typesShown={preferences.waypoint_types_shown}
          verifiedOnly={verifiedOnly}
          onToggleVerifiedOnly={handleToggleVerifiedOnly}
          drought={drought}
          droughtShown={preferences.drought_layer_shown}
          onToggleDrought={handleToggleDrought}
          droughtWeek={droughtWeek}
          selectedPoi={selectedPoi}
          selectedSite={selectedSite}
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
