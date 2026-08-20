import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { get, set, del } from 'idb-keyval'
import {
  downloadTrailData,
  haveTrailData,
  loadTrailData,
  loadTrailLines,
  deleteTrailData,
  TRAIL_DATA_PARTIAL_KEY,
  ELEVATION_STORE_KEY,
  POIS_KEY,
  CLUB_SECTIONS_STORE_KEY,
  SPURS_STORE_KEY,
  TRAILS_BLOB_KEY,
  TrailDataHashMismatchError,
  type StoredPoi,
} from './trailData'
import {
  CLUB_SECTIONS_KEY,
  dataUrl,
  ELEVATION_KEY,
  POI_TYPES,
  SPURS_KEY,
  TRAILS_KEY,
} from './config'
import {
  readTrailsMerged,
  TRAILS_MERGED_STORAGE_KEY,
  writeTrailsMerged,
} from './trailShape'
import type { ElevationProfile } from './elevationProfile'
import { publishedHashes } from './dataManifest'
import { sha256Hex } from './sha256'

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))

// The published-hash lookup, mocked the same way archiveDownload.test.ts
// mocks it: what latest.json says is dataManifest.ts's own subject, and what
// matters here is only whether these artifacts are held to it.
vi.mock('./dataManifest', () => ({ publishedHash: vi.fn(), publishedHashes: vi.fn() }))

const mockedPublishedHashes = vi.mocked(publishedHashes)

/**
 * What `latest.json` publishes, in the shape the download now reads it: ONE
 * snapshot per attempt, handed back as a synchronous lookup (#717). It used to
 * be re-fetched per artifact, so these tests set a per-key async mock; the
 * expectations are unchanged, only where the answer comes from.
 */
function publishing(lookup: (key: string) => string | null) {
  mockedPublishedHashes.mockResolvedValue(lookup)
}

const store = new Map<string, unknown>()

function poiCollection(features: Array<Record<string, unknown>>) {
  return JSON.stringify({
    type: 'FeatureCollection',
    features: features.map((properties) => ({ type: 'Feature', properties })),
  })
}

beforeEach(() => {
  store.clear()
  localStorage.removeItem(TRAILS_MERGED_STORAGE_KEY)
  // No published answer by default, which is what an older release or a
  // field-test server gives - and must leave these downloads behaving
  // exactly as they did before #197.
  publishing(() => null)
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
  vi.mocked(del).mockImplementation((key) => {
    store.delete(key as string)
    return Promise.resolve()
  })
})

afterEach(() => {
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

/** Serves trail lines for any trails URL, the given POIs for poi_*, the given
 *  spur detail for spurs.json and the given samples for
 *  elevation_profile.json. The elevation default is an empty array, which is
 *  "this release publishes no usable profile" - the tests that care about one
 *  pass their own.
 *
 *  `clubSections` is last and defaults to an empty object, which parses to no
 *  attribution at all - the corridor view's own "this release does not publish
 *  it" case, and the right default for every test that is not about it. */
function serve(
  pois: string = poiCollection([]),
  spurs: string = '{}',
  elevation: string = '[]',
  trails: string = '{"type":"FeatureCollection"}',
  clubSections: string = '{}',
) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers(),
        arrayBuffer: () =>
          Promise.resolve(
            bytesOf(
              url.includes('poi_')
                ? pois
                : url.includes(SPURS_KEY)
                  ? spurs
                  : url.includes(CLUB_SECTIONS_KEY)
                    ? clubSections
                    : url.includes(ELEVATION_KEY)
                      ? elevation
                      : trails,
            ),
          ),
        blob: () => Promise.resolve(new Blob(['{"type":"FeatureCollection"}'])),
        text: () =>
          Promise.resolve(
            url.includes('poi_')
              ? pois
              : url.includes(SPURS_KEY)
                ? spurs
                : url.includes(CLUB_SECTIONS_KEY)
                  ? clubSections
                  : url.includes(ELEVATION_KEY)
                    ? elevation
                    : '{}',
          ),
      }),
    ),
  )
}

/** Serves everything but elevation_profile.json, which gets the given failure. */
function serveUntilElevationFails(status: number, statusText: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      Promise.resolve(
        url.includes(ELEVATION_KEY)
          ? { ok: false, status, statusText }
          : {
              ok: true,
              status: 200,
              headers: new Headers(),
              arrayBuffer: () => Promise.resolve(bytesOf(poiCollection([]))),
              blob: () => Promise.resolve(new Blob(['{"type":"FeatureCollection"}'])),
              text: () => Promise.resolve(poiCollection([])),
            },
      ),
    ),
  )
}

/** A response body as bytes, which is what every fetch here now yields: the
 *  artifacts are hashed before anything is stored (#197), so the doubles have
 *  to hand over bytes rather than only the decoded forms. */
function bytesOf(text: string): ArrayBuffer {
  return new TextEncoder().encode(text).buffer as ArrayBuffer
}

const TWO_SAMPLES = JSON.stringify([
  { distance_mi: 0, elevation_ft: 3782.2 },
  { distance_mi: 1, elevation_ft: 3000 },
])

/** Serves trail lines, then fails on the POI type named. */
function serveUntilPoiFails(failing: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      Promise.resolve(
        url.includes(`poi_${failing}`)
          ? { ok: false, status: 503, statusText: 'Service Unavailable' }
          : {
              ok: true,
              headers: new Headers(),
              arrayBuffer: () => Promise.resolve(bytesOf(poiCollection([]))),
              blob: () => Promise.resolve(new Blob(['{"type":"FeatureCollection"}'])),
              text: () => Promise.resolve(poiCollection([])),
            },
      ),
    ),
  )
}

