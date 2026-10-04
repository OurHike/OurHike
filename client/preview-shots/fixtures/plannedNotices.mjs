// Fixtures for planned-hike-notices.mjs (#1805, decisions 66, 67 and 76): a
// long hike and two day hikes planned in the next 7 days, a
// conditions/notices.json holding notices that touch them and notices that do
// not, the conditions/notice_states.json a state-wide notice is placed by, and
// the steward list that names each organization.
//
// NOBODY'S DATA, AND NO ORGANIZATION'S REAL NOTICE. Every notice here is
// invented and its title says "(example)": a shot on every future pull
// request must never put words in a real club's mouth. The organizations are
// real registry entries, named from the steward list as the app names them
// (features/ORG_NOTICES.md §6), so the frame shows the attribution a hiker
// would read. The hikes are the existing fixtures' (fixtures/longHike.mjs,
// fixtures/dayHike.mjs), dated around the browser's own today at seed time
// for the reason longHike.mjs gives: the window moves with the app's clock.
//
// WHAT THE FRAME SHOULD SHOW, against the rule lib/plannedNotices.ts holds:
//
//  - the long hike's stretch (Neels Gap to Dicks Creek Gap, today and
//    tomorrow) with ATC's closure at mile 50.3, inside it;
//  - the day hike (Pine Meadow loop, in two days) with the hunting area its
//    route crosses, as an Advisory, and NYNJTC's unplaced notice, because the
//    loop walks the Long Path NYNJTC maintains;
//  - an invented day hike on BLM's trails in Utah (Canyon rim loop, today)
//    with BLM's invented state-wide Utah notice, its where line reading "All
//    of Utah" (decision 76): an agency's unplaced notice placed by its state;
//  - and NOT the far club's notice or the shooting site 2 degrees away: a
//    notice that touches no planned hike is not in the panel.
//
// THE STATE'S SHAPE IS A BOX, not Utah's: the panel never draws it, and a
// fixture holds no upstream's data (CONTRIBUTING.md, "Data does not go in
// commits"). Its edge is a degree and more from the invented hike, well past
// the 500 m margin the rule holds a route to.
//
// Not a recipe: shared fixtures live one directory down, where the runner's
// recipe glob does not reach (fixtures/suggestedHikes.mjs explains).

import { DAY_HIKES } from './dayHike.mjs'
import { STEWARDS_DOCUMENT } from './stewards.mjs'

/** The browser's local ISO day `offset` days from now - the same machine as
 *  the browser, so the same zone. */
