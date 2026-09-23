// This build must still read what each SHIPPED release wrote (#1253).
//
// storedShapes.compat.test.ts runs the real readers over the pre-1.0
// baseline. That baseline predates every tag, so for three releases the
// question §8c actually asks - can this build read what v1.1.1 left on a
// phone? - was answered by a snapshot of something v1.1.1 never wrote. This
// file asks it per release, against RELEASE_SHAPES, composing each phone as a
// hiker who installed early and updated every time would hold it.
//
// Every assertion runs a real reader, on the same rule as the sibling file:
// a shape check would pass while the function that has to survive the shape
// throws. The assertions are the details a later build is most tempted to
// break - a word a release spelled differently, a key a release added that
// an older record lacks, an absence that means something.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { get, getMany } from 'idb-keyval'

import { isHeld, listQueued } from './outbox'
import { loadPreferences, preferencesSyncState } from './preferences'
import { syncEnabled } from './syncStatus'
import { tripSyncState } from './tripSyncState'
import { dayHikeSyncState } from './dayHikeSyncState'
import { loadHikerMode } from './hikerMode'
import { loadDayHikes, walkedDates } from './dayHikes'
import {
  ELEVATION_STORE_KEY,
  TRAILS_BLOB_KEY,
  haveTrailData,
  loadTrailData,
} from './trailData'
import { dismissedRelease, recallRelease } from './dataRefresh'
import { listOwnPhotos } from './poiPhotos'
import { readWalked } from './walkedMiles'
import { readPassedToday } from './passedToday'
import { readStoredPace } from './pace'
import { completedMarker, estimateAvailableBytes } from './storageHealth'
import { ATC_SOURCE_KEY, readNoticeSilence } from './notices'
import { readTrailsMerged } from './trailShape'
import { createGpsTrace } from './gpsTrace'
import {
  DEM_CELLS,
  NETWORK_CELLS,
  cellPackageKey,
  readStoredCellIndex,
} from './coverageCells'
import { loadTrips } from './trips'
import { loadLastOnTrail } from './lastOnTrail'
import { loadOpenWalk } from './openWalk'
import { loadTakenTrail } from './takenTrail'
import { listSentReports } from './sentReports'
import { readLaunchMirror } from './launchMirror'
import { readArchive, readComplete } from './archiveStore'
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'
import {
  RELEASE_SHAPES,
  phoneOn,
  storedElevation,
  storedInterruptedRelease,
  storedTrailsBlob,
} from './storedShapes.fixtures'

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))

const mockedGet = vi.mocked(get)

/** Puts a release's phone under every reader: IndexedDB through the mock,
 *  localStorage through jsdom's own. */
function installPhone(tag: string, extra: Record<string, unknown> = {}): void {
  const phone = phoneOn(tag)
  const store: Record<string, unknown> = {
    ...phone.indexedDb,
    [TRAILS_BLOB_KEY]: storedTrailsBlob(),
    [ELEVATION_STORE_KEY]: storedElevation(),
    ...extra,
  }
  mockedGet.mockImplementation(async (key: IDBValidKey) => store[key as string])
  // `getMany` follows whatever `get` is doing right now (#1303's one
  // transaction in lib/trailData.ts), so a test that re-points `get`
  // mid-file does not have to re-point both.
  vi.mocked(getMany).mockImplementation((keys) =>
    Promise.all(keys.map((key) => vi.mocked(get)(key))),
  )
  window.localStorage.clear()
  for (const [key, value] of Object.entries(phone.localStorage)) {
    window.localStorage.setItem(key, value)
  }
}

afterEach(() => {
  window.localStorage.clear()
  vi.useRealTimers()
})