describe('trail data', () => {
  it('stores the trail lines and every POI type', async () => {
    serve()
    await downloadTrailData()

    expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob)
    // Every POI type, plus the trail lines, plus the spur detail, plus the
    // maintaining clubs, plus the elevation profile.
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(POI_TYPES.length + 4)
  })

  it('records the merged-chain shape of the trails it stores, both directions', async () => {
    // The flag decides the map's tolerance for these exact bytes on every
    // later launch (lib/trailShape.ts, #161), so it is written from a sniff
    // of what was committed - and written back DOWN when a re-download
    // serves the pre-merge shape, e.g. a field-test server on an older
    // release.
    const merged = JSON.stringify({
      type: 'FeatureCollection',
      features: [{ type: 'Feature', properties: { id: 'centerline:chain:0' } }],
    })
    serve(undefined, undefined, undefined, merged)
    await downloadTrailData()
    expect(readTrailsMerged()).toBe(true)

    serve()
    await downloadTrailData()
    expect(readTrailsMerged()).toBe(false)
  })

  it('reads POIs into the shape the map and search both use', async () => {
    serve(
      poiCollection([
        {
          id: 'atc_shelters:abc',
          poi_type: 'shelter',
          name: 'Chairback Gap Lean-to',
          lat: 45.45,
          lon: -69.26,
          confidence: 'high',
        },
      ]),
    )
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0]).toEqual({
      id: 'atc_shelters:abc',
      type: 'shelter',
      name: 'Chairback Gap Lean-to',
      lat: 45.45,
      lon: -69.26,
      confidence: 'high',
    })
  })

  it('keeps which source listed a POI, so the app can say where it came from', async () => {
    serve(
      poiCollection([
        {
          id: 'opentrail_at:1234',
          poi_type: 'water',
          name: 'Piped spring',
          lat: 44.1,
          lon: -70.2,
          confidence: 'high',
          source: 'opentrail_at',
        },
      ]),
    )
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0].source).toBe('opentrail_at')
  })

  it('leaves the source off entirely when the artifact carries none', async () => {
    // Not stored as "unknown": the detail sheet decides whether to name a
    // source by whether there is one, and a placeholder would be printed as
    // though the pipeline had published it.
    serve(poiCollection([{ id: 'x', poi_type: 'water', name: 'Spring', lat: 1, lon: 2 }]))
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0]).not.toHaveProperty('source')
  })

  // Site grouping (#523/#524). Written against the SHAPE THE BUCKET ACTUALLY
  // HOLDS, checked after the 2026-08-13 publish rather than imagined: the three
  // keys are present on every feature, and `null` on the ones not in a site -
  // 32 of 316 privies, 29 of 280 shelters, 163 of 174 water points.
  it('reads the site a POI belongs to, so the map can draw one pin for it', async () => {
    serve(
      poiCollection([
        {
          id: 'atc_privies:abc',
          poi_type: 'privy',
          name: 'Mt. Algo Shelter Privy',
          lat: 41.7,
          lon: -73.5,
          confidence: 'high',
          site_id: 'site_0421',
          site_role: 'member',
          site_name: 'Mt. Algo Shelter',
        },
      ]),
    )
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0].siteId).toBe('site_0421')
    expect(pois[0].siteRole).toBe('member')
    expect(pois[0].siteName).toBe('Mt. Algo Shelter')
  })

  // The anchor's nearby parts (#614, #625). Published as JSON rather than as
  // the finished sentence it used to be, which is the whole of the fix: prose
  // composed in the pipeline cannot be in the units a hiker picks afterwards.
  it('reads the parts around an anchor, so the card can write them in the hiker’s units', async () => {
    serve(
      poiCollection([
        {
          id: 'atc_shelters:abc',
          poi_type: 'shelter',
          name: 'Mt. Algo Shelter',
          lat: 41.7,
          lon: -73.5,
          confidence: 'high',
          site_id: 'site_0421',
          site_role: 'anchor',
          site_name: 'Mt. Algo Shelter',
          nearby: [
            { phrase: 'a multi-seat moldering privy', distance_ft: 131.2 },
            { phrase: 'water', distance_ft: 295.3 },
          ],
        },
      ]),
    )
    await downloadTrailData()

    expect((store.get(POIS_KEY) as StoredPoi[])[0].nearby).toEqual([
      { phrase: 'a multi-seat moldering privy', distance_ft: 131.2 },
      { phrase: 'water', distance_ft: 295.3 },
    ])
  })

  it('accepts the parts as a JSON string, which is the shape the .fgb carries', async () => {
    // Same export, two wire types - the reason readPhotoList takes both, and
    // the same GDAL behaviour applied to a second column.
    serve(
      poiCollection([
        {
          id: 'atc_shelters:abc',
          poi_type: 'shelter',
          name: 'Shelter',
          lat: 1,
          lon: 2,
          nearby: '[{"phrase":"a pit privy","distance_ft":65.6}]',
        },
      ]),
    )
    await downloadTrailData()

    expect((store.get(POIS_KEY) as StoredPoi[])[0].nearby).toEqual([
      { phrase: 'a pit privy', distance_ft: 65.6 },
    ])
  })

  it('stores no parts at all rather than an empty list, and never throws over a bad one', async () => {
    // A published artifact one version ahead of this build must not make a
    // waypoint unopenable, and an entry needs both halves to be worth keeping:
    // a phrase with no distance is a part the card cannot place, and a distance
    // with no phrase is a number with nothing to attach it to.
    serve(
      poiCollection([
        {
          id: 'a',
          poi_type: 'shelter',
          name: 'A',
          lat: 1,
          lon: 2,
          nearby: 'not json at all',
        },
        {
          id: 'b',
          poi_type: 'shelter',
          name: 'B',
          lat: 1,
          lon: 2,
          nearby: [
            { phrase: 'a privy' },
            { distance_ft: 40 },
            { phrase: 'water', distance_ft: 'far' },
            { phrase: 'a campsite', distance_ft: 82 },
          ],
        },
        { id: 'c', poi_type: 'shelter', name: 'C', lat: 1, lon: 2, nearby: null },
      ]),
    )
    await downloadTrailData()

    const [malformed, partlyUsable, absent] = store.get(POIS_KEY) as StoredPoi[]
    expect(malformed).not.toHaveProperty('nearby')
    expect(partlyUsable.nearby).toEqual([{ phrase: 'a campsite', distance_ft: 82 }])
    expect(absent).not.toHaveProperty('nearby')
  })

  it('treats a null site_id as not in a site, which is how it is published', async () => {
    // THE REAL SHAPE, not a hypothetical. `attach_sites` writes the keys onto
    // every feature and leaves them null where nothing matched, so a client that
    // tested only "key absent" would carry `null` into `composeSites` and ask it
    // to group POIs by a site called null - one giant site containing every
    // ungrouped privy on the trail.
    serve(
      poiCollection([
        {
          id: 'opentrail_water:1188',
          poi_type: 'water',
          name: 'Spring below the ridge',
          lat: 35.6,
          lon: -83.4,
          confidence: 'low',
          site_id: null,
          site_role: null,
          site_name: null,
        },
      ]),
    )
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0]).not.toHaveProperty('siteId')
    expect(pois[0]).not.toHaveProperty('siteRole')
    expect(pois[0]).not.toHaveProperty('siteName')
  })

  it('keeps a shelter capacity, so the card can say how many it sleeps', async () => {
    serve(
      poiCollection([
        {
          id: 'atc_shelters:abc',
          poi_type: 'shelter',
          name: 'Chairback Gap Lean-to',
          lat: 45.45,
          lon: -69.26,
          confidence: 'high',
          capacity: 8,
        },
      ]),
    )
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0].capacity).toBe(8)
  })

  it.each([
    [
      'null, which is what the artifact writes for a shelter with no published number',
      null,
    ],
    ['zero, which is the absence of a capacity rather than a very small one', 0],
    ['a string, which no arithmetic here would survive', '8'],
    ['a fraction, which is not a count of people', 6.5],
  ])('leaves the capacity off when the artifact carries %s', async (_why, capacity) => {
    // The alternative is a card reading "Sleeps 0" at a shelter that sleeps
    // eight, which is worse than a card that says nothing.
    serve(
      poiCollection([
        {
          id: 'atc_shelters:abc',
          poi_type: 'shelter',
          name: 'Shelter',
          lat: 1,
          lon: 2,
          capacity,
        },
      ]),
    )
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0]).not.toHaveProperty('capacity')
  })

  it('keeps the water distance, so the chip can print the stated figure (#694)', async () => {
    // Both carriers in one download: the shelter whose card splices the
    // sentence, and the water member the pipeline synthesized onto its site -
    // which inherits the shelter's coordinates, making this number the only
    // honest distance a chip can show for it.
    serve(
      poiCollection([
        {
          id: 'atc_shelters:abc',
          poi_type: 'shelter',
          name: 'Chairback Gap Lean-to',
          lat: 45.45,
          lon: -69.26,
          confidence: 'high',
          water_distance_ft: 120,
        },
        {
          id: 'atc_csi:abc',
          poi_type: 'water',
          name: 'Water near Chairback Gap Lean-to',
          lat: 45.45,
          lon: -69.26,
          confidence: 'low',
          source: 'atc_csi',
          water_distance_ft: 120,
        },
      ]),
    )
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0].waterDistanceFt).toBe(120)
    expect(pois[1].waterDistanceFt).toBe(120)
  })

  it.each([
    ['null, which the artifact writes where the pipeline refused a number', null],
    ['zero, which the pipeline itself refuses to publish', 0],
    ['a string, which is not a distance', '120'],
  ])(
    'leaves the water distance off when the artifact carries %s',
    async (_why, water_distance_ft) => {
      serve(
        poiCollection([
          {
            id: 'atc_shelters:abc',
            poi_type: 'shelter',
            name: 'Shelter',
            lat: 1,
            lon: 2,
            water_distance_ft,
          },
        ]),
      )
      await downloadTrailData()

      const pois = store.get(POIS_KEY) as StoredPoi[]
      expect(pois[0]).not.toHaveProperty('waterDistanceFt')
    },
  )

  it('keeps the composed description, so the card can say what the place is', async () => {
    serve(
      poiCollection([
        {
          id: 'atc_shelters:abc',
          poi_type: 'shelter',
          name: 'Chairback Gap Lean-to',
          lat: 45.45,
          lon: -69.26,
          description: 'Log shelter, sleeps 6. Built 1954.',
        },
      ]),
    )
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0].description).toBe('Log shelter, sleeps 6. Built 1954.')
  })

  it('leaves the description off when the artifact carries none', async () => {
    // Water and resupply POIs never have one - opentrail.org has no inventory
    // to compose from - so its absence is the normal case, not a gap to fill.
    serve(poiCollection([{ id: 'x', poi_type: 'water', name: 'Spring', lat: 1, lon: 2 }]))
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0]).not.toHaveProperty('description')
  })

  it('carries a photo and its attribution facts, so the card can pay for showing it', async () => {
    // The photo_* properties are how export_poi.py publishes the Wikimedia
    // Commons match. The credit fields are not decoration: CC BY/BY-SA make
    // the attribution a condition of using the photo, so dropping them here
    // would put the card in breach the moment it rendered the image.
    serve(
      poiCollection([
        {
          id: 'atc_shelters:abc',
          poi_type: 'shelter',
          name: 'Chairback Gap Lean-to',
          lat: 45.45,
          lon: -69.26,
          confidence: 'high',
          photo_key: 'photos/abc123.jpg',
          photo_page_url: 'https://commons.wikimedia.org/wiki/File:Lean-to.jpg',
          photo_author: 'A. Hiker',
          photo_license: 'CC BY-SA 4.0',
          photo_taken: '2025-06-18',
        },
      ]),
    )
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    // Resolved through the build-time data base, not stored as published:
    // the artifact carries a bucket key so moving bucket or fronting it with
    // a CDN never invalidates data already published.
    expect(pois[0].photoUrl).toBe(dataUrl('photos/abc123.jpg'))
    expect(pois[0].photoUrl).not.toContain('upload.wikimedia.org')
    expect(pois[0].photoPage).toBe('https://commons.wikimedia.org/wiki/File:Lean-to.jpg')
    expect(pois[0].photoAuthor).toBe('A. Hiker')
    expect(pois[0].photoLicense).toBe('CC BY-SA 4.0')
    expect(pois[0].photoTaken).toBe('2025-06-18')
  })

  it('carries every photo when the artifact publishes a list, in published order', async () => {
    // ATC's layers give up to ten photos per POI and 89% of them use more
    // than one (#471). The card shows the first and steps through the rest,
    // so the whole list has to survive the round trip into IndexedDB.
    serve(
      poiCollection([
        {
          id: 'atc_shelters:abc',
          poi_type: 'shelter',
          name: 'Chairback Gap Lean-to',
          lat: 45.45,
          lon: -69.26,
          photo_key: 'photos/one.jpg',
          photo_taken: '2016-09-12',
          photos: [
            {
              key: 'photos/one.jpg',
              author: 'ATC',
              license: '© ATC',
              taken: '2016-09-12',
            },
            {
              key: 'photos/two.jpg',
              author: 'ATC',
              license: '© ATC',
              taken: '2016-09-13',
            },
          ],
        },
      ]),
    )
    await downloadTrailData()

    const photos = (store.get(POIS_KEY) as StoredPoi[])[0].photos
    expect(photos?.map((p) => p.url)).toEqual([
      dataUrl('photos/one.jpg'),
      dataUrl('photos/two.jpg'),
    ])
    // Per photo, not per card: the licence obliges attribution for whichever
    // one is on screen, so each carries its own.
    expect(photos?.[1].taken).toBe('2016-09-13')
    expect(photos?.[1].author).toBe('ATC')
  })

  it('accepts the photo list as a JSON string, which is the shape the .fgb carries', async () => {
    // Same export, two wire types: GDAL emits the pipeline's JSON string as
    // real JSON in GeoJSON and leaves it a string in FlatGeobuf (measured
    // 2026-08-09). Reading only one shape would return nothing for every POI
    // in the other.
    serve(
      poiCollection([
        {
          id: 'atc_shelters:abc',
          poi_type: 'shelter',
          name: 'Shelter',
          lat: 1,
          lon: 2,
          photo_key: 'photos/one.jpg',
          photos: '[{"key":"photos/one.jpg"},{"key":"photos/two.jpg"}]',
        },
      ]),
    )
    await downloadTrailData()

    expect((store.get(POIS_KEY) as StoredPoi[])[0].photos).toHaveLength(2)
  })

  it('stores no photo list for a single photo, so no controls appear with nowhere to go', async () => {
    serve(
      poiCollection([
        {
          id: 'atc_shelters:abc',
          poi_type: 'shelter',
          name: 'Shelter',
          lat: 1,
          lon: 2,
          photo_key: 'photos/one.jpg',
          photos: [{ key: 'photos/one.jpg' }],
        },
      ]),
    )
    await downloadTrailData()

    const poi = (store.get(POIS_KEY) as StoredPoi[])[0]
    expect(poi.photoUrl).toBe(dataUrl('photos/one.jpg'))
    expect(poi).not.toHaveProperty('photos')
  })

  it('drops a malformed photo list rather than making the waypoint unopenable', async () => {
    // A published artifact one version ahead of this build must degrade to
    // "no gallery", never to a parse error that loses the whole download.
    serve(
      poiCollection([
        {
          id: 'a',
          poi_type: 'shelter',
          name: 'A',
          lat: 1,
          lon: 2,
          photo_key: 'photos/one.jpg',
          photos: 'not json at all',
        },
        {
          id: 'b',
          poi_type: 'shelter',
          name: 'B',
          lat: 3,
          lon: 4,
          photo_key: 'photos/two.jpg',
          photos: [{ nokey: true }, { key: 'photos/three.jpg' }],
        },
      ]),
    )
    await downloadTrailData()

    // Every poi_type artifact is served the same body by this harness, so
    // pick the two by id rather than counting rows.
    const pois = store.get(POIS_KEY) as StoredPoi[]
    const malformed = pois.find((p) => p.id === 'a')
    const partlyUsable = pois.find((p) => p.id === 'b')
    expect(malformed).not.toHaveProperty('photos')
    // The entry with no key is dropped; one usable photo left is not a
    // gallery, so no list is stored.
    expect(partlyUsable).not.toHaveProperty('photos')
    expect(partlyUsable?.photoUrl).toBe(dataUrl('photos/two.jpg'))
  })

  it('leaves photo fields off entirely when the artifact carries none', async () => {
    // The artifact writes null for every photo property of a photo-less POI
    // (the export's columns exist either way). Null is not a photo, and a
    // stored null would read as one to anything checking for the key.
    serve(
      poiCollection([
        { id: 'x', poi_type: 'water', name: 'Spring', lat: 1, lon: 2, photo_key: null },
      ]),
    )
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0]).not.toHaveProperty('photoUrl')
    expect(pois[0]).not.toHaveProperty('photoAuthor')
  })

  it('drops credit fields that arrive without a photo to credit', async () => {
    // An author with no photo is a credit for nothing - it would render as
    // attribution for the placeholder glyph. The photo URL is the gate for
    // the whole group.
    serve(
      poiCollection([
        {
          id: 'x',
          poi_type: 'water',
          name: 'Spring',
          lat: 1,
          lon: 2,
          photo_author: 'A. Hiker',
          photo_license: 'CC BY-SA 4.0',
        },
      ]),
    )
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0]).not.toHaveProperty('photoUrl')
    expect(pois[0]).not.toHaveProperty('photoAuthor')
    expect(pois[0]).not.toHaveProperty('photoLicense')
  })

  it('drops a POI with no coordinates rather than carrying a broken row', async () => {
    // It cannot be drawn, found by search, or reported against - so it is not
    // a POI, it is a row that would fail somewhere further downstream.
    serve(poiCollection([{ id: 'x', poi_type: 'water', name: 'Nowhere' }]))
    await downloadTrailData()

    expect(store.get(POIS_KEY)).toEqual([])
  })

  it('treats a missing confidence as unverified rather than vouching for it', async () => {
    // The legend renders low confidence as "Unverified". Defaulting the other
    // way would have the app vouching for a water source nobody checked.
    serve(poiCollection([{ id: 'x', poi_type: 'water', name: 'Spring', lat: 1, lon: 2 }]))
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0].confidence).toBe('low')
  })

  it('reports which file failed instead of failing anonymously', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: false, status: 404, statusText: 'Not Found' })),
    )

    await expect(downloadTrailData()).rejects.toThrow(/trails\.geojson.*404/)
  })

  it('names the file and the host when the request never completes at all', async () => {
    // A refused origin, a bucket that is not public and a dead zone all reject
    // with the same bare browser TypeError - "NetworkError when attempting to
    // fetch resource." on Firefox - which named neither the artifact nor where
    // it was asked. That sentence went to the hiker and into a bug report
    // verbatim, and it is the whole reason a CORS policy that did not name the
    // app's origin read as a missing centerline.
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.reject(new TypeError('NetworkError when attempting to fetch resource.')),
      ),
    )

    await expect(downloadTrailData()).rejects.toThrow(
      /trails\.geojson.*did not complete.*NetworkError when attempting to fetch resource/,
    )
  })

  it('keeps the browser’s own words, which are what separate refused from offline', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )

    await expect(downloadTrailData()).rejects.toThrow(/Failed to fetch/)
  })

  it('lets a cancellation stay a cancellation rather than dressing it as a failure', async () => {
    // publishedHash() re-throws an abort by name for this reason, and the
    // wrapper has to agree: the hiker stopping a download is not the bucket
    // refusing one, and only one of the two is worth a notice.
    const abort = new Error('The operation was aborted.')
    abort.name = 'AbortError'
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(abort)),
    )

    await expect(downloadTrailData()).rejects.toThrow(abort)
  })

  it('says there is nothing downloaded rather than returning an empty map', async () => {
    expect(await loadTrailData()).toBeNull()
  })

  it('hands back the centerline on its own, without reading anything beside it', async () => {
    // What first run reads and all it reads (#857, lib/useTrailData.ts). The
    // saving is not the trail line - that is a Blob handle either way - it is
    // the 2,837 POI objects and the 141,000-sample profile that the full read
    // deserialises whether or not the caller wanted them.
    serve()
    await downloadTrailData()
    const reads: string[] = []
    vi.mocked(get).mockImplementation((key) => {
      reads.push(String(key))
      return Promise.resolve(store.get(String(key)))
    })

    const lines = await loadTrailLines()

    expect(lines).toBeInstanceOf(Blob)
    expect(reads).toEqual([TRAILS_BLOB_KEY])
  })

  it('says nothing is downloaded when the centerline is not there either', async () => {
    expect(await loadTrailLines()).toBeNull()
    expect(await haveTrailData()).toBe(false)
  })

  it('answers "is a release here" the same way the full read does', async () => {
    // The two must not drift: `haveTrailData` exists only to answer
    // `loadTrailData() !== null` without paying for the read, and a commit
    // writes all four keys or none, so the trails blob IS the question.
    expect(await haveTrailData()).toBe(false)

    serve()
    await downloadTrailData()

    expect(await haveTrailData()).toBe(true)
    expect(await loadTrailData()).not.toBeNull()
  })

  it('reclaims both the trail lines and the POIs on delete', async () => {
    serve()
    await downloadTrailData()
    writeTrailsMerged(true)
    await deleteTrailData()

    expect(await loadTrailData()).toBeNull()
    expect(store.has(POIS_KEY)).toBe(false)
    // No data, no claim about its shape (#161).
    expect(readTrailsMerged()).toBe(false)
  })

  it('keeps the trail lines a failed first download did fetch, and says the release is not here', async () => {
    // This USED to assert that nothing at all was stored, and the reasoning
    // was right about the danger and has been answered rather than dropped
    // (#863). The danger: trail lines committed the moment they arrive, with
    // signal dropping during the POI fetches - the ordinary way this fails -
    // leave a store holding lines and no waypoints, and that state was
    // INVISIBLE on the next launch. The map drew its trail, search and the
    // legend were just empty, and the error was long gone from React state.
    //
    // It is visible now: the marker makes `haveTrailData` answer false, so the
    // next launch downloads the release again instead of reading the phone as
    // done. What that buys is the twelve seconds a first run spent looking at
    // a card over an empty background.
    serveUntilPoiFails('campsite')

    await expect(downloadTrailData()).rejects.toThrow(/poi_campsite/)

    expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob)
    expect(store.has(POIS_KEY)).toBe(false)
    expect(await haveTrailData()).toBe(false)
  })

  it('draws the centerline before the waypoints are even asked for', async () => {
    // The whole point of #863, asserted at the moment it matters rather than
    // afterwards: the callback fires while the POI fetches are still to come,
    // which is what lets the map behind the first-run steps have a trail on it
    // seven seconds earlier.
    const linesAt: Array<string | undefined> = []
    serveUntilPoiFails('campsite')

    await expect(
      downloadTrailData({
        onCenterline: () => {
          linesAt.push(
            store.get(TRAILS_BLOB_KEY) instanceof Blob ? 'lines stored' : undefined,
          )
        },
      }),
    ).rejects.toThrow(/poi_campsite/)

    // Fired once, with the lines readable and the waypoints not yet fetched.
    expect(linesAt).toEqual(['lines stored'])
    expect(store.has(POIS_KEY)).toBe(false)
  })

  it('says the release is here once the rest of it lands', async () => {
    serve()

    await downloadTrailData()

    expect(await haveTrailData()).toBe(true)
    expect(store.has(TRAIL_DATA_PARTIAL_KEY)).toBe(false)
  })

  it('reports the lines once, at the commit, when a release is already here', async () => {
    // The other path. A phone with a release keeps it whole until the new one
    // has entirely arrived, so there is nothing to report early - and the
    // callback must not fire twice either, because each firing re-points a
    // GeoJSON source at twelve megabytes.
    serve()
    await downloadTrailData()
    let reported = 0

    await downloadTrailData({ onCenterline: () => (reported += 1) })

    expect(reported).toBe(1)
  })

  it('leaves a working download alone when a re-download fails partway', async () => {
    // Worse than an empty store: someone who already had the whole set and
    // re-downloaded got the new trail lines written over the old ones while
    // their POIs stayed at the previous version - two halves of different
    // downloads, with nothing saying so.
    serve(
      poiCollection([{ id: 'a', poi_type: 'water', name: 'Spring', lat: 39, lon: -77 }]),
    )
    await downloadTrailData()
    const originalTrails = store.get(TRAILS_BLOB_KEY)
    const originalPois = store.get(POIS_KEY)

    serveUntilPoiFails('resupply')
    await expect(downloadTrailData()).rejects.toThrow(/poi_resupply/)

    expect(store.get(TRAILS_BLOB_KEY)).toBe(originalTrails)
    expect(store.get(POIS_KEY)).toBe(originalPois)
  })

  // Everything below is one POI row being wrong in a file where the other rows
  // are fine. Dropping the whole download over one bad shelter would cost a
  // hiker every other shelter in the file.
  it('drops a POI with no usable coordinates rather than carrying a broken row', async () => {
    // Nothing can be done with it: it cannot be drawn, found by search, or
    // reported against.
    serve(
      poiCollection([
        { id: 'a', name: 'No position', lat: 'not a number', lon: -77 },
        { id: 'b', name: 'Fine', lat: 39, lon: -77 },
        { id: 'c', name: 'Missing lon', lat: 39 },
      ]),
    )
    await downloadTrailData()

    // serve() hands the same file to every POI type, so the one good row
    // arrives once per type - what matters is that only it survived.
    const pois = (await loadTrailData())?.pois ?? []
    expect([...new Set(pois.map((p) => p.id))]).toEqual(['b'])
    expect(pois).toHaveLength(POI_TYPES.length)
  })

  it('falls back to the file it came from when a row does not name its own type', async () => {
    serve(poiCollection([{ id: 'a', name: 'Unnamed type', lat: 39, lon: -77 }]))
    await downloadTrailData()

    const pois = (await loadTrailData())?.pois ?? []
    expect(pois[0].type).toBe(POI_TYPES[0])
  })

  it('ignores a poi_type that is not a string', async () => {
    serve(poiCollection([{ id: 'a', poi_type: 42, name: 'Odd', lat: 39, lon: -77 }]))
    await downloadTrailData()

    const pois = (await loadTrailData())?.pois ?? []
    expect(pois[0].type).toBe(POI_TYPES[0])
  })

  it('shows a nameless POI as Unnamed rather than as blank or undefined', async () => {
    serve(poiCollection([{ id: 'a', lat: 39, lon: -77 }]))
    await downloadTrailData()

    const pois = (await loadTrailData())?.pois ?? []
    expect(pois[0].name).toBe('Unnamed')
  })

  it('builds an id from the position when the row carries none', async () => {
    // Two POIs sharing a synthetic id would collapse into one in search, so it
    // is derived from something that differs per row.
    serve(poiCollection([{ name: 'Anonymous spring', lat: 39, lon: -77 }]))
    await downloadTrailData()

    const pois = (await loadTrailData())?.pois ?? []
    expect(pois[0].id).toBe(`${POI_TYPES[0]}:39,-77`)
  })

  it('treats a file with no features array at all as simply empty', async () => {
    serve(JSON.stringify({ type: 'FeatureCollection' }))
    await downloadTrailData()

    expect((await loadTrailData())?.pois).toEqual([])
  })

  it('returns no POIs, rather than throwing, when the trail lines are there but the POIs are not', async () => {
    serve()
    await downloadTrailData()
    store.delete(POIS_KEY)

    expect((await loadTrailData())?.pois).toEqual([])
  })

  it('skips a feature carrying no properties at all', async () => {
    // GeoJSON allows `properties: null`, and a feature with nothing on it has
    // no coordinates either - so it drops out rather than throwing on the way
    // to reading them.
    serve(
      JSON.stringify({
        type: 'FeatureCollection',
        features: [
          { type: 'Feature', geometry: null },
          { type: 'Feature', properties: null, geometry: null },
          { type: 'Feature', properties: { id: 'ok', name: 'Real', lat: 39, lon: -77 } },
        ],
      }),
    )
    await downloadTrailData()

    const pois = (await loadTrailData())?.pois ?? []
    expect([...new Set(pois.map((p) => p.id))]).toEqual(['ok'])
  })
})

