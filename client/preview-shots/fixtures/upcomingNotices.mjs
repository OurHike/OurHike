// Fixtures for planned-hike-notices-upcoming.mjs (P3, the maintainer's frame
// B, poll of 2026-10-11): one invented day hike planned four days from today,
// and a conditions/notices.json holding four invented notices on its route -
// a closure in force, a closure starting tomorrow, an ordinary notice, and a
// closure starting in three days.
//
// NOBODY'S DATA, NO ORGANIZATION'S NOTICE, AND NO REAL ORGANIZATION. Every
// organization is invented as well as every notice, as on the frame the
// maintainer chose from, so a shot on every future pull request never puts a
// closure in a real club's mouth. The hike is two invented taps in the Utah
// desert, with no account and no location fix.
//
// DATED AROUND THE BROWSER'S OWN TODAY at seed time, for the reason
// fixtures/longHike.mjs gives: the phone judges `starts_on` against its own
// calendar, so a fixed date would have started every closure here the week
// after this was written.
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

/** An ISO stamp `hours` hours ago, as a club's edit stamp reads in the file:
 *  always in the past, so no row is an edit from the future. */
function hoursAgo(hours) {
  return new Date(Date.now() - hours * 3_600_000).toISOString().slice(0, 19) + 'Z'
}

/** The three invented organizations, in the shape stewards.json has on the
 *  wire (lib/stewards.ts parses it as it parses a download). */
export function upcomingStewards() {
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
      steward('ETC', 'Example Trail Club', ['example_trail_club_closures']),
      steward('ESP', 'Example State Parks', ['example_state_parks_closures']),
    ],
  }
}

/** One invented day hike, planned four days from today: two taps a few
 *  miles apart in the Utah desert, on an invented county trail. */
export function upcomingDayHikes() {
  return {
    hikes: [
      {
        id: 'preview-fixture-upcoming',
        name: 'Example Creek loop (example)',
        date: localDay(4),
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
              name: 'Example Creek Trail (example)',
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
    checked_at: hoursAgo(1),
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
export function upcomingNoticesDocument() {
  return {
    generated_at: hoursAgo(1),
    notices: [
      // In force: no start, edited yesterday, so its 90 days run well past
      // the hike.
      row({
        notice_id: 'example_county_parks_alerts:bridge',
        source_key: 'example_county_parks_alerts',
        provider: 'ECP',
        title: 'Bridge out at Mill Creek (example)',
        place: onRoute(0.25),
        updated_at: hoursAgo(26),
        current_until: localDay(89),
      }),
      // Starts tomorrow, so today is the day before its start: it already
      // closes the trail and sorts with the closures, still tagged with its
      // start. Edited five days ago, so after the bridge in force.
      row({
        notice_id: 'example_trail_club_closures:footbridge',
        source_key: 'example_trail_club_closures',
        provider: 'ETC',
        title: 'Rim Trail closed for footbridge repair (example)',
        place: onRoute(0.5),
        starts_on: localDay(1),
        ends_on: localDay(12),
        updated_at: hoursAgo(5 * 24),
        current_until: localDay(12),
      }),
      // An ordinary notice, which no start holds: the row the closure below
      // sorts after while it does not close the trail, and before which it
      // would sort if it counted as a closure today.
      row({
        notice_id: 'example_county_parks_alerts:trail-work',
        source_key: 'example_county_parks_alerts',
        provider: 'ECP',
        title: 'Trail crew on the Example Creek Trail this week (example)',
        place: onRoute(0.6),
        obstructs_trail: false,
        updated_at: hoursAgo(3),
        current_until: localDay(90),
      }),
      // Frame B's row: starts in three days, and does not close the trail
      // until the day before, so it sorts after the ordinary notice above.
      // Only a start, as on the frame - so its row names its club with no
      // edit date, and the pipeline gives it no current_until; before its
      // start it is current all the same.
      row({
        notice_id: 'example_state_parks_closures:emergency',
        source_key: 'example_state_parks_closures',
        provider: 'ESP',
        title: 'Emergency closure, Example Creek Trail (example)',
        place: onRoute(0.75),
        starts_on: localDay(3),
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
export async function routeUpcomingNotices(page) {
  await page.route(/\/conditions\/notices\.json(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(upcomingNoticesDocument()),
    }),
  )
  await page.route(/\/conditions\/notice_states\.json(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ generated_at: hoursAgo(1), states: [] }),
    }),
  )
}