describe('the release ledger itself', () => {
  it('names every tagged release that shipped to hikers, in order', () => {
    // v1.0.0, v1.0.1 and v1.1.0 are deliberately absent, for the reason
    // backend/openapi_baselines/retained.json gives: v1.1.1 superseded all
    // three within days, one never left draft, and their clients are a
    // subset of v1.1.1's rather than a separate claim.
    expect(RELEASE_SHAPES.map((release) => release.tag)).toEqual([
      'v1.1.1',
      'v1.2.0',
      'v1.2.1',
      'v1.2.2',
      'v1.3.0',
      'v1.3.1',
      'v1.3.2',
    ])
    for (const release of RELEASE_SHAPES) {
      expect(release.commit).toMatch(/^[0-9a-f]{8}$/)
      expect(release.published).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    }
  })

  it('composes a phone by laying each release over the last', () => {
    const early = phoneOn('v1.1.1')
    const late = phoneOn('v1.2.1')
    // A key v1.1.1 wrote and no later release touched survives the overlay.
    expect(late.indexedDb['ourhike:stewards']).toBe(early.indexedDb['ourhike:stewards'])
    // A key every release rewrote holds the newest shape.
    expect(late.indexedDb['ourhike:preferences']).not.toBe(
      early.indexedDb['ourhike:preferences'],
    )
    expect(() => phoneOn('v0.0.0')).toThrow(/no release fixture/)
  })
})

