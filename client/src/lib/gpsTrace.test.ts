import { describe, it, expect } from 'vitest'
import {
  createGpsTrace,
  sampleFromPosition,
  traceFilename,
  traceToCsv,
  type TraceSample,
  type TraceStore,
  sampleFromNativeFix,
} from './gpsTrace'

// This module exists to produce evidence for #93, #106 and #1100, so the
// property that matters most is that it does not quietly lose any. Every test
// below is about a way a trace could come back looking complete while being
// short - a chunk never flushed, a marker applied to the wrong minute, a
// reload that stopped the recording without saying so.

/** An in-memory stand-in for idb-keyval, so the chunking is exercised without
 *  a database. `writes` counts every set so a test can assert that a full
 *  chunk is written once rather than per sample - the quadratic mistake
 *  archiveStore.ts already paid for at gigabyte scale. */
function fakeStore() {
  const values = new Map<string, unknown>()
  let writes = 0

  const store: TraceStore = {
    get: <T>(key: string) => Promise.resolve(values.get(key) as T | undefined),
    set: (key: string, value: unknown) => {
      writes += 1
      // Structured-cloned the way IndexedDB would, so a test cannot pass by
      // holding a live reference to the recorder's own buffer array.
      values.set(key, JSON.parse(JSON.stringify(value)))
      return Promise.resolve()
    },
    del: (key: string) => {
      values.delete(key)
      return Promise.resolve()
    },
  }

  return { store, values, writeCount: () => writes }
}

function sampleAt(timestampMs: number): TraceSample {
  return {
    timestampMs,
    lat: 44.2705,
    lon: -71.3033,
    accuracyM: 12,
    altitudeM: 1580,
    altitudeAccuracyM: 8,
    speedMps: 1.1,
    headingDeg: 41,
    mile: 1807.4,
    offTrailFt: 22,
    offTreadFt: 22,
    marker: null,
    wakeLock: null,
    visible: null,
    fixSource: 'web',
    accuracyConfidence: 95,
    simulated: null,
  }
}

async function recordMany(
  trace: ReturnType<typeof createGpsTrace>,
  count: number,
  from = 0,
) {
  for (let i = 0; i < count; i += 1) {
    await trace.record(sampleAt(1_000 + (from + i) * 1_000))
  }
}

