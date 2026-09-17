/**
 * Central Park Throughikers - a whole published organization to walk through.
 *
 * **THE ORG IS INVENTED. THE GROUND IS NOT.** Every coordinate below is WGS84
 * lat/lon for the real place: the park's four surveyed corners (110th/CPW,
 * 110th/5th, 59th/5th, 59th/CPW), the Reservoir, the Ramble, the Bridle Path,
 * the North Woods. The Throughikers, their people, their hours and their
 * reports are made up so somebody can look around without signing anything.
 * The real park is maintained by the Central Park Conservancy, who have
 * nothing to do with this.
 *
 * WHY THIS FILE EXISTS AT ALL, rather than the demo being a deployment with
 * seeded rows. #600 owns standing up the production backend and nobody has,
 * so a demo that needed one would be a demo nobody could open - and the
 * design's whole argument for the demo is that a trails chair should see what
 * their own pages look like BEFORE they type anything. This is what lets that
 * be true today.
 *
 * **EVERY NUMBER HERE IS @unvalidated except the coordinates**, and most are
 * invented outright: 29 volunteers, 13.8 miles, the hours, the thanks. They
 * exist to make a layout dense enough to judge. The design says so and this
 * file says so, because a demo whose figures leak into a screenshot and then
 * into a claim is how an invented number becomes a fact about a product.
 *
 * The one real field set is the Hike Finder's, which comes from
 * [#1427](https://github.com/OurHike/OurHike/issues/1427)'s measured export of
 * NYNJTC's hike list - twelve labelled fields on every detail page.
 */

import type { FinderHike } from './components'
import type { AssistConsent, Org, OrgPark, OrgRole, RosterEntry, Workday } from './orgApi'

export const DEMO_SLUG = 'central-park-throughikers'

function line(points: readonly (readonly [number, number])[]): string {
  // GeoJSON is [lon, lat]. The source coordinates below are written [lat, lon]
  // because that is how a person reads a place off a map, and getting the two
  // the wrong way round is the classic way to put a trail in the Indian Ocean.
  return JSON.stringify({
    type: 'LineString',
    coordinates: points.map(([lat, lon]) => [lon, lat]),
  })
}

/** An ellipse of `steps` points around a centre, for the Reservoir. */
function ring(
  centre: readonly [number, number],
  dLat: number,
  dLon: number,
  steps = 36,
): [number, number][] {
  const out: [number, number][] = []
  for (let i = 0; i <= steps; i += 1) {
    const angle = (i / steps) * Math.PI * 2
    out.push([centre[0] + dLat * Math.cos(angle), centre[1] + dLon * Math.sin(angle)])
  }
  return out
}

/** The park's own outline, from its four surveyed corners. */
export const DEMO_PARK_OUTLINE: readonly (readonly [number, number])[] = [
  [40.80078, -73.95818],
  [40.80028, -73.94991],
  [40.76461, -73.97303],
  [40.76802, -73.9818],
]

export const DEMO_ORG: Org = {
  id: 'demo-central-park-throughikers',
  slug: DEMO_SLUG,
  name: 'Central Park Throughikers',
  region: 'New York, NY',
  domain: 'cpthroughikers.example',
  website: 'https://cpthroughikers.example',
  verified_by: 'email',
  state: 'claimed',
  membership_url: 'https://cpthroughikers.example/join',
  donation_url: 'https://cpthroughikers.example/give',
  created_at: '2026-03-02T09:00:00Z',
  // The demo organization has agreed, so the three assist panels draw the way
  // the wireframes show them rather than drawing their own refusal. `false` is
  // what every real organization starts at - the server defaults to it and
  // `POST /assist` answers 409 until an admin turns it on in Settings.
  assist_opted_in: true,
  admins: [
    {
      id: 'demo-admin-1',
      person_id: 'demo-person-sam',
      title: 'Trails chair',
      is_codeowner: true,
      invited_at: '2026-03-01T09:00:00Z',
      approved_at: '2026-03-01T09:12:00Z',
      declined_at: null,
      decline_reason: null,
    },
    {
      id: 'demo-admin-2',
      person_id: 'demo-person-noor',
      title: 'Crew lead',
      is_codeowner: true,
      invited_at: '2026-03-01T09:00:00Z',
      approved_at: '2026-03-01T18:40:00Z',
      declined_at: null,
      decline_reason: null,
    },
    {
      id: 'demo-admin-3',
      person_id: 'demo-person-wes',
      title: 'Secretary',
      is_codeowner: true,
      invited_at: '2026-03-01T09:00:00Z',
      approved_at: null,
      declined_at: null,
      decline_reason: null,
    },
  ],
}

