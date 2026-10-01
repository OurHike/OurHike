// Fixtures for the challenge recipes (#1780, features/CHALLENGES.md).
//
// WHAT IS REAL AND WHAT IS NOT. The ATC challenge below is 33 of the 100
// items export_challenges.py resolves from pipeline/reference/challenges/atc/
// (every place, waypoint-type, elevation and workday item, the three mystery
// items, and nine of the 76 at-home lines), resolved 2026-09-30 against
// release 2026-09-24-2 - the POI ids, miles, names and coordinates are the
// published records' own, and the titles are the ATC's 2025 PDF verbatim. It
// is a DRAFT, and every frame that names it shows the label saying so.
//
// The second challenge is INVENTED for the frames that need a record with no
// finish and no reward, and its name says "(preview)". Nothing here ships as
// data.
//
// THE HIKER IS NOBODY. `SEEDED_STATE` joins the ATC list and tags four
// places on invented dates inside the 2027 window - no account, no position, no photo, no
// register line. The four things .claude/skills/pr-screenshot/SKILL.md says
// must never appear in a shot are absent by construction.
//
// Not a recipe: shared fixtures live one directory down, where the runner's
// recipe glob does not reach (fixtures/suggestedHikes.mjs explains).

export const ATC_CHALLENGE = {
  id: 'atc-summer-bucket-list-2027',
  org: 'atc',
  trail: 'AT',
  name: 'A.T. Summer Bucket List',
  status: 'draft',
  summary:
    'Complete at least 25 items by September 1 to be eligible for the grand prize drawing.',
  window: {
    opens: '2027-05-15',
    closes: '2027-09-01',
  },
  finish: {
    count: 25,
    label: 'for the drawing',
  },
  reward: {
    kind: 'drawing',
    rules_url: 'https://appalachiantrail.org/sweepstakes',
    art: null,
  },
  photo: null,
  sections: [
    {
      id: 'learn',
      title: 'Learn about the A.T.',
      short: 'Learn',
    },
    {
      id: 'experience',
      title: 'Experience the A.T.',
      short: 'Anywhere',
    },
    {
      id: 'protect',
      title: 'Protect the A.T.',
      short: 'Protect',
    },
    {
      id: 'mystery',
      title: 'Mystery Items',
      short: 'Mystery',
    },
  ],
  items: [
    {
      id: 'trivia-quiz',
      section: 'learn',
      title: 'Take our A.T. trivia quiz.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'self_report',
      },
    },
    {
      id: 'harpers-ferry-visitor-center',
      section: 'learn',
      title: 'Visit the Harpers Ferry Visitor Center.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'place',
        radius_m: 800,
        off_trail: true,
        places: [
          {
            poi: 'atc_communities:60bcf556-71db-4084-8895-79a9c199612a',
            name: 'Bolivar/Harpers Ferry',
            poi_type: 'resupply',
            mile: 1026.5,
            lat: 39.325386,
            lon: -77.738884,
          },
        ],
      },
    },
    {
      id: 'damascus-trail-center',
      section: 'learn',
      title: 'Visit the Damascus Trail Center.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'place',
        radius_m: 800,
        off_trail: true,
        places: [
          {
            poi: 'atc_communities:70620d62-6b5b-4cd2-bc86-0ce2baf0950d',
            name: 'Damascus',
            poi_type: 'resupply',
            mile: 471.302,
            lat: 36.633734,
            lon: -81.783734,
          },
        ],
      },
    },
    {
      id: 'monson-visitor-center',
      section: 'learn',
      title: 'Visit the Monson Visitor Center.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'place',
        radius_m: 800,
        off_trail: true,
        places: [
          {
            poi: 'atc_communities:5af4f547-e26c-4f9e-a916-49ad8c0ba0e6',
            name: 'Monson',
            poi_type: 'resupply',
            mile: 2079.954,
            lat: 45.287003,
            lon: -69.501162,
          },
        ],
      },
    },
    {
      id: 'at-museum',
      section: 'learn',
      title:
        'Learn about the history of the Trail at the Appalachian Trail Museum in Pennsylvania.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'place',
        radius_m: 300,
        off_trail: false,
        places: [
          {
            poi: 'atc_viewpoints:c973c8b0-cde7-4dfb-95dd-a7e9a282cda4',
            name: 'Pine Grove Furnace Vista',
            poi_type: 'viewpoint',
            mile: 1105.95,
            lat: 40.032135,
            lon: -77.305614,
          },
        ],
      },
    },
    {
      id: 'pct-hang',
      section: 'learn',
      title: 'Learn how to do a PCT hang.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'self_report',
      },
    },
    {
      id: 'green-tunnel-podcast',
      section: 'learn',
      title: 'Listen to an episode of the Green Tunnel podcast about A.T. history.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'self_report',
      },
    },
    {
      id: 'read-a-biography',
      section: 'learn',
      title: 'Read The Appalachian Trail: A Biography.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'self_report',
      },
    },
    {
      id: 'white-blaze-photo',
      section: 'experience',
      title: 'Take a photo of a white blaze.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'self_report',
      },
    },
    {
      id: 'shelter-logbook',
      section: 'experience',
      title: 'Hike to an A.T. shelter and sign the shelter logbook.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'poi_type',
        type: 'shelter',
        radius_m: 60,
      },
    },
    {
      id: 'find-a-vista',
      section: 'experience',
      title:
        'Use the “A.T. Vistas” layer of the Appalachian Trail Conservancy’s interactive map to find one of the Trail’s stunning vistas.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'poi_type',
        type: 'viewpoint',
        radius_m: 60,
      },
    },
    {
      id: 'sunrise',
      section: 'experience',
      title: 'Watch the sunrise from the Trail. Don’t forget to take a photo!',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'self_report',
      },
    },
    {
      id: 'mcafee-knob',
      section: 'experience',
      title:
        'Take the McAfee Knob shuttle to hike to one of the most photographed spots on the A.T.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'place',
        radius_m: 150,
        off_trail: false,
        places: [
          {
            poi: 'atc_viewpoints:95a18f95-b78f-43bb-843a-4b9b82fecb76',
            name: 'McAfee Knob Summit',
            poi_type: 'viewpoint',
            mile: 714.92,
            lat: 37.39297,
            lon: -80.03712,
          },
        ],
      },
    },
    {
      id: 'springer-mountain',
      section: 'experience',
      title: 'Visit the A.T.’s southern terminus at Springer Mountain.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'place',
        radius_m: 150,
        off_trail: false,
        places: [
          {
            poi: 'atc_viewpoints:3f45ce01-0943-4700-8ba6-097ec8e74586',
            name: 'Springer Mtn Summit Vista',
            poi_type: 'viewpoint',
            mile: 0.016,
            lat: 34.626714,
            lon: -84.193874,
          },
        ],
      },
    },
    {
      id: 'katahdin',
      section: 'experience',
      title: 'Hike to the A.T.’s northern terminus at Katahdin.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'place',
        radius_m: 150,
        off_trail: false,
        places: [
          {
            poi: 'atc_viewpoints:9c19514f-736c-4f04-9581-d6b989908547',
            name: 'Katahdin Summit (E)',
            poi_type: 'viewpoint',
            mile: 2197.857,
            lat: 45.90433,
            lon: -68.921327,
          },
        ],
      },
    },
    {
      id: 'harpers-ferry-halfway',
      section: 'experience',
      title: 'Visit the A.T.’s psychological halfway point at Harpers Ferry.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'place',
        radius_m: 800,
        off_trail: true,
        places: [
          {
            poi: 'atc_communities:60bcf556-71db-4084-8895-79a9c199612a',
            name: 'Bolivar/Harpers Ferry',
            poi_type: 'resupply',
            mile: 1026.5,
            lat: 39.325386,
            lon: -77.738884,
          },
        ],
      },
    },
    {
      id: 'summit-4000',
      section: 'experience',
      title: 'Summit a 4,000+ foot peak.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'elevation_min_ft',
        value: 4000.0,
      },
    },
    {
      id: 'meal-in-a-community',
      section: 'experience',
      title: 'Visit an A.T. Community and have a meal at a local restaurant.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'poi_type',
        type: 'resupply',
        radius_m: 800,
      },
    },
    {
      id: 'priest-confession',
      section: 'experience',
      title: 'Write a confession in the logbook at the Priest Shelter.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'place',
        radius_m: 150,
        off_trail: false,
        places: [
          {
            poi: 'atc_shelters:e90877f7-1669-4ddf-adce-2a920ee0ba22',
            name: 'The Priest Shelter',
            poi_type: 'shelter',
            mile: 830.5,
            lat: 37.817792,
            lon: -79.070371,
          },
        ],
      },
    },
    {
      id: 'james-river-footbridge',
      section: 'experience',
      title: 'Cross the James River Footbridge—the longest footbridge on the A.T.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'place',
        radius_m: 150,
        off_trail: false,
        places: [
          {
            poi: 'atc_viewpoints:5366ed77-b71a-453b-8f75-90352c9c5c10',
            name: 'James River',
            poi_type: 'viewpoint',
            mile: 787.948,
            lat: 37.596605,
            lon: -79.391108,
          },
        ],
      },
    },
    {
      id: 'virginia-triple-crown',
      section: 'experience',
      title:
        'Hike the “Triple Crown” of Virginia: McAfee Knob, Tinker Cliffs, and Dragon’s Tooth.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'places_all',
        radius_m: 150,
        off_trail: false,
        places: [
          {
            poi: 'atc_viewpoints:3cadebda-9d7d-4373-88f6-b240420eb958',
            name: 'Dragons Tooth Peak',
            poi_type: 'viewpoint',
            mile: 703.114,
            lat: 37.36077,
            lon: -80.17354,
          },
          {
            poi: 'atc_viewpoints:95a18f95-b78f-43bb-843a-4b9b82fecb76',
            name: 'McAfee Knob Summit',
            poi_type: 'viewpoint',
            mile: 714.92,
            lat: 37.39297,
            lon: -80.03712,
          },
          {
            poi: 'atc_viewpoints:0897b09f-f474-4466-adeb-98c23a56106d',
            name: 'Tinker Cliffs 2',
            poi_type: 'viewpoint',
            mile: 720.3,
            lat: 37.43785,
            lon: -79.99923,
          },
        ],
      },
    },
    {
      id: 'pine-grove-ice-cream',
      section: 'experience',
      title:
        'Eat all (or some) of a half-gallon of ice cream at Pine Grove Furnace State Park.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'place',
        radius_m: 300,
        off_trail: false,
        places: [
          {
            poi: 'atc_viewpoints:c973c8b0-cde7-4dfb-95dd-a7e9a282cda4',
            name: 'Pine Grove Furnace Vista',
            poi_type: 'viewpoint',
            mile: 1105.95,
            lat: 40.032135,
            lon: -77.305614,
          },
        ],
      },
    },
    {
      id: 'kennebec-ferry',
      section: 'experience',
      title: 'Ride the Kennebec River ferry.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'place',
        radius_m: 250,
        off_trail: false,
        places: [
          {
            poi: 'atc_viewpoints:db91e68b-f616-4457-b8b5-c23c3d813bd5',
            name: 'West Kennebec River',
            poi_type: 'viewpoint',
            mile: 2045.869,
            lat: 45.235463,
            lon: -70.002412,
          },
        ],
      },
    },
    {
      id: 'kuwohi',
      section: 'experience',
      title: 'Hike to the summit of Kuwohi, the highest point on the A.T.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'place',
        radius_m: 150,
        off_trail: false,
        places: [
          {
            poi: 'atc_viewpoints:288915b1-d985-4bf6-9d5f-863bf14395f7',
            name: 'Clingmans Dome Summit Lookout Tower Vista',
            poi_type: 'viewpoint',
            mile: 200.114,
            lat: 35.562886,
            lon: -83.498351,
          },
        ],
      },
    },
    {
      id: 'volunteer-event',
      section: 'protect',
      title:
        'Sign up for a volunteer event and spend a day doing essential Trail maintenance.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'workday',
        org: null,
        trail: 'AT',
      },
    },
    {
      id: 'become-a-member',
      section: 'protect',
      title: 'Become a member of the ATC to support ongoing conservation work.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'self_report',
      },
    },
    {
      id: 'pick-up-litter',
      section: 'protect',
      title: 'Pick up litter on a hike.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'self_report',
      },
    },
    {
      id: 'trail-crew',
      section: 'protect',
      title: 'Join a Trail Crew.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'workday',
        org: null,
        trail: 'AT',
      },
    },
    {
      id: 'invasive-species-workday',
      section: 'protect',
      title: 'Participate in an invasive species removal workday.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'workday',
        org: null,
        trail: 'AT',
      },
    },
    {
      id: 'hiker-pledge',
      section: 'protect',
      title: 'Take the long-distance hiker pledge.',
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'self_report',
      },
    },
    {
      id: 'mystery-1',
      section: 'mystery',
      title: null,
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'self_report',
      },
      mystery: {
        number: 1,
        reveal_on: null,
      },
    },
    {
      id: 'mystery-2',
      section: 'mystery',
      title: null,
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'self_report',
      },
      mystery: {
        number: 2,
        reveal_on: null,
      },
    },
    {
      id: 'mystery-3',
      section: 'mystery',
      title: null,
      note: null,
      note_by: null,
      photo: null,
      match: {
        kind: 'self_report',
      },
      mystery: {
        number: 3,
        reveal_on: null,
      },
    },
  ],
  reviewed: '2026-09-30',
  org_name: 'Appalachian Trail Conservancy',
  org_short: 'ATC',
  org_domain: 'appalachiantrail.org',
}

