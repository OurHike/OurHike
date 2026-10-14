// A hand-made conditions/trail_closures.json for club-closures-on-the-map.mjs
// and for the client's tests (src/lib/publishedNotices.trailClosures.test.ts
// holds every row here to the reader), written to the file's contract before
// any pipeline wrote one (the maintainer's S6, 2026-10-11):
//
//   { "generated_at": "...", "closures": [row, ...] }
//
// where each row is exactly a conditions/notices.json row - the fields
// client/src/lib/publishedNotices.ts's validNotice reads, `obstructs_trail`
// true and `hazard` null on every one - plus `shape`: "line" (the notice's
// own LineString or MultiLineString), "area" (a MultiLineString of the trail
// stretches the pipeline cut inside the area) or "point" (a Point).
//
// FOUR CLOSURES, ONE OF EACH KIND THE STANDARD DRAWS: a line, an area's cut
// stretches, a point, and a line the list greys because its source gives no
// date (lib/noticeCurrency.ts's "Its source gives no date. It may no longer
// apply."), which the map draws with the same full mark - the maintainer's
// "B: same mark".
//
// NOBODY'S DATA, NO ORGANIZATION'S NOTICE, AND NO REAL ORGANIZATION, as in
// fixtures/notCurrentNotices.mjs: every organization, source key and title is
// invented and says "(example)", so a shot on every future pull request never
// draws a closure a real steward did not publish. The geometry lies over
// farmland in Gove County, Kansas, picked to be away from the trails this map
// is about. Nobody has checked a release for lines there (@unvalidated): a
// frame that shows a trail under one of these marks shows a real trail that
// is NOT closed, under an invented closure. Over bare ground, the paper of
// each mark shows on the map itself rather than over a trail's red.
//
// DATED AROUND THE BROWSER'S OWN TODAY at seed time, for
// fixtures/notCurrentNotices.mjs's reason: the phone judges each closure's
// start and `current_until` against its own calendar.
//
// Not a recipe: shared fixtures live one directory down, where the runner's
// recipe glob does not reach (fixtures/suggestedHikes.mjs explains).

/** The camera the recipe opens on: the middle of the four closures at z13,
 *  the zoom the chain of crosses is drawn at full size from
 *  (lib/closureStyle.ts's CLOSURE_FULL_WIDTH_ZOOM). At z13 a degree of
 *  longitude is 11,651 px (512 * 2^13 / 360), so the 390 px phone canvas
 *  spans 0.033 degrees across; every closure below sits within 0.01 east or
 *  west of the centre and 0.014 north or south of it. A local frame of
 *  2026-10-14 put all four clear of the header plate and the map's buttons,
 *  once the northern line moved 0.004 south off the buttons' row. */
export const TRAIL_CLOSURES_CAMERA = { center: [-100.203, 38.756], zoom: 13 }

/** The browser's local ISO day `offset` days from now. */
function localDay(offset) {
  const at = new Date(Date.now() + offset * 86_400_000)
  const pad = (value) => String(value).padStart(2, '0')
  return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`
}

/** An ISO stamp `offset` days from now, at noon UTC. */
function stamp(offset) {
  return `${localDay(offset)}T12:00:00Z`
}

function row(fields) {
  return {
    club: 'example',
    provider: null,
    steward_kind: 'agency',
    category: null,
    starts_on: null,
    ends_on: null,
    current_until: null,
    updated_at: null,
    checked_at: stamp(0),
    first_seen_at: stamp(-20),
    changed_at: stamp(-20),
    carried_since: null,
    source_url: 'https://example.org/closures',
    review_state: 'unreviewed',
    obstructs_trail: true,
    hazard: null,
    locality: '',
    ...fields,
  }
}

function geometry(value) {
  return { kind: 'geometry', geometry: value }
}

/** The four closures, keyed by the kind each stands for, so a test can name
 *  the one it means. */
export function trailClosureRows() {
  return {
    // A line closure, in force: its own line, from twelve days ago to twenty
    // days ahead.
    line: row({
      notice_id: 'example_forest_closures:ridge-trail-fire',
      source_key: 'example_forest_closures',
      provider: 'ENF',
      title: 'Example Ridge Trail fire closure (example)',
      category: 'Closure Order',
      starts_on: localDay(-12),
      ends_on: localDay(20),
      current_until: localDay(20),
      updated_at: stamp(-2),
      locality: 'Example Ranger District',
      place: geometry({
        type: 'LineString',
        coordinates: [
          [-100.213, 38.765],
          [-100.208, 38.7665],
          [-100.203, 38.766],
          [-100.198, 38.7675],
          [-100.193, 38.768],
        ],
      }),
      shape: 'line',
    }),
    // An area closure: a park shut by a storm, its trails inside it cut into
    // two stretches, as the pipeline cuts an area's trails.
    area: row({
      notice_id: 'example_state_parks_status:lake-park-storm',
      source_key: 'example_state_parks_status',
      provider: 'ESP',
      title: 'Example Lake State Park closed: storm damage (example)',
      category: 'Closed',
      starts_on: localDay(-3),
      current_until: localDay(89),
      updated_at: stamp(-1),
      locality: 'Example Lake State Park',
      place: geometry({
        type: 'MultiLineString',
        coordinates: [
          [
            [-100.201, 38.758],
            [-100.197, 38.7595],
            [-100.193, 38.759],
          ],
          [
            [-100.197, 38.7595],
            [-100.196, 38.755],
            [-100.193, 38.752],
          ],
        ],
      }),
      shape: 'area',
    }),
    // A point closure: a bridge out, one cross.
    point: row({
      notice_id: 'example_trail_club_alerts:creek-bridge',
      source_key: 'example_trail_club_alerts',
      provider: 'ETC',
      steward_kind: 'club',
      title: 'Bridge out at Example Creek (example)',
      current_until: localDay(85),
      updated_at: stamp(-5),
      place: geometry({ type: 'Point', coordinates: [-100.209, 38.75] }),
      shape: 'point',
    }),
    // A line the list greys: its source gives no date at all, so it may no
    // longer apply - and the map still draws it at full strength.
    greyed: row({
      notice_id: 'example_county_parks_closures:canyon-trail',
      source_key: 'example_county_parks_closures',
      provider: 'ECP',
      title: 'Example Canyon Trail closed (example)',
      source_url: null,
      place: geometry({
        type: 'LineString',
        coordinates: [
          [-100.213, 38.743],
          [-100.206, 38.744],
          [-100.199, 38.742],
          [-100.193, 38.7435],
        ],
      }),
      shape: 'line',
    }),
  }
}

/** conditions/trail_closures.json, in the file's contract. */
export function trailClosuresDocument() {
  return {
    generated_at: stamp(0),
    closures: Object.values(trailClosureRows()),
  }
}

/**
 * Answer conditions/trail_closures.json on the wire, before the app loads,
 * whatever the bucket serves: only these invented closures draw.
 *
 * @param {import('@playwright/test').Page} page
 */
export async function routeTrailClosures(page) {
  await page.route(/\/conditions\/trail_closures\.json(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(trailClosuresDocument()),
    }),
  )
}