/**
 * Who turned the demo organization's assistant on, and when.
 *
 * Invented like every other date in this file, and written as a fixed ISO
 * timestamp for the same reason the admins' `invited_at` is: a demo that
 * moved every time somebody opened it would make a screenshot impossible to
 * compare with the last one. `opted_in_by` is Sam Ortiz's id, who is in
 * DEMO_ROSTER, so Settings resolves a name rather than printing an id at
 * somebody.
 */
export const demoAssistConsent: AssistConsent = {
  opted_in: true,
  opted_in_at: '2026-08-19T15:40:00Z',
  opted_in_by: 'demo-person-sam',
  opted_out_at: null,
}

const SECTIONS: readonly {
  id: string
  name: string
  from: string
  to: string
  miles: number
  region: string
  points: readonly (readonly [number, number])[]
}[] = [
  {
    id: 'demo-sec-drive',
    name: 'Park Drive loop',
    from: 'Engineers Gate',
    to: 'Engineers Gate',
    miles: 6.1,
    region: 'The loop',
    points: [
      [40.79985, -73.9579],
      [40.7994, -73.9506],
      [40.789, -73.9584],
      [40.776, -73.9678],
      [40.7662, -73.9733],
      [40.7686, -73.9806],
      [40.779, -73.9734],
      [40.788, -73.967],
      [40.794, -73.9618],
      [40.79985, -73.9579],
    ],
  },
  {
    id: 'demo-sec-reservoir',
    name: 'Reservoir loop',
    from: 'South Gate House',
    to: 'South Gate House',
    miles: 1.58,
    region: 'The loop',
    points: ring([40.78565, -73.96235], 0.00415, 0.00345),
  },
  {
    id: 'demo-sec-bridle',
    name: 'Bridle Path · west',
    from: 'W 79th entrance',
    to: 'W 96th entrance',
    miles: 2.4,
    region: 'West side',
    points: [
      [40.7772, -73.9753],
      [40.781, -73.9716],
      [40.7845, -73.9683],
      [40.788, -73.9656],
    ],
  },
  {
    id: 'demo-sec-ramble',
    name: 'The Ramble',
    from: 'Bow Bridge',
    to: 'Belvedere path',
    miles: 1.2,
    region: 'Mid-park',
    points: [
      [40.7763, -73.9718],
      [40.7772, -73.9706],
      [40.778, -73.9711],
      [40.7785, -73.9698],
      [40.7776, -73.969],
      [40.7766, -73.9702],
      [40.7763, -73.9718],
    ],
  },
  {
    id: 'demo-sec-northwoods',
    name: 'North Woods & the Loch',
    from: 'The Pool',
    to: 'Harlem Meer',
    miles: 1.7,
    region: 'North end',
    points: [
      [40.7938, -73.959],
      [40.7948, -73.9568],
      [40.796, -73.9548],
      [40.7968, -73.9524],
    ],
  },
  {
    id: 'demo-sec-mall',
    name: 'The Mall',
    from: 'Literary Walk',
    to: 'Bethesda Terrace',
    miles: 0.8,
    region: 'Mid-park',
    points: [
      [40.7717, -73.9736],
      [40.7729, -73.9723],
      [40.774, -73.9712],
    ],
  },
]

/** The demo's registry, in the same three tiers a real org's arrives in.
 *
 *  One park with one trail per route rather than a deeper tree, because
 *  Central Park is one park - the top tier being thin is the design's own
 *  example of thin-without-being-wrong.
 */
export const DEMO_REGISTRY: OrgPark[] = [
  {
    id: 'demo-park',
    club_id: DEMO_ORG.id,
    name: 'Central Park',
    kind: 'park',
    created_at: DEMO_ORG.created_at,
    trails: SECTIONS.map((section, index) => ({
      id: `demo-trail-${section.id}`,
      park_id: 'demo-park',
      name: section.name,
      blaze_value_raw:
        ['Blue', 'Red', 'Yellow', 'Green', 'Purple', 'Teal'][index] ?? null,
      blaze_mapped: ['blue', 'red', 'yellow', 'green', null, null][index] ?? null,
      miles: section.miles,
      sections: [
        {
          id: section.id,
          trail_id: `demo-trail-${section.id}`,
          name: section.name,
          start_anchor: section.from,
          end_anchor: section.to,
          start_mile: null,
          end_mile: null,
          miles: section.miles,
          region: section.region,
          geometry: line(section.points),
        },
      ],
    })),
  },
]