describe('spur detail', () => {
  it('stores what each spur leads to, keyed by trail id', async () => {
    serve(
      poiCollection([]),
      JSON.stringify({ 'side_trails:abc': { destination_poi_id: 'shelter:x' } }),
    )

    await downloadTrailData()

    expect(store.get(SPURS_STORE_KEY)).toEqual({
      'side_trails:abc': { destination_poi_id: 'shelter:x' },
    })
  })

  it('treats a release with no spurs.json as no spur detail, not a failure', async () => {
    // spurs.json did not exist before export_spurs.py. A phone pointed at an
    // older release must still get its trails and POIs - the map draws every
    // spur either way, it just cannot say where one goes.
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve(
          url.includes(SPURS_KEY)
            ? { ok: false, status: 404, statusText: 'Not Found' }
            : {
                ok: true,
                status: 200,
                headers: new Headers(),
                arrayBuffer: () => Promise.resolve(bytesOf(poiCollection([]))),
                blob: () => Promise.resolve(new Blob(['{"type":"FeatureCollection"}'])),
                text: () => Promise.resolve(poiCollection([])),
              },
        ),
      ),
    )

    await downloadTrailData()

    expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob)
    expect(store.get(SPURS_STORE_KEY)).toEqual({})
  })

  it('still fails on a broken spurs fetch that is not a 404', async () => {
    // Only "this release predates the feature" is excused. A 503 is a failed
    // download and must not be swallowed along with it.
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve(
          url.includes(SPURS_KEY)
            ? { ok: false, status: 503, statusText: 'Service Unavailable' }
            : {
                ok: true,
                status: 200,
                headers: new Headers(),
                arrayBuffer: () => Promise.resolve(bytesOf(poiCollection([]))),
                blob: () => Promise.resolve(new Blob(['{"type":"FeatureCollection"}'])),
                text: () => Promise.resolve(poiCollection([])),
              },
        ),
      ),
    )

    await expect(downloadTrailData()).rejects.toThrow(/503/)
    // The release is not here, the same rule the POI failure follows (#863).
    expect(await haveTrailData()).toBe(false)
  })

  it('loads spur detail back with the rest of the trail data', async () => {
    serve(poiCollection([]), JSON.stringify({ 'side_trails:abc': { length_ft: 385 } }))
    await downloadTrailData()

    const loaded = await loadTrailData()

    expect(loaded?.spurs['side_trails:abc']).toEqual({ length_ft: 385 })
  })

  it('reads a release whose spur detail was never stored as an empty map', async () => {
    // Data downloaded by a build before this feature: the blob and POIs are in
    // IndexedDB, the spur key is not. That must load, not throw.
    store.set(TRAILS_BLOB_KEY, new Blob(['{}']))
    store.set(POIS_KEY, [])

    const loaded = await loadTrailData()

    expect(loaded?.spurs).toEqual({})
  })

  it('forgets spur detail when the download is deleted', async () => {
    serve(poiCollection([]), JSON.stringify({ 'side_trails:abc': {} }))
    await downloadTrailData()

    await deleteTrailData()

    expect(store.has(SPURS_STORE_KEY)).toBe(false)
  })
})

