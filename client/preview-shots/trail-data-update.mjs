// The ask before a hiker's map is replaced (#919, chrome/TrailDataUpdate.tsx).
//
// WHY THIS NEEDS A SEED AND A STUBBED MANIFEST, WHICH IS MORE FIXTURE THAN
// MOST RECIPES HERE USE
//
// The row appears when three things are true at once: this phone finished a
// download, it recorded WHICH release that was, and the bucket is now
// publishing a different one. No sequence of taps produces that - the third
// condition belongs to the bucket and the first two to IndexedDB - so the
// drive plants both sides.
//
// The manifest is stubbed rather than read live, and that is the difference
// between a shot that shows the change and one that shows whatever the
// production bucket happens to be serving today. A live read would give the
// UNDESCRIBED variant every time until a publish carrying #919's own
// `previous_version` lands, so the picture would be the one sentence the row
// falls back to - "the map data has changed" - rather than the counts a hiker
// is actually being asked about. Stubbed, the frame is deterministic and shows
// the state worth reviewing: a release that removed water points.
//
// Everything invented here is invented: a made-up version pair, a made-up
// hash, and one artifact name. No account, nobody's reports, no location fix,
// and the map underneath holds no waypoints to publish coordinates for (the
// skill's never-photograph list, kept by construction).
//
// WHAT IT DEPENDS ON, MEASURED RATHER THAN ASSUMED
//
// A build whose VITE_DATA_BASE_URL is set: with none, `DATA_CONFIGURED` is
// false, `publishedSnapshot` returns without fetching, the route below never
// fires and the row never appears. Measured 2026-08-26 against this pull
// request's own deployed preview: its bundle carries
// `https://data.ourhike.org`, so the condition holds there today. If a future
// preview is built without one, this drives cleanly and photographs the trail
// screen without the row - the honest frame for a build that cannot ask.

export const caption = 'Newer trail data, offered'
export const alt =
  'The trail screen with a row at its foot offering newer trail data, saying what changed and what it costs'

/** The version this phone is pretending to hold, and the one being published.
 *  Named so they cannot collide with a real release id. */
const HELD = 'preview-fixture-held'
const PUBLISHED = 'preview-fixture-published'

/** One artifact, changed. `previous_version` names HELD, so the row is
 *  entitled to describe the hop rather than falling back to "something
 *  changed" - see dataRefresh.availableRefresh. */
const MANIFEST = {
  version: PUBLISHED,
  previous_version: HELD,
  artifacts: {
    'poi_water.geojson': {
      sha256: 'b'.repeat(64),
      // The DECODED size and the wire cost, both, because the row must show
      // the second (see dataManifest.PublishedSnapshot.sizes). Real figures
      // from the live artifact, measured 2026-08-21, so the sentence in the
      // frame is a number this app would really print.
      size_bytes: 300_000,
      transfer_bytes: 103_584,
      change: { severity: 'consequential', added: 11, removed: 3, moved: 1, edited: 6 },
    },
  },
}

/** What the phone recorded when it last downloaded. The hash differs from the
 *  manifest's, which is what makes this artifact one of the changed ones. */
const HELD_RELEASE = {
  version: HELD,
  hashes: { 'poi_water.geojson': 'a'.repeat(64) },
  at: Date.parse('2026-08-18T04:25:00Z'),
}

/** Written straight into idb-keyval's store, the way the day-hike recipes
 *  plant theirs - this runs as plain node against a built page, with no
 *  bundler to resolve the app's own modules. */
function plant({ release, trails }) {
  return new Promise((done, fail) => {
    const open = indexedDB.open('keyval-store')
    open.onupgradeneeded = () => open.result.createObjectStore('keyval')
    open.onerror = () => fail(open.error)
    open.onsuccess = () => {
      const store = open.result.transaction('keyval', 'readwrite').objectStore('keyval')
      store.put(release, 'ourhike:trail-data-release')
      // An empty but present trail layer, so `haveTrailData()` is true and the
      // launch fetch stands down. Without it the app would start a real
      // download over this frame - the opposite of the state being
      // photographed, and a request to the live bucket besides.
      store.put(new Blob([trails], { type: 'application/json' }), 'ourhike:trails')
      store.transaction.oncomplete = () => done()
      store.transaction.onerror = () => fail(store.transaction.error)
    }
  })
}

export default async function drive(page) {
  // Before the reload, so the app's first read of the manifest is this one.
  await page.route(/latest\.json(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MANIFEST),
    }),
  )

  await page.evaluate(plant, {
    release: HELD_RELEASE,
    trails: '{"type":"FeatureCollection","features":[]}',
  })

  // Both stores are read once at mount, which has already happened - reload so
  // the app wakes holding a release the bucket has moved past, exactly as a
  // phone reopening after a publish would.
  await page.reload({ waitUntil: 'load' })
}
