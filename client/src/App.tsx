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
import { Onboarding, type OnboardingResult } from './screens/Onboarding'
import { ReportForm, type ReportFormSubmission } from './screens/ReportForm'
import { ReportTypePicker, type ReportTypeId } from './screens/ReportTypePicker'
import { MapView } from './map/MapView'
import { mapCredits } from './map/credits'
import { MapAttribution } from './chrome/MapAttribution'
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
  packageArtifactKey,
  packageDownloadUrl,
  packageSizeBytes,
  sheetSizeBytes,
  USGS_SHEET,
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
import { buildTrailIndex, locateOnTrail, type TrailIndex } from './lib/trailPosition'
import {
  downloadTrailData,
  loadTrailData,
  TrailDataHashMismatchError,
  type StoredPoi,
} from './lib/trailData'
import {
  ribbonSamples,
  ribbonWindow,
  type ElevationProfile,
} from './lib/elevationProfile'
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
import { listQueued, removeQueued, retryQueued, type FlushResult } from './lib/outbox'
import { useOutboxSync, syncOutbox } from './lib/outboxSync'
import {
  API_CONFIGURED,
  fetchClosures,
  fetchReports,
  type ClosureSummary,
  type ReportSummary,
} from './lib/api'
import {
  UNAVAILABLE,
  conditionsAgeLabel,
  itemsOf,
  withBaseline,
  withLive,
  worstOf,
  type ConditionState,
} from './lib/conditionState'
import { fetchPublishedClosures, fetchPublishedReports } from './lib/publishedConditions'
import { nearestClosureBanner } from './lib/closureBanner'
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
import {
  isSeriousWarning,
  placeAll,
  routeBannerText,
  warningsOnRoute,
} from './lib/seriousWarnings'
import type { BoundingBox, MapPoint } from './lib/legendContents'
import type { SearchablePoi } from './lib/searchPoi'
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

/** MapLibre needs a resolvable URL even with nothing downloaded; an empty
 *  collection draws nothing, where a missing URL logs a style error. */
function emptyTrailsUrl(): string {
  return URL.createObjectURL(
    new Blob([JSON.stringify({ type: 'FeatureCollection', features: [] })], {
      type: 'application/json',
    }),
  )
}

/**
 * What went wrong fetching the trail's own data, in the shape both fetch paths
 * report.
 *
 * One function because there are two callers and they must not drift: the
 * launch fetch nobody asked for, and the tapped download. They fail for
 * exactly the same reasons - no signal, a refused origin, a bucket with
 * nothing in it - and the hiker reading the sentence has no way to tell which
 * request produced it, so two wordings would be two accounts of one event.
 *
 * The hash mismatch keeps its own kind because its remedy differs: nothing was
 * kept on purpose, and a fresh download is the fix rather than a resume
 * (#238).
 */
function describeTrailDataError(error: unknown): {
  kind: 'hash-mismatch' | 'error'
  message: string
} {
  if (error instanceof TrailDataHashMismatchError) {
    return { kind: 'hash-mismatch', message: error.message }
  }
  return {
    kind: 'error',
    message: error instanceof Error ? error.message : 'Trail data failed to download.',
  }
}

