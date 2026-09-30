// Challenges for tests and preview recipes (#1780). Built through the real
// parser from the exporter's artifact shape, so a fixture that drifts from
// what pipeline/export_challenges.py writes fails to parse rather than
// passing a test about a shape nothing publishes.
//
// The ATC items are real lines from the 2025 PDF and the POI ids, miles and
// names are the published records' own (release 2026-09-24-2). The second
// challenge is invented for tests - a club list with no reward - and is
// named so: nothing here ships as data.

import { parseChallenges, type Challenge } from './challenges'

function place(
  poi: string,
  name: string,
  mile: number,
  lat: number,
  lon: number,
  poiType = 'viewpoint',
) {
  return { poi, name, poi_type: poiType, mile, lat, lon }
}

const MCAFEE = place(
  'atc_viewpoints:95a18f95-b78f-43bb-843a-4b9b82fecb76',
  'McAfee Knob Summit',
  714.92,
  37.39297,
  -80.03712,
)
const DRAGONS_TOOTH = place(
  'atc_viewpoints:3cadebda-9d7d-4373-88f6-b240420eb958',
  'Dragons Tooth Peak',
  703.114,
  37.36077,
  -80.17354,
)
const TINKER = place(
  'atc_viewpoints:0897b09f-f474-4466-adeb-98c23a56106d',
  'Tinker Cliffs 2',
  720.3,
  37.43785,
  -79.99923,
)
const SPRINGER = place(
  'atc_viewpoints:3f45ce01-0943-4700-8ba6-097ec8e74586',
  'Springer Mtn Summit Vista',
  0.016,
  34.626714,
  -84.193874,
)
const KATAHDIN = place(
  'atc_viewpoints:9c19514f-736c-4f04-9581-d6b989908547',
  'Katahdin Summit (E)',
  2197.857,
  45.90433,
  -68.921327,
)
const MONSON = place(
  'atc_communities:5af4f547-e26c-4f9e-a916-49ad8c0ba0e6',
  'Monson',
  2079.954,
  45.287003,
  -69.501162,
  'resupply',
)

export const ATC_ARTIFACT = {
  id: 'atc-summer-bucket-list-2027',
  org: 'atc',
  org_name: 'Appalachian Trail Conservancy',
  org_short: 'ATC',
  trail: 'AT',
  name: 'A.T. Summer Bucket List',
  status: 'draft',
  summary:
    'Complete at least 25 items by September 1 to be eligible for the grand prize drawing.',
  window: { opens: '2027-05-15', closes: '2027-09-01' },
  finish: { count: 5, label: 'for the drawing' },
  reward: { kind: 'drawing', rules_url: 'https://appalachiantrail.org/sweepstakes' },
  sections: [
    { id: 'learn', title: 'Learn about the A.T.', short: 'Learn' },
    { id: 'experience', title: 'Experience the A.T.', short: 'Anywhere' },
    { id: 'protect', title: 'Protect the A.T.', short: 'Protect' },
    { id: 'mystery', title: 'Mystery Items', short: 'Mystery' },
  ],
  items: [
    {
      id: 'trivia-quiz',
      section: 'learn',
      title: 'Take our A.T. trivia quiz.',
      match: { kind: 'self_report' },
    },
    {
      id: 'monson-visitor-center',
      section: 'learn',
      title: 'Visit the Monson Visitor Center.',
      match: { kind: 'place', radius_m: 800, off_trail: true, places: [MONSON] },
    },
    {
      id: 'springer-mountain',
      section: 'experience',
      title: 'Visit the A.T.’s southern terminus at Springer Mountain.',
      match: { kind: 'place', radius_m: 150, off_trail: false, places: [SPRINGER] },
    },
    {
      id: 'mcafee-knob',
      section: 'experience',
      title:
        'Take the McAfee Knob shuttle to hike to one of the most photographed spots on the A.T.',
      match: { kind: 'place', radius_m: 150, off_trail: false, places: [MCAFEE] },
    },
    {
      id: 'virginia-triple-crown',
      section: 'experience',
      title:
        'Hike the “Triple Crown” of Virginia: McAfee Knob, Tinker Cliffs, and Dragon’s Tooth.',
      match: {
        kind: 'places_all',
        radius_m: 150,
        off_trail: false,
        places: [DRAGONS_TOOTH, MCAFEE, TINKER],
      },
    },
    {
      id: 'shelter-logbook',
      section: 'experience',
      title: 'Hike to an A.T. shelter and sign the shelter logbook.',
      match: { kind: 'poi_type', type: 'shelter', radius_m: 60 },
    },
    {
      id: 'summit-4000',
      section: 'experience',
      title: 'Summit a 4,000+ foot peak.',
      match: { kind: 'elevation_min_ft', value: 4000 },
    },
    {
      id: 'katahdin',
      section: 'experience',
      title: 'Hike to the A.T.’s northern terminus at Katahdin.',
      match: { kind: 'place', radius_m: 150, off_trail: false, places: [KATAHDIN] },
    },
    {
      id: 'white-blaze-photo',
      section: 'experience',
      title: 'Take a photo of a white blaze.',
      match: { kind: 'self_report' },
    },
    {
      id: 'trail-crew',
      section: 'protect',
      title: 'Join a Trail Crew.',
      match: { kind: 'workday', org: null, trail: 'AT' },
    },
    {
      id: 'pick-up-litter',
      section: 'protect',
      title: 'Pick up litter on a hike.',
      match: { kind: 'self_report' },
    },
    {
      id: 'mystery-1',
      section: 'mystery',
      title: null,
      sealed_title: btoa('Watch the sun set from Jefferson Rock.'),
      mystery: { number: 1, reveal_on: '2027-07-20' },
      match: { kind: 'self_report' },
    },
    {
      id: 'mystery-2',
      section: 'mystery',
      title: null,
      mystery: { number: 2, reveal_on: null },
      match: { kind: 'self_report' },
    },
  ],
  reviewed: '2026-09-30',
}

/** Invented for tests: a club's record with no finish and no reward. */
export const RECORD_ARTIFACT = {
  id: 'test-roanoke-three-peaks',
  org: 'rac',
  org_name: 'Roanoke A.T. Club',
  org_short: 'RATC',
  trail: 'AT',
  name: 'Three Roanoke peaks (test)',
  status: 'published',
  window: { opens: null, closes: null },
  finish: null,
  reward: null,
  sections: [{ id: 'peaks', title: 'Peaks', short: 'Peaks' }],
  items: [
    {
      id: 'dragons-tooth',
      section: 'peaks',
      title: 'Dragon’s Tooth',
      match: { kind: 'place', radius_m: 150, off_trail: false, places: [DRAGONS_TOOTH] },
    },
    {
      id: 'mcafee',
      section: 'peaks',
      title: 'McAfee Knob',
      match: { kind: 'place', radius_m: 150, off_trail: false, places: [MCAFEE] },
    },
    {
      id: 'tinker',
      section: 'peaks',
      title: 'Tinker Cliffs',
      match: { kind: 'place', radius_m: 150, off_trail: false, places: [TINKER] },
    },
  ],
  reviewed: '2026-09-30',
}

export const CHALLENGES_DOCUMENT = {
  source: 'reference/challenges',
  challenges: [ATC_ARTIFACT, RECORD_ARTIFACT],
}

export const FIXTURE_CHALLENGES: readonly Challenge[] =
  parseChallenges(CHALLENGES_DOCUMENT)
export const ATC_CHALLENGE: Challenge = FIXTURE_CHALLENGES[0]
export const RECORD_CHALLENGE: Challenge = FIXTURE_CHALLENGES[1]
