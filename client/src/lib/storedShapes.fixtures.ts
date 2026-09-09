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
// The baseline below was recorded before any release was tagged - `git tag
// -l` was empty and releases/ held only a README - so N was 1 and this file
// said so. Five tags exist now, v1.0.0 through v1.2.1, and for two of those
// releases the notes flagged that no entry had been captured and nothing
// carried the gap forward (#1253). RELEASE_SHAPES at the foot of this file is
// the per-release ledger §8c asked for: what each shipped build wrote, where
// it differs from the entry before it, read off the writers at the tag. Each
// release adds a map; none of them replaces this one.
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

/** What the entries below describe. Recorded before any tag existed; the
 *  tagged releases are RELEASE_SHAPES at the foot of this file. */
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

  // The day hikes a phone keeps (#976): the shape the build that introduced
  // the key writes, recorded the day it landed so the next build is held to
  // reading it - PLAN_KEY and TRIPS_KEY reached this list late, and this one
  // should not repeat that.
  //
  // The load-bearing details a reader has to keep honouring: ends are
  // COORDINATES ([lon, lat]) with no edgeIndex anywhere - dayHikes.ts's
  // CRITICAL rule, since an edge's array position shifts when the pipeline
  // republishes the graph; `poiId` is stored null by this build (the join
  // lands with #980); and the second hike carries TWO segments, which is
  // #935's deliberate gap - a reader that "fixes" it to one route has
  // changed the walk.
  'ourhike:day-hikes': {
    openId: 'day-hike-0002',
    hikes: [
      {
        id: 'day-hike-0001',
        name: 'Bear Mountain loop',
        date: '2026-09-06',
        segments: [
          [
            { coord: [-73.988997, 41.312807], poiId: null },
            { coord: [-73.968708, 41.322614], poiId: null },
          ],
        ],
        figures: {
          miles: 3.4,
          legs: [
            {
              name: 'Appalachian Trail',
              source: 'nynjtc',
              blaze_color: 'white',
              miles: 3.4,
            },
          ],
        },
        looped: true,
        recorded: 'planned',
      },
      {
        // Unnamed and undated on purpose - both are first-class states, and
        // `recorded: 'walked'` is the provenance flag a screen reads.
        id: 'day-hike-0002',
        name: '',
        date: null,
        segments: [
          [
            { coord: [-74.011355, 41.242191], poiId: null },
            { coord: [-74.003508, 41.25029], poiId: null },
          ],
          [
            { coord: [-73.996802, 41.25565], poiId: null },
            { coord: [-73.987004, 41.262418], poiId: null },
          ],
        ],
        figures: {
          miles: 2.8,
          legs: [{ name: null, source: null, blaze_color: null, miles: 2.8 }],
        },
        looped: false,
        recorded: 'walked',
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

/**
 * The same document once the hiker's own buckets exist (#800), and the one
 * thing about them a reader has to be able to see at a glance: **the same
 * trip is in two groups at once**, which is exactly what a hike does not
 * allow. A reader who "fixes" this to one group has changed the feature.
 *
 * The plan also carries a `rhythm` and a `rest` day (#798) - the fields a
 * phone written by this build will hold, frozen here so a later build
 * cannot quietly stop reading them.
 */
export const STORED_GROUPED_AND_RESTED_TRIPS: Readonly<Record<string, unknown>> =
  deepFreeze({
    'ourhike:trips': {
      openId: 'trip-0001',
      trips: [
        {
          id: 'trip-0001',
          name: 'Every Sunday: Bear Mountain',
          plan: {
            target: { miles: 8 },
            rhythm: { everyDays: 3, kind: 'nearo' },
            stops: [
              { mile: 1407.2, name: 'Bear Mountain', resupply: false },
              { mile: 1415.4, name: 'Anthony’s Nose', resupply: false },
              { mile: 1415.4, name: 'Anthony’s Nose', resupply: false },
            ],
            days: [
              { id: 'day-0001', date: '2026-02-15', pinned: false, generated: true },
              {
                id: 'day-0002',
                date: '2026-02-16',
                pinned: false,
                generated: false,
                rest: true,
              },
            ],
          },
        },
      ],
      hikes: [],
      groups: [
        { id: 'group-0001', name: 'Every Sunday', tripIds: ['trip-0001'] },
        { id: 'group-0002', name: 'With Dad', tripIds: ['trip-0001'] },
      ],
    },
  })

export const STORED_ARCHIVE_BYTES = SEGMENT_BYTES.flat().length

// --- What each shipped release wrote (#1253) --------------------------------
//
// RELEASING.md §8c: "a fixture of each supported release's stored shapes,
// written at release time, kept afterwards". Three releases shipped without
// one. v1.1.1's own notes said so - "no v1.0.0 entry was ever captured… the
// upgrade path is therefore tested against a pre-1.0 snapshot rather than
// against what v1.0.0 actually wrote to a phone" - and v1.2.0 and v1.2.1
// repeated the gap without repeating the sentence. This is the ledger.
//
// RECONSTRUCTED FROM THE WRITERS, NOT CAPTURED FROM A PHONE, and that is the
// weaker of the two claims #1253 allowed. Each entry was read off the code at
// its tag in a worktree (`git worktree add /tmp/x <tag>`): the interface the
// writer serialises, the literal it stores, the defaults it fills in. What a
// real device would add is the accidents - a key a build wrote once and
// nothing documents - and those are exactly what a reconstruction cannot
// see. A capture from an installed phone would supersede the matching entry
// here, not join it.
//
// EACH ENTRY IS A DELTA. It holds every key whose written shape differs from
// the entry before it - the previous release's, or STORED_SHAPES above for
// the first - plus every key the release introduced. `phoneOn(tag)` composes
// a whole phone by laying the entries over the baseline, oldest first, which
// is the same order a phone that installed early and updated every time
// would have been written in.
//
// WHAT IS DELIBERATELY NOT HERE: the artifact caches. `ourhike:trail-graph`
// and its three index-aligned halves, `ourhike:nearby-trails`,
// `ourhike:network-overview` and `ourhike:trail-index` hold published bytes
// or something rebuilt from them, each behind a manifest hash; a reader that
// cannot make sense of one drops it and fetches again (lib/trailGraphData.ts,
// lib/nearbyTrailData.ts). That costs signal, not a hiker's own work, which
// is the line §8c draws. Everything a hiker wrote, chose, walked or
// downloaded is below.

export interface ReleaseShapes {
  /** The git tag, verbatim, so the reading can be repeated. */
  tag: string
  /** The commit the tag points at. */
  commit: string
  /** When it shipped, from releases/. */
  published: string
  /** IndexedDB keys, as idb-keyval holds them. */
  indexedDb: Readonly<Record<string, unknown>>
  /** localStorage keys, as strings, because that is all localStorage holds. */
  localStorage: Readonly<Record<string, string>>
}

/** A few bytes standing in for a 640 px JPEG. */
const OWN_PHOTO_BYTES = new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xe1, 0x00, 0x10])], {
  type: 'image/jpeg',
})

