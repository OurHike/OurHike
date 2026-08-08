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
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'
import { MAP_PACKAGES } from './packages'
import { STORED_SHAPES, storedElevation, storedTrailsBlob } from './storedShapes.fixtures'

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))

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

    expect(queued).toHaveLength(3)
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
    ]

    const covered = new Set([
      ...Object.keys(STORED_SHAPES),
      // The two that are functions rather than frozen entries, because a
      // Blob and a Float32Array cannot be frozen literals.
      TRAILS_BLOB_KEY,
      ELEVATION_STORE_KEY,
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
  })
})
