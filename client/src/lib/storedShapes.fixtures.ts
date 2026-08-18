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

  // A two-day plan with a resupply at the far end and its first day already
  // walked (#756/#758). Boundary-shaped: three stops carry two days, dates
  // ride on the days (the cascade moves the calendar in pieces, which one
  // start date cannot carry), and lib/plan.ts refuses the record wholesale
  // if any invariant fails - so this fixture is also what pins the shape a
  // future migration has to keep reading.
  //
  // Edited once before any release existed, when #758 moved dates from a
  // plan-level startDate onto the days in the same unmerged PR that
  // introduced the key. Nothing shipped ever wrote the earlier shape.
  'ourhike:plan': {
    target: { walkingHours: 7 },
    stops: [
      { mile: 470.8, name: 'Damascus', resupply: false },
      {
        mile: 486.2,
        name: 'Lost Mountain Shelter',
        poiId: 'atc_shelter_0999',
        resupply: false,
      },
      { mile: 503.3, name: 'Atkins', resupply: true },
    ],
    days: [
      {
        id: 'day-0001',
        date: '2026-05-12',
        pinned: false,
        generated: false,
        walked: true,
      },
      { id: 'day-0002', date: '2026-05-13', pinned: true, generated: false },
    ],
  },

  // Two trips under one key, and which of them the Plan tab has open (#787).
  //
  // NO `hikes` FIELD, deliberately: this is the shape the #787 build wrote,
  // and it is a phone in the support window. #788 added hikes to this same
  // document, so the reader has to treat absent as "none" rather than as
  // invalid - `storedGroupedTrips` below is that shape's own entry.
  //
  // The entry ABOVE is what makes this one load-bearing rather than
  // decorative: a phone that stopped at the single-plan build holds
  // `ourhike:plan` and no `ourhike:trips` at all, and `loadTrips()` has to
  // turn that into this without losing the plan. The compat test asserts
  // both directions - the legacy key still migrates, and a store written by
  // this build still reads.
  //
  // A trip nests its whole `HikePlan` rather than spreading it, so the plan
  // model, its validator and every edit in plan.ts are untouched by having
  // acquired a name. The second trip carries an unnamed end on purpose:
  // that is the dropped-point case, whose trip name has to come from a mile
  // marker rather than from a place.
  'ourhike:trips': {
    openId: 'trip-0002',
    trips: [
      {
        id: 'trip-0001',
        name: 'Damascus → Atkins',
        plan: {
          target: { walkingHours: 7 },
          stops: [
            { mile: 470.8, name: 'Damascus', resupply: false },
            { mile: 503.3, name: 'Atkins', resupply: true },
          ],
          days: [{ id: 'day-0001', date: '2026-05-12', pinned: false, generated: true }],
        },
      },
      {
        id: 'trip-0002',
        name: 'mi 601.0 → mi 620.4',
        plan: {
          target: { miles: 15 },
          stops: [
            { mile: 601.0, resupply: false },
            { mile: 620.4, resupply: false },
          ],
          days: [{ id: 'day-0002', pinned: false, generated: true }],
        },
      },
    ],
  },

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

// --- The downloaded archive itself (#586) ---------------------------------
//
// The records above are a download's RESUME state. The archive is the thing
// §8c's sentence is actually about - "orphans a downloaded archive" - and it
// was missing from this file entirely, so nothing ran a reader over a stored
// archive of any shape. Breaking `readArchive`'s legacy branch left the compat
// suite 18/18 green; only one unit test noticed.
//
// TWO SHAPES, BECAUSE #553 CHANGED THE LAYOUT. No release is tagged yet, so
// today the older shape is on testers' phones rather than hikers' - which is
// precisely why it is worth capturing now, while the evidence of what it looked
// like still exists. Once releases are tagged, #374 §2's window (three releases
// plus ninety days) puts #553 inside it, and by then nobody will be able to
// reconstruct the pre-#553 records from the code, because the code no longer
// writes them.
//
// Keys are LITERAL STRINGS here rather than built with `segmentKeyFor` and
// friends, unlike the resume records above. That is not an inconsistency: a
// phone holds literal strings, and deriving them from the app's own builder
// would make a rename invisible exactly where it costs a gigabyte. The compat
// test pins the builders against these literals instead, which catches the
// rename and keeps the coverage.
//
// The blobs are a handful of bytes. A real corridor archive is 1.18 GB in 36
// segments of 32 MiB (archiveDownload.ts's SEGMENT_BYTES), and none of these
// readers care about the size - they care about assembly order, the marker's
// agreement with what is on disk, and which record wins. `totalBytes` below is
// honest to the fixture's own bytes rather than copying the real figure, so a
// reader that reports the marker instead of the archive cannot pass by
// coincidence.