/**
 * The preferences blob as v1.1.1 wrote it: every key its `UserPreferences`
 * declared, none it did not. `impact_panel_shown` arrived with v1.2.0 and is
 * absent here on purpose; `hiking_detail_level` could hold `standard` or
 * `fine` and nothing else, because the Light rung was v1.2.0's too. Every
 * value is one a hiker could have chosen on that release's Settings screen.
 */
const PREFERENCES_V1_1_1 = {
  trail_name: 'Sprocket',
  reporter_type: 'section',
  theme: 'dark',
  unit_system: 'metric',
  background_source: 'usgs_topo_offline',
  max_background_zoom: 13,
  hiking_detail_level: 'fine',
  map_style: 'night_hike',
  red_light_enabled: true,
  show_roads: true,
  drought_layer_shown: true,
  waypoint_types_shown: ['shelter', 'water', 'campsite', 'privy'],
  layer_detail_level: 'full',
  auto_rotate_enabled: false,
  wrong_way_alert_enabled: true,
  anonymity_window_days: 7,
  contribute_conditions: true,
  onboarding_completed: true,
  download_choice_made: true,
  location_permission_requested: true,
}

/**
 * A shelter as v1.1.1's `readPois` stored one from a full-featured release:
 * capacity and water distance (both absent-not-zero when unknown), the site
 * grouping of #523, the structured `nearby` parts of #614, and a photo with
 * its credit plus a two-entry gallery. Every optional field is present so a
 * reader that drops one is caught; the baseline's two POIs above cover the
 * sparse end.
 */
