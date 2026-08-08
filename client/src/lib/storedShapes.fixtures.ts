// What a phone has in IndexedDB, frozen as literals (#374, surface 1).
//
// RELEASING.md §8c: "An update that cannot read the previous release's
// IndexedDB orphans a downloaded archive or drops queued reports… forcing a
// 1.18 GB re-download onto somebody at a resupply stop with one bar is a
// safety failure, not an inconvenience." Nothing watched that surface at all.
// This file is what it is watched against.
//
// **These are deliberately not typed as the app's current interfaces, and
// that is the entire design.** `const item: OutboxItem = {…}` would turn a
// shape change into a compile error whose obvious fix is to edit the fixture
// - which is to say, into a prompt to erase the evidence. Bytes on a phone
// do not update when an interface does. So these are `unknown`, and
// storedShapes.compat.test.ts asserts on what the real readers RETURN when
// handed them.
//
// **Do not edit an existing entry to make a test pass.** A failure here means
// this build cannot read what a shipped build wrote, which is the finding,
// not the obstacle. The fix goes in the reader - a fallback, a migration, a
// widened type. Adding a NEW entry for a new key is the one edit that is
// always right.
//
// N = 1, and honestly so: `git tag -l` is empty and releases/ holds only a
// README, so there is no shipped release to capture. This records the shape
// as of the baseline below, which is what the release process attaches to
// going forward. Each release adds a map; none of them replaces this one.
//
// **Entries here are kept indefinitely, and that is deliberately NOT the
// backend's rule.** RELEASING.md §8c bounds API support at three releases
// plus ninety days from supersession, because holding the schema still has a
// running cost. This surface has almost none: the penalty for failing to read
// an old stored shape is a 1.18 GB re-download at a resupply stop, and the
// price of preventing it is a fallback in the reader and a fixture that is
// already written. Nothing here ages out. If an entry is ever removed, it is
// because the app deliberately stopped supporting an upgrade path, and that
// is a decision with a release note attached rather than a tidy-up.

/** What the entries below describe. Not a git tag - none exists yet. */
export const BASELINE_LABEL = 'pre-1.0 baseline, recorded 2026-08-08'

/** Deep-freezes so a test cannot mutate the record it is checking against and
 *  leave the next test reading its edit. Blobs and typed arrays are left
 *  alone - freezing them is meaningless and `Object.freeze` on a Blob would
 *  not stop a read anyway. */
function deepFreeze<T>(value: T): T {
  if (value === null || typeof value !== 'object') return value
  if (value instanceof Blob || ArrayBuffer.isView(value)) return value
  for (const key of Object.getOwnPropertyNames(value)) {
    deepFreeze((value as Record<string, unknown>)[key])
  }
  return Object.freeze(value)
}

/** The photo bytes an outbox item carries. A real `Blob`, because that is
 *  what `idb-keyval` stores and what the flush path hands to `api.ts` - a
 *  base64 string here would test a shape the app never wrote. */
const STORED_PHOTO = new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xe0])], {
  type: 'image/jpeg',
})

/**
 * Keyed exactly as IndexedDB holds it. The keys are string literals rather
 * than the app's exported constants for the same reason the values are not
 * typed: renaming `OUTBOX_KEY`'s value must fail this test, and it cannot if
 * the fixture renames itself in step.
 */
