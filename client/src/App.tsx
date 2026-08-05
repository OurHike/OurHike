// The app shell: what screen is showing, and where its data comes from.
//
// There is no router. Every screen is reached from the three-tab bar or from a
// flow that owns its own back-out, so URLs would be a second navigation model
// to keep in sync with the first for no gain a hiker would notice - and the
// service worker precaches one document either way.
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
// Auth is what a hiker signs in to, not this project's own backend. Sending a
// queued report still needs that backend deployed, which is why saving is
// still what the flow guarantees and sending still is not.
//
// Which providers appear is a build-time answer (lib/supabase.ts's
// ENABLED_PROVIDERS), because a button whose credentials do not exist yet
// reaches an error page rather than an account.
//
// Identity - trail name and reporter type - is still not collected here.
// stepAfterSaving() reports when it is wanted and there is no screen for it,
// so that step ends the flow the way it already ended, with the report
// queued.

import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MapScreen } from './chrome/MapScreen'
import type { PoiDetail } from './chrome/PoiCard'
import { TabBar } from './chrome/TabBar'
import { ErrorBoundary, ScreenFailed } from './chrome/ErrorBoundary'
import type { TabId } from './chrome/tabs'
import { Downloads } from './screens/Downloads'
import { More } from './screens/More'
import { InstallPrompt } from './screens/InstallPrompt'
import { Onboarding, type OnboardingResult } from './screens/Onboarding'
import { ReportForm, type ReportFormSubmission } from './screens/ReportForm'
import { ReportTypePicker, type ReportTypeId } from './screens/ReportTypePicker'
import { CORRIDOR_ARCHIVE_URL } from './map/protocol'
import { archiveUrl, DATA_CONFIGURED } from './lib/config'
import { loadPreferences, savePreferences } from './lib/preferences'
import { DEFAULT_PREFERENCES, type UserPreferences } from './lib/userPreferences'
import {
  detailLevelForZoom,
  getDownloadDetail,
  type DetailLevel,
} from './lib/downloadDetail'
import { useArchiveDownload } from './lib/useArchiveDownload'
import { CORRIDOR_BACKGROUND_PACKAGE } from './lib/packages'
import { useClock } from './lib/useClock'
import { useOnline } from './lib/useOnline'
import { useDataSaver } from './lib/useDataSaver'
import { backgroundOverridden, effectiveBackground } from './lib/dataSaver'
import { useFinePointer } from './lib/useFinePointer'
import { useInstallPrompt } from './lib/useInstallPrompt'
import { useAppUpdate } from './lib/useAppUpdate'
import { useGeolocation } from './lib/useGeolocation'
import { buildTrailIndex, locateOnTrail, type TrailIndex } from './lib/trailPosition'
import {
  deleteTrailData,
  downloadTrailData,
  loadTrailData,
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
import { SignInPrompt, type AuthProvider } from './screens/SignInPrompt'
import { EmailSignIn } from './screens/EmailSignIn'
import { ENABLED_PROVIDERS } from './lib/supabase'
import { useAccount } from './lib/useAuth'
import {
  sendMagicLink,
  signInWithEmail,
  signInWithProvider,
  signOut,
  signUpWithEmail,
} from './lib/auth'
import { listQueued } from './lib/outbox'
import type { BoundingBox, MapPoint } from './lib/legendContents'
import type { SearchablePoi } from './lib/searchPoi'
import './App.css'
// Last, and entirely inside media queries - see the file header. Nothing in it
// can match a phone, which is how the WEBSITE.md §8 constraint is kept
// structurally rather than by review.
import './desktop.css'

const TRAIL_NAME = 'Appalachian Trail'

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
  const [legendOpen, setLegendOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  // The tapped pin, held as an id rather than as the POI itself. Everything the
  // card shows is derived below, so a POI that changes underneath - a fresh
  // download, or the hiker deleting the one they had - is described correctly
  // or closes itself, instead of the card going on showing a copy of data the
  // app no longer holds.
  const [selectedPoiId, setSelectedPoiId] = useState<string | null>(null)
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set())
  const [bbox, setBbox] = useState<BoundingBox>(EMPTY_BBOX)

  const [trailIndex, setTrailIndex] = useState<TrailIndex | null>(null)
  const [pois, setPois] = useState<StoredPoi[]>([])
  const [elevation, setElevation] = useState<ElevationProfile | null>(null)
  const [trailsUrl, setTrailsUrl] = useState<string>(emptyTrailsUrl)
  const [dataError, setDataError] = useState<string | null>(null)

  const [reporting, setReporting] = useState<ReportingState>(null)
  const [authFlow, setAuthFlow] = useState<AuthFlowState>(null)
  // Null until a stored session is read, and null forever if nobody signs in.
  // Signed out is the state every screen already works in, so this gates
  // nothing.
  const account = useAccount()
  const [queuedCount, setQueuedCount] = useState(0)
  const [lastSyncedAt] = useState<Date | null>(null)

  const [direction, setDirection] = useState<DirectionTracker | null>(null)
  // The live map is state rather than a ref because effects have to run when
  // it appears. It appears more than once: the map screen unmounts whenever
  // another tab is showing, so every trip through Downloads builds a new one.
  const [map, setMap] = useState<MapLibreMap | null>(null)
  // Where the camera was left, so a rebuilt map opens where the hiker left it
  // instead of snapping back to the whole corridor.
  const [camera, setCamera] = useState<Camera | null>(null)

  const now = useClock()
  const online = useOnline()
  // Read here rather than inside the map, so the settings screen and the canvas
  // are answering from the same value - a row that says "live" over a map
  // drawing the archive would be the exact mismatch this feature exists to
  // avoid.
  const saveData = useDataSaver()
  // Decides whether the map gets zoom buttons - see lib/useFinePointer.ts.
  // Read here rather than inside MapView so the whole map screen answers from
  // one value.
  const finePointer = useFinePointer()
  const install = useInstallPrompt()
  useAppUpdate()

  useEffect(() => {
    void loadPreferences().then((stored) => {
      setPreferences(stored)
      setPreferencesLoaded(true)
    })
  }, [])

  useEffect(() => {
    void listQueued().then((queue) => setQueuedCount(queue.length))
  }, [reporting])

  const locationAllowed = preferences.location_permission_requested
  const gps = useGeolocation(locationAllowed)

  const detailLevel: DetailLevel = detailLevelForZoom(preferences.max_background_zoom)

  const {
    status: archiveStatus,
    start: startArchive,
    resume: resumeArchive,
    remove: removeArchive,
    error: archiveError,
  } = useArchiveDownload(CORRIDOR_BACKGROUND_PACKAGE.idbKey, archiveUrl(detailLevel))

  const refreshTrailData = useCallback(async () => {
    const data = await loadTrailData()
    if (data === null) return

    setTrailsUrl(URL.createObjectURL(data.trails))
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
  }, [])

  useEffect(() => {
    void refreshTrailData()
  }, [refreshTrailData])

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

  const updatePreferences = useCallback((patch: Partial<UserPreferences>) => {
    setPreferences((current) => {
      const next = { ...current, ...patch }
      void savePreferences(next)
      return next
    })
  }, [])

  const handleOnboardingComplete = useCallback(
    ({ detailLevel: chosen, locationRequested }: OnboardingResult) => {
      updatePreferences({
        onboarding_completed: true,
        download_choice_made: true,
        location_permission_requested: locationRequested,
        max_background_zoom: getDownloadDetail(chosen).zoom,
      })
      // Straight to Downloads: the choice just made is a download that has not
      // started, and a map screen with no map behind it is a worse first
      // impression than the screen that explains why.
      setActiveTab('downloads')
    },
    [updatePreferences],
  )

  const handleDownload = useCallback(async () => {
    setDataError(null)
    // Trail lines and POIs first. They are a fraction of the archive's size,
    // and getting them early means a failed raster download still leaves a
    // usable trail line rather than nothing at all.
    try {
      await downloadTrailData()
      await refreshTrailData()
    } catch (error) {
      setDataError(
        error instanceof Error ? error.message : 'Trail data failed to download.',
      )
      // Stop here rather than starting the archive anyway. These few megabytes
      // are the canary: whatever stopped them - no signal, a missing key, a
      // misconfigured bucket - will stop the next several hundred too, and
      // finding that out costs a hiker their data allowance to learn nothing.
      return
    }
    await startArchive()
  }, [refreshTrailData, startArchive])

  const handleDeleteDownload = useCallback(async () => {
    await removeArchive()
    await deleteTrailData()
    setPois([])
    setTrailIndex(null)
    setElevation(null)
    setTrailsUrl(emptyTrailsUrl())
  }, [removeArchive])

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
      setCamera({ center: [centre.lng, centre.lat], zoom: map.getZoom() })
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

  const handleToggleType = useCallback((type: string) => {
    setHiddenTypes((current) => {
      const next = new Set(current)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }, [])

  const handleSubmitReport = useCallback(
    async ({ authoredAt, ...draft }: ReportFormSubmission) => {
      // Saved first, always, and before authentication is so much as
      // mentioned. Everything below this line can fail without costing the
      // hiker what they just wrote.
      await beginContribution(draft, authoredAt)
      setReporting(null)

      const next = stepAfterSaving({
        hasAccount: account !== null,
        hasIdentity: preferences.trail_name !== null,
      })
      // 'identity' has no screen yet, and 'send' needs a backend that is not
      // deployed. Both end the flow exactly as it ended before, with the
      // report queued and said so. Only the sign-in step is built.
      if (next === 'sign-in') setAuthFlow({ screen: 'choose', afterReport: true })
    },
    [account, preferences.trail_name],
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

  // Nothing renders until the phone's own preferences have been read, so a
  // returning hiker never sees a flash of the first-run onboarding.
  if (!preferencesLoaded) return null

  if (!preferences.onboarding_completed) {
    return <Onboarding onComplete={handleOnboardingComplete} />
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
        reporterType="thru"
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

  if (activeTab === 'downloads') {
    return (
      <div className="app__screen">
        <div>
          {!DATA_CONFIGURED && (
            <p role="alert" className="app__notice">
              No data source is configured in this build, so downloading will not work.
              VITE_DATA_BASE_URL has to point at the published bucket.
            </p>
          )}
          {dataError !== null && (
            <p role="alert" className="app__notice">
              {dataError}
            </p>
          )}
          {archiveError !== null && (
            <p role="alert" className="app__notice">
              {archiveError}
            </p>
          )}
          <InstallPrompt
            platform={install.platform}
            canPrompt={install.canPrompt}
            onInstall={install.install}
          />
          <Downloads
            status={archiveStatus}
            detailLevel={detailLevel}
            onChangeDetail={(level) =>
              updatePreferences({ max_background_zoom: getDownloadDetail(level).zoom })
            }
            onStart={() => void handleDownload()}
            onResume={() => void resumeArchive()}
            onDelete={() => void handleDeleteDownload()}
          />
        </div>
        <TabBar active={activeTab} onSelect={setActiveTab} />
      </div>
    )
  }

  if (activeTab === 'more') {
    return (
      <div className="app__screen">
        <div>
          <More
            account={account}
            reporterType="thru"
            onSignIn={() => setAuthFlow({ screen: 'choose', afterReport: false })}
            onSignOut={() => void handleSignOut()}
            preferences={preferences}
            onChange={updatePreferences}
            lastSyncedAt={lastSyncedAt}
            onSync={notYet}
            onExport={notYet}
            now={now}
            dataSaver={saveData}
            onStartReport={() => setReporting({ step: 'pick' })}
            queuedReportCount={queuedCount}
          />
        </div>
        <TabBar active={activeTab} onSelect={setActiveTab} />
      </div>
    )
  }

  // The map is both the likeliest thing in this app to throw - WebGL, a GPS
  // watcher, byte-range reads against an archive that can be 1.18 GB, and a
  // pile of MapLibre attach/detach lifecycle - and the worst thing to lose,
  // since it is what someone is looking at when they do not recognise where
  // they are. Its own boundary keeps a map failure from costing Downloads and
  // More as well, and the tab bar below the fallback is the way back to them.
  return (
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
        background={effectiveBackground(preferences.background_source, saveData)}
        // Same two inputs, same module, one line apart - so the strip cannot
        // say the background was overridden while the canvas draws the one
        // that was chosen, which is the mismatch dataSaver.ts exists to stop.
        backgroundOverridden={backgroundOverridden(
          preferences.background_source,
          saveData,
        )}
        trailName={TRAIL_NAME}
        mile={fix?.mile}
        direction={direction?.direction}
        time={now}
        online={online}
        hasGpsFix={gps.status === 'located'}
        lastSyncedAt={lastSyncedAt}
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
        selectedPoi={selectedPoi}
        onSelectPoi={handleSelectPoi}
        onClosePoi={handleClosePoi}
        // WIREFRAMES.md §1.5: zoom buttons are web-only. Nothing was passing
        // this, so `showZoomButtons` sat on its default of false everywhere and
        // a browser with a mouse had no visible way to zoom at all.
        showZoomButtons={finePointer}
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
  )
}

export default App