type ReportingState = null | { step: 'pick' } | { step: 'form'; type: ReportTypeId }

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

  const [trailIndex, setTrailIndex] = useState<TrailIndex | null>(null)
  const [pois, setPois] = useState<StoredPoi[]>([])
  const [elevation, setElevation] = useState<ElevationProfile | null>(null)
  const [trailsUrl, setTrailsUrl] = useState<string>(emptyTrailsUrl)
  /** Whether the map has a real trail line on it, as against the empty
   *  collection the style is seeded with. What the strip reads to say the
   *  trail itself is missing - see `trailLinesMissing` below. */
  const [haveTrailLines, setHaveTrailLines] = useState(false)
  /** The trail-data download's failure, with the one distinction that changes
   *  what the notice says: a hash mismatch kept nothing on purpose, and its
   *  remedy is a clean re-download rather than a retry of what stopped
   *  (#238). Typed at the moment the error still has a type - matching on
   *  message text would break the day the sentence was reworded. */
  const [dataError, setDataError] = useState<{
    kind: 'hash-mismatch' | 'error'
    message: string
  } | null>(null)

  const [reporting, setReporting] = useState<ReportingState>(null)
  const [authFlow, setAuthFlow] = useState<AuthFlowState>(null)
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
  // Null means "we have not managed to ask", not "there are none" - the two
  // draw the same map and mean opposite things on the ground (#286). Nothing
  // renders a reassuring absence from either: a clear header is what a hiker
  // sees when the way ahead is clear AND when we could not check, and the
  // status strip's sync age is what tells those apart (lib/syncAge.ts).
  // One state rather than a list plus a separate "where did this come from",
  // because the two reads race and updating two states from a race is how you
  // get fresh closures labelled stale. lib/conditionState.ts owns the rule
  // that live always wins; `closures` and `reports` below stay exactly the
  // `T[] | null` every consumer already expects. Reports carry the same state
  // machine as closures (#436) - they are the warning pins, the other half of
  // what a hiker walks into.
  const [closureState, setClosureState] =
    useState<ConditionState<ClosureSummary>>(UNAVAILABLE)
  const closures = itemsOf(closureState)
  const [reportState, setReportState] =
    useState<ConditionState<ReportSummary>>(UNAVAILABLE)
  const reports = itemsOf(reportState)
  // Was a state with no setter until #231 - nothing ever synced, so the status
  // strip said "never synced" on every device forever, which was true and
  // looked like a bug in the strip rather than a missing feature.
  const [lastSyncedAt, setLastSyncedAt] = useState<Date | null>(null)

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

  useEffect(() => {
    void refreshOutbox()
  }, [reporting, refreshOutbox])

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
      if (sent > 0) setLastSyncedAt(new Date())
      // Refreshed even when nothing was sent, because a flush that only
      // discovered a refusal still changed what the hiker needs to see -
      // that is the whole point of the stuck state.
      if (sent > 0 || stuck > 0) void refreshOutbox()
    },
    [refreshOutbox],
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

  // The map's own reads (#232), separate from the outbox flush above and
  // deliberately not gated on an account: browsing has never needed one, and
  // the reads send a token only if there is one (lib/api.ts).
  //
  // Both settle independently. A closures read that succeeds while reports
  // fails should still warn about the closure - pairing them would mean one
  // failure silencing both, and closures are the half a hiker walks into.
  // The published baseline, fetched once and independently of the backend
  // (features/CONDITIONS_DELIVERY.md). This is the read that makes an
  // unreachable backend mean "day-old closures, labelled as day-old" rather
  // than the silence it used to mean.
  //
  // Gated on `online`, matching the rule the trail-line fetch already keeps -
  // "waits for signal rather than failing a fetch it knows cannot work".
  // This was written ungated first, on the theory that the service worker
  // might hold a copy; it does not. vite.config.ts precaches the app shell and
  // the glyph ranges and nothing else, because this app's offline story is
  // IndexedDB rather than cached responses. So offline there is genuinely no
  // baseline to get, and the honest state is `unavailable` - which the strip
  // now says out loud instead of rendering as a clear trail.
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

    return () => {
      cancelled = true
    }
  }, [online])

  useEffect(() => {
    if (!online || !API_CONFIGURED) return

    let cancelled = false
    // A read reaching the server IS a sync, and the status strip's age is the
    // only thing distinguishing "nothing reported here" from "we could not
    // ask" - so it has to move when the map data does, not only when a
    // report goes out.
    const markSynced = () => {
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
      markSynced()
    }, leaveUnknown)

    void fetchReports().then((next) => {
      if (cancelled) return
      setReportState(withLive(next))
      markSynced()
    }, leaveUnknown)

    return () => {
      cancelled = true
    }
  }, [online])

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
          if (result !== null && result.sent > 0) setLastSyncedAt(new Date())
        })
        .finally(() => void refreshOutbox())
    },
    [refreshOutbox],
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

  // The background sheets a hiker can choose between (#237), and every
  // archive behind them (#192). One flat download store underneath - the
  // per-sheet grouping is a fact about what a card shows, not about how
  // bytes are held.
  const backgroundSheets = useMemo(() => offeredSheets(), [])
  const downloadRequests = useMemo(
    () =>
      backgroundSheets
        .flatMap((sheet) => offeredPackages(sheet))
        .map((pkg) => ({
          packageKey: pkg.idbKey,
          url: packageDownloadUrl(pkg, detailLevel, hikingLevel),
          artifactKey: packageArtifactKey(pkg, detailLevel, hikingLevel),
        })),
    [backgroundSheets, detailLevel, hikingLevel],
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

  /** Returns whether anything was actually on the phone to load. */
  const refreshTrailData = useCallback(async () => {
    const data = await loadTrailData()
    if (data === null) return false

    setTrailsUrl(URL.createObjectURL(data.trails))
    // Set here rather than derived from `trailsUrl`, which starts life as a
    // perfectly valid object URL for an empty collection and so cannot answer
    // "is there a trail on this map". Nothing else can answer it either: the
    // POIs are a separate artifact and the index is best-effort, so a phone
    // can hold both and still be drawing no line.
    setHaveTrailLines(true)
    setPois(data.pois)
    setElevation(data.elevation)

    // Best-effort, and separate from the POIs above on purpose. A shelter is
    // findable by name with no geometry at all, so a trails.geojson that
    // arrived truncated or malformed should cost the mile numbers decorating
    // each row and nothing else.
    //
    // buildTrailIndex() guards the shape it is handed, but JSON.parse runs
    // first and throws on the more likely symptom of a truncated download -
    // half a file. Uncaught, that escaped through the `void refreshTrailData()`
    // below as an unhandled rejection: no index, no message, and no search
    // either, which is the failure this whole path was rebuilt to avoid.
    try {
      setTrailIndex(buildTrailIndex(JSON.parse(await data.trails.text())))
    } catch {
      setTrailIndex(null)
    }
    return true
  }, [])

  /**
   * The trail-data fetch that is in flight, so that re-renders, connectivity
   * flapping and a tapped download cannot start a second one. A ref rather
   * than state because nothing renders from it.
   *
   * THE PROMISE, not a boolean, and that is the whole point of it. It was a
   * flag, which only the launch fetch below ever read - so a hiker who tapped
   * Download while that fetch was still running got `loadTrailData()` back as
   * null (nothing committed yet), and pulled the same 12.3 MB of
   * trails.geojson a second time, against the same connection, ahead of the
   * archive they were actually waiting for. Sharing the attempt means the tap
   * waits for the bytes already coming rather than racing them.
   *
   * Cleared when it settles, either way: a fetch that failed must be
   * retryable when signal returns, and one that succeeded leaves
   * `loadTrailData()` answering from the phone, which is cheaper than any
   * flag.
   */
  const trailDataFetch = useRef<Promise<void> | null>(null)

  /**
   * The trail's own data on the phone, fetched at most once at a time.
   *
   * Rejects with whatever the fetch rejected with - both callers report it,
   * differently: the launch fetch nobody asked for reports through the status
   * strip, a tapped download reports on the card that was tapped.
   */
  const fetchTrailDataOnce = useCallback(() => {
    const inFlight = trailDataFetch.current
    if (inFlight !== null) return inFlight

    const attempt = (async () => {
      // Asked directly rather than assumed: a phone that already has the
      // lines needs no network at all.
      if ((await loadTrailData()) !== null) return
      await downloadTrailData()
      await refreshTrailData()
    })()
    trailDataFetch.current = attempt
    const clear = () => {
      if (trailDataFetch.current === attempt) trailDataFetch.current = null
    }
    attempt.then(clear, clear)
    return attempt
  }, [refreshTrailData])

  // The trail lines load themselves, rather than waiting for someone to tap
  // Download.
  //
  // They are a few megabytes against the archive's 314 MB - the download flow
  // already treats them that way, fetching them first as the canary - and they
  // are not decoration on the map, they ARE the map: without them the app
  // opens on a background with no trail on it, no POIs, nothing to search and
  // no elevation ribbon. Making the whole corridor download a precondition for
  // seeing where the Appalachian Trail runs is the wrong trade at any
  // connection speed, and it is the state every first run was in.
  //
  // NOT quiet about failing, which is what this used to be, and the reasoning
  // for the quiet was wrong in a way worth writing down rather than deleting.
  // It ran: the hiker did not ask for this, so a failure is not a result they
  // are owed a message about - it leaves exactly the empty map they would have
  // had anyway, and the Downloads screen still reports the download they DO
  // ask for.
  //
  // Both halves fail. "The empty map they would have had anyway" is a map with
  // no Appalachian Trail drawn on it, which this file argues three paragraphs
  // up is not the empty state but a broken one: the lines "are not decoration
  // on the map, they ARE the map". And the Downloads screen only reports what
  // was tapped, so a launch fetch that failed was recorded nowhere at all -
  // not on the map, not in the window, not in a state anything rendered.
  //
  // What that cost is the bug report this comment was rewritten for: an app
  // whose trail line was missing because the bucket refused its origin, and
  // whose entire account of itself was a map with no trail on it. The failure
  // is now carried the same way a tapped download's is, and the strip says the
  // trail is missing (`trailLinesMissing`) so the sentence is findable from
  // the screen the missing line is on. Retried when the phone comes back
  // online, which is the one condition likely to have changed.
  // Reading what is already on the phone, and unconditionally. This has to
  // stay independent of the fetch below: an unconfigured build and a phone
  // with no signal both still have whatever was downloaded last time, and
  // gating this on either one would leave a hiker on a ridge - the exact
  // person the offline store exists for - looking at a map with no trail.
  useEffect(() => {
    void refreshTrailData()
  }, [refreshTrailData])

  useEffect(() => {
    if (!DATA_CONFIGURED || !online) return

    let cancelled = false

    // Deduplicated inside fetchTrailDataOnce rather than by a flag here, so
    // that a download tapped while this is still running joins it instead of
    // fetching the same megabytes alongside it.
    void fetchTrailDataOnce().catch((error: unknown) => {
      // Not reported if the effect was torn down under us: by then this is a
      // fetch nobody is waiting on, and a notice about it would outlive the
      // screen that could act on it. Nothing is stored either way -
      // downloadTrailData commits all four files or none - so coming back
      // into signal can simply try again.
      if (cancelled) return
      setDataError(describeTrailDataError(error))
    })

    return () => {
      cancelled = true
    }
  }, [fetchTrailDataOnce, online])

  // Revoking belongs here rather than inside the setTrailsUrl updater it used
  // to live in. A state updater has to be pure: React may run it more than
  // once for a single update and may throw a render away entirely, and either
  // one leaked a blob URL - or, in the discarded-render case, revoked the URL
  // the map was still using. As a cleanup it runs exactly once per value, when
  // that value stops being current, which is precisely when the bytes behind
  // it stop being needed.
  useEffect(() => () => URL.revokeObjectURL(trailsUrl), [trailsUrl])

  // A fix moves no camera - see CORRIDOR_BOUNDS. It is read for everything
  // else: the mile below, the direction of travel, the elevation ribbon.
  const fix = useMemo(() => {
    if (trailIndex === null || gps.status !== 'located') return null
    return locateOnTrail(trailIndex, gps.at)
  }, [trailIndex, gps])

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
  const closureAhead = useMemo(() => {
    if (closures === null || fix === null) return null
    return nearestClosureBanner(closures, fix.mile, heading)
  }, [closures, fix, heading])

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
    if (closures === null || trailIndex === null) return []
    return closureBands(closures, trailIndex)
  }, [closures, trailIndex])

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
  const searchablePois: SearchablePoi[] = useMemo(
    () =>
      pois.map((poi) => ({
        id: poi.id,
        name: poi.name,
        type: poi.type,
        mile:
          trailIndex === null
            ? undefined
            : locateOnTrail(trailIndex, { lon: poi.lon, lat: poi.lat })?.mile,
      })),
    [pois, trailIndex],
  )

  // What the tapped pin's card says. Built from both arrays on purpose: the
  // POI itself carries the geometry and the provenance, and searchablePois has
  // already paid for the locateOnTrail() call that places it on the trail, so
  // the mile in the card is the same number search puts on the same POI rather
  // than a second computation that could disagree with it.
  const selectedPoi: PoiDetail | null = useMemo(() => {
    if (selectedPoiId === null) return null
    const poi = pois.find((candidate) => candidate.id === selectedPoiId)
    if (poi === undefined) return null
    return {
      ...poi,
      mile: searchablePois.find((candidate) => candidate.id === selectedPoiId)?.mile,
    }
  }, [selectedPoiId, pois, searchablePois])

  const viewportPoints: MapPoint[] = useMemo(
    () =>
      pois.map((poi) => ({
        id: poi.id,
        type: poi.type,
        lat: poi.lat,
        lon: poi.lon,
        confidence: poi.confidence,
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
    }
  }, [ribbon, searchablePois])

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

  /** The trail's own data - centerline, spurs, POIs, elevation profile - on
   *  the phone, fetching it only if it is not already here.
   *
   *  Not a choice anyone is offered: it is a few megabytes against a
   *  background measured in hundreds, and it is what makes the app an app
   *  rather than a map viewer, so it is downloaded by default wherever it is
   *  missing (the effect above does the same on launch). Called before the
   *  background too, where it doubles as the canary: whatever stopped these
   *  few megabytes - no signal, a missing key, a misconfigured bucket - will
   *  stop the next several hundred, and finding that out costs a hiker their
   *  data allowance to learn nothing.
   *
   *  Returns whether to go on. */
  const ensureTrailData = useCallback(async () => {
    setDataError(null)
    try {
      // Shares whatever is already coming, and asks the phone first - both
      // inside fetchTrailDataOnce, so that a tap during the launch fetch
      // waits on it rather than duplicating it.
      await fetchTrailDataOnce()
      return true
    } catch (error) {
      setDataError(describeTrailDataError(error))
      return false
    }
  }, [fetchTrailDataOnce])

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
      // 'send' needs no step here:
      // useOutboxSync above is already watching, and a report queued by a
      // signed-in hiker with signal goes on its own. Nothing is awaited for
      // it, because a send that blocked this callback would be a network round
      // trip standing between someone and the map they were reading.
      if (next === 'sign-in') setAuthFlow({ screen: 'choose', afterReport: true })
      else if (next === 'identity') askForIdentity()
    },
    [account, preferences.reporter_type, askForIdentity],
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

  // First run, over the map rather than in front of a blank page.
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
  // Deliberately NOT the map SCREEN. What is behind the steps is the canvas
  // and nothing else - no header, no tab bar, no legend - because chrome
  // behind a modal is either a trap or a way to skip the flow sideways, and
  // neither is the first thing to hand someone.
  //
  // `inert` (with pointer-events: none in App.css behind it) is what makes
  // that safe, and it is not only about stray taps. MapView attaches a locate
  // control (map/mapChrome.ts), and a tap on it would put the OS location
  // prompt on screen before the step whose entire job is to explain why we
  // are asking - spending the one permission this app cares about at the exact
  // moment it has earned the least trust. Inert also keeps the canvas out of
  // the tab order and its region out of the accessibility tree, so a keyboard
  // or screen-reader user is in the steps and only the steps.
  //
  // It costs one extra map build - this one is torn down when the steps
  // finish and the map screen builds its own - which is the same price a trip
  // through the More tab already pays, and buys the entire first run.
  if (!preferences.onboarding_completed) {
    // The same call the map screen makes below. With nothing downloaded yet -
    // which is every first run - it answers the live sheet whatever the stored
    // preference or Data Saver says, so this draws exactly what the map screen
    // would have drawn seconds later and spends no bytes that were not already
    // going to be spent.
    const entryBackground = effectiveBackground(
      preferences.background_source,
      saveData,
      archiveDownloaded,
    )

    return (
      <div className="app__entry">
        <div className="app__entry-map" aria-hidden="true" inert>
          <MapView
            topoArchiveUrl={CORRIDOR_ARCHIVE_URL}
            trailsUrl={trailsUrl}
            background={entryBackground}
            pois={viewportPoints}
            archiveZooms={archiveZooms}
            bounds={CORRIDOR_BOUNDS}
          />
        </div>
        {/* Outside the inert backdrop, and not optional. The live sheet's OSM
            data is ODbL and its credit is a licence condition, so a map that
            is drawn has to be credited whether or not anyone is meant to touch
            it - the map screen renders this same line for the same reason
            (chrome/MapScreen.tsx). Kept out of the inert subtree so it is
            readable rather than merely present.

            Same pair as the map screen - what it names is map/credits.ts's
            decision, how much room it takes is MapAttribution's - so first run
            cannot end up crediting a different set of sources from the screen
            it hands over to a moment later. */}
        <div className="app__entry-attribution">
          <MapAttribution
            credits={mapCredits({
              background: entryBackground,
              hasRasterArchive: archiveDownloaded,
            })}
            inline={isDesktop}
          />
        </div>
        <Onboarding onComplete={handleOnboardingComplete} />
      </div>
    )
  }

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

  if (reporting !== null) {
    if (reporting.step === 'pick') {
      return (
        <ReportTypePicker
          onPick={(type) => setReporting({ step: 'form', type })}
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
        // Null with no fix, rather than 0,0 - which is a real place in the
        // Atlantic, and one a maintainer cannot tell from a missing location.
        // The mile is separately unknown when the fix is off the centerline or
        // the trail index has not been downloaded yet.
        location={
          gps.status === 'located'
            ? { lat: gps.at.lat, lon: gps.at.lon, mile: fix?.mile }
            : null
        }
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
            <ErrorBoundary
              resetKey={activeTab}
              fallback={() => <ScreenFailed what="This screen" />}
            >
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
          topoArchiveUrl={CORRIDOR_ARCHIVE_URL}
          trailsUrl={trailsUrl}
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
          warningsAhead={warningsAhead}
          closures={closureBandsOnMap}
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
          hiddenTypes={hiddenTypes}
          onToggleType={handleToggleType}
          onOnlyType={handleOnlyType}
          onShowAllTypes={handleShowAllTypes}
          typesShown={preferences.waypoint_types_shown}
          verifiedOnly={verifiedOnly}
          onToggleVerifiedOnly={handleToggleVerifiedOnly}
          selectedPoi={selectedPoi}
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
          // The corridor is the opening view only. Once there is a camera to put
          // back, it wins: `bounds` would otherwise re-frame the entire trail
          // every time the map screen came back from another tab.
          center={camera?.center}
          zoom={camera?.zoom}
          bounds={camera === null ? CORRIDOR_BOUNDS : undefined}
          onViewportChange={handleViewportChange}
          onMapReady={handleMapReady}
        />
      </ErrorBoundary>
      {downloadsWindow}
    </>
  )
}

export default App
