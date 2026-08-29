// The instrument #106's field walk needs, so it comes back with data rather
// than impressions (#1180).
//
// WHY THIS EXISTS AT ALL. `useGeolocation` has always read
// `position.coords.accuracy`, converted it to `accuracyFeet` and put it in
// state, and nothing has ever read it back - grep says that file and two test
// fixtures. So this app has never retained one observation of its own
// positional uncertainty, and every threshold argument here has had to
// proceed without one: #93's 90 ft, #1100's noise radius, staleness.ts's
// tildes. This module is the other end of that: a walk with it running
// produces the distribution those numbers should have been derived from.
//
// IT RECORDS THE WATCH, NOT THE STATE THE APP RENDERS. #1090's bail-out drops
// a fix reporting coordinates the hook already holds, which is right for
// rendering and wrong for measurement - fix CADENCE is one of the things
// being measured, so a recorder fed from the deduplicated state would report
// a silence the platform never had. The seam this fills sits before that
// bail-out (see useGeolocation.ts's `onFix`).
//
// THE MARKER IS THE PART THAT MAKES A TRACE INTERPRETABLE. #1100 needs a
// phone "stationary under canopy for several minutes" told apart from one
// "walking from a standing start", and #93 needs a wooded section "walked
// both correctly and deliberately off-trail". Neither split is recoverable
// from coordinates after the fact - a stationary phone under canopy and a
// slow walk look alike in the very data whose ambiguity is the finding. So
// the hiker says which, and every sample carries what they last said.
//
// A SILENCE IS A MEASUREMENT, AND IT USED TO BE UNREADABLE.
//
// The third field walk stopped dead for 272 seconds in the middle of the
// stationary block it existed to collect - fixes arriving at a metronomic
// 5.7 s, then nothing, then one. Three things produce that shape and the CSV
// could tell none of them apart: the screen went dark, the hiker pocketed the
// phone, or the platform stopped answering. So every sample now carries what
// the app knew about itself when the fix arrived - whether the screen was
// actually being held awake, and whether the page was visible at all. Neither
// is about where anybody is; both are the difference between a gap that is
// evidence and a gap that is a shrug.
//
// NOTHING HERE LEAVES THE PHONE. On-device storage, manual export, and no
// caller anywhere may attach a trace to an app-failure report. A location
// trace is the most sensitive thing this app could hold and
// features/IDENTITY_AND_PRIVACY.md has no row for one, because until now
// nothing produced one. See #1180 for the boundary as agreed.

import { get, set, del } from 'idb-keyval'

/**
 * What the hiker says they are doing, stamped onto every sample until they
 * say otherwise.
 *
 * Three because three is what the two waiting issues actually asked for, not
 * because three is a tidy number: `stationary` and `walking` are #1100's (a)
 * and (b), and `off-trail` is the deliberate excursion #93 wants a drift
 * distribution for. A fourth would need somebody to say what they would do
 * with it.
 */
export type TraceMarker = 'stationary' | 'walking' | 'off-trail'

export const TRACE_MARKERS: readonly TraceMarker[] = [
  'stationary',
  'walking',
  'off-trail',
]

export interface TraceSample {
  /**
   * The platform's own fix timestamp, not `Date.now()`.
   *
   * They differ by however long the callback waited to run, and on a
   * throttled hidden tab that is exactly the quantity a cadence measurement
   * is trying to see. Recording the wall clock would fold the throttling into
   * the fix interval and hide it.
   */
  timestampMs: number
  lat: number
  lon: number
  /**
   * The 95%-confidence radius, in metres, as the platform reports it - the
   * field this whole exercise exists to collect.
   *
   * Kept in metres rather than converted to feet, unlike `accuracyFeet` on
   * the hook. This is the platform's number and the analysis should see it
   * before anybody has multiplied it by anything.
   */
  accuracyM: number
  /** Null where the platform declines to answer, which is ordinary indoors
   *  and on a network fix. Never defaulted to 0 - absent means unknown. */
  altitudeM: number | null
  altitudeAccuracyM: number | null
  speedMps: number | null
  headingDeg: number | null
  /**
   * What the app made of this fix at the time, when it could place it.
   *
   * Captured live rather than reconstructed later, because reconstructing it
   * means shipping a trail index to whatever reads the CSV and getting the
   * same answer out of a different implementation. The whole question is what
   * the APP believed while somebody was standing there.
   */
  mile: number | null
  offTrailFt: number | null
  offTreadFt: number | null
  marker: TraceMarker | null
  /**
   * Whether the screen was actually being held awake (lib/useWakeLock.ts).
   *
   * Recorded per sample rather than once per recording because it CHANGES
   * mid-walk - a battery-saver threshold crossed at 20% withdraws the lock
   * hours in - and the fix either side of a gap is the only place that shows.
   */
  wakeLock: WakeLockLabel | null
  /**
   * Whether the page was visible when the fix arrived.
   *
   * `watchPosition` keeps firing on a merely hidden page and stops on a
   * suspended one, so a run of hidden-but-arriving fixes and a silence are
   * different findings about #313's pocket behaviour, and this is what
   * separates them.
   */
  visible: boolean | null
}