const place = (poi, name, mile, lat, lon) => ({
  poi,
  name,
  poi_type: 'viewpoint',
  mile,
  lat,
  lon,
})

/** Invented for the frames that need a record: no finish, no reward. */
export const RECORD_CHALLENGE = {
  id: 'preview-roanoke-three-peaks',
  org: 'preview',
  org_name: 'A club (preview)',
  org_short: 'CLUB',
  org_domain: 'club.example',
  trail: 'AT',
  name: 'Three Roanoke peaks (preview)',
  status: 'published',
  summary: null,
  window: { opens: null, closes: null },
  finish: null,
  reward: null,
  photo: null,
  sections: [{ id: 'peaks', title: 'Peaks', short: 'Peaks' }],
  items: [
    [
      'dragons-tooth',
      'Dragon’s Tooth',
      place(
        'atc_viewpoints:3cadebda-9d7d-4373-88f6-b240420eb958',
        'Dragons Tooth Peak',
        703.114,
        37.36077,
        -80.17354,
      ),
    ],
    [
      'mcafee-knob',
      'McAfee Knob',
      place(
        'atc_viewpoints:95a18f95-b78f-43bb-843a-4b9b82fecb76',
        'McAfee Knob Summit',
        714.92,
        37.39297,
        -80.03712,
      ),
    ],
    [
      'tinker-cliffs',
      'Tinker Cliffs',
      place(
        'atc_viewpoints:0897b09f-f474-4466-adeb-98c23a56106d',
        'Tinker Cliffs 2',
        720.3,
        37.43785,
        -79.99923,
      ),
    ],
  ].map(([id, title, spot]) => ({
    id,
    section: 'peaks',
    title,
    note: null,
    note_by: null,
    photo: null,
    match: { kind: 'place', radius_m: 150, off_trail: false, places: [spot] },
  })),
  reviewed: '2026-09-30',
}

