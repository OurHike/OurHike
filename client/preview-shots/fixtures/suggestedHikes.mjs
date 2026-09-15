// Fixtures for the suggested-hikes recipes (#1284): the routes the design
// handoff wrote as card copy, as a published document seeded into the kept
// copy the app reads (lib/suggestedHikesData.ts, through the conditions
// cache under `ourhike:conditions:suggested_hikes.json`).
//
// NOBODY'S DATA. Invented routes with invented ends on a grid, publishers
// named as the design names them, no photos - a photo is a data surface with
// a credit and a licence (features/POI_PHOTOS.md), and a recipe that pointed
// at somebody's photograph would publish it on every future pull request.
// The cards show the sunken no-photo block, which is the honest frame for a
// route with none.
//
// Not a recipe: the runner treats every top-level `preview-shots/*.mjs` as
// one (photograph-preview.mjs's isRecipePath), so shared fixtures live one
// directory down, where that pattern does not reach. Five recipes import
// this: the shelf, the finder and its results, and the two hike-detail
// shots #1290 added. Since #1473 it seeds TWO objects, because a hike IS
// two objects on the wire: the shelf record, and that hike's own prose
// under `ourhike:conditions:suggested_hikes_detail_<n>.json`.

const NJ = { lon: -74.6, lat: 41.2 }
const VA = { lon: -80.7, lat: 37.3 }

function ends(at, step) {
  return [
    [
      { coord: [at.lon + step * 0.02, at.lat + step * 0.01], poiId: null },
      { coord: [at.lon + step * 0.02 + 0.015, at.lat + step * 0.01], poiId: null },
    ],
  ]
}

export const SUGGESTED_HIKES_DOCUMENT = {
  generated_at: '2026-09-08T12:00:00Z',
  hikes: [
    {
      id: 'fixture-sunrise',
      name: 'Sunrise Mtn loop',
      miles: 6.2,
      climb: { gainFt: 980, lossFt: 980 },
      difficulty: 'moderate',
      author: { kind: 'club', name: 'NY-NJ Trail Conference' },
      transit: {
        line: 'NJT 197',
        toStop: 'Culvers Gap',
        walkMiles: 0.3,
        source: 'NJ Transit',
      },
      segments: ends(NJ, 0),
    },
    {
      id: 'fixture-angels-rest',
      name: 'Angels Rest',
      miles: 5.6,
      climb: { gainFt: 1540, lossFt: 1540 },
      difficulty: 'strenuous',
      author: { kind: 'guidebook', name: 'L. Adkins' },
      segments: ends(VA, 0),
    },
    {
      id: 'fixture-pochuck',
      name: 'Pochuck boardwalk',
      miles: 3.6,
      climb: { gainFt: 120, lossFt: 120 },
      difficulty: 'easy',
      author: { kind: 'hiker', name: '@slackpack' },
      transit: {
        line: 'NJT 890',
        toStop: 'Vernon',
        walkMiles: 0.6,
        source: 'NJ Transit',
      },
      segments: ends(NJ, 1),
    },
    {
      id: 'fixture-terrace-pond',
      name: 'Terrace Pond circular',
      miles: 4.4,
      climb: { gainFt: 610, lossFt: 610 },
      difficulty: 'moderate',
      author: { kind: 'hiker', name: '@slackpack' },
      transit: {
        line: 'NJT 194',
        toStop: 'West Milford',
        walkMiles: 1.1,
        source: 'NJ Transit',
      },
      segments: ends(NJ, 2),
    },
    {
      id: 'fixture-dismal-falls',
      name: 'Dismal Falls',
      miles: 2.2,
      climb: { gainFt: 180, lossFt: 180 },
      difficulty: 'easy',
      author: { kind: 'club', name: 'Outdoor Club at Virginia Tech' },
      transit: {
        line: 'Route 100',
        toStop: 'Pearisburg',
        walkMiles: 1.4,
        source: 'the club',
      },
      segments: ends(VA, 1),
    },
    {
      // The unmeasured-climb case the handoff says not to skip: no time,
      // and it says so. It is also the ONE fixture the hike-detail recipes
      // reach, so it is the one with a detail object beside it (#1473) - and
      // the only one whose publisher is invented outright ('Vernon Trails'),
      // which is why the invented prose below hangs on this route and not
      // on one attributed to a club that really exists. Made-up sentences
      // under a real publisher's byline would be a fixture telling a lie
      // about somebody, on every future pull request.
      //
      // Its difficulty is one of the two COMPOUND levels #1290 added, so a
      // shot of this screen is also the evidence that the five-rung ladder
      // renders. No existing recipe's copy moves with it: the shelf shows
      // the first three published, and the results recipe filters by
      // transit, which this route has none of.
      //
      // THE SHELF CARRIES SHELF_FIELDS AND NOTHING ELSE, because that is
      // what `pipeline/export_suggested_hikes.py` writes since #1473 - the
      // prose moved to its own object and this fixture moved with it
      // (WAPITI_DETAIL below). `routeType` and `park` stay here, on the
      // shelf, because a facet finder filters what it already holds.
      //
      // THE ID IS `<source>:<digits>`, which is not decoration: it is what
      // `detailKeyFor` needs to name the detail object, and it answers null
      // for anything else. The old `fixture-wapiti` would have reached no
      // prose at all.
      //
      // The rule this fixture has always kept, now applied to the split
      // itself: an earlier version nested these fields under `detail:` and
      // every one was silently dropped - the shot showed a detail screen
      // with no publisher's length, no start, no prose and no link back.
      // A fixture that does not match the wire is a shot that is evidence
      // about a document nobody publishes.
      id: 'nynjtc_hike_finder:7909',
      name: 'Wapiti to Docs Knob',
      miles: 7.9,
      climb: null,
      difficulty: 'moderate-strenuous',
      author: { kind: 'ourhike', name: 'Vernon Trails' },
      segments: ends(VA, 2),
      // On the shelf beside the line, never behind a fetch: App.tsx draws
      // `segments` from this record, so a drawn line is never separated
      // from what drew it (#1473).
      routeProvenance: 'generated',
      routeGrade: 'strong',
      routeType: 'Out and back',
      park: 'Vernon State Forest',
    },
    {
      id: 'fixture-pinwheel',
      name: 'Pinwheel Vista out and back',
      miles: 3.1,
      climb: { gainFt: 640, lossFt: 640 },
      difficulty: 'easy',
      author: { kind: 'club', name: 'NY-NJ Trail Conference' },
      segments: ends(NJ, 3),
    },
    {
      id: 'fixture-mcafee',
      name: 'McAfee Knob from the parking lot',
      miles: 8.8,
      climb: { gainFt: 1740, lossFt: 1740 },
      difficulty: 'strenuous',
      author: { kind: 'guidebook', name: 'L. Adkins' },
      segments: ends(VA, 3),
    },
    {
      id: 'fixture-stony-brook',
      name: 'Stony Brook and back',
      miles: 4.0,
      climb: { gainFt: 350, lossFt: 350 },
      difficulty: 'easy',
      author: { kind: 'ourhike', name: 'Harriman State Park' },
      transit: {
        line: 'Metro-North',
        toStop: 'Sloatsburg',
        walkMiles: 0.9,
        source: 'MTA',
      },
      segments: ends(NJ, 4),
    },
  ],
}