export const DEMO_ROLES: OrgRole[] = [
  {
    id: 'demo-role-chair',
    club_id: DEMO_ORG.id,
    name: 'Trails chair',
    category: 'trail_maintenance',
    reports_to_role_id: null,
    section_id: null,
    required: false,
    required_by: null,
    retired_at: null,
  },
  {
    id: 'demo-role-maintainer',
    club_id: DEMO_ORG.id,
    name: 'Path maintainer',
    category: 'trail_maintenance',
    reports_to_role_id: 'demo-role-chair',
    section_id: null,
    required: false,
    required_by: null,
    retired_at: null,
  },
  {
    id: 'demo-role-steward',
    club_id: DEMO_ORG.id,
    name: 'Way-marking steward',
    category: 'stewards',
    reports_to_role_id: 'demo-role-chair',
    section_id: null,
    required: false,
    required_by: null,
    retired_at: null,
  },
  {
    id: 'demo-role-invasives',
    club_id: DEMO_ORG.id,
    name: 'Invasives surveyor',
    category: 'environmental',
    reports_to_role_id: 'demo-role-chair',
    section_id: null,
    required: true,
    required_by: 'NYC Parks',
    retired_at: null,
  },
]

export const DEMO_ROSTER: RosterEntry[] = [
  {
    person_id: 'demo-person-sam',
    email: null,
    display_name: 'Sam',
    full_name: 'Sam Ortiz',
    roles: ['Trails chair', 'Path maintainer'],
    sections: ['The Ramble'],
    pending_invite: false,
  },
  {
    person_id: 'demo-person-noor',
    email: null,
    display_name: 'Noor',
    full_name: 'Noor Haddad',
    roles: ['Path maintainer'],
    sections: ['Park Drive loop'],
    pending_invite: false,
  },
  {
    person_id: 'demo-person-wes',
    email: null,
    display_name: null,
    full_name: 'Wes Hartley',
    roles: ['Way-marking steward'],
    sections: ['Reservoir loop'],
    pending_invite: false,
  },
  {
    person_id: null,
    email: 'dana@cpthroughikers.example',
    display_name: null,
    full_name: 'Dana Liu',
    roles: ['Path maintainer'],
    sections: [],
    pending_invite: true,
  },
  {
    person_id: null,
    email: 'priya@cpthroughikers.example',
    display_name: null,
    full_name: 'Priya Raghavan',
    roles: [],
    sections: [],
    pending_invite: true,
  },
]