describe('a phone that stopped on v1.1.1', () => {
  beforeEach(() => installPhone('v1.1.1'))

  it('keeps every preference the hiker set, and fills in the one this build added', async () => {
    const preferences = await loadPreferences()

    expect(preferences.trail_name).toBe('Sprocket')
    expect(preferences.reporter_type).toBe('section')
    expect(preferences.theme).toBe('dark')
    expect(preferences.unit_system).toBe('metric')
    expect(preferences.hiking_detail_level).toBe('fine')
    expect(preferences.map_style).toBe('night_hike')
    expect(preferences.waypoint_types_shown).toEqual([
      'shelter',
      'water',
      'campsite',
      'privy',
    ])
    expect(preferences.anonymity_window_days).toBe(7)
    expect(preferences.contribute_conditions).toBe(true)
    // Absent on this release, and the default is ON - a hiker's own logbook
    // shown back to them, never a record kept in secret.
    expect(preferences.impact_panel_shown).toBe(true)
  })

  it('still knows what has and has not synced', async () => {
    expect(await preferencesSyncState()).toEqual({
      dirty: true,
      syncedAt: '2026-08-26T21:14:03.512Z',
    })
    expect(await syncEnabled()).toBe(false)

    const trips = await tripSyncState()
    expect(trips.dirty).toEqual(['trip-0001'])
    expect(trips.deleted).toEqual(['trip-0009'])
    expect(trips.hikeDirty).toBe(true)
    expect(trips.since).toBe('2026-08-26T21:14:03.512Z')

    const dayHikes = await dayHikeSyncState()
    expect(dayHikes.dirty).toEqual(['day-hike-0002'])
    expect(dayHikes.seen).toEqual({ 'day-hike-0001': '2026-08-26T21:14:03.512Z' })
  })

  // THE RENAME. This release spelled the middle mode `thru`; #1127 made it
  // `long`. A hiker who chose it has to come up in the same mode, not in the
  // default - the default would overwrite an explicit statement.
  it('reads the mode this release called thru as long', async () => {
    expect(await loadHikerMode()).toBe('long')
  })

  it('still has every kind of thing the outbox could carry', async () => {
    const queued = await listQueued()

    expect(queued).toHaveLength(11)
    const kinds = queued
      .map((item) => item.action?.kind)
      .filter((kind) => kind !== undefined)
    expect(kinds).toEqual(['poi_photo_share', 'poi_photo_withdraw', 'poi_photo_report'])
    expect(queued[4].photo).toBeInstanceOf(Blob)
    expect(queued[7].appFailure?.harms).toEqual(['lost'])
    expect(queued[7].appFailure?.was_offline).toBe(true)
    expect(queued[8].fieldNote?.observation).toBe('trickling')
    expect(queued[9].volunteerHours?.hours).toBe(3.5)
    expect(queued[10].closure?.reason_type).toBe('storm_damage')
    expect(queued[10].closure?.end_mile_marker).toBe(1403.4)
    // Nothing this release wrote was held - the key did not exist.
    expect(queued.every((item) => item.holdUntil === undefined)).toBe(true)
  })

  it('still knows which release its trail data came from, and which it declined', async () => {
    const release = await recallRelease()

    expect(release?.version).toBe('2026-08-26')
    expect(release?.hashes['trails.geojson']).toMatch(/^[0-9a-f]{64}$/)
    expect(release?.at).toBe(1756251000000)
    expect(await dismissedRelease()).toBe('2026-08-27')
  })

  it('still reads a fully featured shelter - capacity, water, site, nearby, photos', async () => {
    const data = await loadTrailData()
    const shelter = data?.pois.find((poi) => poi.id === 'atc_shelter_0512')

    expect(shelter?.capacity).toBe(8)
    expect(shelter?.waterDistanceFt).toBe(350)
    expect(shelter?.mile).toBe(1407.9)
    expect(shelter?.siteRole).toBe('anchor')
    expect(shelter?.nearby).toEqual([{ phrase: 'privy', distance_ft: 140 }])
    expect(shelter?.photos).toHaveLength(2)
    expect(shelter?.photoLicense).toBe('CC BY-SA 4.0')
    const privy = data?.pois.find((poi) => poi.id === 'atc_privy_0512')
    expect(privy?.siteId).toBe('site_0512')
    expect(privy?.siteRole).toBe('member')
    // A release before #1192 stored no miles beside its lines.
    expect(data?.trailMiles).toBeNull()
  })

  it('still reads the four side stores beside the waypoints', async () => {
    const data = await loadTrailData()

    expect(data?.clubSections.clubs.map((club) => club.acronym)).toEqual([
      'NYNJTC',
      'GATC',
    ])
    expect(data?.clubSections.clubs[1].runs).toHaveLength(2)
    expect(data?.clubSections.unattributed).toEqual([{ startMile: 30.2, endMile: 31.4 }])
    expect(data?.clubSections.sourceEdited).toEqual({ 'Trail Clubs': '2026-08-14' })
    expect(data?.stewards.map((steward) => steward.provider)).toEqual([
      'ATC',
      'NYS OPRHP',
    ])
    expect(data?.stewards[0].keys).toContain('atc_shelters')
    expect(data?.stewards[1].attribution).toBeNull()
    expect(data?.highlights[0].id).toBe('mahoosuc-arm')
    expect(data?.highlights[0].legs[0]).toEqual({
      trail: 'AT',
      startMile: 1925.0,
      endMile: 1930.5,
    })
    expect(data?.retiredPois['atc_shelter_0100']?.supersededBy).toBe('atc_shelter_0421')
    expect(data?.retiredPois['opentrail_water_0002']?.name).toBeUndefined()
  })

  it('still has the hiker’s own photos, with the chosen one first', async () => {
    const photos = await listOwnPhotos('atc_shelter_0512')

    expect(photos.map((photo) => photo.id)).toEqual(['photo-0002', 'photo-0001'])
    expect(photos[0].blob).toBeInstanceOf(Blob)
    expect(photos[0].shared).toBe('2026-08-22T15:01:00.000Z')
    expect(photos[1].shared).toBeUndefined()
    expect(photos[1].source).toBe('camera')
  })

  it('still knows the ground walked, today’s slice of it, and the pace set', () => {
    expect(readWalked()).toEqual([
      { startMile: 1405.2, endMile: 1409.8 },
      { startMile: 1411, endMile: 1412.4 },
    ])
    expect(readPassedToday(new Date('2026-08-27T20:00:00')).ranges).toEqual([
      { startMile: 1405.2, endMile: 1409.8 },
    ])
    // A record from another day reads as an empty today, never as today's.
    expect(readPassedToday(new Date('2026-08-28T08:00:00')).ranges).toEqual([])
    expect(readStoredPace()).toEqual({
      flatPaceMph: 2.4,
      ascentMetersPerHour: 420,
      descentMinutesPer1000m: 8,
    })
  })

  it('still credits the storage it gave back, while the note is fresh', async () => {
    // The note expires by its own clock, so the reader is asked on the day it
    // was written: 314,572,800 bytes released, and the browser still
    // reporting the same usage as immediately afterwards - none returned yet.
    vi.useFakeTimers()
    vi.setSystemTime(new Date(1756250000000 + 1000))
    const original = Object.getOwnPropertyDescriptor(navigator, 'storage')
    Object.defineProperty(navigator, 'storage', {
      configurable: true,
      value: { estimate: async () => ({ quota: 2_000_000_000, usage: 903_000_000 }) },
    })
    try {
      expect(await estimateAvailableBytes()).toBe(
        2_000_000_000 - 903_000_000 + 314_572_800,
      )
    } finally {
      if (original === undefined) {
        delete (navigator as { storage?: unknown }).storage
      } else {
        Object.defineProperty(navigator, 'storage', original)
      }
    }
  })

  it('still knows the corridor archive finished here', () => {
    expect(completedMarker(CORRIDOR_ARCHIVE_KEY)?.toISOString()).toBe(
      '2026-08-26T02:10:00.000Z',
    )
  })

  // The watermark moved to a per-organization key in v1.2.0. The old key is
  // still read for the ATC, so a banner dismissed on this release stays
  // dismissed on the next rather than coming back for everybody.
  it('still honours the ATC alerts a hiker already dismissed', () => {
    expect(readNoticeSilence(ATC_SOURCE_KEY)?.toISOString()).toBe(
      '2026-08-20T00:00:00.000Z',
    )
    expect(readTrailsMerged()).toBe(true)
  })
})