export const CHALLENGES_DOCUMENT = {
  source: 'reference/challenges',
  challenges: [ATC_CHALLENGE, RECORD_CHALLENGE],
}

/** A hiker who joined the ATC list in June and tagged four places. */
export const SEEDED_STATE = {
  joined: [{ challengeId: ATC_CHALLENGE.id, at: '2027-06-01T12:00:00.000Z' }],
  tags: [
    {
      challengeId: ATC_CHALLENGE.id,
      itemId: 'springer-mountain',
      at: '2027-06-03T15:10:00.000Z',
      how: 'gps',
    },
    {
      challengeId: ATC_CHALLENGE.id,
      itemId: 'virginia-triple-crown',
      poi: 'atc_viewpoints:3cadebda-9d7d-4373-88f6-b240420eb958',
      at: '2027-07-12T16:40:00.000Z',
      how: 'gps',
    },
    {
      challengeId: ATC_CHALLENGE.id,
      itemId: 'mcafee-knob',
      at: '2027-07-14T10:12:00.000Z',
      how: 'gps',
    },
    {
      challengeId: ATC_CHALLENGE.id,
      itemId: 'trivia-quiz',
      at: '2027-05-20T20:00:00.000Z',
      how: 'hand',
    },
  ],
  sectionWalked: {},
  hiddenSuggestions: {},
  answeredDay: null,
  layerShown: false,
  sent: [],
}

