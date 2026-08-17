// This build must still read what a shipped build wrote (#374, surface 1).
//
// RELEASING.md §8c names four backwards-compatibility surfaces. This is the
// first one, and the issue calls it the one to do first because it was the
// only one nothing watched at all: an update that cannot read the previous
// release's IndexedDB orphans a downloaded archive or drops queued reports.
//
// **Every assertion here runs a real reader.** Not a schema comparison, not a
// snapshot of the fixture against itself - `listQueued`, `loadPreferences`,
// `loadTrailData` and the rest, the same functions the app calls on launch,
// against storedShapes.fixtures.ts. A shape check would pass while the
// function that has to survive the shape throws.
//
// The last test is the one that keeps this file honest as the app grows: it
// walks the key constants the app actually exports and fails when one is
// missing from the fixture. Without it, this suite silently stops covering
// every key added after today, and a passing run would mean less each week.

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { get } from 'idb-keyval'

import { OUTBOX_KEY, listQueued } from './outbox'
import { PREFERENCES_KEY, loadPreferences } from './preferences'
import { PLANNED_HIKE_KEY, loadPlannedHike } from './plannedHike'
import { CAMERA_MEMORY_KEY, readCamera } from './cameraMemory'
import {
  ELEVATION_STORE_KEY,
  POIS_KEY,
  SPURS_STORE_KEY,
  TRAILS_BLOB_KEY,
  loadTrailData,
} from './trailData'
import {
  progressKeyFor,
  readArchiveVersion,
  readDownloadProgress,
  sourceKeyFor,
  versionKeyFor,
  partialKeyFor,
} from './archiveDownload'
import {
  completeKeyFor,
  readArchive,
  readArchiveSize,
  readComplete,
  segmentKeyFor,
} from './archiveStore'
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'
import { MAP_PACKAGES } from './packages'
import {
  STORED_ARCHIVE_BYTES,
  STORED_SHAPES,
  storedElevation,
  storedLegacyArchive,
  storedLegacyPartial,
  storedSegmentedArchive,
  storedTrailsBlob,
} from './storedShapes.fixtures'

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))

const mockedGet = vi.mocked(get)

/** The store a phone launched with: the frozen fixture, plus the two values
 *  that have to be constructed rather than frozen. */
function phoneStore(): Record<string, unknown> {
  return {
    ...STORED_SHAPES,
    [TRAILS_BLOB_KEY]: storedTrailsBlob(),
    [ELEVATION_STORE_KEY]: storedElevation(),
  }
}

beforeEach(() => {
  const store = phoneStore()
  mockedGet.mockImplementation(async (key: IDBValidKey) => store[key as string])

  // cameraMemory reads sessionStorage, not IndexedDB.
  window.sessionStorage.setItem(
    CAMERA_MEMORY_KEY,
    JSON.stringify(STORED_SHAPES[CAMERA_MEMORY_KEY]),
  )
})

