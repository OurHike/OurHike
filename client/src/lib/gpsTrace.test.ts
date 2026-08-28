import { describe, it, expect } from 'vitest'
import {
  createGpsTrace,
  sampleFromPosition,
  traceFilename,
  traceToCsv,
  type TraceSample,
  type TraceStore,
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
        'speed_mps,heading_deg,mile,off_trail_ft,off_tread_ft,marker',
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
    expect(csv.trim().split('\n')[1].endsWith(',stationary')).toBe(true)
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