const SHELTER_V1_1_1 = {
  id: 'atc_shelter_0512',
  type: 'shelter',
  name: 'Fingerboard Shelter',
  lat: 41.2503,
  lon: -74.0961,
  confidence: 'high',
  mile: 1407.9,
  source: 'atc_shelters',
  capacity: 8,
  waterDistanceFt: 350,
  description:
    'Stone shelter on the ridge; the spring is down the blue-blazed side trail.',
  siteId: 'site_0512',
  siteRole: 'anchor',
  siteName: 'Fingerboard Shelter',
  nearby: [{ phrase: 'privy', distance_ft: 140 }],
  photoUrl: 'https://data.ourhike.org/photos/atc_shelter_0512.jpg',
  photoPage: 'https://commons.wikimedia.org/wiki/File:Fingerboard_Shelter.jpg',
  photoAuthor: 'A. Hiker',
  photoLicense: 'CC BY-SA 4.0',
  photoTaken: '2024-10-03',
  photos: [
    {
      url: 'https://data.ourhike.org/photos/atc_shelter_0512.jpg',
      page: 'https://commons.wikimedia.org/wiki/File:Fingerboard_Shelter.jpg',
      author: 'A. Hiker',
      license: 'CC BY-SA 4.0',
      taken: '2024-10-03',
    },
    { url: 'https://data.ourhike.org/photos/atc_shelter_0512_2.jpg' },
  ],
}

/** The privy that shares the shelter's pin - a site MEMBER, not an anchor. */
const PRIVY_V1_1_1 = {
  id: 'atc_privy_0512',
  type: 'privy',
  name: 'Fingerboard Shelter Privy',
  lat: 41.2507,
  lon: -74.0958,
  confidence: 'high',
  mile: 1407.9,
  source: 'atc_privies',
  siteId: 'site_0512',
  siteRole: 'member',
  siteName: 'Fingerboard Shelter',
}

/** The outbox as a v1.1.1 phone could hold it: the baseline's four reports
 *  (a queue is rewritten whole, so older items ride along unchanged) plus one
 *  of each other cargo that release could queue. */
