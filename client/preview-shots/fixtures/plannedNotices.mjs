// Fixtures for planned-hike-notices.mjs (#1805, decision 66 and 67): a long
// hike and a day hike planned in the next 7 days, a conditions/notices.json
// holding notices that touch them and notices that do not, and the steward
// list that names each organization.
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
//  - and NOT the far club's notice or the shooting site 2 degrees away: a
//    notice that touches no planned hike is not in the panel.
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

/** The Pine Meadow loop, planned two days from today. */
export function plannedDayHikes() {
  return {
    ...DAY_HIKES,
    hikes: DAY_HIKES.hikes.map((hike) => ({ ...hike, date: localDay(2) })),
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

/**
 * Answer conditions/notices.json and stewards.json on the wire, before the
 * app loads. A pattern on the key and not the whole URL, because the bucket
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
}