describe('a stored phone from the baseline release', () => {
  // The failure mode this whole file exists to prevent, and the one with a
  // person attached: a hiker's unsent reports are the only copy of something
  // they wrote down.
  it('still has its queued reports, photo bytes included', async () => {
    const queued = await listQueued()

    expect(queued).toHaveLength(4)
    expect(queued[0].id).toBe('5f8e1b3a-0c4d-4a2e-9f1b-2c3d4e5f6a7b')
    expect(queued[0].authoredAt).toBe('2026-08-01T14:32:00.000Z')
    expect(queued[0].payload.type).toBe('blowdown')
    expect(queued[0].payload.mile).toBe(1407.2)
    expect(queued[0].photo).toBeInstanceOf(Blob)
    expect(queued[0].photo?.size).toBe(4)
  })

  it('still reads a report stored with only its required fields', async () => {
    const queued = await listQueued()

    expect(queued[1].payload.type).toBe('thanks')
    expect(queued[1].payload.reporter_type).toBe('day')
    expect(queued[1].photo).toBeUndefined()
    expect(queued[1].failure).toBeUndefined()
  })

  it('still reads a report marked as permanently refused', async () => {
    const queued = await listQueued()

    expect(queued[2].failure?.reason).toBe(
      'That report was refused and will not be retried.',
    )
    expect(queued[2].failure?.at).toBe('2026-07-30T08:00:00.000Z')
  })

  // #412 added `build` to OutboxFailure. Both shapes are on phones: written
  // before it existed, and written after. Absent must stay absent rather than
  // being defaulted to something - `flushOutbox` reads it as "some other
  // build", which is what buys an older build's casualty one retry.
  it('still reads a failure stored before builds were recorded', async () => {
    const queued = await listQueued()

    expect(queued[2].failure).toBeDefined()
    expect(queued[2].failure?.build).toBeUndefined()
  })

  it('still reads a failure that recorded its build', async () => {
    const queued = await listQueued()

    expect(queued[3].failure?.build).toBe('4c1f9a2b7e6d5c4b3a29180f7e6d5c4b3a291807')
  })

  it('keeps the preferences it recognises', async () => {
    const preferences = await loadPreferences()

    expect(preferences.theme).toBe('auto')
    expect(preferences.map_style).toBe('quiet_pine')
    expect(preferences.hiking_detail_level).toBe('standard')
  })

  // Not a nicety. preferences.ts documents this exact value: `usgs_topo_live`
  // shipped, was removed, and surviving the merge would reach buildMapStyle,
  // match no background and draw none - a black map, arriving by a different
  // road than the one MAP_OPTIONS.md guarded.
  it('falls back rather than trusting a background this build removed', async () => {
    const preferences = await loadPreferences()

    expect(preferences.background_source).not.toBe('usgs_topo_live')
    expect(preferences.background_source).toBeDefined()
  })

  it('still knows which way the hiker said they were walking', async () => {
    const hike = await loadPlannedHike()

    expect(hike).toEqual({ startMile: 0, endMile: 2189.1 })
  })

  it('still reopens the map where it was left', () => {
    expect(readCamera()).toEqual({ center: [-83.4821, 35.6012], zoom: 12.5 })
  })

  it('still reads the downloaded trail, its POIs, spurs and ribbon', async () => {
    const data = await loadTrailData()

    expect(data).not.toBeNull()
    expect(data?.trails).toBeInstanceOf(Blob)
    expect(data?.pois).toHaveLength(2)
    expect(data?.spurs['spur_0007']?.destination_poi_id).toBe('atc_shelter_0421')
    expect(data?.elevation?.distanceMi).toHaveLength(5)
  })

  // trailData.ts calls this out in a comment: a phone that downloaded before
  // the client read `source` has POIs without one, and undefined means "this
  // copy predates the field" rather than "the pipeline published no source".
  it('still reads a POI stored before `source` existed', async () => {
    const data = await loadTrailData()
    const older = data?.pois.find((poi) => poi.id === 'opentrail_water_1188')

    expect(older).toBeDefined()
    expect(older?.name).toBe('Spring below the ridge')
    expect(older?.source).toBeUndefined()
  })

  // The same case one field later. Every shelter in this baseline predates
  // `capacity`, and none of them should gain a zero on the way out - "Sleeps
  // 0" at a shelter that sleeps eight is the failure this guards.
  it('still reads a shelter stored before `capacity` existed', async () => {
    const data = await loadTrailData()
    const shelter = data?.pois.find((poi) => poi.id === 'atc_shelter_0421')

    expect(shelter).toBeDefined()
    expect(shelter?.name).toBe('Tricorner Knob Shelter')
    expect(shelter?.capacity).toBeUndefined()
  })

  it('still reads a spur record with every optional field absent', async () => {
    const data = await loadTrailData()

    expect(data?.spurs['spur_0008']).toEqual({})
  })

  // The 1.18 GB at a resupply stop with one bar. A resume record this build
  // cannot read is a download that starts over.
  it('still has a resumable corridor download', async () => {
    const progress = await readDownloadProgress(CORRIDOR_ARCHIVE_KEY)

    expect(progress).toEqual({ receivedBytes: 412_663_296, totalBytes: 1_267_384_320 })
  })

  it('still knows which published build the held archive belongs to', async () => {
    expect(await readArchiveVersion(CORRIDOR_ARCHIVE_KEY)).toBe('2026-08-06')
  })
})

// --- The guards that keep the above meaningful ----------------------------
//
// backend/tests/test_preferences_contract.py states the principle these two
// borrow: "the one thing this must never do is pass because it failed to find
// the file."