function inDays(days: number): string {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

export const DEMO_WORKDAYS: Workday[] = [
  {
    id: 'demo-wd-1',
    club_id: DEMO_ORG.id,
    title: 'Ramble path edging',
    description:
      'Cutting back the edges on the unsigned paths. Tools provided; bring gloves.',
    starts_on: inDays(6),
    ends_on: inDays(6),
    meet_point: 'Bow Bridge, 9am',
    mile: null,
    lat: 40.7763,
    lon: -73.9718,
    status: 'upcoming',
    cap: 12,
    source: 'ourhike',
    signup_mode: 'in_app',
    signup_contact: null,
    signup_url: null,
    interested_count: 7,
    confirmed_count: 5,
  },
  {
    id: 'demo-wd-2',
    club_id: DEMO_ORG.id,
    title: 'North Woods storm sweep',
    description: 'Clearing what came down in the Ravine. Sawyers only for the big stuff.',
    starts_on: inDays(13),
    ends_on: inDays(14),
    meet_point: 'The Pool, 8:30am',
    mile: null,
    lat: 40.7938,
    lon: -73.959,
    status: 'upcoming',
    cap: null,
    source: 'ourhike',
    signup_mode: 'in_app',
    signup_contact: null,
    signup_url: null,
    interested_count: 3,
    confirmed_count: 1,
  },
  {
    id: 'demo-wd-3',
    club_id: DEMO_ORG.id,
    title: 'Monthly Reservoir walk-through',
    description:
      'On their own calendar. Signup goes to the Throughikers, not to OurHike.',
    starts_on: inDays(20),
    ends_on: inDays(20),
    meet_point: 'South Gate House, 10am',
    mile: null,
    lat: 40.7822,
    lon: -73.9624,
    status: 'upcoming',
    cap: null,
    source: 'mirrored',
    signup_mode: 'contact',
    signup_contact: null,
    signup_url: 'https://cpthroughikers.example/volunteer',
    interested_count: 0,
    confirmed_count: 0,
  },
]

/** The Hike Finder's field set, which is #1427's measured one. */
export const DEMO_HIKES: FinderHike[] = [
  {
    id: 'demo-hike-reservoir',
    name: 'Reservoir loop',
    features: 'Skyline · Water',
    park: 'Central Park',
    region: 'The loop',
    miles: 1.58,
    time: '0:35',
    route: 'Loop',
    difficulty: 'Easy',
  },
  {
    id: 'demo-hike-ramble',
    name: 'The Ramble wander',
    features: 'Woodland · Unsigned',
    park: 'Central Park',
    region: 'Mid-park',
    miles: 1.2,
    time: '0:40',
    route: 'Loop',
    difficulty: 'Moderate',
  },
  {
    id: 'demo-hike-northwoods',
    name: 'North Woods & the Loch',
    features: 'Waterfall · Steep steps',
    park: 'Central Park',
    region: 'North end',
    miles: 1.7,
    time: '0:55',
    route: 'Out and back',
    difficulty: 'Moderate',
  },
  {
    id: 'demo-hike-drive',
    name: 'Full Park Drive loop',
    features: 'Views · Historic',
    park: 'Central Park',
    region: 'The loop',
    miles: 6.1,
    time: '2:10',
    route: 'Loop',
    difficulty: 'Strenuous',
  },
  {
    id: 'demo-hike-mall',
    name: 'The Mall and Bethesda',
    features: 'Historic · Shade',
    park: 'Central Park',
    region: 'Mid-park',
    miles: 0.8,
    time: '0:25',
    route: 'Point to point',
    difficulty: 'Easy',
  },
  {
    id: 'demo-hike-bridle',
    name: 'Bridle Path west',
    features: 'Soft surface · Shade',
    park: 'Central Park',
    region: 'West side',
    miles: 2.4,
    time: '0:50',
    route: 'Point to point',
    difficulty: 'Easy',
  },
]

export const DEMO_SECTIONS = DEMO_REGISTRY[0].trails.flatMap((trail) => trail.sections)

/** Which sections nobody currently holds. Matches DEMO_ROSTER. */
export const DEMO_COVERED = new Set([
  'demo-sec-ramble',
  'demo-sec-drive',
  'demo-sec-reservoir',
])

/**
 * A trail the demo organization is proposing to add, as a registry fragment.
 *
 * WHY THIS EXISTS AT ALL. Add-a-trail's whole content - the diff, the map, the
 * "existing sections changed: 0" tile - is behind a read, so the screen with
 * nothing read is an empty state and that is all anybody looking at the demo
 * ever saw. A screen whose argument nobody can reach has not been shown.
 *
 * The North Meadow paths are real ground in the same park, at the same
 * @unvalidated standard as everything else here: the coordinates are the
 * place, the mileages are invented to make a diff worth reading.
 */
export const DEMO_PROPOSED: OrgPark[] = [
  {
    id: 'demo-park-proposed',
    club_id: DEMO_ORG.id,
    name: 'Central Park',
    kind: 'park',
    created_at: '2026-03-01T00:00:00Z',
    trails: [
      {
        id: 'demo-trail-north-meadow',
        park_id: 'demo-park-proposed',
        name: 'North Meadow paths',
        blaze_value_raw: 'GRN',
        blaze_mapped: 'Green',
        miles: 2.2,
        sections: [
          {
            id: 'demo-sec-north-meadow',
            trail_id: 'demo-trail-north-meadow',
            name: 'North Meadow loop',
            start_anchor: 'W 97th entrance',
            end_anchor: 'W 97th entrance',
            start_mile: 0,
            end_mile: 1.4,
            miles: 1.4,
            region: 'North end',
            geometry: line([
              [40.79449, -73.9589],
              [40.79661, -73.95672],
              [40.79535, -73.95398],
              [40.79312, -73.95633],
              [40.79449, -73.9589],
            ]),
          },
          {
            id: 'demo-sec-pool-path',
            trail_id: 'demo-trail-north-meadow',
            name: 'The Pool path',
            start_anchor: 'W 100th entrance',
            end_anchor: 'The Loch',
            start_mile: 0,
            end_mile: 0.8,
            miles: 0.8,
            region: 'North end',
            geometry: line([
              [40.79704, -73.9601],
              [40.79821, -73.95826],
              [40.79879, -73.9566],
            ]),
          },
        ],
      },
    ],
  },
]

export function isDemoOrg(slug: string): boolean {
  return slug === DEMO_SLUG
}