describe('the elevation profile', () => {
  it('stores the published samples', async () => {
    serve(poiCollection([]), '{}', TWO_SAMPLES)

    await downloadTrailData()

    const profile = store.get(ELEVATION_STORE_KEY) as ElevationProfile
    expect(Array.from(profile.distanceMi)).toEqual([0, 1])
    expect(profile.elevationFt[0]).toBeCloseTo(3782.2, 3)
  })

  it('treats a release with no elevation_profile.json as no profile, not a failure', async () => {
    // It did not exist before export_elevation.py. A phone pointed at an older
    // release must still get its trails and POIs; it just has no ribbon.
    serveUntilElevationFails(404, 'Not Found')

    await downloadTrailData()

    expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob)
    expect(store.get(ELEVATION_STORE_KEY)).toBeNull()
  })

  it('still fails on a broken elevation fetch that is not a 404', async () => {
    // Only "this release predates the feature" is excused. A 503 is a failed
    // download and must not be swallowed along with it.
    serveUntilElevationFails(503, 'Service Unavailable')

    await expect(downloadTrailData()).rejects.toThrow(/503/)
    // The release is not here, the same rule the POI failure follows - the
    // trail lines a first download managed to fetch stay, marked (#863).
    expect(await haveTrailData()).toBe(false)
    expect(store.has(POIS_KEY)).toBe(false)
  })

  it('costs the ribbon and not the map when the profile arrives malformed', async () => {
    // A truncated download of the largest vector artifact. The ribbon is a
    // decoration on a screen whose job is showing a hiker where they are, so it
    // gives itself up rather than taking the trail lines down with it.
    serve(poiCollection([]), '{}', '[{"distance_mi":0,')

    await downloadTrailData()

    expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob)
    expect(store.get(ELEVATION_STORE_KEY)).toBeNull()
  })

  it('loads the profile back with the rest of the trail data', async () => {
    serve(poiCollection([]), '{}', TWO_SAMPLES)
    await downloadTrailData()

    const loaded = await loadTrailData()

    expect(loaded?.elevation?.distanceMi.length).toBe(2)
  })

  it('reads a release whose profile was never stored as no profile', async () => {
    // Data downloaded by a build before this feature: the blob and POIs are in
    // IndexedDB, the elevation key is not. That must load, not throw.
    store.set(TRAILS_BLOB_KEY, new Blob(['{}']))
    store.set(POIS_KEY, [])

    const loaded = await loadTrailData()

    expect(loaded?.elevation).toBeNull()
  })

  it('forgets the profile when the download is deleted', async () => {
    serve(poiCollection([]), '{}', TWO_SAMPLES)
    await downloadTrailData()

    await deleteTrailData()

    expect(store.has(ELEVATION_STORE_KEY)).toBe(false)
  })
})

