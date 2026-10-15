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
// stretches the pipeline cut inside the area), "point" (a Point, or a
// MultiPoint, which pipeline/dbt writes as "point" too and the map crosses at
// each of its points), or "shade" (decision 191, 2026-10-14: the Polygon of
// an area no mapped trail runs inside, which the map hatches).
//
// FIVE CLOSURES, ONE OF EACH KIND THE STANDARD DRAWS: a line, an area's cut
// stretches, a point, a line the list greys because its source gives no
// date (lib/noticeCurrency.ts's "Its source gives no date. It may no longer
// apply."), which the map draws with the same full mark - the maintainer's
// "B: same mark" - and an area with no trail inside, shaded.
//
// NO A.T. UNDER ANY OF THEM. Decision 192 crosses out the A.T. like any trail
// inside a club's area, and the pipeline cuts its stretch into the area's
// MultiLineString beside the others, so in this file it would be one more
// stretch, drawn the same. What would show the decision is the mark lying
// over the A.T.'s own red line, and the phone draws that line from the
// release's trails.geojson, which is held to its published hash
// (lib/trailData.ts), so a recipe cannot invent one; over farmland there is
// no real one. map/style.test.ts holds the order instead: every crossed-out
// layer above the A.T.'s.
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

/** The camera the recipe opens on: the middle of the closures at z13,
 *  the zoom the chain of crosses is drawn at full size from
 *  (lib/closureStyle.ts's CLOSURE_FULL_WIDTH_ZOOM). At z13 a degree of
 *  longitude is 11,651 px (512 * 2^13 / 360), so the 390 px phone canvas
 *  spans 0.033 degrees across; every closure below sits within 0.0125 east
 *  or west of the centre and 0.014 north or south of it. A local frame of
 *  2026-10-14 put the first four clear of the header plate and the map's
 *  buttons, once the northern line moved 0.004 south off the buttons' row;
 *  the shaded area sits in the empty ground CI's frame of that day showed
 *  between the area's stretches and the greyed line. */
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

/** The five closures, keyed by the kind each stands for, so a test can name
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
    // An area closure no mapped trail runs inside (decision 191, "Shade
    // them, no edge"): a preserve's closed lands, drawn as the area itself,
    // hatched, with nothing on its edge, below the park's stretches.
    shade: row({
      notice_id: 'example_open_space_access:closed-lands',
      source_key: 'example_open_space_access',
      provider: 'EOS',
      title: 'Example Hills Preserve closed lands (example)',
      category: 'Closed',
      current_until: localDay(60),
      updated_at: stamp(-30),
      locality: 'Example Hills Preserve',
      place: geometry({
        type: 'Polygon',
        coordinates: [
          [
            [-100.1985, 38.7505],
            [-100.1935, 38.7508],
            [-100.1905, 38.7488],
            [-100.1912, 38.7462],
            [-100.1958, 38.7455],
            [-100.199, 38.7478],
            [-100.1985, 38.7505],
          ],
        ],
      }),
      shape: 'shade',
    }),
  }
}

/** A point well inside the shaded area, where a tap opens its sheet. */
export const SHADE_TAP_AT = [-100.1948, 38.7484]

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

/** The five invented organizations, in the shape stewards.json has on the
 *  wire (fixtures/stewards.mjs's seedStewards takes it), so a sheet names
 *  each closure's publisher rather than its provider code. */
export function clubClosureStewards() {
  const steward = (provider, name, key) => ({
    provider,
    name,
    trust: 'authoritative',
    licence: null,
    attribution: null,
    terms: null,
    terms_source: null,
    layers: [],
    keys: [key],
    support: null,
    store: null,
    steward_id: `org:${provider.toLowerCase()}`,
  })
  return {
    stewards: [
      steward('ENF', 'Example National Forest', 'example_forest_closures'),
      steward('ESP', 'Example State Parks', 'example_state_parks_status'),
      steward('ETC', 'Example Trail Club', 'example_trail_club_alerts'),
      steward('ECP', 'Example County Parks', 'example_county_parks_closures'),
      steward('EOS', 'Example Open Space District', 'example_open_space_access'),
    ],
  }
}

/** How long a drive taps a closure before it gives up: the ceiling
 *  hazard-area-no-plan.mjs keeps for the same wait, on the same reasoning
 *  (nobody has timed it on a preview). */
const TAP_FOR_MS = 45_000

/** A lon/lat as a point on the map canvas at TRAIL_CLOSURES_CAMERA:
 *  MapLibre's world is 512 px a tile, so at zoom z a degree of longitude is
 *  512 * 2^z / 360 px, and with no map padding the camera's centre is the
 *  canvas's centre (hazard-area-no-plan.mjs's canvasPoint). */
function canvasPoint([lon, lat], box) {
  const { center, zoom } = TRAIL_CLOSURES_CAMERA
  const pxPerDegree = (512 * 2 ** zoom) / 360
  const mercator = (degrees) =>
    (Math.log(Math.tan(Math.PI / 4 + (degrees * Math.PI) / 360)) * 180) / Math.PI
  return {
    x: box.width / 2 + (lon - center[0]) * pxPerDegree,
    y: box.height / 2 - (mercator(lat) - mercator(center[1])) * pxPerDegree,
  }
}

/**
 * Open the map at TRAIL_CLOSURES_CAMERA and tap `lonLat` until a closure's
 * sheet opens, then wait for `title` in it; returns the sheet.
 *
 * Tapping until the sheet opens is the proof the file, its reader and
 * map/clubClosureTaps.ts have all landed, since nothing else on screen says
 * so; a tap before then opens nothing, so tapping early costs nothing.
 *
 * @param {import('@playwright/test').Page} page
 * @param {[number, number]} lonLat
 * @param {string} title
 */
export async function openClosureSheet(page, lonLat, title) {
  // lib/cameraMemory.ts's contract, as long-term-closures.mjs seeds it.
  await page.evaluate((camera) => {
    sessionStorage.setItem('ourhike:camera', JSON.stringify(camera))
  }, TRAIL_CLOSURES_CAMERA)
  await page.reload({ waitUntil: 'load' })

  await page.getByRole('tab', { name: 'Map' }).click()
  return tapUntilClosureSheet(page, lonLat, title)
}

/**
 * On the map openClosureSheet opened, tap `lonLat` until a closure's sheet
 * opens, then wait for `title` in it; returns the sheet. For a second
 * closure after the first sheet is closed, with no reload.
 *
 * @param {import('@playwright/test').Page} page
 * @param {[number, number]} lonLat
 * @param {string} title
 */
export async function tapUntilClosureSheet(page, lonLat, title) {
  const canvas = page.locator('canvas.maplibregl-canvas').first()
  await canvas.waitFor()
  const box = await canvas.boundingBox()
  if (box === null) throw new Error('the map canvas has no box to tap')
  const position = canvasPoint(lonLat, box)

  const sheet = page.getByRole('dialog', { name: 'Closure notice' })
  const deadline = Date.now() + TAP_FOR_MS
  while (!(await sheet.isVisible())) {
    if (Date.now() > deadline) {
      throw new Error(
        `no "Closure notice" sheet after ${TAP_FOR_MS / 1000} s of taps at ` +
          `${lonLat.join(', ')}: the closures did not draw, or something drawn ` +
          'over the mark takes the tap',
      )
    }
    try {
      await canvas.click({ position, timeout: 5000 })
    } catch (error) {
      if (await sheet.isVisible()) break
      throw error
    }
    await sheet.waitFor({ timeout: 1500 }).catch(() => undefined)
  }
  await sheet.getByText(title).waitFor()
  return sheet
}