// --- The downloaded archive (#586) ----------------------------------------
//
// §8c's sentence is "orphans a downloaded archive", and until now nothing here
// read one. Both layouts are inside the three-release window #374 §2 settled, so
// both have to keep opening.
//
// Each test builds its own store rather than using `phoneStore()`, because the
// point is a phone in ONE shape: a store holding both a legacy Blob and a
// completion marker would let a reader pass on the wrong record.
describe('a downloaded archive from before #553', () => {
  function legacyPhone(): void {
    const store = { ...phoneStore(), ...storedLegacyArchive() }
    mockedGet.mockImplementation(async (key: IDBValidKey) => store[key as string])
  }

  it('still opens, rather than asking for 1.18 GB again', async () => {
    // THE MOST EXPENSIVE THING IN THIS FILE. A hiker who downloaded on the
    // previous release and updates the app at a resupply stop with one bar keeps
    // their map, because `readArchive` falls back to the bare package key.
    legacyPhone()

    const archive = await readArchive(CORRIDOR_ARCHIVE_KEY)

    expect(archive).toBeInstanceOf(Blob)
    expect(archive!.size).toBe(STORED_ARCHIVE_BYTES)
  })

  it('reports its size, so the Downloads screen says the map is here', async () => {
    // A separate reader, and separately load-bearing: this is what decides
    // whether the screen offers a re-download. `readArchive` working while this
    // returns null would still send someone to fetch a gigabyte they have.
    legacyPhone()

    expect(await readArchiveSize(CORRIDOR_ARCHIVE_KEY)).toBe(STORED_ARCHIVE_BYTES)
  })

  it('is not mistaken for an unfinished transfer', async () => {
    // No marker exists on this phone, and a reader that treats "no marker" as
    // "nothing finished" is the bug this whole fallback exists to avoid.
    legacyPhone()

    expect(await readComplete(CORRIDOR_ARCHIVE_KEY)).toBeNull()
    expect(await readArchive(CORRIDOR_ARCHIVE_KEY)).toBeInstanceOf(Blob)
  })
})

describe('a downloaded archive from after #553', () => {
  function segmentedPhone(): void {
    const store = { ...phoneStore(), ...storedSegmentedArchive() }
    mockedGet.mockImplementation(async (key: IDBValidKey) => store[key as string])
  }

  it('assembles its segments in order', async () => {
    // Order is the correctness property. The fixture's segments have distinct
    // bytes so a reader that concatenates them wrongly produces different
    // content rather than the same length.
    segmentedPhone()

    const archive = await readArchive(CORRIDOR_ARCHIVE_KEY)

    expect(archive).toBeInstanceOf(Blob)
    expect(new Uint8Array(await archive!.arrayBuffer())).toEqual(
      new Uint8Array([
        0x50, 0x4d, 0x54, 0x69, 0x6c, 0x65, 0x73, 0x01, 0x02, 0x03, 0x04, 0xfe, 0xff,
      ]),
    )
  })

  it('reads the marker this build writes', async () => {
    segmentedPhone()

    expect(await readComplete(CORRIDOR_ARCHIVE_KEY)).toEqual({
      generation: 0,
      segments: 3,
      totalBytes: STORED_ARCHIVE_BYTES,
    })
  })

  it('reports its size off the marker rather than reassembling', async () => {
    segmentedPhone()

    expect(await readArchiveSize(CORRIDOR_ARCHIVE_KEY)).toBe(STORED_ARCHIVE_BYTES)
  })
})

describe('a download caught mid-flight before #553', () => {
  it('does not read as a finished archive', async () => {
    // The bytes under `:partial` are real but incomplete. Serving them as the
    // archive would hand MapLibre a truncated PMTiles file, which is worse than
    // having no map: it is a map that draws part of the trail and stops.
    const store = { ...phoneStore(), ...storedLegacyPartial() }
    mockedGet.mockImplementation(async (key: IDBValidKey) => store[key as string])

    expect(await readArchive(CORRIDOR_ARCHIVE_KEY)).toBeUndefined()
    expect(await readArchiveSize(CORRIDOR_ARCHIVE_KEY)).toBeNull()
  })

  it('leaves the resume records saying what was already fetched', async () => {
    // The partial itself is discarded on the next attempt by design
    // (archiveDownload.ts: copying it needs room for a second copy, which is
    // #544). What must survive is the accounting a hiker sees.
    const store = { ...phoneStore(), ...storedLegacyPartial() }
    mockedGet.mockImplementation(async (key: IDBValidKey) => store[key as string])

    expect(await readDownloadProgress(CORRIDOR_ARCHIVE_KEY)).toEqual({
      receivedBytes: 412_663_296,
      totalBytes: 1_267_384_320,
    })
  })
})