const OUTBOX_V1_1_1 = [
  ...(STORED_SHAPES['ourhike:outbox'] as readonly unknown[]),
  {
    id: 'd4e5f607-2839-4a4b-8c5d-6e7f80912a3b',
    authoredAt: '2026-08-26T16:20:00.000Z',
    action: {
      kind: 'poi_photo_share',
      poiId: 'atc_shelter_0512',
      taken: '2026-08-26',
      flagged: null,
    },
    photo: OWN_PHOTO_BYTES,
  },
  {
    id: 'e5f60718-394a-4b5c-9d6e-7f8091a2b3c4',
    authoredAt: '2026-08-26T16:25:00.000Z',
    action: { kind: 'poi_photo_withdraw', poiId: 'atc_shelter_0421' },
  },
  {
    id: 'f6071829-4a5b-4c6d-ae7f-8091a2b3c4d5',
    authoredAt: '2026-08-26T17:02:00.000Z',
    action: {
      kind: 'poi_photo_report',
      poiId: 'atc_shelter_0421',
      photoId: 'photo_9f3a',
      reason: 'wrong_place',
    },
  },
  {
    id: '0718293a-5b6c-4d7e-bf80-91a2b3c4d5e6',
    authoredAt: '2026-08-26T19:41:00.000Z',
    appFailure: {
      what_happened:
        'The mile readout froze at 1407.2 for twenty minutes under the trees.',
      whereabouts: 'Just south of Fingerboard Shelter',
      contact: 'sprocket@example.org',
      harms: ['lost'],
      build: 'v1.1.1 (31c80c2e)',
      was_offline: true,
    },
  },
  {
    id: '18293a4b-6c7d-4e8f-8091-a2b3c4d5e6f7',
    authoredAt: '2026-08-27T07:15:00.000Z',
    fieldNote: {
      poi_id: 'opentrail_water_1188',
      lat: 35.6104,
      lon: -83.4402,
      mile: 1405.9,
      observation: 'trickling',
      note: 'Enough to fill a bottle in a minute or two.',
      reporter_type: 'section',
    },
  },
  {
    id: '293a4b5c-7d8e-4f90-91a2-b3c4d5e6f708',
    authoredAt: '2026-08-23T21:00:00.000Z',
    volunteerHours: {
      worked_on: '2026-08-23',
      hours: 3.5,
      activity: 'maintenance',
      note: 'Cleared two blowdowns north of the shelter.',
      club_id: 'nynjtc',
      mile: 1401.2,
    },
  },
  {
    id: '3a4b5c6d-8e9f-4001-a2b3-c4d5e6f70819',
    authoredAt: '2026-08-24T12:30:00.000Z',
    closure: {
      reason_type: 'storm_damage',
      note: 'Bridge out at the brook; ford is knee-deep.',
      start_mile_marker: 1403.0,
      end_mile_marker: 1403.4,
      start_lat: 41.2311,
      start_lon: -74.1102,
    },
  },
]

/** A day hike as v1.2.0 wrote a new one: a `note`, the climb it priced, and
 *  the concurrent organizations a merged leg folded in (#1115, #982). */
const DAY_HIKE_0003_V1_2_0 = {
  id: 'day-hike-0003',
  name: 'Fingerboard and back',
  date: '2026-08-30',
  segments: [
    [
      { coord: [-74.1052, 41.2411], poiId: null },
      { coord: [-74.0961, 41.2503], poiId: null },
    ],
  ],
  figures: {
    miles: 2.6,
    legs: [
      {
        name: 'Appalachian Trail',
        source: 'nynjtc',
        blaze_color: 'white',
        miles: 2.6,
        concurrent_sources: ['oprhp_trails'],
      },
    ],
    climb: { gainFt: 640, lossFt: 610 },
  },
  looped: true,
  recorded: 'planned',
  note: '',
}

/** A walk the graph could not price: `climb` written as null, which is a
 *  different fact from the key being absent (see dayHikes.ts). */
const DAY_HIKE_0004_V1_2_0 = {
  id: 'day-hike-0004',
  name: '',
  date: null,
  segments: [
    [
      { coord: [-74.011355, 41.242191], poiId: null },
      { coord: [-74.003508, 41.25029], poiId: null },
    ],
  ],
  figures: {
    miles: 1.1,
    legs: [{ name: null, source: null, blaze_color: null, miles: 1.1 }],
    climb: null,
  },
  looped: false,
  recorded: 'walked',
  note: 'Wet rocks past the brook.',
}

/** A hash-shaped string for the fixtures that carry one. */
const SOME_SHA256 = '9b74c9897bac770ffc029102a200c5de9e5b0c6aa6b3a2c5b8f3f2a1c0d1e2f3'

/** A sample as v1.2.1's GPS trace recorder writes one (lib/gpsTrace.ts). */
function traceSample(timestampMs: number, lat: number, lon: number, mile: number) {
  return {
    timestampMs,
    lat,
    lon,
    accuracyM: 12.5,
    altitudeM: 412.0,
    altitudeAccuracyM: 8.0,
    speedMps: 1.1,
    headingDeg: 210,
    mile,
    offTrailFt: 18,
    offTreadFt: 6,
    marker: 'walking',
    fixSource: 'native',
    accuracyConfidence: 68,
    simulated: false,
    wakeLock: 'screen',
    visible: true,
    blockedMs: 0,
    worstTaskMs: 14,
    shell: 'android',
    deviceOs: 'android',
  }
}

