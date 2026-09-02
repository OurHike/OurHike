// The trail's own data - centerline, POIs, elevation profile - and how it gets
// onto the phone.
//
// Lifted out of App.tsx whole. Six pieces of state, three effects, a ref
// holding an in-flight promise and four callbacks, all of which only ever
// talked to each other: nothing else in the shell writes any of it, and the
// only things outside that read it are the map screen and the download card,
// which take the finished values. That is a module, and it was sitting in the
// middle of a two-thousand-line component being read past.
//
// What did NOT move is the deciding: `trailLinesMissing`, the notice the
// download card shows, and which sheets are downloadable are all the shell's
// calls about what this hook reports, and they stay where the rest of that
// reasoning is.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { DATA_CONFIGURED, TRAILS_KEY } from './config'
import type { TrailIndex } from './trailPosition'
import { packPois, resolveTrailIndex } from './trailIndexBuild'
import {
  downloadTrailData,
  haveTrailData,
  loadTrailData,
  loadTrailLines,
  TrailDataHashMismatchError,
  type StoredPoi,
} from './trailData'
import { EMPTY_CLUB_SECTIONS, type ClubSections } from './clubSections'
import { EMPTY_STEWARDS, type Stewards } from './stewards'
import {
  loadNearbyTrails,
  loadNetworkOverview,
  type NearbyTrailsAnswer,
} from './nearbyTrailData'
import {
  isSettledAbsence,
  loadTrailGraph,
  type TrailNetworkAbsence,
  type TrailNetworkState,
} from './trailGraphData'
import type { TrailGraphIndex } from './trailGraph'
import { fetchTrailOverview } from './trailOverview'
import type { Highlight } from './highlights'
import { NO_TOMBSTONES, type Tombstones } from './poiIdentity'
import type { ElevationProfile } from './elevationProfile'
import type { SpurRecord } from './spurDestination'
import { publishedSnapshot } from './dataManifest'
import {
  availableRefresh,
  dismissRelease,
  dismissedRelease,
  recallRelease,
  warnsAboutData,
  type AvailableRefresh,
} from './dataRefresh'

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
 * (#238). Typed at the moment the error still has a type - matching on message
 * text would break the day the sentence was reworded.
 */
/**
 * How far a waypoint's published mile may sit from where the index would
 * place it before the console hears about it (#1192).
 *
 * @unvalidated - reasoned from one release, not measured against several.
 * The largest backward step in the 2026-09-02 release's own vertex miles is
 * 0.27 mi (pipeline/export_trails.py's manifest records it per release), so a
 * waypoint beside such a step can honestly read a quarter-mile from its
 * nearest vertex; anything past that has no explanation inside one release.
 * What would settle it: the axisDrift the worker reports across the next few
 * releases, which is exactly what this warning surfaces.
 */
export const AXIS_DRIFT_WARN_MILES = 0.3

export interface TrailDataError {
  kind: 'hash-mismatch' | 'error'
  message: string
}

function describeTrailDataError(error: unknown): TrailDataError {
  if (error instanceof TrailDataHashMismatchError) {
    return { kind: 'hash-mismatch', message: error.message }
  }
  return {
    kind: 'error',
    message: error instanceof Error ? error.message : 'Trail data failed to download.',
  }
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

export interface TrailData {
  /**
   * The published release this phone does not have, or null (#919).
   *
   * Null is the answer for "nothing newer", "nothing downloaded yet" and
   * "could not ask" alike - none of the three is something to put in front of
   * anybody, and collapsing them here keeps the shell from having to know
   * which it is looking at.
   */
  update: AvailableRefresh | null
  /** Whether to caution about what taking it costs: not on wifi, and big
   *  enough to matter. An unknown size counts as big - see warnsAboutData. */
  updateWarnsAboutData: boolean
  /** True while the bytes are coming, so the prompt can say so rather than
   *  vanishing into a map that has not changed yet. */
  applyingUpdate: boolean
  /** Take it. Re-downloads the whole vector set, committed all-or-nothing. */
  applyUpdate: () => Promise<void>
  /** Not now, remembered against this version so the next release still asks. */
  declineUpdate: () => Promise<void>
  /** The centerline index, or null when there is none to build one from - and
   *  null too when the file was there and unreadable, which is best-effort on
   *  purpose (see below). */
  trailIndex: TrailIndex | null
  /**
   * Where each of `pois` sits on `trailIndex`, one mile per waypoint in the
   * same order, NaN where it has none - or null while the index is still
   * being built, and after a build that failed (#1192).
   *
   * Beside the index rather than derived from it in a memo, because deriving
   * it was the freeze: 16,949 nearest-vertex searches in one render. It is
   * now answered where the index is built, off this thread, and on the
   * pipeline's axis it is simply each waypoint's published mile. Null and
   * NaN both read as "unknown" downstream, which is the honest state of a
   * waypoint nobody has placed yet.
   */
  poiMiles: Float64Array | null
  pois: StoredPoi[]
  /** Spur detail keyed by trail id (pipeline/export_spurs.py). Empty until a
   *  release that publishes it is on the phone - the map draws every spur
   *  either way, the line-detail sheet (#134) just cannot say where one
   *  goes. */
  spurs: Record<string, SpurRecord>
  elevation: ElevationProfile | null
  /** Who maintains which stretch (pipeline/export_club_sections.py, #594).
   *  Empty until a release that publishes it is on the phone, which costs the
   *  corridor view its subject and nothing else. */
  clubSections: ClubSections
  /** Who the map's data belongs to (#927), for the About tab's sources
   *  section. Empty until a download lands, and on any release built before
   *  pipeline/export_sources.py existed. */
  stewards: Stewards
  /** Stretches worth going to (pipeline/export_highlights.py, #595). Empty
   *  until a release that publishes them is on the phone. */
  highlights: Highlight[]
  /** Every POI id this project has ever retired (#831,
   *  pipeline/export_retired_poi.py). Empty for a release that publishes none
   *  and for a bucket whose ledger has retired nothing — the same state, and
   *  neither is a failure. Empty costs a hiker the card that says what
   *  happened to a place they saved something on. */
  retiredPois: Tombstones
  trailsUrl: string
  /**
   * The corridor-view centerline to draw INSTEAD, while there is no real one
   * (#869) - and null the moment there is, which is what makes it a stand-in
   * rather than a second trail line.
   *
   * Null too on a phone that has the release already, because it never had a
   * gap to fill: this is worth 51 KB of somebody's data only on the launch
   * where the alternative is an empty map for five seconds.
   */
  overviewTrailsUrl: string | null
  /**
   * The trail lines other organizations maintain, as an object URL, or null
   * (#950, lib/nearbyTrailData.ts).
   *
   * Null is the ordinary answer today and is not a failure: publish.py holds
   * that artifact back while NYS OPRHP's or NYNJTC's reuse terms are unstated
   * (pipeline/sources.json), so the bucket does not have one to fetch.
   *
   * Unlike `overviewTrailsUrl` above, this is never withdrawn once set. The
   * overview is a stand-in for a line that is coming; these are lines of
   * their own.
   */
  nearbyTrailsUrl: string | null
  /**
   * The corridor-view sketch of that whole network, as an object URL, or null
   * (#1135, lib/nearbyTrailData.ts's loadNetworkOverview).
   *
   * What the OPENING camera draws: below the pin seam the full network's
   * layers do not draw at all (map/style.ts's minzoom on them), so without
   * this the map's first screen shows the A.T. alone however many
   * organizations' trails the phone holds. 255 KB gzipped for all of them,
   * measured 2026-08-27 (pipeline/spike_network_overview.py).
   *
   * Like `nearbyTrailsUrl` and unlike `overviewTrailsUrl`: never withdrawn
   * once set, because nothing better replaces it - it IS the below-seam
   * network, not a stand-in for one. Null is ordinary: an older release, or
   * a bucket holding the artifact back with its parent.
   */
  networkOverviewUrl: string | null
  /** The junction graph's routing half, indexed - or null while this phone
   *  has not got one, which PlanKindSheet reads as "no day hikes yet". The
   *  two heavy halves are NOT here: the edge vertices and the per-edge climb
   *  (#1011) are fetched lazily when the builder opens
   *  (lib/trailGraphData.fetchTrailGraphGeometry and
   *  fetchTrailGraphElevation), because with the whole A.T. in the graph they
   *  are far heavier than the routing half and a launch that never opens the
   *  builder should not pay for either. */
  graphIndex: TrailGraphIndex | null
  /**
   * The same fact with its REASON attached, for the one surface that speaks
   * to a hiker about it (#1049).
   *
   * `graphIndex` above answers "can the router route", which is what almost
   * everything needs. This answers "what do I tell somebody who just asked
   * for a day hike", and those are different questions: four of the five ways
   * to have no graph never resolve by waiting, and the door used to promise
   * all of them a data sync.
   */
  trailNetwork: TrailNetworkState
  /**
   * Ask the bucket for the graph again.
   *
   * A no-op unless the last answer was one a connection could cure - see
   * `isSettledAbsence`. A 404 re-requested on a button press is a hammer on a
   * bucket that has already answered, and the sheet only offers the button
   * where it is honest to.
   */
  retryTrailNetwork: () => void
  /** Whether the map has a real trail line on it, as against the empty
   *  collection the style is seeded with. */
  haveTrailLines: boolean
  /** The download's failure, or null. */
  error: TrailDataError | null
  /**
   * The data on the phone, fetching it only if it is not already here.
   *
   * Not a choice anyone is offered: it is a few megabytes against a background
   * measured in hundreds, and it is what makes the app an app rather than a
   * map viewer, so it is downloaded by default wherever it is missing (the
   * launch effect does the same, unprompted). Called before the background
   * too, where it doubles as the canary: whatever stopped these few megabytes
   * - no signal, a missing key, a misconfigured bucket - will stop the next
   * several hundred, and finding that out costs a hiker their data allowance
   * to learn nothing.
   *
   * Returns whether to go on.
   */
  ensure(): Promise<boolean>
}

export interface TrailDataOptions {
  /**
   * Draw the centerline and read nothing else off the phone (#857).
   *
   * First run is the case this exists for. The three entry steps sit over the
   * map (App.tsx's `entering`), the card covers up to 78% of the screen, and
   * the only thing anybody can see behind it is the trail line - while the
   * shell reads 2,837 POIs back out of IndexedDB, places every one of them on
   * a mile axis, folds them into sites, hands them to MapLibre and rasterises
   * 46 pin images for them. None of that reaches a pixel a hiker can see, and
   * all of it is on the thread the Skip button is waiting for.
   *
   * Measured 2026-08-20, Chromium at 390x844 on a 4x CPU throttle against a
   * build serving artifacts at the live release's sizes (#717's figures),
   * replaying first run with the release already on the phone: 5,479 ms of
   * blocking work in 22 long tasks while the steps were up, the longest of
   * them 2,374 ms, and the second Skip could not be clicked for 3.4 s after
   * the first. Same run with this held back: 3,673 ms, longest task 434 ms,
   * the three taps answered in 11, 4 and 220 ms.
   *
   * So the centerline is published and everything else waits. Nothing is
   * skipped, only held: the moment this goes false the second effect below
   * reads the rest, and the map fills in.
   *
   * NOT the download - that keeps running while the steps are read, which is
   * the whole reason it starts before them. This is about what the shell does
   * with what has landed.
   */
  centerlineOnly?: boolean
}

/**
 * One verified network artifact's state machine, shared by the nearby-trail
 * network and its corridor-view sketch (#1082, #1135) so the two cannot
 * drift - every guard below is load-bearing and was tuned on the first of
 * them.
 *
 * One refresh attempt per online spell, cleared when signal drops. This is
 * the loop guard the loaders' contract asks their caller for: every failed
 * refresh answers `revalidated: false` so the asking can RESUME on the next
 * real reconnection - a captive portal at a trailhead says "online" while
 * carrying nothing, and treating its failure as final would hold yesterday's
 * closures off the map all day - but re-asking within the same online spell
 * would loop against a manifest that is simply down. And never again once an
 * answer has actually been verified against the manifest.
 *
 * `ready` is the caller's sequencing gate (#1117), applied ONLINE ONLY: the
 * offline path always falls through to the store read, so a phone with no
 * signal draws its last verified copy on the first tick whatever the gate
 * says. `load` must be module-stable - it is in the dependency list, and a
 * closure would re-arm this on every render.
 */
function useVerifiedNetworkArtifact(
  load: (online: boolean, signal?: AbortSignal) => Promise<NearbyTrailsAnswer | null>,
  online: boolean,
  ready: boolean,
): NearbyTrailsAnswer | null {
  const [answer, setAnswer] = useState<NearbyTrailsAnswer | null>(null)
  const tried = useRef(false)
  useEffect(() => {
    if (!online) tried.current = false
  }, [online])

  useEffect(() => {
    // The state is in the dependency list so that setting it re-runs this
    // and takes one of the early returns.
    if (!DATA_CONFIGURED) return
    if (online && !ready) return
    if (answer !== null && answer.revalidated) return
    if (!online && answer !== null) return
    if (online && tried.current) return
    if (online) tried.current = true

    const controller = new AbortController()
    let wanted = true

    void load(online, controller.signal).then((fresh) => {
      if (fresh === null) return
      // An object URL nothing will draw is a blob the page holds until it is
      // closed - the same reason the A.T. overview revokes an answer it no
      // longer wants.
      if (!wanted) {
        URL.revokeObjectURL(fresh.url)
        return
      }
      setAnswer((previous) => {
        // Same bytes, by hash: keep the URL the map has already parsed and
        // throw the new one away, carrying over only what the refresh
        // learned. Swapping URLs here would make MapLibre re-fetch and
        // re-tile megabytes of identical GeoJSON mid-hike for pixels that
        // cannot change. Returning `previous` unchanged when nothing was
        // learned lets React bail out entirely.
        if (previous !== null && previous.hash === fresh.hash) {
          URL.revokeObjectURL(fresh.url)
          // OR, never overwrite: a verified answer stays verified even if a
          // later attempt failed - which the guards above make unreachable,
          // and cheap insurance against the day they move.
          const revalidated = previous.revalidated || fresh.revalidated
          return revalidated === previous.revalidated
            ? previous
            : { ...previous, revalidated }
        }
        // A new release arrived: the old URL is revoked - safe at this
        // point: MapLibre reads a blob URL once, when `setData` hands it
        // over, and a URL this state has held has either been read by now
        // or is being replaced before any map mounted. Parsed tiles outlive
        // the URL either way.
        if (previous !== null) URL.revokeObjectURL(previous.url)
        return fresh
      })
    })

    return () => {
      wanted = false
      controller.abort()
    }
  }, [load, online, answer, ready])

  return answer
}

export function useTrailData(
  online: boolean,
  { centerlineOnly = false }: TrailDataOptions = {},
): TrailData {
  const [trailIndex, setTrailIndex] = useState<TrailIndex | null>(null)
  const [poiMiles, setPoiMiles] = useState<Float64Array | null>(null)
  /** Which read of the release is the current one - see readTheRest. */
  const readToken = useRef(0)
  const [pois, setPois] = useState<StoredPoi[]>([])
  const [spurs, setSpurs] = useState<Record<string, SpurRecord>>({})
  const [elevation, setElevation] = useState<ElevationProfile | null>(null)
  const [clubSections, setClubSections] = useState<ClubSections>(EMPTY_CLUB_SECTIONS)
  const [stewards, setStewards] = useState<Stewards>(EMPTY_STEWARDS)
  const [highlights, setHighlights] = useState<Highlight[]>([])
  const [retiredPois, setRetiredPois] = useState<Tombstones>(NO_TOMBSTONES)
  const [trailsUrl, setTrailsUrl] = useState<string>(emptyTrailsUrl)
  const [haveTrailLines, setHaveTrailLines] = useState(false)
  const [overviewUrl, setOverviewUrl] = useState<string | null>(null)
  const [graphIndex, setGraphIndex] = useState<TrailGraphIndex | null>(null)
  /** Why there is no graph, or null while nothing has answered yet. The two
   *  are different on screen: "looking" is not "there isn't one". */
  const [graphAbsence, setGraphAbsence] = useState<TrailNetworkAbsence | null>(null)
  /** Bumped by `retryTrailNetwork` to make the effect below run again. A
   *  counter rather than a flag because two retries in a row must both fire,
   *  and re-setting a flag to the same value would not. */
  const [graphAttempt, setGraphAttempt] = useState(0)
  /** Whether the phone has been asked whether it holds trail lines yet.
   *  Distinct from holding none: for the first tick of every launch those two
   *  look the same, and one of them is a reason to spend a hiker's data. */
  const [centerlineRead, setCenterlineRead] = useState(false)
  const [error, setError] = useState<TrailDataError | null>(null)
  /**
   * Whether the launch fetch has stopped competing for the pipe (#1117).
   *
   * The two background artifacts below - the other organizations' lines and
   * the junction graph - used to start alongside `trails.geojson` and one of
   * them is nearly twice its size. MEASURED on a cold first run against the
   * published artifacts, Chromium throttled to 4,000 kbps / 100 ms and 4x CPU,
   * two runs agreeing: `trail_graph.json` (1,176 KB) opened at 1,524 ms,
   * `trails.geojson` (3,891 KB) at 1,830 ms, `nearby_trails.geojson`
   * (7,524 KB) at 2,612 ms - and the trail line, the one thing every entry
   * step is talking about, did not land until 20,267 ms of a 32,325 ms launch
   * that moved 14.71 MB.
   *
   * SETTLED, not "succeeded". See the launch effect's `finally`.
   *
   * A warm launch releases this within milliseconds - `fetchOnce` returns
   * after two small IndexedDB reads once the phone holds a release - so this
   * costs a returning hiker nothing. It is only ever a wait on the cold run,
   * which is the only run where those two artifacts have anything to compete
   * with.
   */
  const [trailFetchSettled, setTrailFetchSettled] = useState(false)

  /**
   * Two counters, because the two halves of a release no longer land at the
   * same moment (#863).
   *
   * `centerlineAt` is bumped when trail lines become readable - which on a
   * phone that held nothing is BEFORE the waypoints have been fetched, and on
   * every other download is at the final commit. `releaseAt` is bumped when
   * the whole release is committed.
   *
   * One counter would not do. Bumping it twice on a first download would
   * re-read the same trail lines and mint a second object URL for them, and
   * re-pointing that source costs MapLibre a re-tile of twelve megabytes of
   * coordinates - at the exact moment the download window is opening. Counters
   * rather than callbacks so each read is an effect with its own schedule
   * (and its own cleanup) instead of a promise chain that has to know which
   * of them has already happened.
   */
  const [centerlineAt, setCenterlineAt] = useState(0)
  const [releaseAt, setReleaseAt] = useState(0)

  /**
   * The trail line, onto the map.
   *
   * Its own read, and the cheap one: `loadTrailLines` hands back a Blob
   * HANDLE, so this costs an IndexedDB round trip and an object URL rather
   * than deserialising every POI beside it.
   */
  const drawCenterline = useCallback(async () => {
    const lines = await loadTrailLines()
    // Answered either way, and before the early return: "no lines" is what
    // sends the overview fetch below, and it is not the same answer as "not
    // asked yet".
    setCenterlineRead(true)
    if (lines === null) return

    setTrailsUrl(URL.createObjectURL(lines))
    // Set here rather than derived from `trailsUrl`, which starts life as a
    // perfectly valid object URL for an empty collection and so cannot answer
    // "is there a trail on this map". Nothing else can answer it either: the
    // POIs are a separate artifact and the index is best-effort, so a phone
    // can hold both and still be drawing no line.
    setHaveTrailLines(true)
  }, [])

  /** Everything the centerline does not need: the waypoints, the spur
   *  destinations, the elevation profile, and the index that puts a
   *  coordinate on a mile. */
  const readTheRest = useCallback(async () => {
    const data = await loadTrailData()
    if (data === null) return

    setPois(data.pois)
    setSpurs(data.spurs)
    setElevation(data.elevation)
    setClubSections(data.clubSections)
    setStewards(data.stewards)
    setHighlights(data.highlights)
    setRetiredPois(data.retiredPois)

    // The index and the waypoints' miles, built off this thread (#1192,
    // lib/trailIndexBuild.ts) - a worker where there is one, slices where
    // there is not, and a per-release cache in front of both. The waypoints
    // above are already in state, so the screen renders with every mile
    // unknown and fills in when this answers, rather than freezing until it
    // can claim to know: on a 4x-throttled phone profile the old synchronous
    // build and placement held the thread for 13 s.
    //
    // Best-effort, and separate from the POIs above on purpose. A shelter is
    // findable by name with no geometry at all, so a trails.geojson that
    // arrived truncated or malformed should cost the mile numbers decorating
    // each row and nothing else. A throw anywhere in the build - JSON.parse
    // on half a file is the likely one - lands here as "no index, no miles",
    // never as an unhandled rejection out of the `void readTheRest()` below.
    //
    // The token is for the second read a re-download triggers while the first
    // is still building: whichever finished last would otherwise win, and the
    // one that finished last is not reliably the newer release.
    const token = (readToken.current += 1)
    try {
      const release = await recallRelease()
      const { index, poiMiles, axisDrift } = await resolveTrailIndex({
        trails: data.trails,
        trailMiles: data.trailMiles,
        pois: packPois(data.pois),
        trailsHash: release?.hashes[TRAILS_KEY] ?? null,
      })
      if (token !== readToken.current) return
      // The consistency check the anchors used to be (#1192): said, never
      // acted on. Only a maintainer reading a console will ever see it, and
      // that is the right audience - a hiker cannot do anything with "the
      // miles file disagrees with the lines file" except not trust the app.
      if (axisDrift !== null && axisDrift.maxMiles > AXIS_DRIFT_WARN_MILES) {
        console.warn(
          `trail_miles.json and the placed waypoints disagree, over ` +
            `${axisDrift.sampled} sampled waypoints, by up to ` +
            `${axisDrift.maxMiles.toFixed(3)} (miles on the pipeline axis); ` +
            `the two files may not be the pair they claim to be.`,
        )
      }
      setTrailIndex(index)
      setPoiMiles(poiMiles)
    } catch {
      if (token !== readToken.current) return
      setTrailIndex(null)
      setPoiMiles(null)
    }
  }, [])

  /**
   * The fetch that is in flight, so that re-renders, connectivity flapping and
   * a tapped download cannot start a second one. A ref rather than state
   * because nothing renders from it.
   *
   * THE PROMISE, not a boolean, and that is the whole point of it. It was a
   * flag, which only the launch fetch ever read - so a hiker who tapped
   * Download while that fetch was still running got `loadTrailData()` back as
   * null (nothing committed yet), and pulled the same 12.3 MB of
   * trails.geojson a second time, against the same connection, ahead of the
   * archive they were actually waiting for. Sharing the attempt means the tap
   * waits for the bytes already coming rather than racing them.
   *
   * Cleared when it settles, either way: a fetch that failed must be retryable
   * when signal returns, and one that succeeded leaves `loadTrailData()`
   * answering from the phone, which is cheaper than any flag.
   */
  const inFlight = useRef<Promise<void> | null>(null)

  /**
   * Fetched at most once at a time. Rejects with whatever the fetch rejected
   * with - both callers report it, differently: the launch fetch nobody asked
   * for reports through the status strip, a tapped download reports on the card
   * that was tapped.
   */
  const fetchOnce = useCallback(() => {
    const current = inFlight.current
    if (current !== null) return current

    const attempt = (async () => {
      // Asked directly rather than assumed: a phone that already has a WHOLE
      // release needs no network at all. A read of two small things rather
      // than of everything - see haveTrailData, which also decides what a
      // half-downloaded release means.
      if (await haveTrailData()) return
      // The lines are drawn the moment they are on the phone, which on a first
      // download is several seconds before the waypoints beside them - that is
      // the whole of #863, and the reason this is a callback rather than
      // something read after the promise resolves.
      await downloadTrailData({ onCenterline: () => setCenterlineAt((at) => at + 1) })
      setReleaseAt((at) => at + 1)
    })()
    inFlight.current = attempt
    const clear = () => {
      if (inFlight.current === attempt) inFlight.current = null
    }
    attempt.then(clear, clear)
    return attempt
  }, [])

  /**
   * The published release this phone does not have, or null (#919).
   *
   * Null covers three different situations and deliberately renders as one:
   * nothing downloaded yet, nothing newer published, and a manifest that could
   * not be read. None of them is something to say to a hiker - the first is the
   * launch fetch's job, the second is the normal state, and the third is not a
   * claim about anything.
   */
  const [update, setUpdate] = useState<AvailableRefresh | null>(null)
  const [applyingUpdate, setApplyingUpdate] = useState(false)

  /**
   * Ask the bucket whether this phone is current, on launch and when signal
   * returns.
   *
   * Beside the `conditions/*` refresh that already works this way
   * (useConditions.ts) - the maintainer's decision of 2026-08-21 was for this
   * check to run there, and it costs one `latest.json` read, the same 3.5 KB
   * the launch fetch pays anyway.
   *
   * `releaseAt` is in the deps so that accepting an update re-asks and clears
   * the prompt from what is now true, rather than from what this code believes
   * it just did.
   */
  useEffect(() => {
    if (!DATA_CONFIGURED || !online) return

    const controller = new AbortController()
    let wanted = true

    void (async () => {
      const stored = await recallRelease()
      if (stored === null) return
      const snapshot = await publishedSnapshot({ signal: controller.signal })
      const found = availableRefresh(stored, snapshot)
      // A release the hiker has already declined. Silenced by version, so the
      // next one asks again - see dismissRelease.
      const declined = found === null ? null : await dismissedRelease()
      if (!wanted) return
      setUpdate(found !== null && declined === snapshot.version ? null : found)
    })().catch(() => {
      // Never fatal and never reported. A phone that could not ask is a phone
      // with the data it already had, which is the state it was in a moment
      // ago - and an error about a check nobody requested would be noise on
      // top of a map that is working.
    })

    return () => {
      wanted = false
      controller.abort()
    }
  }, [online, releaseAt])

  /**
   * Take the update, having been asked.
   *
   * Re-downloads the whole vector set rather than the changed artifacts alone,
   * and that is a choice worth stating: it is 5.78 MB against about 0.67 MB for
   * a POI-only release (measured 2026-08-21), and it buys the commit
   * `downloadTrailData` already makes - every artifact verified and stored
   * together, or none of them. Replacing files one at a time would mean a phone
   * that could hold half of one release and half of another, which is a state
   * nothing else in this app has to reason about and nothing should have to.
   */
  const applyUpdate = useCallback(async () => {
    setApplyingUpdate(true)
    setError(null)
    try {
      await downloadTrailData()
      setReleaseAt((at) => at + 1)
      setCenterlineAt((at) => at + 1)
      setUpdate(null)
    } catch (thrown) {
      setError(describeTrailDataError(thrown))
    } finally {
      setApplyingUpdate(false)
    }
  }, [])

  /** Not now. Remembered against the version declined, so this release stops
   *  asking and the next one does not inherit the answer. */
  const declineUpdate = useCallback(async () => {
    const version = update?.version ?? null
    setUpdate(null)
    if (version !== null) await dismissRelease(version)
  }, [update])

  // Reading what is already on the phone, and unconditionally. This has to stay
  // independent of the fetch below: an unconfigured build and a phone with no
  // signal both still have whatever was downloaded last time, and gating this
  // on either one would leave a hiker on a ridge - the exact person the offline
  // store exists for - looking at a map with no trail.
  useEffect(() => {
    void drawCenterline()
  }, [drawCenterline, centerlineAt])

  // And the rest of it, which is everything the entry steps do not show. Held
  // rather than skipped: `centerlineOnly` going false is what runs this, so a
  // hiker who finishes first run gets their waypoints on the same read they
  // would have had, one step later. See TrailDataOptions for what that step is
  // worth.
  useEffect(() => {
    if (centerlineOnly) return
    void readTheRest()
  }, [centerlineOnly, readTheRest, releaseAt])

  // The trail lines load themselves, rather than waiting for someone to tap
  // Download.
  //
  // They are a few megabytes against the archive's 314 MB - the download flow
  // already treats them that way, fetching them first as the canary - and they
  // are not decoration on the map, they ARE the map: without them the app opens
  // on a background with no trail on it, no POIs, nothing to search and no
  // elevation ribbon. Making the whole corridor download a precondition for
  // seeing where the Appalachian Trail runs is the wrong trade at any
  // connection speed, and it is the state every first run was in.
  //
  // NOT quiet about failing, which is what this used to be, and the reasoning
  // for the quiet was wrong in a way worth writing down rather than deleting.
  // It ran: the hiker did not ask for this, so a failure is not a result they
  // are owed a message about - it leaves exactly the empty map they would have
  // had anyway, and the Downloads screen still reports the download they DO ask
  // for.
  //
  // Both halves fail. "The empty map they would have had anyway" is a map with
  // no Appalachian Trail drawn on it, which is not the empty state but a broken
  // one - the lines are not decoration on the map, they ARE the map. And the
  // Downloads screen only reports what was tapped, so a launch fetch that
  // failed was recorded nowhere at all.
  //
  // What that cost is the bug report this comment was rewritten for: an app
  // whose trail line was missing because the bucket refused its origin, and
  // whose entire account of itself was a map with no trail on it. The failure
  // is carried the same way a tapped download's is now, and the status strip
  // says the trail is missing so the sentence is findable from the screen the
  // missing line is on. Retried when the phone comes back online, which is the
  // one condition likely to have changed.
  useEffect(() => {
    if (!DATA_CONFIGURED || !online) return

    let cancelled = false

    // Deduplicated inside fetchOnce rather than by a flag here, so that a
    // download tapped while this is still running joins it instead of fetching
    // the same megabytes alongside it.
    void fetchOnce()
      .catch((thrown: unknown) => {
        // Not reported if the effect was torn down under us: by then this is a
        // fetch nobody is waiting on, and a notice about it would outlive the
        // screen that could act on it. Nothing is stored either way -
        // downloadTrailData commits all four files or none - so coming back into
        // signal can simply try again.
        if (cancelled) return
        setError(describeTrailDataError(thrown))
      })
      // EITHER WAY, which is the half that keeps this from being a trap: the
      // two effects below wait on this flag, and a phone whose trail fetch
      // failed must not be left holding them forever. A failed launch fetch
      // releases the gate and they run exactly as they did before #1117.
      .finally(() => {
        if (!cancelled) setTrailFetchSettled(true)
      })

    return () => {
      cancelled = true
    }
  }, [fetchOnce, online])

  // Revoking belongs here rather than inside the setTrailsUrl updater it used
  // to live in. A state updater has to be pure: React may run it more than once
  // for a single update and may throw a render away entirely, and either one
  // leaked a blob URL - or, in the discarded-render case, revoked the URL the
  // map was still using. As a cleanup it runs exactly once per value, when that
  // value stops being current, which is precisely when the bytes behind it stop
  // being needed.
  useEffect(() => () => URL.revokeObjectURL(trailsUrl), [trailsUrl])

  /**
   * The corridor-view sketch, fetched once and only while it would be the
   * only trail line on the map (#869).
   *
   * Gated on what the phone turned out to hold rather than on "is this a
   * first run", because that is the actual question: a phone with the release
   * already on it draws the real line within a tick of launching and never has
   * a gap for this to fill, so fetching it would be 51 KB of somebody's data
   * spent on a frame nobody sees. On an empty phone the real line is seconds
   * away and this is the map the entry steps are talking about.
   *
   * Which is why it waits for `centerlineRead` and not merely for
   * `haveTrailLines` to be false. Those two are indistinguishable for the
   * first tick of EVERY launch - the IndexedDB read has not answered yet - and
   * starting on that tick would fetch the sketch on every launch a returning
   * hiker ever makes. The wait costs nothing: the bytes are already in the
   * HTTP cache by then, preloaded from the document head (vite.config.ts), so
   * what this runs is a cache read.
   *
   * The abort is what makes the race safe rather than lucky: the real line can
   * land while this is in flight, and the cleanup below both cancels the
   * request and throws away an answer that arrives anyway.
   */
  useEffect(() => {
    if (!DATA_CONFIGURED || !online || !centerlineRead || haveTrailLines) return

    const controller = new AbortController()
    let wanted = true

    void fetchTrailOverview(controller.signal).then((url) => {
      if (url === null) return
      // Revoked rather than kept: an object URL nothing draws is a blob the
      // page holds until it is closed, and by here the real line has won.
      if (!wanted) {
        URL.revokeObjectURL(url)
        return
      }
      setOverviewUrl(url)
    })

    return () => {
      wanted = false
      controller.abort()
    }
  }, [online, centerlineRead, haveTrailLines])

  // Dropped as soon as there is a real line, and revoked with it. Both halves
  // matter: the sketch is only true below the pin seam, and a blob URL that
  // outlives its layer is a leak with nothing pointing at it.
  useEffect(() => {
    if (!haveTrailLines || overviewUrl === null) return
    URL.revokeObjectURL(overviewUrl)
    setOverviewUrl(null)
  }, [haveTrailLines, overviewUrl])

  /**
   * The other organizations' trails (#950), from the store first and checked
   * against the manifest once per online launch (#1082).
   *
   * NOT GATED ON WHAT THE PHONE HOLDS the way the overview above is, because
   * the store IS what the phone holds: lib/nearbyTrailData.ts keeps the last
   * verified copy, serves it with or without signal, and re-fetches the
   * 7.3 MB artifact only when the manifest names a hash the stored copy does
   * not carry - a ~KB question on the ordinary launch, where this used to be
   * the whole artifact every time (pipeline/README.md's "one number wants
   * watching"). What a named download CONTAINS is still
   * **#552 — Decide the unit of offline coverage, and write it down**'s
   * decision - see that module's header for the line between this cache and
   * that machinery.
   *
   * Behind the trail line, never beside it (#1117): the gate holds the online
   * fetch until the launch fetch settles either way. On the cold run where
   * the refetch would be the whole 7.5 MB artifact, there is no stored copy
   * to draw in the meantime either, so the wait costs a hiker nothing
   * visible and buys `trails.geojson` the pipe.
   */
  const nearbyTrails = useVerifiedNetworkArtifact(
    loadNearbyTrails,
    online,
    trailFetchSettled,
  )

  /**
   * The corridor-view sketch of that network (#1135), through the same state
   * machine and deliberately NOT behind #1117's gate: this is what the
   * OPENING camera draws - below the pin seam the full network's layers do
   * not draw at all - and at 255 KB gzipped (measured 2026-08-27,
   * pipeline/spike_network_overview.py) it is the A.T. sketch's kind of
   * fetch, not the 7.5 MB kind that gate exists to sequence. Ungated, the
   * first screen's lines arrive in the overview class of seconds; gated,
   * they would wait ~30 s behind a fetch they do not need.
   */
  const networkOverview = useVerifiedNetworkArtifact(loadNetworkOverview, online, true)

  // The junction graph's routing half, on the nearby-lines pattern above -
  // once, not once per reconnection, with the state itself as the guard. No
  // object URL to revoke: fetchTrailGraph returns a parsed index.
  useEffect(() => {
    if (graphIndex !== null) return
    if (!DATA_CONFIGURED) {
      setGraphAbsence('unconfigured')
      return
    }
    // OFFLINE NO LONGER MEANS ABSENT (#1050). Until the graph was stored,
    // this branch set 'unreachable' and returned: a hiker at a trailhead with
    // no signal got a builder that refused every tap, having downloaded the
    // corridor at home the night before. `loadTrailGraph` now reads the store
    // when there is no connection, and 'unreachable' is what it answers when
    // the store is empty too - which is the same sentence, arrived at only
    // when it is true.
    //
    // Behind the trail line (#1117), and ONLINE ONLY - which is the same
    // asymmetry the nearby-lines effect above spells out, arrived at here by
    // #1050 rather than by design. What #1117's gate buys `trails.geojson` is
    // the pipe, and offline there is no 1.2 MB fetch to defer: there is a
    // store read, which competes with nothing. Gating it unconditionally
    // would have handed back exactly the trailhead #1050 exists to fix, one
    // effect further down. 'unconfigured' is still recorded above, on the
    // tick it becomes true, because that is an answer the network strip
    // renders rather than a fetch.
    if (online && !trailFetchSettled) return
    // A settled absence is not re-requested. Without this the reason below
    // becoming a dependency would put the app back on the bucket every time
    // React re-ran the effect, for an answer that cannot have changed.
    if (graphAbsence !== null && isSettledAbsence(graphAbsence)) return

    const controller = new AbortController()
    let wanted = true

    void loadTrailGraph(controller.signal, online).then((load) => {
      if (!wanted) return
      if (load.kind === 'graph') {
        // A VALID GRAPH IS NOT THE SAME AS A ROUTABLE ONE (#1044 review). An
        // empty one is a real published state - a ring with no maintained
        // trail in it - and the loader accepts it on purpose. Treating it as
        // "ready" opened the day-hike door onto a builder that could answer
        // no tap, which reads as a broken app rather than as empty ground.
        if (load.index.graph.edges.length === 0) {
          setGraphAbsence('empty')
          return
        }
        setGraphIndex(load.index)
        setGraphAbsence(null)
        return
      }
      setGraphAbsence(load.because)
    })

    return () => {
      wanted = false
      controller.abort()
    }
  }, [online, graphIndex, graphAbsence, graphAttempt, trailFetchSettled])

  const retryTrailNetwork = useCallback(() => {
    setGraphAttempt((attempt) => attempt + 1)
  }, [])

  /**
   * What to SAY about the graph, as against whether there is one.
   *
   * Memoised on the two facts it is built from rather than rebuilt per render:
   * it is a prop, and a fresh object every render is a re-render for whatever
   * holds it.
   */
  const trailNetwork = useMemo<TrailNetworkState>(() => {
    if (graphIndex !== null) return { kind: 'ready' }
    if (graphAbsence === null) return { kind: 'looking' }
    return { kind: 'absent', because: graphAbsence }
  }, [graphIndex, graphAbsence])

  const ensure = useCallback(async () => {
    setError(null)
    try {
      // Shares whatever is already coming, and asks the phone first - both
      // inside fetchOnce, so that a tap during the launch fetch waits on it
      // rather than duplicating it.
      await fetchOnce()
      return true
    } catch (thrown) {
      setError(describeTrailDataError(thrown))
      return false
    }
  }, [fetchOnce])

  return {
    /** The published release this phone does not have, or null (#919). Null is
     *  the answer for "nothing newer", "nothing downloaded yet" and "could not
     *  ask" alike - none of the three is something to put in front of anybody. */
    update,
    /** Whether to caution about what taking it costs: not on wifi, and big
     *  enough to matter. An unknown size counts as big - see warnsAboutData. */
    updateWarnsAboutData: update !== null && warnsAboutData(update),
    /** True while the bytes are coming. The prompt stays up and says so rather
     *  than vanishing into a map that has not changed yet. */
    applyingUpdate,
    applyUpdate,
    declineUpdate,
    trailIndex,
    poiMiles,
    pois,
    spurs,
    elevation,
    clubSections,
    stewards,
    highlights,
    retiredPois,
    // Never both. The real line winning is what ends the sketch, and saying so
    // here rather than in the shell means one place decides which line the map
    // is drawing.
    overviewTrailsUrl: haveTrailLines ? null : overviewUrl,
    // The url alone: whether it was revalidated is this hook's business (the
    // effect above), not a consumer's - the map draws a stored copy and a
    // fresh one identically.
    nearbyTrailsUrl: nearbyTrails?.url ?? null,
    networkOverviewUrl: networkOverview?.url ?? null,
    graphIndex,
    trailNetwork,
    retryTrailNetwork,
    trailsUrl,
    haveTrailLines,
    error,
    ensure,
  }
}
