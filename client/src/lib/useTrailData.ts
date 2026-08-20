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

import { useCallback, useEffect, useRef, useState } from 'react'
import { DATA_CONFIGURED } from './config'
import { buildTrailIndex, type TrailIndex } from './trailPosition'
import {
  downloadTrailData,
  loadTrailData,
  TrailDataHashMismatchError,
  type StoredPoi,
} from './trailData'
import { EMPTY_CLUB_SECTIONS, type ClubSections } from './clubSections'
import type { ElevationProfile } from './elevationProfile'
import type { SpurRecord } from './spurDestination'

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
  /** The centerline index, or null when there is none to build one from - and
   *  null too when the file was there and unreadable, which is best-effort on
   *  purpose (see below). */
  trailIndex: TrailIndex | null
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
  trailsUrl: string
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

export function useTrailData(online: boolean): TrailData {
  const [trailIndex, setTrailIndex] = useState<TrailIndex | null>(null)
  const [pois, setPois] = useState<StoredPoi[]>([])
  const [spurs, setSpurs] = useState<Record<string, SpurRecord>>({})
  const [elevation, setElevation] = useState<ElevationProfile | null>(null)
  const [clubSections, setClubSections] = useState<ClubSections>(EMPTY_CLUB_SECTIONS)
  const [trailsUrl, setTrailsUrl] = useState<string>(emptyTrailsUrl)
  const [haveTrailLines, setHaveTrailLines] = useState(false)
  const [error, setError] = useState<TrailDataError | null>(null)

  /** Returns whether anything was actually on the phone to load. */
  const refresh = useCallback(async () => {
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
    setSpurs(data.spurs)
    setElevation(data.elevation)
    setClubSections(data.clubSections)

    // Best-effort, and separate from the POIs above on purpose. A shelter is
    // findable by name with no geometry at all, so a trails.geojson that
    // arrived truncated or malformed should cost the mile numbers decorating
    // each row and nothing else.
    //
    // buildTrailIndex() guards the shape it is handed, but JSON.parse runs
    // first and throws on the more likely symptom of a truncated download -
    // half a file. Uncaught, that escaped through the `void refresh()` below as
    // an unhandled rejection: no index, no message, and no search either, which
    // is the failure this whole path was rebuilt to avoid.
    try {
      setTrailIndex(buildTrailIndex(JSON.parse(await data.trails.text())))
    } catch {
      setTrailIndex(null)
    }
    return true
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
      // Asked directly rather than assumed: a phone that already has the lines
      // needs no network at all.
      if ((await loadTrailData()) !== null) return
      await downloadTrailData()
      await refresh()
    })()
    inFlight.current = attempt
    const clear = () => {
      if (inFlight.current === attempt) inFlight.current = null
    }
    attempt.then(clear, clear)
    return attempt
  }, [refresh])

  // Reading what is already on the phone, and unconditionally. This has to stay
  // independent of the fetch below: an unconfigured build and a phone with no
  // signal both still have whatever was downloaded last time, and gating this
  // on either one would leave a hiker on a ridge - the exact person the offline
  // store exists for - looking at a map with no trail.
  useEffect(() => {
    void refresh()
  }, [refresh])

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
    void fetchOnce().catch((thrown: unknown) => {
      // Not reported if the effect was torn down under us: by then this is a
      // fetch nobody is waiting on, and a notice about it would outlive the
      // screen that could act on it. Nothing is stored either way -
      // downloadTrailData commits all four files or none - so coming back into
      // signal can simply try again.
      if (cancelled) return
      setError(describeTrailDataError(thrown))
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
    trailIndex,
    pois,
    spurs,
    elevation,
    clubSections,
    trailsUrl,
    haveTrailLines,
    error,
    ensure,
  }
}