export const STORED_SHAPES: Readonly<Record<string, unknown>> = deepFreeze({
  // Two queued reports and a marked one. The first carries a photo; the
  // second is the minimal shape (no photo, no failure, no optional payload
  // fields); the third is `failure`-marked, which the More screen reads.
  'ourhike:outbox': [
    {
      id: '5f8e1b3a-0c4d-4a2e-9f1b-2c3d4e5f6a7b',
      authoredAt: '2026-08-01T14:32:00.000Z',
      payload: {
        type: 'blowdown',
        reporter_type: 'thru',
        note: 'Large tree across the trail just north of the gap.',
        lat: 35.6012,
        lon: -83.4821,
        mile: 1407.2,
      },
      photo: STORED_PHOTO,
    },
    {
      id: '7a1c2d3e-4f50-4617-8829-9a0b1c2d3e4f',
      authoredAt: '2026-08-02T09:05:00.000Z',
      payload: {
        type: 'thanks',
        reporter_type: 'day',
      },
    },
    {
      id: '9b2d3e4f-5061-4728-993a-ab1c2d3e4f50',
      authoredAt: '2026-07-29T18:44:00.000Z',
      payload: {
        type: 'trash',
        reporter_type: 'section',
        poi_id: 'atc_shelter_0421',
      },
      // No `build`, deliberately. That field arrived with #412, so this is
      // the shape a phone that upgraded into it is holding - and `flushOutbox`
      // reads its absence as "not this build", which buys the report one
      // retry rather than stranding it on a verdict an older build reached.
      failure: {
        reason: 'That report was refused and will not be retried.',
        at: '2026-07-30T08:00:00.000Z',
      },
    },
    {
      id: 'c3e4f506-1728-493a-ab1c-2d3e4f5061a7',
      authoredAt: '2026-07-28T11:12:00.000Z',
      payload: {
        type: 'flooding',
        reporter_type: 'thru',
        note: 'Creek over the trail at the ford.',
      },
      // The same record as written by a build that does stamp itself.
      failure: {
        reason: 'That report was refused and will not be retried.',
        at: '2026-07-29T08:00:00.000Z',
        build: '4c1f9a2b7e6d5c4b3a29180f7e6d5c4b3a291807',
      },
    },
  ],

  // A full preferences object, plus one key this build does not know.
  // `background_source: 'usgs_topo_live'` is not invented for the test: it
  // shipped, was removed, and preferences.ts carries a section on why a value
  // like it must be treated as absent rather than trusted through to
  // buildMapStyle, where it draws no background at all.
  'ourhike:preferences': {
    theme: 'auto',
    map_style: 'quiet_pine',
    background_source: 'usgs_topo_live',
    hiking_detail_level: 'standard',
    units: 'imperial',
  },

  'ourhike:hike': { startMile: 0, endMile: 2189.1 },

  // sessionStorage rather than IndexedDB, and included anyway - the surface
  // is "stored client data", and a camera that fails to parse reopens the map
  // somewhere the hiker was not.
  'ourhike:camera': { center: [-83.4821, 35.6012], zoom: 12.5 },

  // Two POIs: one current, one WITHOUT `source`. The second is the documented
  // real case - trailData.ts says a phone that downloaded before the client
  // read that field "has POIs in IndexedDB without one", and undefined there
  // means "this copy predates the field", not "the pipeline published none".
  'ourhike:pois': [
    {
      id: 'atc_shelter_0421',
      type: 'shelter',
      name: 'Tricorner Knob Shelter',
      lat: 35.7031,
      lon: -83.2094,
      confidence: 'high',
      source: 'atc_shelters',
    },
    {
      id: 'opentrail_water_1188',
      type: 'water',
      name: 'Spring below the ridge',
      lat: 35.6104,
      lon: -83.4402,
      confidence: 'low',
    },
  ],

  'ourhike:spurs': {
    spur_0007: {
      name: 'Side trail to the shelter',
      length_ft: 940,
      destination_poi_id: 'atc_shelter_0421',
      destination_distance_m: 286.5,
    },
    // Every field optional, and a record with none of them is a real stored
    // state - the pipeline publishes the id whether or not it resolved a
    // destination.
    spur_0008: {},
  },

  // Resume records for the corridor package. A phone holding these has
  // several hundred megabytes it expects to continue, which is the exact
  // thing §8c says must not be orphaned.
  'ourhike:corridor-archive:progress': {
    receivedBytes: 412_663_296,
    totalBytes: 1_267_384_320,
  },
  'ourhike:corridor-archive:source': {
    url: 'https://data.ourhike.org/2026-08-06/corridor-z13.pmtiles',
    etag: 'W/"3f8a1c9e"',
    sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    hashedBytes: 412_663_296,
  },
  'ourhike:corridor-archive:version': '2026-08-06',

  // The other two packages store under the same suffix scheme. Present so a
  // change to `partialKeyFor` and friends is caught for every package rather
  // than only the corridor one whose names are historical.
  'ourhike:basemap:progress': { receivedBytes: 12_582_912, totalBytes: 314_572_800 },
  'ourhike:basemap:version': '2026-08-06',
  'ourhike:dem:progress': { receivedBytes: 0, totalBytes: 607_265_661 },
  'ourhike:dem:version': '2026-08-06',
})

/**
 * The trail geometry blob, built rather than frozen: `loadTrailData` requires
 * an actual `Blob` and returns null for anything else, so a plain object
 * would make this pass by taking the "nothing downloaded" branch - a test
 * that proves nothing while looking green.
 */
export function storedTrailsBlob(): Blob {
  return new Blob([new Uint8Array([0x50, 0x4d, 0x54, 0x69, 0x6c, 0x65, 0x73])], {
    type: 'application/octet-stream',
  })
}

/**
 * The elevation profile as stored: two `Float32Array`s.
 *
 * Rebuilt per call rather than frozen at module scope for the same reason the
 * blob is - a typed array shared across tests is a shared mutable buffer.
 */
export function storedElevation(): {
  distanceMi: Float32Array
  elevationFt: Float32Array
} {
  return {
    distanceMi: new Float32Array([1405.0, 1405.5, 1406.0, 1406.5, 1407.0]),
    elevationFt: new Float32Array([4210, 4488, 4702, 4655, 4901]),
  }
}
