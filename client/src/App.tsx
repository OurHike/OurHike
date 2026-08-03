// The app shell: what screen is showing, and where its data comes from.
//
// There is no router. Every screen is reached from the three-tab bar or from a
// flow that owns its own back-out, so URLs would be a second navigation model
// to keep in sync with the first for no gain a hiker would notice - and the
// service worker precaches one document either way.
//
// Sign-in and identity are deliberately NOT in the reporting flow yet. There
// is no deployed backend to sign in to, and stepAfterSaving() (lib/
// contributionFlow.ts) is where they slot in the day there is. Until then a
// report is saved to the outbox and said so - which is the promise that flow
// exists to keep. Showing three provider buttons that cannot authenticate
// would break it.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MapScreen } from './chrome/MapScreen'
import { TabBar } from './chrome/TabBar'
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
import { useClock } from './lib/useClock'
import { useOnline } from './lib/useOnline'
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
import { startTracking, trackDirection, type DirectionTracker } from './lib/hikeDirection'
import { beginContribution } from './lib/contributionFlow'
import { listQueued } from './lib/outbox'
import type { BoundingBox, MapPoint } from './lib/legendContents'
import type { SearchablePoi } from './lib/searchPoi'
import './App.css'
// Last, and entirely inside media queries - see the file header. Nothing in it
// can match a phone, which is how the WEBSITE.md §8 constraint is kept
// structurally rather than by review.
import './desktop.css'

const TRAIL_NAME = 'Appalachian Trail'

// Sign in, sign out, sync and export are all rendered and all do nothing: what
// they need is the backend, which is Phase 2 (ROADMAP.md). They share one
// placeholder rather than getting an identical empty arrow each, because the
// sign-out control in particular is unreachable today - Settings renders it
// only when `account` is set, and that is hardcoded null below - and four
// separate copies would mean carrying a function nothing can ever call.
const notYet = () => undefined

// The whole trail, Springer to Katahdin, as the opening view. Taken from the
// published topo archive's own header bounds, so it frames exactly the ground
// the map actually covers rather than a hand-typed guess.
//
// Opening on the entire corridor rather than a point on it because before there
// is a GPS fix the app genuinely does not know where the hiker is, and Harpers
// Ferry - the previous default - is a confident-looking answer to that question
// that is wrong for everyone not standing in Harpers Ferry. A view of the whole
// trail says "somewhere on this" honestly, and the first fix zooms in.
const CORRIDOR_BOUNDS: [[number, number], [number, number]] = [
  [-84.73, 34.2],
  [-68.3, 46.34],
]

const EMPTY_BBOX: BoundingBox = { west: 0, south: 0, east: 0, north: 0 }

/** Close enough to read a shelter's surroundings, on the first GPS fix. */
const FIX_ZOOM = 13

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
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set())
  const [bbox, setBbox] = useState<BoundingBox>(EMPTY_BBOX)

  const [trailIndex, setTrailIndex] = useState<TrailIndex | null>(null)
  const [pois, setPois] = useState<StoredPoi[]>([])
  const [trailsUrl, setTrailsUrl] = useState<string>(emptyTrailsUrl)
  const [dataError, setDataError] = useState<string | null>(null)

  const [reporting, setReporting] = useState<ReportingState>(null)
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
  const hasJumpedToFix = useRef(false)

  const now = useClock()
  const online = useOnline()
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
  } = useArchiveDownload(archiveUrl(detailLevel))

  const refreshTrailData = useCallback(async () => {
    const data = await loadTrailData()
    if (data === null) return

    setTrailsUrl(URL.createObjectURL(data.trails))
    setPois(data.pois)

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

  // The map is usually built long before a fix arrives, so the first one moves
  // the camera imperatively. Only the first: after that the view belongs to
  // whoever is panning it.
  //
  // `map` is a dependency because a fix that lands while another tab is
  // showing has no map to move. Without it that fix was simply dropped - the
  // effect had already run against a null map and would not run again - and
  // the hiker stayed looking at the whole trail until the watch happened to
  // report again.
  useEffect(() => {
    if (map === null || gps.status !== 'located' || hasJumpedToFix.current) return

    map.jumpTo({ center: [gps.at.lon, gps.at.lat], zoom: FIX_ZOOM })
    hasJumpedToFix.current = true
  }, [map, gps])

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
      await beginContribution(draft, authoredAt)
      setReporting(null)
    },
    [],
  )

  // Nothing renders until the phone's own preferences have been read, so a
  // returning hiker never sees a flash of the first-run onboarding.
  if (!preferencesLoaded) return null

  if (!preferences.onboarding_completed) {
    return <Onboarding onComplete={handleOnboardingComplete} />
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
            account={null}
            reporterType="thru"
            onSignIn={notYet}
            onSignOut={notYet}
            preferences={preferences}
            onChange={updatePreferences}
            lastSyncedAt={lastSyncedAt}
            onSync={notYet}
            onExport={notYet}
            now={now}
            onStartReport={() => setReporting({ step: 'pick' })}
            queuedReportCount={queuedCount}
          />
        </div>
        <TabBar active={activeTab} onSelect={setActiveTab} />
      </div>
    )
  }

  return (
    <MapScreen
      topoArchiveUrl={CORRIDOR_ARCHIVE_URL}
      trailsUrl={trailsUrl}
      background={preferences.background_source}
      trailName={TRAIL_NAME}
      mile={fix?.mile}
      direction={direction?.direction}
      time={now}
      online={online}
      hasGpsFix={gps.status === 'located'}
      lastSyncedAt={lastSyncedAt}
      activeTab={activeTab}
      onSelectTab={setActiveTab}
      onOpenLegend={() => setLegendOpen(true)}
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
      viewportPoints={viewportPoints}
      blazeCounts={[]}
      hiddenTypes={hiddenTypes}
      onToggleType={handleToggleType}
      // The corridor is the opening view only. Once there is a camera to put
      // back, it wins: `bounds` would otherwise re-frame the entire trail
      // every time the map screen came back from another tab.
      center={camera?.center}
      zoom={camera?.zoom}
      bounds={camera === null ? CORRIDOR_BOUNDS : undefined}
      onViewportChange={handleViewportChange}
      onMapReady={handleMapReady}
    />
  )
}

export default App