describe('createGpsTrace', () => {
  it('records nothing until started', async () => {
    const { store } = fakeStore()
    const trace = createGpsTrace(store)

    await trace.record(sampleAt(1_000))

    expect(trace.status().samples).toBe(0)
    expect(await trace.readAll()).toEqual([])
  })

  it('keeps unflushed samples readable, so a short walk is still a trace', async () => {
    // The case that would otherwise export an empty file: fewer samples than
    // one chunk, which is every test walk short of a minute.
    const { store } = fakeStore()
    const trace = createGpsTrace(store)

    await trace.start(1_000)
    await recordMany(trace, 3)

    expect(trace.status().samples).toBe(3)
    expect(await trace.readAll()).toHaveLength(3)
  })

  it('flushes a full chunk once, not once per sample', async () => {
    const { store, writeCount } = fakeStore()
    const trace = createGpsTrace(store)

    await trace.start(1_000)
    const beforeWrites = writeCount()
    await recordMany(trace, 60)

    // One chunk write plus one state write for the 60 samples. If this ever
    // starts scaling with sample count, the recorder has gone quadratic.
    expect(writeCount() - beforeWrites).toBe(2)
  })

  it('returns flushed chunks and the live buffer in order', async () => {
    const { store } = fakeStore()
    const trace = createGpsTrace(store)

    await trace.start(1_000)
    await recordMany(trace, 145)

    const all = await trace.readAll()
    expect(all).toHaveLength(145)
    // Two full chunks flushed, 25 still buffered, and the boundary between
    // them invisible to the reader.
    expect(all.map((s) => s.timestampMs)).toEqual(
      Array.from({ length: 145 }, (_, i) => 1_000 + i * 1_000),
    )
  })

  it('stamps the marker the hiker last set onto each sample', async () => {
    const { store } = fakeStore()
    const trace = createGpsTrace(store)

    await trace.start(1_000)
    await recordMany(trace, 2)
    await trace.mark('stationary')
    await recordMany(trace, 2, 2)
    await trace.mark('off-trail')
    await recordMany(trace, 1, 4)

    expect((await trace.readAll()).map((s) => s.marker)).toEqual([
      null,
      null,
      'stationary',
      'stationary',
      'off-trail',
    ])
  })

  it('ignores a marker passed in on the sample itself', async () => {
    // One owner for that value. A caller that disagreed with the recorder
    // about which minute a marker started would corrupt exactly the split
    // #1100 needs and nothing would flag it.
    const { store } = fakeStore()
    const trace = createGpsTrace(store)

    await trace.start(1_000)
    await trace.mark('walking')
    await trace.record({ ...sampleAt(2_000), marker: 'off-trail' })

    expect((await trace.readAll())[0].marker).toBe('walking')
  })

  it('stops recording, and a late fix cannot extend the trace', async () => {
    // A fix in flight when the hiker taps stop must not land after it.
    const { store } = fakeStore()
    const trace = createGpsTrace(store)

    await trace.start(1_000)
    await recordMany(trace, 2)
    await trace.stop()
    await trace.record(sampleAt(99_000))

    expect(trace.status().recording).toBe(false)
    expect(await trace.readAll()).toHaveLength(2)
  })

  it('flushes the buffer on stop, so the tail survives a reload', async () => {
    const { store } = fakeStore()
    const trace = createGpsTrace(store)

    await trace.start(1_000)
    await recordMany(trace, 5)
    await trace.stop()

    const resumed = createGpsTrace(store)
    await resumed.resume()
    expect(await resumed.readAll()).toHaveLength(5)
  })

  it('resumes a recording that survived a reload', async () => {
    // The failure this guards: a phone that reloaded three miles in and
    // quietly stopped recording hands back a truncated trace that looks
    // complete, on a walk nobody is repeating that day.
    const { store } = fakeStore()
    const trace = createGpsTrace(store)

    await trace.start(1_000)
    await trace.mark('walking')
    await recordMany(trace, 60)

    const resumed = createGpsTrace(store)
    const status = await resumed.resume()

    expect(status.recording).toBe(true)
    expect(status.marker).toBe('walking')
    expect(status.samples).toBe(60)
    expect(await resumed.readAll()).toHaveLength(60)
  })

  it('starts a fresh trace rather than appending to the last one', async () => {
    const { store } = fakeStore()
    const trace = createGpsTrace(store)

    await trace.start(1_000)
    await recordMany(trace, 70)
    await trace.stop()

    await trace.start(500_000)
    await recordMany(trace, 2)

    expect(trace.status().samples).toBe(2)
    expect(await trace.readAll()).toHaveLength(2)
  })

  it('clears every chunk it wrote', async () => {
    const { store, values } = fakeStore()
    const trace = createGpsTrace(store)

    await trace.start(1_000)
    await recordMany(trace, 130)
    await trace.clear()

    expect(values.size).toBe(0)
    expect(await trace.readAll()).toEqual([])
    expect(trace.status().samples).toBe(0)
  })

  it('does not lose or duplicate a chunk when fixes overlap a flush', async () => {
    // `record` is async and fixes do not queue politely. Claiming the chunk
    // index before the first await is what stops two of them writing the same
    // key and leaving the count naming a chunk nobody wrote.
    const { store } = fakeStore()
    const trace = createGpsTrace(store)

    await trace.start(1_000)
    await Promise.all(
      Array.from({ length: 180 }, (_, i) => trace.record(sampleAt(1_000 + i * 1_000))),
    )

    const all = await trace.readAll()
    expect(all).toHaveLength(180)
    expect(new Set(all.map((s) => s.timestampMs)).size).toBe(180)
  })

  it('skips an evicted chunk rather than refusing to build the export', async () => {
    // Storage this app does not own can be evicted. Half a walk is worth more
    // to the issues waiting on it than an export that throws.
    const { store, values } = fakeStore()
    const trace = createGpsTrace(store)

    await trace.start(1_000)
    await recordMany(trace, 120)
    values.delete('ourhike:gps-trace:c0')

    expect(await trace.readAll()).toHaveLength(60)
  })
})