describe('a phone that stopped on v1.2.0', () => {
  beforeEach(() => installPhone('v1.2.0'))

  it('keeps the Light rung and the logbook switch as the hiker left them', async () => {
    const preferences = await loadPreferences()

    // Storable and unofferable, and the reader must not "fix" it to standard.
    expect(preferences.hiking_detail_level).toBe('light')
    expect(preferences.impact_panel_shown).toBe(false)
    expect(await loadHikerMode()).toBe('long')
  })

  it('still reads a report held for its undo window, and lets it go when the window closes', async () => {
    const queued = await listQueued()
    const held = queued.find((item) => item.holdUntil !== undefined)

    expect(queued).toHaveLength(12)
    expect(held?.holdUntil).toBe('2026-08-28T14:00:08.000Z')
    expect(isHeld(held!, Date.parse('2026-08-28T14:00:03.000Z'))).toBe(true)
    expect(isHeld(held!, Date.parse('2026-08-28T14:00:09.000Z'))).toBe(false)
  })

  it('still reads day hikes with a note, a climb, and a merged leg’s other organizations', async () => {
    const store = await loadDayHikes()

    expect(store.openId).toBe('day-hike-0003')
    expect(store.hikes.map((hike) => hike.id)).toEqual([
      'day-hike-0001',
      'day-hike-0003',
      'day-hike-0004',
    ])
    // Written on an earlier build and never re-saved: no climb key at all,
    // which means "the app never asked" and must stay distinct from null.
    expect('climb' in store.hikes[0].figures).toBe(false)
    expect(store.hikes[0].note).toBe('')
    expect(store.hikes[1].figures.climb).toEqual({ gainFt: 640, lossFt: 610 })
    expect(store.hikes[1].figures.legs[0].concurrent_sources).toEqual(['oprhp_trails'])
    // Asked, and the graph had no answer.
    expect(store.hikes[2].figures.climb).toBeNull()
    expect(store.hikes[2].note).toBe('Wet rocks past the brook.')
    expect(store.hikes[2].recorded).toBe('walked')
  })

  it('still reads the other organizations’ waypoints beside the A.T.’s', async () => {
    const data = await loadTrailData()
    const leanTo = data?.pois.find((poi) => poi.id === 'dec_lean_tos:1234')

    expect(leanTo?.type).toBe('shelter')
    expect(leanTo?.source).toBe('dec_lean_tos')
    expect(leanTo?.capacity).toBe(8)
    // Not on the A.T.'s axis: no mile, and absent rather than null or zero.
    expect(leanTo?.mile).toBeUndefined()
    expect(data?.pois.filter((poi) => poi.source?.startsWith('dec_'))).toHaveLength(3)
  })
})