/** `WakeLockState` from lib/useWakeLock.ts, restated as a string so this
 *  module stays free of the hook - it is written to a CSV, not switched on. */
export type WakeLockLabel = string

/** What the app made of a fix, or null when it could not place it at all.
 *  Structurally `TrailFix`, named separately so this module does not import
 *  the trail index just to describe three numbers. */
export interface TraceReading {
  mile: number
  offTrailFeet: number
  offTreadFeet: number
}

export interface TraceStatus {
  recording: boolean
  /** Null before the first `start`, and after `clear`. */
  startedAt: number | null
  marker: TraceMarker | null
  /** Everything recorded so far, buffered and flushed together. */
  samples: number
  /**
   * The platform timestamp of the most recent fix, or null before the first.
   *
   * Here so the SCREEN can say how long it has been. A count that has stopped
   * climbing is indistinguishable from one climbing slowly unless you watched
   * it, and the third walk's tester stood still for several minutes next to a
   * recording that had already stopped.
   */
  lastSampleAt: number | null
}

/** The IndexedDB surface this needs, injected so the suite can exercise the
 *  chunking without a real database - the same shape `idb-keyval` exports. */
export interface TraceStore {
  get: <T>(key: string) => Promise<T | undefined>
  set: (key: string, value: unknown) => Promise<void>
  del: (key: string) => Promise<void>
}

const idbStore: TraceStore = { get, set, del }

const STATE_KEY = 'ourhike:gps-trace:state'
const chunkKey = (index: number) => `ourhike:gps-trace:c${index}`

/**
 * How many samples ride in memory before a chunk is written.
 *
 * WHAT THIS NUMBER WAS DERIVED FROM, AND WHY THAT DERIVATION IS NOW WRONG.
 *
 * It was picked on the assumption that `watchPosition` under
 * `enableHighAccuracy` delivers about one fix a second, which made 60 samples
 * "about a minute of walking" - the most a tab the OS kills mid-walk may cost.
 * The first field trace says otherwise. Measured over the 135 intervals of an
 * 18-minute walk (2026-08-29, one Android phone, one browser): a median of
 * 5.71 s between fixes, p90 5.88 s, so about 10.5 fixes a minute rather than
 * 60. At that rate this buys a loss window of roughly 5.7 minutes, not one.
 *
 * The number is left at 60 anyway, and that is now a choice rather than a
 * derivation. @unvalidated - nobody has measured how often a browser tab is
 * actually killed mid-walk, so the cost of a 5.7-minute window is unknown, and
 * cutting it to a minute would mean ~316 IndexedDB writes over a six-hour walk
 * instead of ~63 to buy back something nobody has shown is being lost. What
 * would settle it is the next few traces: a recording that comes back short of
 * the walk, with a gap at the end, is the evidence that this window is too
 * wide. One phone is also not a fix rate - a different chipset, browser or
 * battery-saver setting may deliver at a different cadence entirely.
 *
 * What has not changed is why samples are chunked at all. archiveStore.ts
 * measured that: rewriting one accumulated record per sample is quadratic in
 * bytes written, and it made that mistake at gigabyte scale so this does not
 * have to make it at megabyte scale.
 */
const CHUNK_SAMPLES = 60

interface PersistedState {
  recording: boolean
  startedAt: number | null
  marker: TraceMarker | null
  /** Chunks already written. The buffer holding sample `chunks * CHUNK_SAMPLES`
   *  onwards has not been. */
  chunks: number
  samples: number
  lastSampleAt: number | null
}

const EMPTY: PersistedState = {
  recording: false,
  startedAt: null,
  marker: null,
  chunks: 0,
  samples: 0,
  lastSampleAt: null,
}