describe('sampleFromPosition', () => {
  const position = {
    timestamp: 1_724_800_000_000,
    coords: {
      latitude: 44.2705,
      longitude: -71.3033,
      accuracy: 2_400,
      altitude: null,
      altitudeAccuracy: null,
      speed: null,
      heading: null,
    },
  } as GeolocationPosition

  it('keeps accuracy in the platform’s own metres', () => {
    // The one field this whole instrument exists to collect, and the analysis
    // should see it before anybody has multiplied it by anything.
    expect(sampleFromPosition(position, null).accuracyM).toBe(2_400)
  })

  it('takes the platform fix timestamp, not the wall clock', () => {
    expect(sampleFromPosition(position, null).timestampMs).toBe(1_724_800_000_000)
  })

  it('carries absent altitude and speed through as null, never zero', () => {
    const sample = sampleFromPosition(position, null)
    expect(sample.altitudeM).toBeNull()
    expect(sample.speedMps).toBeNull()
    expect(sample.headingDeg).toBeNull()
  })

  it('records what the app made of the fix when it could place it', () => {
    const sample = sampleFromPosition(position, {
      mile: 1807.4,
      offTrailFeet: 197,
      offTreadFeet: 22,
    })
    expect(sample.mile).toBe(1807.4)
    expect(sample.offTrailFt).toBe(197)
    expect(sample.offTreadFt).toBe(22)
  })

  it('records nulls when the app could not place the fix at all', () => {
    // The case the whole exercise is about: a coarse fix the trail index
    // refuses. The sample is still worth keeping - that refusal IS the datum.
    const sample = sampleFromPosition(position, null)
    expect(sample.mile).toBeNull()
    expect(sample.offTrailFt).toBeNull()
  })
})

describe('traceToCsv', () => {
  it('writes a header DuckDB can read without being told the schema', () => {
    expect(traceToCsv([]).trim()).toBe(
      'timestamp_ms,iso_time,lat,lon,accuracy_m,altitude_m,altitude_accuracy_m,' +
        'speed_mps,heading_deg,mile,off_trail_ft,off_tread_ft,marker,' +
        'wake_lock,page_visible,fix_source,accuracy_confidence,simulated',
    )
  })

  it('writes an absent value as an empty field, never as zero', () => {
    const csv = traceToCsv([
      { ...sampleAt(1_000), altitudeM: null, mile: null, marker: null },
    ])
    const row = csv.trim().split('\n')[1]

    expect(row).toContain(',,')
    expect(row.split(',')[5]).toBe('')
    expect(row.split(',')[9]).toBe('')
  })

  it('carries the marker into its own column', () => {
    const csv = traceToCsv([{ ...sampleAt(1_000), marker: 'stationary' }])
    expect(csv.trim().split('\n')[1].split(',')[12]).toBe('stationary')
  })

  it('records what the app knew about itself, so a silence is readable', () => {
    // THE THIRD WALK'S UNANSWERED QUESTION. 272 seconds with no fix, in the
    // middle of the stationary block the walk existed to collect, and three
    // explanations the file could not tell apart. The fix either side of a
    // gap now says whether the screen was being held and whether the page was
    // even visible.
    const csv = traceToCsv([{ ...sampleAt(1_000), wakeLock: 'released', visible: false }])
    const cells = csv.trim().split('\n')[1].split(',')

    expect(cells[13]).toBe('released')
    expect(cells[14]).toBe('no')
  })

  it('writes an unknown condition as empty, never as a confident "no"', () => {
    // Absent means unknown here as everywhere else: a sample recorded by a
    // caller that could not answer must not read as a page that was hidden.
    const cells = traceToCsv([sampleAt(1_000)])
      .trim()
      .split('\n')[1]
      .split(',')

    expect(cells[13]).toBe('')
    expect(cells[14]).toBe('')
  })

  it('pairs the epoch with a readable time rather than replacing it', () => {
    const csv = traceToCsv([sampleAt(1_724_800_000_000)])
    const cells = csv.trim().split('\n')[1].split(',')
    expect(cells[0]).toBe('1724800000000')
    expect(cells[1]).toBe('2024-08-27T23:06:40.000Z')
  })

  it('ends with a newline, so an appended file does not glue two rows', () => {
    expect(traceToCsv([sampleAt(1_000)]).endsWith('\n')).toBe(true)
  })
})