/** Segment bytes, per index, for the corridor package's current-shape fixture.
 *  Distinct per segment so a reader that concatenates them out of order, or
 *  drops one, produces a different Blob rather than the same length. */
const SEGMENT_BYTES = [
  [0x50, 0x4d, 0x54, 0x69, 0x6c, 0x65, 0x73], // "PMTiles", as segment 0 really starts
  [0x01, 0x02, 0x03, 0x04],
  [0xfe, 0xff],
] as const

/**
 * A phone that finished its download BEFORE #553: one whole-archive Blob under
 * the bare package key, and no marker.
 *
 * `archiveStore.ts` promises this "keeps resolving" and is served "untouched".
 * That promise is why a hiker who updates the app at a resupply stop with one
 * bar is not asked for 1.18 GB again, and it is the single most expensive thing
 * in this file to get wrong.
 */
export function storedLegacyArchive(): Record<string, unknown> {
  return {
    'ourhike:corridor-archive': new Blob([new Uint8Array(SEGMENT_BYTES.flat())], {
      type: 'application/octet-stream',
    }),
  }
}

/**
 * A phone that finished its download AFTER #553: segments in generation 0 plus
 * the completion marker that says which generation is whole.
 *
 * Generation 0 rather than 1 because a first download writes there - a phone
 * only reaches generation 1 by re-downloading over a working archive.
 */
export function storedSegmentedArchive(): Record<string, unknown> {
  return {
    'ourhike:corridor-archive:g0:0': new Blob([new Uint8Array(SEGMENT_BYTES[0])]),
    'ourhike:corridor-archive:g0:1': new Blob([new Uint8Array(SEGMENT_BYTES[1])]),
    'ourhike:corridor-archive:g0:2': new Blob([new Uint8Array(SEGMENT_BYTES[2])]),
    'ourhike:corridor-archive:complete': {
      generation: 0,
      segments: 3,
      totalBytes: SEGMENT_BYTES.flat().length,
    },
  }
}

/**
 * A phone caught mid-download before #553: bytes under `:partial`, with the
 * resume records above pointing at them.
 *
 * Kept as a fixture even though the app deliberately DISCARDS this rather than
 * adopting it - `archiveDownload.ts` argues that at length, and the short of it
 * is that copying up to a gigabyte into segment 0 needs room for a second copy,
 * which is the headroom failure #544 is about. What has to be true is that it is
 * reclaimed rather than left behind: an orphaned 412 MB record that nothing will
 * ever read is #554's failure wearing different clothes.
 */
export function storedLegacyPartial(): Record<string, unknown> {
  return {
    'ourhike:corridor-archive:partial': new Blob([new Uint8Array(SEGMENT_BYTES[0])]),
  }
}

/** How many bytes the two finished-archive fixtures hold, so a test can assert
 *  a size without restating the byte table. */
/**
 * The trip store as #788 writes it: the same key, one shape later, with the
 * trips grouped into a hike whose ends are REFERENCES.
 *
 * A separate export rather than a second `STORED_SHAPES` entry because an
 * object cannot hold one key twice - the same reason `storedLegacyArchive`
 * and `storedSegmentedArchive` sit apart. Both shapes are inside the support
 * window and both are asserted: the entry above is what a #787 phone holds,
 * this is what a #788 one does.
 *
 * `start` carries a `poiId` and a mile that has since MOVED (the live POI
 * publishes 471.2), which is the drift the reference exists to survive;
 * `end` carries a reference this download no longer has, which is the case
 * the reader must admit to rather than resolve silently.
 */
export const STORED_GROUPED_TRIPS: Readonly<Record<string, unknown>> = deepFreeze({
  'ourhike:trips': {
    openId: 'trip-0001',
    trips: [
      {
        id: 'trip-0001',
        name: 'Damascus → Atkins',
        plan: {
          target: { walkingHours: 7 },
          stops: [
            { mile: 470.8, name: 'Damascus', resupply: false },
            { mile: 503.3, name: 'Atkins', resupply: true },
          ],
          days: [
            {
              id: 'day-0001',
              date: '2026-05-12',
              pinned: false,
              generated: true,
              walked: true,
            },
          ],
        },
      },
    ],
    hikes: [
      {
        id: 'hike-0001',
        name: 'Virginia, over a few years',
        type: 'section',
        start: { poiId: 'atc_shelter_0777', name: 'Damascus', mile: 470.8 },
        end: { poiId: 'atc_shelter_gone', name: 'Retired Shelter', mile: 560.0 },
        tripIds: ['trip-0001'],
      },
    ],
  },
})

export const STORED_ARCHIVE_BYTES = SEGMENT_BYTES.flat().length