describe('a phone that stopped on v1.2.1', () => {
  beforeEach(() => installPhone('v1.2.1'))

  it('still reads the stops on a day hike, and none on one saved without them', async () => {
    const store = await loadDayHikes()

    expect(store.hikes[1].stops).toEqual([
      { poiId: 'atc_shelter_0512', type: 'shelter', name: 'Fingerboard Shelter' },
    ])
    expect('stops' in store.hikes[0]).toBe(false)
    expect('stops' in store.hikes[2]).toBe(false)
  })

  it('still reads the trailhead category and the miles beside the lines', async () => {
    const data = await loadTrailData()

    expect(data?.pois.find((poi) => poi.type === 'trailhead')?.source).toBe(
      'oprhp_facilities',
    )
    expect(data?.trailMiles).toBeInstanceOf(Blob)
    expect(await data?.trailMiles?.text()).toContain('"trails_sha256"')
  })

  it('resumes a GPS trace that was recording when the app last closed', async () => {
    const trace = createGpsTrace()
    const status = await trace.resume()

    expect(status.recording).toBe(true)
    expect(status.marker).toBe('walking')
    expect(status.samples).toBe(2)
    expect(status.lastAccuracyConfidence).toBe(68)
    const samples = await trace.readAll()
    expect(samples.map((sample) => sample.mile)).toEqual([1406.1, 1406.15])
    expect(samples[0].fixSource).toBe('native')
  })

  it('still holds the offline cells it downloaded, and the index that names them', async () => {
    const index = await readStoredCellIndex()

    expect(index?.cellDegrees).toBe(1)
    expect(index?.context).toBe('basemap_context.pmtiles')
    expect(index?.cells.map((cell) => cell.name)).toEqual(['n41w074'])
    expect(index?.cells[0].bounds).toEqual([-74, 41, -73, 42])

    const cell = cellPackageKey('n41w074')
    expect(cell).toBe('ourhike:basemap-cell:n41w074')
    expect(await readComplete(cell)).toEqual({
      generation: 0,
      segments: 1,
      totalBytes: 7,
    })
    expect((await readArchive(cell))?.size).toBe(7)
    expect((await readArchive('ourhike:basemap-context'))?.size).toBe(4)
    expect(completedMarker(cell)?.toISOString()).toBe('2026-09-07T13:30:00.000Z')
  })

  it('still reads everything the earlier releases wrote', async () => {
    // The overlay carries v1.1.1's keys forward untouched, so one reader per
    // family is enough here to prove the composition, not the shapes.
    expect((await loadPreferences()).trail_name).toBe('Sprocket')
    expect(await loadHikerMode()).toBe('long')
    expect(await listQueued()).toHaveLength(12)
    expect((await loadTrailData())?.stewards).toHaveLength(2)
    expect(readWalked()).toHaveLength(2)
  })
})

describe('a phone that stopped on v1.2.2', () => {
  beforeEach(() => installPhone('v1.2.2'))

  it('still holds the network cell it downloaded, under its own family’s keys', async () => {
    const index = await readStoredCellIndex(NETWORK_CELLS)

    expect(index?.context).toBeNull()
    expect(index?.cells.map((cell) => cell.name)).toEqual(['n41w074'])

    const cell = cellPackageKey('n41w074', NETWORK_CELLS)
    expect(cell).toBe('ourhike:network-cell:n41w074')
    expect(await readComplete(cell)).toEqual({
      generation: 0,
      segments: 1,
      totalBytes: 2,
    })
    expect((await readArchive(cell))?.size).toBe(2)
    expect(completedMarker(cell)?.toISOString()).toBe('2026-09-08T22:05:00.000Z')
    // The basemap cell of the same name is a different archive, untouched.
    expect((await readArchive(cellPackageKey('n41w074')))?.size).toBe(7)
  })
})