describe('traceFilename', () => {
  it('names the file for when the walk started, not when it was exported', () => {
    // Two exports of one walk should be the same file, and two walks exported
    // in one sitting should not collide.
    expect(traceFilename(1_724_800_000_000)).toBe(
      'ourhike-gps-trace-2024-08-27T23-06-40-000Z.csv',
    )
  })

  it('falls back to now when there is no start time', () => {
    expect(traceFilename(null, new Date(1_724_800_000_000))).toBe(
      'ourhike-gps-trace-2024-08-27T23-06-40-000Z.csv',
    )
  })
})

describe('the flush time budget', () => {
  // THE FIFTH FIELD TRACE. 74 minutes of recording, one sample in the file.
  // Nothing reached storage until 60 samples had arrived, and at the measured
  // stationary rate of 0.87 fixes a minute that is 69 minutes of readings
  // held in a JavaScript array and nowhere else. A reload, a tab eviction or
  // an Android low-memory kill takes all of it - while the module header
  // promises a recording survives a reload.

  it('writes a chunk once the clock says to, long before 60 samples', async () => {
    const { store, values } = fakeStore()
    let now = 1_000_000
    const trace = createGpsTrace(store, () => now)

    await trace.start(now)
    await trace.record(sampleAt(1))
    await trace.record(sampleAt(2))
    expect(values.has('ourhike:gps-trace:c0')).toBe(false)

    now += 60_000
    await trace.record(sampleAt(3))

    expect(values.get('ourhike:gps-trace:c0')).toHaveLength(3)
  })

  it('bounds the loss in MINUTES, which is the thing the app controls', async () => {
    // The sample count does not bound it: the platform decides how fast
    // samples arrive and it varies by a factor of nine (7.58 a minute
    // walking, 0.87 standing still). Three samples in an hour must still
    // reach storage.
    const { store } = fakeStore()
    let now = 0
    const trace = createGpsTrace(store, () => now)
    await trace.start(now)

    for (let i = 0; i < 3; i += 1) {
      now += 21 * 60_000
      await trace.record(sampleAt(i))
    }

    expect(await trace.readAll()).toHaveLength(3)
    // And they are on disk rather than in the buffer: a fresh reader over the
    // same store sees them without the recorder's memory.
    const reopened = createGpsTrace(store, () => now)
    await reopened.resume()
    expect(await reopened.readAll()).toHaveLength(3)
  })

  it('measures the budget from `start`, not from when the module was built', async () => {
    // Otherwise a recording begun an hour after app launch flushes on its
    // first sample and every sample after it.
    const { store, writeCount } = fakeStore()
    let now = 0
    const trace = createGpsTrace(store, () => now)

    now += 60 * 60_000
    await trace.start(now)
    const before = writeCount()
    await trace.record(sampleAt(1))

    // The state write from `start` only; no chunk.
    expect(writeCount()).toBe(before)
  })

  it('still chunks on the count when samples come in fast', async () => {
    const { store, values } = fakeStore()
    const now = 0
    const trace = createGpsTrace(store, () => now)
    await trace.start(now)

    await recordMany(trace, 60)

    expect(values.get('ourhike:gps-trace:c0')).toHaveLength(60)
  })
})