export interface GpsTrace {
  /** Reads any trace left by a previous run of the app. Recording survives a
   *  reload on purpose - see `resume`'s note. */
  resume: () => Promise<TraceStatus>
  start: (now?: number) => Promise<TraceStatus>
  stop: () => Promise<TraceStatus>
  mark: (marker: TraceMarker) => Promise<TraceStatus>
  /** Buffers a sample, flushing a full chunk to storage. Silently does
   *  nothing while stopped, so a fix arriving between `stop` and the watch
   *  actually unwinding cannot extend the trace. */
  record: (sample: TraceSample) => Promise<TraceStatus>
  /** Everything recorded, in order, including the unflushed buffer. */
  readAll: () => Promise<TraceSample[]>
  /** Deletes every chunk and forgets the trace. There is no undo, and the
   *  screen says so before calling this. */
  clear: () => Promise<TraceStatus>
  status: () => TraceStatus
}

function statusOf(state: PersistedState): TraceStatus {
  return {
    recording: state.recording,
    startedAt: state.startedAt,
    marker: state.marker,
    samples: state.samples,
    lastSampleAt: state.lastSampleAt,
  }
}

export function createGpsTrace(store: TraceStore = idbStore): GpsTrace {
  let state: PersistedState = { ...EMPTY }
  let buffer: TraceSample[] = []

  const persist = async () => {
    await store.set(STATE_KEY, state)
  }

  /**
   * Writes the buffered samples as the next chunk.
   *
   * The index is claimed and the buffer swapped SYNCHRONOUSLY, before the
   * first await. `record` is async and fixes do not queue politely: two
   * arriving either side of one `store.set` would otherwise both read
   * `state.chunks` as the same number, write the same key twice, and leave
   * the count claiming a chunk that was never written. Vanishingly unlikely
   * at one fix a second, and this module's entire job is not losing a walk.
   *
   * A rejected write therefore costs one chunk rather than the index - which
   * is the right way round, and why `readAll` skips a chunk it cannot find
   * instead of throwing.
   */
  const flush = async () => {
    if (buffer.length === 0) return
    const chunk = buffer
    const index = state.chunks
    buffer = []
    state = { ...state, chunks: index + 1 }
    await store.set(chunkKey(index), chunk)
  }

  return {
    async resume(): Promise<TraceStatus> {
      // Recording deliberately survives a reload. A phone that reloaded
      // itself three miles in and quietly stopped recording would hand back a
      // truncated trace that looks complete, which is the one failure this
      // whole instrument cannot afford - the walk is not repeatable that day.
      const stored = await store.get<PersistedState>(STATE_KEY)
      state = stored === undefined ? { ...EMPTY } : { ...EMPTY, ...stored }
      buffer = []
      return statusOf(state)
    },

    async start(now: number = Date.now()): Promise<TraceStatus> {
      // A fresh trace rather than an append. Two walks in one file, with no
      // marker between them saying where one ended, is a dataset nobody can
      // safely split later.
      await this.clear()
      state = { ...EMPTY, recording: true, startedAt: now }
      await persist()
      return statusOf(state)
    },

    async stop(): Promise<TraceStatus> {
      state = { ...state, recording: false }
      await flush()
      await persist()
      return statusOf(state)
    },

    async mark(marker: TraceMarker): Promise<TraceStatus> {
      state = { ...state, marker }
      // Persisted immediately rather than with the next chunk: the marker is
      // the hiker's own statement about the minute they are standing in, and
      // a reload before the chunk fills would otherwise resume with the
      // previous one still stamped on everything that followed.
      await persist()
      return statusOf(state)
    },

    async record(sample: TraceSample): Promise<TraceStatus> {
      if (!state.recording) return statusOf(state)

      buffer.push({ ...sample, marker: state.marker })
      state = {
        ...state,
        samples: state.samples + 1,
        lastSampleAt: sample.timestampMs,
      }

      if (buffer.length >= CHUNK_SAMPLES) {
        await flush()
        await persist()
      }

      return statusOf(state)
    },

    async readAll(): Promise<TraceSample[]> {
      const chunks: TraceSample[] = []
      for (let index = 0; index < state.chunks; index += 1) {
        const chunk = await store.get<TraceSample[]>(chunkKey(index))
        // A missing chunk is skipped rather than thrown on. Storage this app
        // does not own can be evicted, and half a walk is worth more to the
        // issues waiting on it than an export that refuses to build.
        if (chunk !== undefined) chunks.push(...chunk)
      }
      return [...chunks, ...buffer]
    },

    async clear(): Promise<TraceStatus> {
      for (let index = 0; index < state.chunks; index += 1) {
        await store.del(chunkKey(index))
      }
      await store.del(STATE_KEY)
      state = { ...EMPTY }
      buffer = []
      return statusOf(state)
    },

    status(): TraceStatus {
      return statusOf(state)
    },
  }
}