export const RELEASE_SHAPES: readonly ReleaseShapes[] = deepFreeze<
  readonly ReleaseShapes[]
>([
  {
    tag: 'v1.1.1',
    commit: '31c80c2e',
    published: '2026-08-27',
    // The first release hikers installed, and so the first phone whose whole
    // store had to be readable by the next build. Most of this entry is not a
    // shape that MOVED but a key the baseline never held: the release wrote
    // twenty-nine of them, and thirteen had no entry above.
    indexedDb: {
      'ourhike:preferences': PREFERENCES_V1_1_1,
      // The three sync ledgers and the switch (features/IDENTITY_AND_PRIVACY.md).
      // A trip dirty here and deleted there is the state a phone is in between
      // a road crossing and the next one.
      'ourhike:preferences:sync': { dirty: true, syncedAt: '2026-08-26T21:14:03.512Z' },
      'ourhike:sync:enabled': false,
      'ourhike:trips:sync': {
        dirty: ['trip-0001'],
        deleted: ['trip-0009'],
        seen: { 'trip-0001': '2026-08-26T21:14:03.512Z' },
        since: '2026-08-26T21:14:03.512Z',
        hikeDirty: true,
        hikeSeen: '2026-08-26T21:14:03.512Z',
      },
      'ourhike:day-hikes:sync': {
        dirty: ['day-hike-0002'],
        deleted: [],
        seen: { 'day-hike-0001': '2026-08-26T21:14:03.512Z' },
        since: '2026-08-26T21:14:03.512Z',
      },
      // THE WORD THIS RELEASE USED FOR THE MIDDLE MODE. #1127 renamed it to
      // `long` in v1.2.0, and a phone that chose Thru-hike on this release
      // still holds this string. The reader maps it forward; falling back to
      // the default would overwrite an explicit choice.
      'ourhike:hiker-mode': 'thru',
      'ourhike:outbox': OUTBOX_V1_1_1,
      // The download's own record (#1059): which manifest the artifacts came
      // from and when, so an update prompt can say how old the data is.
      'ourhike:trail-data-release': {
        version: '2026-08-26',
        hashes: {
          'trails.geojson': SOME_SHA256,
          'poi_shelter.geojson':
            '3f2a1c0d1e2f39b74c9897bac770ffc029102a200c5de9e5b0c6aa6b3a2c5b8f',
        },
        at: 1756251000000,
      },
      'ourhike:trail-data-update-dismissed': '2026-08-27',
      // The four side stores loadTrailData reads beside the waypoints, each
      // in the DOMAIN shape the release stored (a club's pieces are `runs`
      // here and `stretches` in the artifact - clubSections.ts says why that
      // distinction once cost a test run).
      'ourhike:club-sections': {
        clubs: [
          {
            acronym: 'NYNJTC',
            name: 'New York-New Jersey Trail Conference',
            region: 'Mid-Atlantic',
            runs: [{ startMile: 1360.1, endMile: 1448.6 }],
            miles: 88.5,
          },
          {
            acronym: 'GATC',
            name: 'Georgia Appalachian Trail Club',
            region: 'Deep South',
            runs: [
              { startMile: 0, endMile: 30.2 },
              { startMile: 31.4, endMile: 78.5 },
            ],
            miles: 77.3,
          },
        ],
        unattributed: [{ startMile: 30.2, endMile: 31.4 }],
        sources: {
          attribution: 'ATC Trail Clubs polygon layer',
          names: 'ATC Trail Club roster',
          miles: 'ATC Trail Clubs polygon layer',
        },
        sourceEdited: { 'Trail Clubs': '2026-08-14' },
      },
      'ourhike:stewards': [
        {
          provider: 'ATC',
          name: 'Appalachian Trail Conservancy',
          trust: 'authoritative',
          licence: 'ATC data use terms',
          attribution: 'Data © Appalachian Trail Conservancy',
          layers: ['Centerline', 'Shelters'],
          keys: ['atc_shelters', 'centerline'],
        },
        {
          provider: 'NYS OPRHP',
          name: 'New York State Office of Parks, Recreation and Historic Preservation',
          trust: null,
          licence: null,
          attribution: null,
          layers: ['State Park Trails'],
          keys: ['oprhp_trails'],
        },
      ],
      'ourhike:highlights': [
        {
          id: 'mahoosuc-arm',
          name: 'Mahoosuc Arm',
          bases: ['atc_viewpoint'],
          citations: {
            atc_viewpoint: {
              by: 'Appalachian Trail Conservancy',
              note: '',
              reviewed: '2026-08-19',
            },
          },
          legs: [{ trail: 'AT', startMile: 1925.0, endMile: 1930.5 }],
          club: 'MATC',
          caution: '',
        },
      ],
      'ourhike:retired-poi': {
        atc_shelter_0100: {
          id: 'atc_shelter_0100',
          poiType: 'shelter',
          source: 'atc_shelters',
          retired: '2026-08-26',
          lon: -83.1044,
          lat: 35.7112,
          name: 'Old Gap Shelter',
          supersededBy: 'atc_shelter_0421',
        },
        opentrail_water_0002: {
          id: 'opentrail_water_0002',
          poiType: 'water',
          source: 'opentrail',
          retired: '2026-08-26',
          lon: -83.2001,
          lat: 35.6902,
        },
      },
      'ourhike:pois': [
        ...(STORED_SHAPES['ourhike:pois'] as readonly unknown[]),
        SHELTER_V1_1_1,
        PRIVY_V1_1_1,
      ],
      // The hiker's own photos of a place (#573): the 640 px rendering is the
      // only bytes kept, one of the two has been shared, and one is chosen.
      'ourhike:my-photos:atc_shelter_0512': {
        photos: [
          {
            id: 'photo-0001',
            blob: OWN_PHOTO_BYTES,
            taken: '2026-08-20',
            added: '2026-08-20',
            source: 'camera',
          },
          {
            id: 'photo-0002',
            blob: OWN_PHOTO_BYTES,
            taken: null,
            added: '2026-08-22',
            source: 'library',
            shared: '2026-08-22T15:01:00.000Z',
          },
        ],
        chosenId: 'photo-0002',
      },
    },
    localStorage: {
      // The ground walked, normalised (start below end) as writeWalked stores
      // it, and today's slice of it. The day here is the one the tests read
      // it back on; on any other day the reader correctly returns nothing.
      'ourhike:walked-miles':
        '[{"startMile":1405.2,"endMile":1409.8},{"startMile":1411,"endMile":1412.4}]',
      'ourhike:passed-today':
        '{"day":"2026-08-27","ranges":[{"startMile":1405.2,"endMile":1409.8}]}',
      // A pace the hiker set, inside every clamp pace.ts applies.
      'ourhike:pace':
        '{"flatPaceMph":2.4,"ascentMetersPerHour":420,"descentMinutesPer1000m":8}',
      // Storage the phone gave back and the browser had not yet reclaimed
      // (#554), and the marker that an archive finished here.
      'ourhike:released-bytes':
        '{"bytes":314572800,"usageAfter":903000000,"at":1756250000000}',
      'ourhike:corridor-archive:completed': '2026-08-26T02:10:00.000Z',
      // The ATC alerts watermark under the name this release wrote it by.
      // notices.ts moved every organization onto its own key in v1.2.0 and
      // kept reading this one for the ATC, so a hiker who dismissed the
      // banner on this release does not get it back on the next.
      'ourhike:atc-alerts-silenced-through': '2026-08-20T00:00:00.000Z',
      'ourhike:trails-merged-chains': 'true',
    },
  },
  {
    tag: 'v1.2.0',
    commit: 'e8b02638',
    published: '2026-08-28',
    indexedDb: {
      // Two moves in one blob: the Light rung became storable (and stays
      // unofferable - a value here is not an offer, userPreferences.ts) and
      // `impact_panel_shown` arrived, defaulting on and here switched off.
      'ourhike:preferences': {
        ...PREFERENCES_V1_1_1,
        hiking_detail_level: 'light',
        impact_panel_shown: false,
      },
      'ourhike:hiker-mode': 'long',
      // A report inside its Undo window (#1133): queued, complete, and held
      // back by `holdUntil`. Every item before it has no such key.
      'ourhike:outbox': [
        ...OUTBOX_V1_1_1,
        {
          id: '4b5c6d7e-9f00-4112-b3c4-d5e6f708192a',
          authoredAt: '2026-08-28T14:00:00.000Z',
          payload: {
            type: 'blowdown',
            reporter_type: 'day',
            note: 'Across the trail at the switchback.',
            mile: 1406.4,
          },
          holdUntil: '2026-08-28T14:00:08.000Z',
        },
      ],
      // The first hike is the baseline's, untouched: a record saved on an
      // earlier build and never re-saved has no `note` and no `climb` key at
      // all, and both absences have to keep meaning what they mean.
      'ourhike:day-hikes': {
        openId: 'day-hike-0003',
        hikes: [
          (STORED_SHAPES['ourhike:day-hikes'] as { hikes: readonly unknown[] }).hikes[0],
          DAY_HIKE_0003_V1_2_0,
          DAY_HIKE_0004_V1_2_0,
        ],
      },
      // The other organizations' waypoints joined the same array (#1097). A
      // DEC lean-to is a shelter with a DEC source and NO mile - it is not on
      // the A.T.'s axis, and readPois omits the field rather than writing
      // null. The types are the release's eight; `trailhead` is v1.2.1's.
      'ourhike:pois': [
        ...(STORED_SHAPES['ourhike:pois'] as readonly unknown[]),
        SHELTER_V1_1_1,
        PRIVY_V1_1_1,
        {
          id: 'dec_lean_tos:1234',
          type: 'shelter',
          name: 'Slide Mountain Lean-to',
          lat: 42.0192,
          lon: -74.3927,
          confidence: 'high',
          source: 'dec_lean_tos',
          capacity: 8,
        },
        {
          id: 'dec_parking_areas:77',
          type: 'parking',
          name: 'Woodland Valley',
          lat: 42.0431,
          lon: -74.3608,
          confidence: 'high',
          source: 'dec_parking_areas',
        },
        {
          id: 'dec_firetowers:5',
          type: 'viewpoint',
          name: 'Hunter Mountain Fire Tower',
          lat: 42.1776,
          lon: -74.2223,
          confidence: 'high',
          source: 'dec_firetowers',
        },
      ],
    },
    localStorage: {},
  },
  {
    tag: 'v1.2.1',
    commit: '23204349',
    published: '2026-09-07',
    indexedDb: {
      // Stops on a day hike (#1194): the shelter, not its position - mile and
      // off-course distance are facts about the route and are re-derived.
      'ourhike:day-hikes': {
        openId: 'day-hike-0003',
        hikes: [
          (STORED_SHAPES['ourhike:day-hikes'] as { hikes: readonly unknown[] }).hikes[0],
          {
            ...DAY_HIKE_0003_V1_2_0,
            stops: [
              { poiId: 'atc_shelter_0512', type: 'shelter', name: 'Fingerboard Shelter' },
            ],
          },
          DAY_HIKE_0004_V1_2_0,
        ],
      },
      // The ninth waypoint type, from OPRHP's facilities layer (#1197).
      'ourhike:pois': [
        ...(STORED_SHAPES['ourhike:pois'] as readonly unknown[]),
        SHELTER_V1_1_1,
        PRIVY_V1_1_1,
        {
          id: 'oprhp_facilities:8812',
          type: 'trailhead',
          name: 'Reeves Meadow Trailhead',
          lat: 41.2352,
          lon: -74.1583,
          confidence: 'high',
          source: 'oprhp_facilities',
        },
      ],
      // The per-vertex miles beside the lines (#1192): the verified bytes as
      // a Blob, whose front names the trails.geojson it was measured on.
      'ourhike:trail-miles': new Blob(
        [
          `{"format":1,"trails_sha256":"${SOME_SHA256}","axis":"export_elevation.calibrated_trail_axis","decimals":4,"feature_count":1,"vertex_count":3,"miles":{"centerline:chain:0":[1405.0,1405.5,1406.0]}}`,
        ],
        { type: 'application/json' },
      ),
      // A GPS trace mid-walk (#1182): the recorder's state and its first
      // chunk. Recording deliberately survives a reload, so a reader that
      // cannot resume this hands back a truncated trace that looks complete.
      'ourhike:gps-trace:state': {
        recording: true,
        startedAt: 1757230800000,
        marker: 'walking',
        chunks: 1,
        samples: 2,
        lastSampleAt: 1757230811000,
        lastAccuracyM: 12.5,
        lastAccuracyConfidence: 68,
      },
      'ourhike:gps-trace:c0': [
        traceSample(1757230805000, 41.2411, -74.1052, 1406.1),
        traceSample(1757230811000, 41.2415, -74.1047, 1406.15),
      ],
      // Offline coverage in one-degree cells (#1229): the index as fetched,
      // with the hash the manifest named, and one held cell plus the context
      // sketch under the archive store's segment scheme.
      'ourhike:basemap-cells-index': {
        index: {
          cell_degrees: 1,
          seam_margin_km: 3,
          context_zoom: 9,
          context: 'basemap_context.pmtiles',
          cells: [
            {
              name: 'n41w074',
              key: 'basemap_cell_n41w074.pmtiles',
              bounds: [-74, 41, -73, 42],
            },
          ],
        },
        hash: SOME_SHA256,
      },
      'ourhike:basemap-cell:n41w074:g0:0': new Blob([new Uint8Array(SEGMENT_BYTES[0])]),
      'ourhike:basemap-cell:n41w074:complete': {
        generation: 0,
        segments: 1,
        totalBytes: SEGMENT_BYTES[0].length,
      },
      'ourhike:basemap-context:g0:0': new Blob([new Uint8Array(SEGMENT_BYTES[1])]),
      'ourhike:basemap-context:complete': {
        generation: 0,
        segments: 1,
        totalBytes: SEGMENT_BYTES[1].length,
      },
    },
    localStorage: {
      'ourhike:basemap-cell:n41w074:completed': '2026-09-07T13:30:00.000Z',
    },
  },
])