/**
 * Wapiti's prose, as its own published object (#1473).
 *
 * This is `suggested_hikes_detail_7909.json` - what `lib/useHikeDetail.ts`
 * fetches when somebody opens that walk, and what `recallHikeDetail` reads
 * back with no signal. Seeded into the same kept copy the shelf rides in, so
 * the detail recipes photograph the FETCH PATH rather than a shelf record
 * pretending the split never happened.
 *
 * It carries its own `id` because the exporter writes one: a phone handed
 * another walk's prose by a stale cache would render it under this walk's
 * name, and `saysItIs` refuses it on that field. A fixture that omitted the
 * id would photograph a document the exporter does not write.
 */
export const WAPITI_DETAIL = {
  id: 'nynjtc_hike_finder:7909',
  url: 'https://example.org/routes/wapiti-to-docs-knob',
  // Deliberately NOT 7.9. The two figures disagreeing is the whole point of
  // the screen, and a fixture where they agree photographs nothing. Since
  // the split this arrives HERE rather than on the shelf, which is what the
  // shot is now evidence for.
  publishedMiles: 8.5,
  overview: [
    'A long ridge walk to a knob with one wide view north, and a second one south if you carry on past the cairn.',
    'The tread is rocky for the middle two miles. Nothing here is exposed, but it is slow.',
  ],
  description: [
    'Park at the pull-off and cross the road to the kiosk.',
    'Follow the blue blazes uphill for a mile and a quarter to the first bench.',
    'At the fork, keep left. The right fork drops to the creek and does not come back.',
    'The knob is a half mile past the second bench. Return the way you came.',
  ],
  publication: {
    submittedBy: 'R. Okonjo',
    submittedOn: '2019-05-02',
    verifiedOn: '2024-10-11',
  },
  // Read off a place card's map centre rather than a placed pin, so the
  // screen prints the caveat that says which. That sentence is one of the
  // things worth photographing.
  start: { lat: 37.31, lon: -80.66, basis: 'map_centre' },
  trails: ['Wapiti Trail', 'Docs Knob Connector'],
  hikerNote:
    'The turnaround sits where their description puts it rather than at a junction, so this line runs shorter than the length on their page.',
}