function localDay(offset) {
  const at = new Date(Date.now() + offset * 86_400_000)
  const pad = (value) => String(value).padStart(2, '0')
  return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`
}

/** The steward list, with the registry keys these notices are published
 *  under added to the organizations that own them, and NY Parks, whose
 *  hunting area it is. */
export function plannedNoticeStewards() {
  const stewards = STEWARDS_DOCUMENT.stewards.map((steward) => {
    if (steward.provider === 'ATC') {
      return { ...steward, keys: [...steward.keys, 'atc_trail_updates'] }
    }
    if (steward.provider === 'NYNJTC') {
      return { ...steward, keys: [...steward.keys, 'nynjtc_trail_alerts'] }
    }
    return steward
  })
  stewards.push({
    provider: 'BLM',
    name: 'Bureau of Land Management',
    trust: 'authoritative',
    licence: null,
    attribution: null,
    terms: null,
    terms_source: null,
    layers: ['BLM trails', 'BLM Utah fire restrictions'],
    keys: ['blm_trails', 'blm_fire_restrictions_utah', 'blm_shooting_points'],
    support: null,
    store: null,
    steward_id: 'org:blm',
  })
  stewards.push({
    provider: 'NYS OPRHP',
    name: 'New York State Office of Parks, Recreation and Historic Preservation',
    trust: 'authoritative',
    licence: null,
    attribution: null,
    terms: null,
    terms_source: null,
    layers: ['NY State Parks hunting areas', 'NYS Parks trails'],
    keys: ['oprhp_hunting_areas', 'oprhp_trails'],
    support: null,
    store: null,
    steward_id: 'org:nysoprhp',
  })
  return { stewards }
}

/** An invented day hike on BLM's trails in Utah, planned for today: two
 *  taps a few miles apart, nobody's route and nobody's location fix. */
const CANYON_RIM_LOOP = {
  id: 'preview-fixture-blm',
  name: 'Canyon rim loop (example)',
  segments: [
    [
      { coord: [-109.4, 38.7], poiId: null },
      { coord: [-109.36, 38.72], poiId: null },
    ],
  ],
  figures: {
    miles: 5.2,
    legs: [
      {
        name: 'Canyon Rim Trail (example)',
        source: 'blm_trails',
        blaze_color: null,
        miles: 5.2,
      },
    ],
  },
  looped: true,
  recorded: 'planned',
}

/** The Pine Meadow loop, planned two days from today, and the Canyon rim
 *  loop, today. */
export function plannedDayHikes() {
  return {
    ...DAY_HIKES,
    hikes: [
      ...DAY_HIKES.hikes.map((hike) => ({ ...hike, date: localDay(2) })),
      { ...CANYON_RIM_LOOP, date: localDay(0) },
    ],
  }
}

function row(fields) {
  return {
    club: null,
    category: null,
    locality: '',
    hazard: null,
    obstructs_trail: false,
    starts_on: null,
    ends_on: null,
    updated_at: new Date(Date.now() - 2 * 86_400_000).toISOString().slice(0, 19) + 'Z',
    checked_at: new Date(Date.now() - 3_600_000).toISOString().slice(0, 19) + 'Z',
    first_seen_at: null,
    changed_at: null,
    carried_since: null,
    source_url: null,
    review_state: 'unreviewed',
    ...fields,
  }
}

/** conditions/notices.json, in the shape pub_conditions_notices writes. */
export function noticesDocument() {
  return {
    generated_at: new Date(Date.now() - 3_600_000).toISOString().slice(0, 19) + 'Z',
    notices: [
      row({
        notice_id: 'atc_trail_updates:example-footbridge-out',
        source_key: 'atc_trail_updates',
        club: 'atc',
        provider: 'ATC',
        title: 'Footbridge out below Tray Mountain (example)',
        category: 'Closure',
        locality: 'GA',
        place: { kind: 'at_miles', start: 50.3, end: 50.3 },
        obstructs_trail: true,
        review_state: 'reviewed',
        source_url: 'https://appalachiantrail.org/trail-updates/',
      }),
      row({
        notice_id: 'oprhp_hunting_areas:example',
        source_key: 'oprhp_hunting_areas',
        club: 'nysparks',
        provider: 'NYS OPRHP',
        title: 'Pine Meadow hunting area (example)',
        category: 'Hunting area',
        locality: 'Harriman State Park',
        hazard: 'hunting',
        place: {
          kind: 'geometry',
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [-74.093, 41.246],
                [-74.087, 41.246],
                [-74.087, 41.254],
                [-74.093, 41.254],
                [-74.093, 41.246],
              ],
            ],
          },
        },
        source_url: 'https://parks.ny.gov/',
      }),
      row({
        notice_id: 'nynjtc_trail_alerts:example-long-path-trail-work',
        source_key: 'nynjtc_trail_alerts',
        club: 'nynjtc',
        provider: 'NYNJTC',
        title: 'Trail work on the Long Path this weekend (example)',
        locality: 'Harriman-Bear Mountain',
        place: { kind: 'org_terms', terms: ['trail:long-path'] },
        source_url: 'https://www.nynjtc.org/trail-alerts/',
      }),
      row({
        notice_id: 'blm_fire_restrictions_utah:example',
        source_key: 'blm_fire_restrictions_utah',
        club: 'blm',
        provider: 'BLM',
        steward_kind: 'agency',
        title: 'Stage 1 fire restrictions on BLM land in Utah (example)',
        place: { kind: 'unplaced' },
        states: ['UT'],
        source_url:
          'https://www.blm.gov/programs/fire/regional-info/utah/fire-restrictions',
      }),
      row({
        notice_id: 'faraway_trail_club:example',
        source_key: 'faraway_trail_club',
        club: 'faraway',
        provider: 'Faraway Trail Club',
        title: 'A notice from a club on no planned hike (example)',
        place: { kind: 'unplaced' },
      }),
      row({
        notice_id: 'blm_shooting_points:example',
        source_key: 'blm_shooting_points',
        club: 'blm',
        provider: 'BLM',
        title: 'A shooting site far from any planned hike (example)',
        hazard: 'shooting',
        place: {
          kind: 'geometry',
          geometry: { type: 'Point', coordinates: [-112.0, 40.5] },
        },
      }),
    ],
  }
}

/** conditions/notice_states.json, in the shape pub_conditions_notice_states
 *  writes: one invented box standing in for Utah (the header says why). */
export function noticeStatesDocument() {
  return {
    generated_at: '2026-10-01T06:00:00Z',
    states: [
      {
        state: 'UT',
        name: 'Utah',
        edge_margin_m: 500,
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [-114, 37],
              [-109, 37],
              [-109, 42],
              [-114, 42],
              [-114, 37],
            ],
          ],
        },
      },
    ],
  }
}

/**
 * Answer conditions/notices.json and conditions/notice_states.json on the
 * wire, before the app loads. A pattern on the key and not the whole URL, because the bucket
 * and the environment folder in front of it are the build's business.
 *
 * @param {import('@playwright/test').Page} page
 */
export async function routePlannedNotices(page) {
  await page.route(/\/conditions\/notices\.json(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(noticesDocument()),
    }),
  )
  await page.route(/\/conditions\/notice_states\.json(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(noticeStatesDocument()),
    }),
  )
}