/**
 * Put the challenges on the phone the way a refresh would, and the hiker's
 * record beside them, then boot again to read both.
 *
 * The release is ANSWERED as well as the cache seeded, for
 * fixtures/suggestedHikes.mjs's reason: the preview is built against real
 * data, whose challenges.json would otherwise replace the fixture the moment
 * it landed (every release before export_challenges.py 404s, which keeps the
 * kept copy - but a later release would not).
 */
export async function seedChallenges(
  page,
  {
    state = SEEDED_STATE,
    document = CHALLENGES_DOCUMENT,
    passedToday = null,
    trips = null,
    takenTrail = null,
  } = {},
) {
  await page.route(/\/challenges\.json(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(document),
    }),
  )
  await page.evaluate(
    ({ document, state, passedToday, trips, takenTrail }) =>
      new Promise((done, fail) => {
        localStorage.setItem('ourhike:challenge-state', JSON.stringify(state))
        if (passedToday !== null) {
          localStorage.setItem('ourhike:passed-today', JSON.stringify(passedToday))
        }
        const open = indexedDB.open('keyval-store')
        open.onupgradeneeded = () => open.result.createObjectStore('keyval')
        open.onerror = () => fail(open.error)
        open.onsuccess = () => {
          const shelf = open.result
            .transaction('keyval', 'readwrite')
            .objectStore('keyval')
          if (trips !== null) {
            shelf.put(trips, 'ourhike:trips')
            shelf.put('long', 'ourhike:hiker-mode')
          }
          if (takenTrail !== null) shelf.put(takenTrail, 'ourhike:taken-trail')
          const write = shelf.put(
            { document, storedAt: '2027-07-14T12:00:00.000Z' },
            'ourhike:conditions:challenges.json',
          )
          write.onsuccess = () => done()
          write.onerror = () => fail(write.error)
        }
      }),
    { document, state, passedToday, trips, takenTrail },
  )
  await page.reload({ waitUntil: 'load' })
}