/**
 * Make these routes what the app reads, then reload so it wakes up owning
 * them - the same move day-hike-list.mjs makes for its store.
 *
 * BOTH OBJECTS, because since #1473 a hike IS two objects. Seeding only the
 * shelf would photograph a detail screen with no prose, which is a real
 * state (a publisher who said nothing more) but not the one these recipes
 * are about.
 *
 * AND THE BUCKET IS ANSWERED, not just the cache, because seeding alone is a
 * RACE THIS RECIPE LOSES IN CI. `useSuggestedHikes` reads the kept copy and
 * then fetches, and `setHikes(fresh)` replaces the shelf outright - so a
 * seeded fixture stands only until the real `suggested_hikes.json` lands.
 * The preview is built against production's data (pr-preview.yml), where
 * that artifact answers 200 with nine real hikes and no Wapiti; the drive
 * then waits 30 s for a card that has already been replaced. Measured
 * 2026-09-15: the camera could not take `hike-detail` or `hike-detail-saved`
 * on d9a6ccfd, both `locator.click: Timeout 30000ms exceeded` on
 * `getByRole('button', { name: /Wapiti to Docs Knob/ })`, while the same
 * recipes passed locally - where the fetch resolves before `ready` flips and
 * the drive wins.
 *
 * Intercepting settles it rather than making the window bigger, and it is
 * the more honest shot besides: the detail now ARRIVES OVER THE NETWORK, the
 * way a phone gets it, instead of being pre-placed in the cache the phone
 * would only read with no signal.
 */
export async function seedSuggestedHikes(
  page,
  document = SUGGESTED_HIKES_DOCUMENT,
  detail = WAPITI_DETAIL,
) {
  const json = (body) => ({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
  // Registered before the reload, and they outlive it. The patterns are the
  // key names rather than a full URL, because `dataUrl` puts the release
  // folder in front of them and that prefix is not this fixture's business.
  await page.route(/\/suggested_hikes\.json(\?|$)/, (route) =>
    route.fulfill(json(document)),
  )
  await page.route(/\/suggested_hikes_detail_\d+\.json(\?|$)/, (route) =>
    route.fulfill(json(detail)),
  )
  await page.evaluate(
    ({ document, detail }) =>
      new Promise((done, fail) => {
        const open = indexedDB.open('keyval-store')
        open.onupgradeneeded = () => open.result.createObjectStore('keyval')
        open.onerror = () => fail(open.error)
        open.onsuccess = () => {
          const store = open.result
            .transaction('keyval', 'readwrite')
            .objectStore('keyval')
          const storedAt = '2026-09-08T12:00:00.000Z'
          store.put({ document, storedAt }, 'ourhike:conditions:suggested_hikes.json')
          // The number off the record's own id, the way detailKeyFor builds
          // it - a second spelling here would photograph a key nothing asks
          // for.
          const number = detail.id.slice(detail.id.lastIndexOf(':') + 1)
          const write = store.put(
            { document: detail, storedAt },
            `ourhike:conditions:suggested_hikes_detail_${number}.json`,
          )
          write.onsuccess = () => done()
          write.onerror = () => fail(write.error)
        }
      }),
    { document, detail },
  )
  await page.reload({ waitUntil: 'load' })
  await page.getByText('Suggested hikes').waitFor()
}

/**
 * The same document with every climb removed, which is the shape the
 * PUBLISHED routes actually have.
 *
 * MEASURED, 2026-09-11, against release 2026-09-10: not one of the nine
 * routes in `suggested_hikes.json` carries a climb, so `hikeEstimate` prices
 * none of them and every card reads "no time — climb unmeasured". The fixture
 * above is a mix on purpose — five priced walks and one unmeasured — because
 * its recipes are about the card's two shapes. This one is the phone a hiker
 * has today, and it is the only way to photograph what Today withholds when
 * nothing can be priced.
 */
export const UNPRICED_HIKES_DOCUMENT = {
  ...SUGGESTED_HIKES_DOCUMENT,
  hikes: SUGGESTED_HIKES_DOCUMENT.hikes.map((hike) => ({ ...hike, climb: null })),
}

/** `seedSuggestedHikes` over the unpriced document. */
export async function seedUnpricedHikes(page) {
  await seedSuggestedHikes(page, UNPRICED_HIKES_DOCUMENT)
}