describe('a phone that stopped on v1.3.0', () => {
  beforeEach(() => installPhone('v1.3.0'))

  it('keeps the place the hiker named on first run', async () => {
    const preferences = await loadPreferences()

    expect(preferences.default_place?.id).toBe('oprhp_park_polygons:1')
    expect(preferences.default_place?.kind).toBe('park')
    expect(preferences.default_place?.bbox).toEqual([
      -74.2021, 41.1558, -73.9829, 41.3363,
    ])
    expect(preferences.hiking_detail_level).toBe('light')
  })

  it('reads a long hike stored as points, paused, and still the active one', async () => {
    const store = await loadTrips()

    expect(store.activeHikeId).toBe('hike-0001')
    const hike = store.hikes[0]
    expect(hike.trailId).toBe('AT')
    expect(hike.status).toBe('paused')
    expect(hike.pausedAtMile).toBe(481.4)
    expect(hike.pausedOn).toBe('2026-09-04')
    expect(hike.points.map((point) => point.mile)).toEqual([470.8, 503.3, 486.2])
    expect(hike.points[0].date).toBe('2026-09-01')
    expect(hike.points[0].poiId).toBe('atc_shelter_0777')
    expect(store.trips.map((trip) => trip.id)).toEqual(['trip-0001'])

    const sync = await tripSyncState()
    expect(sync.hikesDirty).toEqual(['hike-0001'])
    expect(sync.hikesDeleted).toEqual(['hike-0002'])
    expect(sync.activeHikeDirty).toBe(true)
  })

  it('reads a day hike saved from a published route, with its walks', async () => {
    const store = await loadDayHikes()
    const saved = store.hikes.find((hike) => hike.id === 'day-hike-0005')

    expect(saved?.sourceId).toBe('nynjtc_hike_finder:77')
    expect(saved?.sourceAuthor).toBe('New York-New Jersey Trail Conference')
    expect(walkedDates(saved!)).toEqual(['2026-09-13', '2026-09-06'])
    expect(saved?.walks?.[0].note).toBe('Lake was low.')
    // Saved on an earlier release and never re-saved: no walks key at all.
    expect('walks' in store.hikes[0]).toBe(false)
  })

  it('reads the four device-local records this release introduced', async () => {
    expect(await loadLastOnTrail()).toBe('2026-09-04')
    expect(await loadOpenWalk()).toEqual({ hikeId: 'day-hike-0005', day: '2026-09-13' })
    expect(await loadTakenTrail()).toBe('LP')
    const sent = await listSentReports()
    expect(sent.map((report) => report.id)).toEqual([
      '4b5c6d7e-9f00-4112-b3c4-d5e6f708192a',
      '5f8e1b3a-0c4d-4a2e-9f1b-2c3d4e5f6a7b',
    ])
    expect(sent[0].poiId).toBeNull()
    expect(sent[1].mile).toBeNull()
  })

  it('reads the launch mirror, so the first frame shows the mode and trail chosen', () => {
    expect(readLaunchMirror()).toEqual({
      onboardingCompleted: true,
      theme: 'dark',
      hikerMode: 'long',
      takenTrail: 'LP',
    })
  })

  it('reads a steward’s terms quoted whole', async () => {
    const data = await loadTrailData()
    const njdep = data?.stewards.find((steward) => steward.provider === 'NJDEP')

    expect(njdep?.terms).toMatch(/^New Jersey Department of Environmental Protection/)
    // `termsSource` is deliberately NOT asserted here. v1.3.0 stored it as
    // camelCase and lib/stewards.ts's storedStewards re-parses the stored
    // array with the wire's snake_case reader, so it reads back null. That
    // is a finding against the reader, reported with this entry rather than
    // hidden by editing the fixture.
  })
})

describe('a phone that stopped on v1.3.1', () => {
  beforeEach(() => installPhone('v1.3.1'))

  it('still sends a report placed in words, with every photo it holds', async () => {
    const queued = await listQueued()
    const worded = queued.find((item) => item.payload?.place_words !== undefined)

    expect(queued).toHaveLength(13)
    expect(worded?.payload?.place_words).toMatch(/Fitzgerald Falls/)
    expect(worded?.payload?.lat).toBeUndefined()
    expect(worded?.payload?.mile).toBeUndefined()
    expect(worded?.photos).toHaveLength(2)
    expect(worded?.photos?.[0]).toBeInstanceOf(Blob)
    // An earlier release's single-photo report is still that shape.
    expect(queued[0].photo).toBeInstanceOf(Blob)
    expect(queued[0].photos).toBeUndefined()
  })

  it('still holds the terrain cell, its context, and the covered box', async () => {
    const index = await readStoredCellIndex(DEM_CELLS)

    expect(index?.context).toBe('dem_context.pmtiles')
    expect(index?.cells[0].covered).toEqual([-74, 41, -73.5, 41.6])

    const cell = cellPackageKey('n41w074', DEM_CELLS)
    expect(cell).toBe('ourhike:dem-cell:n41w074')
    expect((await readArchive(cell))?.size).toBe(7)
    expect((await readArchive(DEM_CELLS.contextPackageKey))?.size).toBe(4)
    expect(completedMarker(cell)?.toISOString()).toBe('2026-09-16T20:45:00.000Z')
  })
})