/** The evening the camp-card recipe is shot at, and its local day. Fixed on
 *  the page clock in the recipe's `before`, so the card - which waits for the
 *  day to be over - is on screen whatever time CI runs. */
export const EVENING = new Date('2027-07-14T23:30:00Z')
export const EVENING_DAY = '2027-07-14'

/** Today's walked miles past McAfee Knob Summit (mile 714.92) and Campbell
 *  Shelter - lib/passedToday.ts's own record, the input the camp card reads. */
export const PASSED_MCAFEE = {
  day: EVENING_DAY,
  ranges: [{ startMile: 710, endMile: 716 }],
}

function dayOf(from, offset) {
  return new Date(from.getTime() + offset * 86_400_000).toISOString().slice(0, 10)
}

/**
 * One planned section over Virginia's Triple Crown, for Plan's card. The
 * stops are INVENTED names at real A.T. miles - a plan somebody might make,
 * not anybody's - and the days are laid around the browser's own today, for
 * fixtures/longHike.mjs's reason: Plan renders the plan it holds, dated.
 */
export function planStore(today = new Date()) {
  const planDay = (id, offset) => ({
    id,
    date: dayOf(today, offset),
    pinned: false,
    generated: true,
    walked: false,
  })
  return {
    openId: null,
    activeHikeId: 'preview-hike',
    groups: [],
    trips: [
      {
        id: 'preview-section',
        name: 'Pearisburg → Daleville',
        plan: {
          target: { miles: 14 },
          stops: [
            { mile: 686.0, name: 'Start (preview)', resupply: false },
            { mile: 699.0, name: 'Night one (preview)', resupply: false },
            { mile: 713.9, name: 'Night two (preview)', resupply: false },
            { mile: 727.5, name: 'Daleville', resupply: true },
          ],
          days: [
            planDay('preview-day-1', 1),
            planDay('preview-day-2', 2),
            planDay('preview-day-3', 3),
          ],
        },
      },
    ],
    hikes: [
      {
        id: 'preview-hike',
        name: 'Pearisburg → Daleville',
        type: 'section',
        trailId: 'AT',
        points: [
          { name: 'Start (preview)', mile: 686.0 },
          { name: 'Daleville', mile: 727.5 },
        ],
        status: 'planned',
        tripIds: ['preview-section'],
      },
    ],
  }
}

/** Nobody joined anything - for the Plan suggestion and Browse. */
export const UNJOINED_STATE = { ...SEEDED_STATE, joined: [], tags: [] }

/** More → Challenges, from wherever the app opened. */
export async function openChallenges(page) {
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /^Challenges/ }).click()
  await page.getByRole('heading', { name: 'Your challenges' }).waitFor()
}