describe('sampleFromNativeFix', () => {
  // THE TRAP THIS SUITE EXISTS FOR. `navigator.geolocation` states its
  // accuracy radius at 95% confidence; the background plugin states its own
  // at 68%. Same units, same field name, about 1.62x apart - so an identical
  // phone reports a number roughly 40% SMALLER through the plugin. A trace
  // that mixed them would make every threshold derived from it wrong in the
  // optimistic direction, which is the one direction this app may not be
  // wrong in.

  const nativeFix = {
    timestampMs: 1_000,
    lat: 41.7348,
    lon: -74.1873,
    accuracyM: 11,
    altitudeM: 180.4,
    altitudeAccuracyM: 4,
    speedMps: 0.55,
    headingDeg: 268,
    simulated: false,
  }

  it('states the plugin’s 68% convention, and never the web API’s 95%', () => {
    expect(sampleFromNativeFix(nativeFix, null).accuracyConfidence).toBe(68)
  })

  it('leaves a web fix stating 95%', () => {
    expect(sampleAt(1_000).accuracyConfidence).toBe(95)
  })

  it('does not convert the radius into the other convention', () => {
    // Converting would bury a 1.62x factor inside a column nobody would think
    // to question later. The platform's number goes in untouched and the
    // convention travels beside it.
    expect(sampleFromNativeFix(nativeFix, null).accuracyM).toBe(11)
  })

  it('carries the last accuracy onto the status, for the screen to print', () => {
    // The fifth trace's one reading stated exactly 100 m with no speed and no
    // heading - a network fix - and the screen said nothing, so a tester
    // waited 74 minutes for a satellite lock that had never happened.
    expect(sampleAt(1_000).accuracyM).toBe(12)
  })

  it('says which watch produced it', () => {
    expect(sampleFromNativeFix(nativeFix, null).fixSource).toBe('native')
    expect(sampleAt(1_000).fixSource).toBe('web')
  })

  it('tells a fix the app ASKED for apart from one the platform volunteered', () => {
    // The watch's natural cadence is itself a measurement - 7.58 fixes a
    // minute walking, 0.87 standing still. Merging polled rows into `web`
    // would delete that finding while looking like better data.
    const position = {
      coords: {
        latitude: 41.7348,
        longitude: -74.1873,
        accuracy: 21,
        altitude: null,
        altitudeAccuracy: null,
        speed: null,
        heading: null,
      },
      timestamp: 2_000,
    } as unknown as GeolocationPosition

    expect(sampleFromPosition(position, null, { source: 'web-poll' }).fixSource).toBe(
      'web-poll',
    )
    expect(sampleFromPosition(position, null).fixSource).toBe('web')
  })

  it('states 95% for a polled fix too, because it is the same API', () => {
    const position = {
      coords: {
        latitude: 41.7348,
        longitude: -74.1873,
        accuracy: 21,
        altitude: null,
        altitudeAccuracy: null,
        speed: null,
        heading: null,
      },
      timestamp: 2_000,
    } as unknown as GeolocationPosition

    expect(
      sampleFromPosition(position, null, { source: 'web-poll' }).accuracyConfidence,
    ).toBe(95)
  })

  it('carries the mock-location flag, and leaves it unknown for a web fix', () => {
    // The web API has no such field, so a web row must say "unknown" rather
    // than "real" - absent means unknown here as everywhere else.
    expect(sampleFromNativeFix({ ...nativeFix, simulated: true }, null).simulated).toBe(
      true,
    )
    expect(sampleAt(1_000).simulated).toBeNull()
  })

  it('takes the trail reading the same way a web fix does', () => {
    const sample = sampleFromNativeFix(nativeFix, {
      mile: 1807.4,
      offTrailFeet: 22,
      offTreadFeet: 8,
    })
    expect(sample.mile).toBe(1807.4)
    expect(sample.offTrailFt).toBe(22)
  })

  it('leaves the marker to `record`, exactly as the web constructor does', () => {
    expect(sampleFromNativeFix(nativeFix, null).marker).toBeNull()
  })

  it('writes both conventions into the CSV so an analysis can group by them', () => {
    // Columns are located by NAME rather than by index. A hardcoded offset
    // silently starts asserting about its neighbour the next time a column
    // is added in the middle, which is how a test stops testing.
    const csv = traceToCsv([sampleAt(1_000), sampleFromNativeFix(nativeFix, null)])
    const [header, web, native] = csv
      .trim()
      .split('\n')
      .map((line) => line.split(','))
    const at = (row: string[], column: string) => row[header.indexOf(column)]

    expect(at(web, 'fix_source')).toBe('web')
    expect(at(web, 'accuracy_confidence')).toBe('95')
    expect(at(web, 'simulated')).toBe('')

    expect(at(native, 'fix_source')).toBe('native')
    expect(at(native, 'accuracy_confidence')).toBe('68')
    expect(at(native, 'simulated')).toBe('no')
  })
})
