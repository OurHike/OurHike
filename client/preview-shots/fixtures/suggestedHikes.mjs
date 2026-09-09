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
// shots #1290 added.

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
      // and it says so. Since #1290 it is also the ONE fixture carrying a
      // `detail`, so the hike-detail recipes have a screen to reach - and
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
      id: 'fixture-wapiti',
      name: 'Wapiti to Docs Knob',
      miles: 7.9,
      climb: null,
      difficulty: 'moderate-strenuous',
      author: { kind: 'ourhike', name: 'Vernon Trails' },
      segments: ends(VA, 2),
      detail: {
        url: 'https://example.org/routes/wapiti-to-docs-knob',
        // Deliberately NOT 7.9. The two figures disagreeing is the whole
        // point of the screen, and a fixture where they agree photographs
        // nothing.
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
        // Read off a place card's map centre rather than a placed pin, so
        // the screen prints the caveat that says which. That sentence is
        // one of the things worth photographing.
        start: { lat: 37.31, lon: -80.66, basis: 'map_centre' },
        routeType: 'Out and back',
        park: 'Vernon State Forest',
        trails: ['Wapiti Trail', 'Docs Knob Connector'],
        hikerNote:
          'The turnaround sits where their description puts it rather than at a junction, so this line runs shorter than the length on their page.',
      },
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

/** Seed the kept copy, then reload so the app wakes up owning it - the
 *  same move day-hike-list.mjs makes for its store. */
export async function seedSuggestedHikes(page) {
  await page.evaluate(
    ({ document }) =>
      new Promise((done, fail) => {
        const open = indexedDB.open('keyval-store')
        open.onupgradeneeded = () => open.result.createObjectStore('keyval')
        open.onerror = () => fail(open.error)
        open.onsuccess = () => {
          const write = open.result
            .transaction('keyval', 'readwrite')
            .objectStore('keyval')
            .put(
              { document, storedAt: '2026-09-08T12:00:00.000Z' },
              'ourhike:conditions:suggested_hikes.json',
            )
          write.onsuccess = () => done()
          write.onerror = () => fail(write.error)
        }
      }),
    { document: SUGGESTED_HIKES_DOCUMENT },
  )
  await page.reload({ waitUntil: 'load' })
  await page.getByText('Suggested hikes').waitFor()
}