describe('holding the trail data to its published hash (#197)', () => {
  // These files are small and are never resumed, so the splice the archive
  // check exists for cannot happen to them. They are still worth checking:
  // trails.geojson IS the trail line, a corrupted POI file is a water source
  // in the wrong place, and a JSON file damaged rather than truncated parses
  // perfectly well - so the parse is not the check it looks like.

  it('stores the trail data when every artifact matches what was published', async () => {
    serve(poiCollection([]))
    publishing((key) =>
      key === TRAILS_KEY
        ? sha256Hex(new TextEncoder().encode('{"type":"FeatureCollection"}'))
        : null,
    )

    await downloadTrailData()

    expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob)
  })

  it('keeps none of it when the trail lines are not what was published', async () => {
    // Nothing is committed until everything has arrived, so a mismatch
    // anywhere leaves the phone exactly as it was - including the trail data
    // it was already using.
    store.set(TRAILS_BLOB_KEY, new Blob(['the lines that already work']))
    serve(poiCollection([]))
    publishing((key) =>
      key === TRAILS_KEY
        ? sha256Hex(new TextEncoder().encode('a different build'))
        : null,
    )

    await expect(downloadTrailData()).rejects.toThrow(TrailDataHashMismatchError)

    expect(await (store.get(TRAILS_BLOB_KEY) as Blob).text()).toBe(
      'the lines that already work',
    )
    expect(store.get(POIS_KEY)).toBeUndefined()
  })

  it('names the artifact that did not match', async () => {
    // Which file it was is the difference between a useful field report and
    // "the download failed".
    serve(poiCollection([]))
    publishing((key) =>
      key === 'poi_water.geojson'
        ? sha256Hex(new TextEncoder().encode('not what arrived'))
        : null,
    )

    const thrown = await downloadTrailData().catch((error: unknown) => error)

    expect(thrown).toBeInstanceOf(TrailDataHashMismatchError)
    expect((thrown as TrailDataHashMismatchError).artifactKey).toBe('poi_water.geojson')
  })

  it('checks the optional artifacts too, where a release publishes them', async () => {
    serve(poiCollection([]), '{"at-1":{"destination":"Somewhere"}}')
    publishing((key) =>
      key === SPURS_KEY
        ? sha256Hex(new TextEncoder().encode('an older spurs.json'))
        : null,
    )

    await expect(downloadTrailData()).rejects.toThrow(TrailDataHashMismatchError)
  })

  it('reads latest.json once for the whole attempt, not once per artifact', async () => {
    // #717. readChecked() used to call publishedHash() itself, so a launch
    // fetch of eleven artifacts pulled the manifest eleven times - measured on
    // a real first run as eleven round trips strung between the downloads.
    // One snapshot is also the more correct thing to check an attempt against:
    // every artifact is held to ONE published version rather than to whatever
    // the bucket was serving at the moment each file happened to finish.
    serve(poiCollection([]))

    await downloadTrailData()

    expect(mockedPublishedHashes).toHaveBeenCalledTimes(1)
  })

  it('stores what arrived when nothing published a hash for it', async () => {
    // Absence of a check is not a failed check - the same downgrade the
    // archive download makes, for the same reason.
    serve(poiCollection([]))
    publishing(() => null)

    await downloadTrailData()

    expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob)
  })
})