/**
 * The phone a hiker who installed early and updated at every release holds
 * on `tag`: the baseline, then each release's entry laid over it in order.
 *
 * Fresh objects per call, the way the Blob and Float32Array builders above
 * are, because a test that overlays its own case onto the result must not
 * be editing the fixture the next test reads.
 */
export function phoneOn(tag: string): {
  indexedDb: Record<string, unknown>
  localStorage: Record<string, string>
} {
  const upTo = RELEASE_SHAPES.findIndex((release) => release.tag === tag)
  if (upTo === -1) throw new Error(`no release fixture is tagged ${tag}`)
  const indexedDb: Record<string, unknown> = { ...STORED_SHAPES }
  const localStorage: Record<string, string> = {}
  for (const release of RELEASE_SHAPES.slice(0, upTo + 1)) {
    Object.assign(indexedDb, release.indexedDb)
    Object.assign(localStorage, release.localStorage)
  }
  return { indexedDb, localStorage }
}

/**
 * A download that died between the centerline and the waypoints (#1084): the
 * lines are stored and the partial marker says the rest never landed. A
 * reader must answer "no trail data" so the launch fetch finishes the job,
 * rather than drawing a trail whose search and legend are silently empty.
 */
export function storedInterruptedRelease(): Record<string, unknown> {
  return { 'ourhike:trail-data-partial': true }
}
