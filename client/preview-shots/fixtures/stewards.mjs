// Fixtures for the recipes that photograph an organization's own links
// (#1574): who the map's data belongs to, as pipeline/export_sources.py
// publishes it in `stewards.json`, with the two blocks the registry now
// records for NYNJTC - `support` (#932, their "Donate Today") and `store`
// (their "Trail Maps", and the paper maps on it).
//
// NOBODY'S DATA. Two organizations whose registry entries are public, their
// own button text as pipeline/sources.json records it off their own sites,
// and two of the twelve products with the sheets and parks NYNJTC's own
// index lists. No account, no report, no photograph, no location fix.
//
// WHY A RECIPE HAS TO SEED A RELEASE TO SHOW THIS. The app reads its steward
// list out of the downloaded trail data (lib/trailData.ts's loadTrailData),
// and reads nothing at all until `ourhike:trails` holds a Blob - a phone
// with no download has no steward list, by design, and the preview's phone
// has no download. So `seedStewards` puts a one-line fixture centerline in
// that slot (client/src/test/appHarness.ts's putTrailData, the same trick)
// beside the steward list, and the app then treats the phone as holding a
// release. The centerline is forty points at 77 degrees west, which draws
// nothing a shot of the More tab or a hike's record can see.
//
// Not a recipe: shared fixtures live one directory down, where the runner's
// recipe glob does not reach (fixtures/suggestedHikes.mjs explains).

/** The shape `stewards.json` has on the wire, so lib/stewards.ts parses
 *  this exactly as it parses a download. */
export const STEWARDS_DOCUMENT = {
  stewards: [
    {
      provider: 'ATC',
      name: 'Appalachian Trail Conservancy',
      trust: null,
      licence: '© ATC, used with permission',
      attribution: null,
      terms: null,
      terms_source: null,
      layers: ['A.T. Centerline', 'A.T. Shelters', 'A.T. Side Trails'],
      keys: ['centerline', 'side_trails', 'atc_shelters'],
      support: {
        donate_url: 'https://appalachiantrail.org/get-involved/become-a-member/',
        donate_cta: 'Become a Member',
        donate_surfaces: ['sources_screen', 'trail_card', 'day_hike_summary'],
      },
      store: null,
      steward_id: 'org:atc',
    },
    {
      provider: 'NYNJTC',
      name: 'New York-New Jersey Trail Conference',
      trust: 'authoritative',
      licence:
        'Maintainer authorisation, 2026-08-24 - NYNJTC has stated no terms of their own',
      attribution: null,
      terms: null,
      terms_source: null,
      layers: ['NYNJTC Hike Finder export (the full 385-hike list)', 'NYNJTC Long Path'],
      keys: ['nynjtc_hike_finder', 'nynjtc_long_path'],
      support: {
        donate_url: 'https://www.nynjtc.org/support/',
        donate_cta: 'Donate Today',
        donate_surfaces: ['sources_screen', 'trail_card', 'day_hike_summary'],
      },
      store: {
        store_url:
          'https://store.nynjtc.org/collections/maps?utm_source=ourhike&utm_medium=app',
        store_cta: 'Trail Maps',
        store_surfaces: ['hike_detail', 'sources_screen', 'trail_sheet'],
        paper_maps: [
          {
            handle: 'harriman-bear-mountain-trails-map',
            title: 'Harriman-Bear Mountain Trails Map',
            url: 'https://store.nynjtc.org/products/harriman-bear-mountain-trails-map?utm_source=ourhike&utm_medium=app',
            sheets: ['118', '119'],
            covers: ['Harriman State Park', 'Bear Mountain State Park'],
            sheet_covers: {
              118: ['Southern Harriman State Park', 'Long Path'],
              119: [
                'Northern Harriman State Park',
                'Bear Mountain State Park',
                'Appalachian Trail',
                'Long Path',
              ],
            },
          },
          {
            handle: 'delaware-water-gap-kittatinny-trails-map',
            title: 'Delaware Water Gap & Kittatinny Trails Map',
            url: 'https://store.nynjtc.org/products/delaware-water-gap-kittatinny-trails-map?utm_source=ourhike&utm_medium=app',
            sheets: ['120', '121', '122', '123'],
            covers: ['Delaware Water Gap National Recreation Area'],
            sheet_covers: {
              120: [
                'Southern Delaware Water Gap National Recreation Area',
                'Worthington State Forest',
                'Appalachian Trail',
              ],
              121: [
                'Southern Delaware Water Gap National Recreation Area',
                'Appalachian Trail',
              ],
              122: [
                'Northern Delaware Water Gap National Recreation Area',
                'Stokes State Forest',
                'Appalachian Trail',
              ],
              123: [
                'Northern Delaware Water Gap National Recreation Area',
                'High Point State Park',
                'Huckleberry Ridge State Forest',
                'Port Jervis Watershed Park',
                'Appalachian Trail',
              ],
            },
          },
        ],
      },
      steward_id: 'org:nynjtc',
    },
  ],
}

/** Forty vertices at 77 degrees west, a mile apart: the shape
 *  appHarness.ts's centerlineGeoJSON makes, and enough for loadTrailData
 *  to count the phone as holding a release. */
function centerlineGeoJSON(miles = 40) {
  return JSON.stringify({
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { source: 'centerline' },
        geometry: {
          type: 'LineString',
          coordinates: Array.from({ length: miles }, (_, i) => [-77, 37 + i / 69]),
        },
      },
    ],
  })
}

/**
 * Put the steward list where the app reads it, beside the fixture release
 * that makes it read anything.
 *
 * Seeded into IndexedDB and ALSO answered on the wire, because a preview with
 * a real bucket may re-read `stewards.json` for the pinned release, and the
 * published one carries no `store` until the publish that follows this
 * change - a route on the key keeps the shot about the screen rather than
 * about which publish has run. The pattern is the key name, as the hikes
 * fixture's is, because the release folder in front of it is not this
 * fixture's business.
 *
 * Does NOT reload: a recipe seeding more than one fixture reloads once, after
 * all of them (`seedSuggestedHikes` reloads itself, so call this first).
 */
export async function seedStewards(page, document = STEWARDS_DOCUMENT) {
  await page.route(/\/stewards\.json(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(document),
    }),
  )
  await page.evaluate(
    ({ document, centerline }) =>
      new Promise((done, fail) => {
        const open = indexedDB.open('keyval-store')
        open.onupgradeneeded = () => open.result.createObjectStore('keyval')
        open.onerror = () => fail(open.error)
        open.onsuccess = () => {
          const store = open.result
            .transaction('keyval', 'readwrite')
            .objectStore('keyval')
          store.put(new Blob([centerline]), 'ourhike:trails')
          store.put([], 'ourhike:pois')
          store.put(document, 'ourhike:stewards')
          const write = store.put(false, 'ourhike:trail-data-partial')
          write.onsuccess = () => done()
          write.onerror = () => fail(write.error)
        }
      }),
    { document, centerline: centerlineGeoJSON() },
  )
}