/**
 * The fields worth keeping off one `watchPosition` callback.
 *
 * Its own function so the extraction is testable without a watch, and so
 * App.tsx's recorder wiring stays a call rather than a transcription - a
 * field dropped silently there would not show up until somebody opened the
 * CSV, by which time the walk is over.
 */
/** What the app knew about itself when a fix arrived, as distinct from what
 *  the fix said about the world. Optional so a caller with nothing to say
 *  writes null rather than guessing. */
export interface TraceConditions {
  wakeLock?: WakeLockLabel | null
  visible?: boolean | null
}

export function sampleFromPosition(
  position: GeolocationPosition,
  reading: TraceReading | null,
  conditions: TraceConditions = {},
): TraceSample {
  const { coords } = position
  return {
    timestampMs: position.timestamp,
    lat: coords.latitude,
    lon: coords.longitude,
    accuracyM: coords.accuracy,
    altitudeM: coords.altitude,
    altitudeAccuracyM: coords.altitudeAccuracy,
    speedMps: coords.speed,
    headingDeg: coords.heading,
    mile: reading === null ? null : reading.mile,
    offTrailFt: reading === null ? null : reading.offTrailFeet,
    offTreadFt: reading === null ? null : reading.offTreadFeet,
    // Stamped by `record` from what the hiker last said, not passed in. One
    // owner for that value, so a caller cannot disagree with the recorder
    // about which minute a marker started.
    marker: null,
    wakeLock: conditions.wakeLock ?? null,
    visible: conditions.visible ?? null,
  }
}

const CSV_COLUMNS = [
  'timestamp_ms',
  'iso_time',
  'lat',
  'lon',
  'accuracy_m',
  'altitude_m',
  'altitude_accuracy_m',
  'speed_mps',
  'heading_deg',
  'mile',
  'off_trail_ft',
  'off_tread_ft',
  'marker',
  // What the app knew about ITSELF, so a gap in the rows above is readable.
  // See the header: a 272-second silence with no answer for why cost the one
  // stationary block the third walk was taken to collect.
  'wake_lock',
  'page_visible',
] as const

/** Empty rather than a zero or the string "null": absent means unknown here
 *  exactly as it does everywhere else in this codebase, and DuckDB reads an
 *  empty CSV field as NULL without being asked. */
const cell = (value: number | string | null): string =>
  value === null ? '' : String(value)

/**
 * The trace as CSV, one row per sample.
 *
 * CSV because the analysis will happen in DuckDB like everything else in this
 * repository, and `read_csv_auto` needs no parser written for it. `iso_time`
 * rides alongside the epoch milliseconds rather than replacing them - the
 * epoch is what arithmetic wants and the ISO string is what a human scrolling
 * the file wants, and at this size the duplication costs nothing worth
 * protecting.
 *
 * No quoting logic, deliberately: every column is a number, a fixed marker
 * word, or empty, and none can contain a comma. A future column that can must
 * bring quoting with it.
 */
export function traceToCsv(samples: TraceSample[]): string {
  const rows = samples.map((sample) =>
    [
      cell(sample.timestampMs),
      cell(new Date(sample.timestampMs).toISOString()),
      cell(sample.lat),
      cell(sample.lon),
      cell(sample.accuracyM),
      cell(sample.altitudeM),
      cell(sample.altitudeAccuracyM),
      cell(sample.speedMps),
      cell(sample.headingDeg),
      cell(sample.mile),
      cell(sample.offTrailFt),
      cell(sample.offTreadFt),
      cell(sample.marker),
      cell(sample.wakeLock),
      cell(sample.visible === null ? null : sample.visible ? 'yes' : 'no'),
    ].join(','),
  )

  return [CSV_COLUMNS.join(','), ...rows].join('\n') + '\n'
}

export function traceFilename(startedAt: number | null, now: Date = new Date()): string {
  const stamp = new Date(startedAt ?? now.getTime()).toISOString().replace(/[:.]/g, '-')
  return `ourhike-gps-trace-${stamp}.csv`
}

/**
 * Writes the trace to a file the hiker keeps.
 *
 * The same anchor dance `downloadArchive` uses for #895's account export,
 * rather than a shared helper: two callers is not yet a pattern, and the one
 * thing worth sharing between them - that an export is a deliberate act by
 * the person whose data it is - is not code.
 */
export function downloadTrace(csv: string, filename: string): void {
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