describe('the fixture itself', () => {
  it('is actually loaded, so a green run is not an empty one', () => {
    expect(Object.keys(STORED_SHAPES).length).toBeGreaterThan(10)
    expect(STORED_SHAPES[OUTBOX_KEY]).toBeDefined()
  })

  it('covers every key this build stores under', () => {
    // Built from the app's own exported constants, so a key renamed or added
    // in a later release lands here rather than quietly escaping coverage.
    // The derived download records are generated the same way the app
    // generates them - through `partialKeyFor` and friends - so a change to
    // the suffix scheme is caught too.
    //
    // THIS LIST FAILED ONCE, AND #586 IS WHY IT NOW REACHES THE ARCHIVE. The
    // header above calls this the test that "keeps this file honest as the app
    // grows"; it is a hand-written array, so it only ever caught keys somebody
    // remembered to add to it. #553 introduced the segment and marker families
    // and demoted the bare package key to a legacy read, and none of the three
    // arrived here - so the guard reported success about the one release that
    // changed the layout. The archive entries below are derived from
    // archiveStore.ts's own builders for that reason.
    const packageKeys = MAP_PACKAGES.map((mapPackage) => mapPackage.idbKey)
    const required = [
      OUTBOX_KEY,
      PREFERENCES_KEY,
      PLANNED_HIKE_KEY,
      CAMERA_MEMORY_KEY,
      TRAILS_BLOB_KEY,
      POIS_KEY,
      SPURS_STORE_KEY,
      ELEVATION_STORE_KEY,
      ...packageKeys.flatMap((key) => [progressKeyFor(key), versionKeyFor(key)]),
      sourceKeyFor(CORRIDOR_ARCHIVE_KEY),
      // The archive under the corridor key, in both shapes that are inside the
      // support window: the bare key a pre-#553 phone holds a whole Blob under,
      // and the marker plus first segment a current one holds.
      CORRIDOR_ARCHIVE_KEY,
      completeKeyFor(CORRIDOR_ARCHIVE_KEY),
      segmentKeyFor(CORRIDOR_ARCHIVE_KEY, 0, 0),
      partialKeyFor(CORRIDOR_ARCHIVE_KEY),
    ]

    const covered = new Set([
      ...Object.keys(STORED_SHAPES),
      // The entries that are functions rather than frozen entries, because a
      // Blob and a Float32Array cannot be frozen literals.
      TRAILS_BLOB_KEY,
      ELEVATION_STORE_KEY,
      ...Object.keys(storedLegacyArchive()),
      ...Object.keys(storedSegmentedArchive()),
      ...Object.keys(storedLegacyPartial()),
    ])

    const missing = required.filter((key) => !covered.has(key))
    expect(missing).toEqual([])
  })

  it('names the archive keys the same way the app derives them', () => {
    // A rename of CORRIDOR_ARCHIVE_KEY would orphan a downloaded archive
    // outright - the blob stays in IndexedDB under a name nothing looks up.
    expect(CORRIDOR_ARCHIVE_KEY).toBe('ourhike:corridor-archive')
    expect(partialKeyFor(CORRIDOR_ARCHIVE_KEY)).toBe('ourhike:corridor-archive:partial')
    expect(progressKeyFor(CORRIDOR_ARCHIVE_KEY)).toBe('ourhike:corridor-archive:progress')
    // #553's two families, pinned as literals for the same reason: the fixture
    // holds literal strings because a phone does, so a builder that stopped
    // agreeing with them would read past a real archive in silence.
    expect(completeKeyFor(CORRIDOR_ARCHIVE_KEY)).toBe('ourhike:corridor-archive:complete')
    expect(segmentKeyFor(CORRIDOR_ARCHIVE_KEY, 0, 2)).toBe(
      'ourhike:corridor-archive:g0:2',
    )
  })

  it('holds an archive fixture in each supported shape, not just one', () => {
    // The failure this file is most able to have is a green run that proves
    // less than it looks like. An empty or single-shape archive fixture would
    // pass every test above by never exercising the branch that matters.
    expect(Object.keys(storedLegacyArchive())).toEqual([CORRIDOR_ARCHIVE_KEY])
    expect(Object.keys(storedSegmentedArchive())).toContain(
      completeKeyFor(CORRIDOR_ARCHIVE_KEY),
    )
    expect(
      Object.keys(storedSegmentedArchive()).filter((key) => key.includes(':g0:')),
    ).toHaveLength(3)
  })
})
