// Fixtures for planned-hike-notices-not-current.mjs (#1805, the maintainer's
// frame A, poll of 2026-10-10): one invented day hike planned for today, and
// a conditions/notices.json holding four invented notices on its route - one
// that reads as current and three that may no longer apply, each for a
// different reason the pipeline's `current_until` gives
// (pipeline/dbt/macros/notice_current_until.sql).
//
// NOBODY'S DATA, NO ORGANIZATION'S NOTICE, AND NO REAL ORGANIZATION. Every
// organization here is invented as well as every notice, as on the frame the
// maintainer chose from ("Example County Parks", "Example City Parks",
// "Example Trail Alliance", "Example National Forest"), so a shot on every
// future pull request never puts a stale closure in a real club's mouth. The
// hike is two invented taps in the Utah desert, today, with no account and
// no location fix.
//
// DATED AROUND THE BROWSER'S OWN TODAY at seed time, for the reason
// fixtures/longHike.mjs gives: the phone judges `current_until` against its
// own calendar, so a fixed date would grey the "current" row the week after
// this was written.
//
// Not a recipe: shared fixtures live one directory down, where the runner's
// recipe glob does not reach (fixtures/suggestedHikes.mjs explains).

/** The browser's local ISO day `offset` days from now - the same machine as
 *  the browser, so the same zone. */
function localDay(offset) {
  const at = new Date(Date.now() + offset * 86_400_000)
  const pad = (value) => String(value).padStart(2, '0')
  return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`
}

/** An ISO stamp `offset` days from now, at noon UTC, as a club's edit stamp
 *  reads in the file. */
function stamp(offset) {
  return `${localDay(offset)}T12:00:00Z`
}

/** The four invented organizations, in the shape stewards.json has on the
 *  wire (lib/stewards.ts parses it as it parses a download). */
export function notCurrentStewards() {
  const steward = (provider, name, keys) => ({
    provider,
    name,
    trust: 'authoritative',
    licence: null,
    attribution: null,
    terms: null,
    terms_source: null,
    layers: [],
    keys,
    support: null,
    store: null,
    steward_id: `org:${provider.toLowerCase()}`,
  })
  return {
    stewards: [
      steward('ECP', 'Example County Parks', [
        'example_county_parks_alerts',
        'example_county_trails',
      ]),
      steward('ECIP', 'Example City Parks', ['example_city_parks_alerts']),
      steward('ETA', 'Example Trail Alliance', ['example_trail_alliance_closures']),
      steward('ENF', 'Example National Forest', ['example_national_forest_orders']),
    ],
  }
}

/** One invented day hike planned for today: two taps a few miles apart in
 *  the Utah desert, on an invented county trail. */
export function notCurrentDayHikes() {
  return {
    hikes: [
      {
        id: 'preview-fixture-not-current',
        name: 'Canyon rim loop (example)',
        date: localDay(0),
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
              source: 'example_county_trails',
              blaze_color: null,
              miles: 5.2,
            },
          ],
        },
        looped: true,
        recorded: 'planned',
      },
    ],
    openId: null,
  }
}

/** A point on the hike's straight line between its taps, `share` of the way
 *  along: on the route, so the notice touches it by its own place. */
function onRoute(share) {
  return {
    kind: 'geometry',
    geometry: {
      type: 'Point',
      coordinates: [-109.4 + 0.04 * share, 38.7 + 0.02 * share],
    },
  }
}

function row(fields) {
  return {
    club: 'example',
    provider: null,
    steward_kind: 'club',
    category: null,
    locality: '',
    hazard: null,
    obstructs_trail: true,
    starts_on: null,
    ends_on: null,
    updated_at: null,
    current_until: null,
    checked_at: stamp(0),
    first_seen_at: null,
    changed_at: null,
    carried_since: null,
    source_url: 'https://example.org/notice',
    review_state: 'unreviewed',
    ...fields,
  }
}

/** conditions/notices.json, in the shape pub_conditions_notices writes, with
 *  `current_until` as notice_current_until.sql would give each row. */
export function notCurrentNoticesDocument() {
  return {
    generated_at: stamp(0),
    notices: [
      // Current: edited two days ago, so its 90 days run well past today.
      row({
        notice_id: 'example_county_parks_alerts:bridge',
        source_key: 'example_county_parks_alerts',
        provider: 'ECP',
        title: 'Bridge out at Mill Creek (example)',
        place: onRoute(0.25),
        updated_at: stamp(-2),
        current_until: localDay(88),
      }),
      // Frame A's middle row: "closed for 3 to 6 months" from a start 21
      // months ago, last edited 7 months ago. Its stated 6 months ran out
      // long since; the line says when it was last reported.
      row({
        notice_id: 'example_city_parks_alerts:lower-loop',
        source_key: 'example_city_parks_alerts',
        provider: 'ECIP',
        title: 'Lower loop closed for 3 to 6 months (example)',
        place: onRoute(0.5),
        starts_on: localDay(-640),
        updated_at: stamp(-219),
        current_until: localDay(-640 + 181),
      }),
      // Frame A's last row: no date of any kind.
      row({
        notice_id: 'example_trail_alliance_closures:section-12',
        source_key: 'example_trail_alliance_closures',
        provider: 'ETA',
        title: 'Section 12 closed (example)',
        place: onRoute(0.6),
        source_url: null,
      }),
      // The case the frame did not draw: its own end date passed three days
      // ago, so it no longer closes the trail and is greyed.
      row({
        notice_id: 'example_national_forest_orders:campground',
        source_key: 'example_national_forest_orders',
        provider: 'ENF',
        steward_kind: 'agency',
        title: 'Campground closed (example)',
        place: onRoute(0.75),
        obstructs_trail: false,
        starts_on: localDay(-30),
        ends_on: localDay(-3),
        current_until: localDay(-3),
      }),
    ],
  }
}

/**
 * Answer conditions/notices.json on the wire, before the app loads, and
 * conditions/notice_states.json with no state: no notice here is state-wide.
 *
 * @param {import('@playwright/test').Page} page
 */
export async function routeNotCurrentNotices(page) {
  await page.route(/\/conditions\/notices\.json(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(notCurrentNoticesDocument()),
    }),
  )
  await page.route(/\/conditions\/notice_states\.json(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ generated_at: stamp(0), states: [] }),
    }),
  )
}