describe('a phone that stopped on v1.3.2', () => {
  beforeEach(() => installPhone('v1.3.2'))

  it('keeps the real name and the blaze-colour switch', async () => {
    const preferences = await loadPreferences()

    expect(preferences.real_name).toBe('Pat Example')
    expect(preferences.blaze_colors_shown).toBe(true)
    expect(preferences.default_place?.name).toBe('Harriman State Park')
  })

  it('still sends a report with its fix’s source, radius and age, and its signature', async () => {
    const queued = await listQueued()
    const signed = queued.find((item) => item.payload?.signed_name !== undefined)

    expect(queued).toHaveLength(14)
    expect(signed?.payload?.location_source).toBe('gps')
    expect(signed?.payload?.location_accuracy_m).toBe(9.6)
    expect(signed?.payload?.location_fix_age_s).toBe(4)
    expect(signed?.payload?.signed_name_kind).toBe('real')
    expect(signed?.payload?.contact_ok).toBe(true)
  })

  it('still reads everything the earlier releases wrote', async () => {
    expect((await loadPreferences()).trail_name).toBe('Sprocket')
    expect((await loadTrips()).activeHikeId).toBe('hike-0001')
    expect(await readStoredCellIndex(NETWORK_CELLS)).not.toBeNull()
    expect(await readStoredCellIndex(DEM_CELLS)).not.toBeNull()
    expect((await loadTrailData())?.stewards).toHaveLength(3)
    expect(readLaunchMirror()?.takenTrail).toBe('LP')
  })
})

describe('a download that died between the lines and the waypoints', () => {
  it('reads as no trail data, so the launch fetch finishes the job', async () => {
    installPhone('v1.2.1', storedInterruptedRelease())

    // The lines are there and load; the marker is what says "not whole".
    expect(await loadTrailData()).not.toBeNull()
    expect(await haveTrailData()).toBe(false)
  })

  it('reads as whole once the marker is gone', async () => {
    installPhone('v1.2.1')

    expect(await haveTrailData()).toBe(true)
  })
})