describe('the published mile (#753)', () => {
  const shelter = (extra: Record<string, unknown>) => ({
    id: 'atc_shelters:abc',
    poi_type: 'shelter',
    name: 'Chairback Gap Lean-to',
    lat: 45.45,
    lon: -69.26,
    confidence: 'high',
    ...extra,
  })

  it('rides the parse when the artifact carries one', async () => {
    serve(poiCollection([shelter({ mile: 1407.2 })]))
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0].mile).toBe(1407.2)
  })

  it('is absent - never guessed - when the release predates the field', async () => {
    serve(poiCollection([shelter({})]))
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0]).not.toHaveProperty('mile')
  })

  it('is absent when the artifact published null', async () => {
    serve(poiCollection([shelter({ mile: null })]))
    await downloadTrailData()

    const pois = store.get(POIS_KEY) as StoredPoi[]
    expect(pois[0]).not.toHaveProperty('mile')
  })
})

/**
 * The corridor view's own artifact (#598), through the same download and store
 * path every other artifact takes.
 *
 * Worth its own block because the failure mode is silent: club_sections.json
 * has been published since #594 and read by nothing, so a wiring mistake here
 * looks exactly like a release that does not publish it - an empty corridor
 * view and no error anywhere.
 */
describe('the maintaining clubs', () => {
  const ARTIFACT = JSON.stringify({
    sources: { attribution: 'centerline', names: 'trail_club_sections' },
    clubs: [
      {
        acronym: 'GATC',
        name: 'Georgia Appalachian Trail Club',
        region: 'SORO',
        stretches: [{ start_mile: 0, end_mile: 77 }],
        miles: 77,
      },
    ],
    unattributed: [{ start_mile: 77, end_mile: 78.5 }],
  })

  /** Serves everything, but 404s club_sections.json - a release built before
   *  pipeline/export_club_sections.py existed. */
  function serveWithoutClubSections() {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve(
          url.includes(CLUB_SECTIONS_KEY)
            ? { ok: false, status: 404, statusText: 'Not Found' }
            : {
                ok: true,
                status: 200,
                headers: new Headers(),
                arrayBuffer: () => Promise.resolve(bytesOf(poiCollection([]))),
                blob: () => Promise.resolve(new Blob(['{"type":"FeatureCollection"}'])),
                text: () => Promise.resolve(poiCollection([])),
              },
        ),
      ),
    )
  }

  it('survives the round trip from the bucket to a later launch', async () => {
    serve(undefined, undefined, undefined, undefined, ARTIFACT)
    await downloadTrailData()

    const loaded = await loadTrailData()
    expect(loaded?.clubSections.clubs).toEqual([
      {
        acronym: 'GATC',
        name: 'Georgia Appalachian Trail Club',
        region: 'SORO',
        runs: [{ startMile: 0, endMile: 77 }],
        miles: 77,
      },
    ])
    expect(loaded?.clubSections.unattributed).toEqual([{ startMile: 77, endMile: 78.5 }])
    expect(loaded?.clubSections.sources.attribution).toBe('centerline')
  })

  it('costs a release built before the exporter nothing but its attribution', async () => {
    // A 404 here is not a failed download. The trail lines and every waypoint
    // still have to land - the corridor view simply has no subject below the
    // seam, which is the screen this app already shipped with.
    serveWithoutClubSections()
    await downloadTrailData()

    const loaded = await loadTrailData()
    expect(loaded?.trails).toBeInstanceOf(Blob)
    expect(loaded?.clubSections.clubs).toEqual([])
    expect(loaded?.clubSections.unattributed).toEqual([])
  })

  it('takes the attribution back down when a re-download no longer serves it', async () => {
    // The same direction trailShape's merged flag is written in: pointing a
    // phone at an older release has to REMOVE what the newer one put there,
    // or the map keeps drawing thirty clubs the current release cannot back.
    serve(undefined, undefined, undefined, undefined, ARTIFACT)
    await downloadTrailData()
    expect((await loadTrailData())?.clubSections.clubs).toHaveLength(1)

    serveWithoutClubSections()
    await downloadTrailData()
    expect((await loadTrailData())?.clubSections.clubs).toEqual([])
  })

  it('is dropped with the rest of the trail data', async () => {
    serve(undefined, undefined, undefined, undefined, ARTIFACT)
    await downloadTrailData()
    expect(store.has(CLUB_SECTIONS_STORE_KEY)).toBe(true)

    await deleteTrailData()
    expect(store.has(CLUB_SECTIONS_STORE_KEY)).toBe(false)
  })
})