// --- The guard that keeps the ledger meaningful -----------------------------
//
// storedShapes.compat.test.ts's "covers every key" list is hand-written and
// its own comment says what that costs: it only ever caught keys somebody
// remembered to add. This is the same guard for the keys the releases wrote,
// built from the app's exported constants where one exists, so a rename of
// any of them lands here rather than orphaning a hiker's record in silence.
describe('the release ledger', () => {
  it('covers every key the shipped releases store under', async () => {
    const { PREFERENCES_SYNC_KEY } = await import('./preferences')
    const { SYNC_ENABLED_KEY } = await import('./syncStatus')
    const { TRIPS_SYNC_KEY } = await import('./tripSyncState')
    const { DAY_HIKES_SYNC_KEY } = await import('./dayHikeSyncState')
    const { HIKER_MODE_KEY } = await import('./hikerMode')
    const { DISMISSED_KEY, RELEASE_KEY } = await import('./dataRefresh')
    const {
      CLUB_SECTIONS_STORE_KEY,
      HIGHLIGHTS_STORE_KEY,
      RETIRED_POI_STORE_KEY,
      STEWARDS_STORE_KEY,
      TRAIL_MILES_STORE_KEY,
    } = await import('./trailData')
    const { POI_PHOTOS_PREFIX } = await import('./poiPhotos')
    const { BASEMAP_CELLS } = await import('./coverageCells')
    const { completeKeyFor, segmentKeyFor } = await import('./archiveStore')
    const { LAST_ON_TRAIL_KEY } = await import('./lastOnTrail')
    const { OPEN_WALK_KEY } = await import('./openWalk')
    const { TAKEN_TRAIL_KEY } = await import('./takenTrail')
    const { SENT_REPORTS_KEY } = await import('./sentReports')

    const cell = cellPackageKey('n41w074', BASEMAP_CELLS)
    const required = [
      PREFERENCES_SYNC_KEY,
      SYNC_ENABLED_KEY,
      TRIPS_SYNC_KEY,
      DAY_HIKES_SYNC_KEY,
      HIKER_MODE_KEY,
      RELEASE_KEY,
      DISMISSED_KEY,
      CLUB_SECTIONS_STORE_KEY,
      STEWARDS_STORE_KEY,
      HIGHLIGHTS_STORE_KEY,
      RETIRED_POI_STORE_KEY,
      TRAIL_MILES_STORE_KEY,
      `${POI_PHOTOS_PREFIX}atc_shelter_0512`,
      // lib/gpsTrace.ts keeps its two key builders private, so these are the
      // literals a phone holds, pinned here the way the fixture pins its own.
      'ourhike:gps-trace:state',
      'ourhike:gps-trace:c0',
      BASEMAP_CELLS.indexStoreKey,
      segmentKeyFor(cell, 0, 0),
      completeKeyFor(cell),
      segmentKeyFor(BASEMAP_CELLS.contextPackageKey, 0, 0),
      completeKeyFor(BASEMAP_CELLS.contextPackageKey),
      NETWORK_CELLS.indexStoreKey,
      segmentKeyFor(cellPackageKey('n41w074', NETWORK_CELLS), 0, 0),
      completeKeyFor(cellPackageKey('n41w074', NETWORK_CELLS)),
      DEM_CELLS.indexStoreKey,
      segmentKeyFor(cellPackageKey('n41w074', DEM_CELLS), 0, 0),
      completeKeyFor(cellPackageKey('n41w074', DEM_CELLS)),
      segmentKeyFor(DEM_CELLS.contextPackageKey, 0, 0),
      completeKeyFor(DEM_CELLS.contextPackageKey),
      LAST_ON_TRAIL_KEY,
      OPEN_WALK_KEY,
      TAKEN_TRAIL_KEY,
      SENT_REPORTS_KEY,
    ]

    const covered = new Set([
      ...RELEASE_SHAPES.flatMap((release) => Object.keys(release.indexedDb)),
      ...Object.keys(storedInterruptedRelease()),
    ])
    expect(required.filter((key) => !covered.has(key))).toEqual([])
  })

  it('covers every localStorage key the shipped releases write', async () => {
    const { WALKED_STORAGE_KEY } = await import('./walkedMiles')
    const { PASSED_TODAY_STORAGE_KEY } = await import('./passedToday')
    const { PACE_STORAGE_KEY } = await import('./pace')
    const { RELEASED_KEY, completedMarkerKeyFor } = await import('./storageHealth')
    const { LEGACY_ATC_SILENCE_KEY } = await import('./notices')
    const { TRAILS_MERGED_STORAGE_KEY } = await import('./trailShape')
    const { LAUNCH_MIRROR_KEY } = await import('./launchMirror')

    const required = [
      WALKED_STORAGE_KEY,
      PASSED_TODAY_STORAGE_KEY,
      PACE_STORAGE_KEY,
      RELEASED_KEY,
      LEGACY_ATC_SILENCE_KEY,
      TRAILS_MERGED_STORAGE_KEY,
      completedMarkerKeyFor(CORRIDOR_ARCHIVE_KEY),
      completedMarkerKeyFor(cellPackageKey('n41w074')),
      completedMarkerKeyFor(cellPackageKey('n41w074', NETWORK_CELLS)),
      completedMarkerKeyFor(cellPackageKey('n41w074', DEM_CELLS)),
      LAUNCH_MIRROR_KEY,
    ]

    const covered = new Set(
      RELEASE_SHAPES.flatMap((release) => Object.keys(release.localStorage)),
    )
    expect(required.filter((key) => !covered.has(key))).toEqual([])
  })
})
