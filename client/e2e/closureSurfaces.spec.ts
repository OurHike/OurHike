// The closure and notice surfaces the cutover (#1880) publishes for, driven
// in a real browser from files answered on the wire (`@bucket`,
// e2e/support/bucket.ts).
//
// chrome/PlannedNoticeList.tsx, chrome/HazardAreaSheet.tsx and
// chrome/ClubClosureSheet.tsx were `planned` in src/test/flowCoverage.ts on a
// blocker that stopped being one on 2026-10-23: "the release e2e/data/ reads
// has none until the cutover". The unit tests hold each surface's words
// against a fixture (PlannedNoticeList.test.tsx, HazardAreaSheet.test.tsx,
// ClubClosureSheet.test.tsx, noticesPanel.clubClosures.test.tsx). What none
// of them can see is the chain a hiker's finger goes through: the file
// arriving at lib/useConditions.ts, the lazily fetched map chunk that draws a
// mark from it (map/clubClosureTaps.ts, map/hazardAreaTaps.ts), a tap on the
// WebGL canvas being read as THAT mark rather than the trail line beside it,
// and the sheet the map opens being the one the list would show. These are
// RELEASING.md §8b's safety set: a closure a hiker walks into because the map
// drew nothing, or opened the wrong sheet, is the first of CLAUDE.md's four
// ways this app can hurt somebody.
//
// WHY `@bucket` AND NOT PLAIN HERMETIC. The hermetic build has no bucket, and
// lib/publishedConditions.ts's `readPublished` returns before any request
// without one - so these files cannot be routed in there at all (the header
// of e2e/support/bucket.ts says the rest). Nothing here reaches a network:
// every artifact is answered by `page.route`, 404 unless named.
//
// THE FIXTURES ARE THE RECIPES' OWN (preview-shots/fixtures/plannedNotices.mjs,
// clubClosures.mjs, stewards.mjs), so a spec and a shot describe the same
// invented notices: every organization, closure and notice is an example and
// says so, over Kansas farmland or at 77 degrees west. Nobody's data, no
// account, no location fix.
//
// ENTRANCE. Every sheet is opened the way a hiker opens it - the Map tab, the
// legend's row, a tap on the canvas - and no navigator state is injected
// (features/FLOW_TESTING.md, "Not a router"). The camera is seeded, for the
// reason support/seed.ts's `seedCamera` gives: it is a state, not a route.
//
// EXIT. Each sheet is closed by its own Close, asserted on the map being
// back rather than on the button having been clicked.

import { test, expect, type Locator, type Page, type Request } from '@playwright/test'

import { stubBucket } from './support/bucket'
import { seedCamera, seedPreferences } from './support/seed'
import { setSignal } from './support/signal'
import {
  canvasPointAt,
  clubClosureStewards,
  openClosureSheet,
  tapUntilOpen,
  trailClosureRows,
  trailClosuresDocument,
} from '../preview-shots/fixtures/clubClosures.mjs'
import { seedDayHikes } from '../preview-shots/fixtures/dayHike.mjs'
import { seedLongHike } from '../preview-shots/fixtures/longHike.mjs'
import {
  noticesDocument,
  noticeStatesDocument,
  plannedDayHikes,
  plannedNoticeStewards,
} from '../preview-shots/fixtures/plannedNotices.mjs'
import { seedStewards } from '../preview-shots/fixtures/stewards.mjs'

const NOTICES = 'conditions/notices.json'
const NOTICE_STATES = 'conditions/notice_states.json'
const HAZARD_AREAS = 'conditions/hazard_areas.json'
const TRAIL_CLOSURES = 'conditions/trail_closures.json'

/**
 * An invented hunting area around the release `seedStewards` puts on the
 * phone - forty points at 77 degrees west, a mile apart from 37 north - so
 * that lib/hazardAreas.ts's `crossedHazardAreas` finds a trail running
 * through it and the map draws it. The same shape as hazard-area-no-plan.mjs's
 * box at Bear Mountain, moved to where this phone's one trail is.
 */
const HAZARD_BOX = { west: -77.02, east: -76.98, south: 37.3, north: 37.32 }
const HAZARD_CAMERA = { center: [-76.99, 37.31], zoom: 13 }
/**
 * Where the hazard test taps: inside HAZARD_BOX, 0.015 degrees east of the
 * centerline - 175 px at z13, which is well clear of map/lineTaps.ts's
 * LINE_TAP_SLOP_PX (19.75 px plus half the line's width), so the tap reaches
 * the area rather than the line (map/hazardAreaTaps.ts puts an area last).
 * Reasoned from the arithmetic in `canvasPointAt`, not measured on a device.
 */
const HAZARD_TAP: [number, number] = [-76.985, 37.312]

/** conditions/hazard_areas.json with one invented hunting area, in the
 *  shape pub_conditions_hazard_areas writes (hazard-area-no-plan.mjs's). */
function hazardAreasDocument() {
  const stamp = new Date(Date.now() - 3_600_000).toISOString().slice(0, 19) + 'Z'
  return {
    generated_at: stamp,
    notices: [
      {
        notice_id: 'oprhp_hunting_areas:example-seventy-seven-west',
        source_key: 'oprhp_hunting_areas',
        club: 'nysparks',
        provider: 'NYS OPRHP',
        steward_kind: 'agency',
        title: 'Example hunting area at 77 west (example)',
        category: 'Hunting area',
        locality: 'Example State Park',
        place: {
          kind: 'geometry',
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [HAZARD_BOX.west, HAZARD_BOX.south],
                [HAZARD_BOX.east, HAZARD_BOX.south],
                [HAZARD_BOX.east, HAZARD_BOX.north],
                [HAZARD_BOX.west, HAZARD_BOX.north],
                [HAZARD_BOX.west, HAZARD_BOX.south],
              ],
            ],
          },
        },
        hazard: 'hunting',
        obstructs_trail: false,
        starts_on: null,
        ends_on: null,
        updated_at: null,
        checked_at: stamp,
        first_seen_at: stamp,
        changed_at: stamp,
        carried_since: null,
        source_url: 'https://parks.ny.gov/',
        review_state: 'unreviewed',
      },
    ],
  }
}

/** The planned-hike panel, opened from the legend and the legend put away
 *  (planned-hike-notices.mjs's door, for its reason: the legend's rows would
 *  cover all but the panel's first hike). */
async function openPlannedNotices(page: Page): Promise<Locator> {
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Legend' }).click()
  await page.getByRole('button', { name: /Notices for your planned hikes/ }).click()
  const panel = page.getByRole('dialog', { name: 'Notices for your planned hikes' })
  await expect(panel).toBeVisible()
  await page.getByRole('button', { name: 'Close legend' }).click()
  await expect(panel).toBeVisible()
  return panel
}

test.describe(
  'the closure and notice surfaces, from files answered on the wire',
  { tag: '@bucket' },
  () => {
    test("a club closure's mark opens its sheet and says it is the club's notice, not OurHike's", async ({
      page,
    }) => {
      await stubBucket(page, { [TRAIL_CLOSURES]: trailClosuresDocument() })
      await seedPreferences(page)
      await page.goto('/')
      // The five invented organizations, so the sheet names the closure's
      // publisher rather than its provider code.
      await seedStewards(page, clubClosureStewards())

      // THE BRIDGE'S CROSS, tapped until its sheet opens - the recipe's own
      // door, which is the proof the file, its reader and the map's closure
      // chunk have all landed.
      const { point } = trailClosureRows()
      const sheet = await openClosureSheet(
        page,
        point.place.geometry.coordinates,
        point.title,
      )

      // THE LIST'S OWN ROW: its tag and title, as a hiker would meet them in
      // "Notices for your planned hikes" (the maintainer's "same sheet as its
      // list row").
      await expect(sheet.getByText('Closure', { exact: true })).toBeVisible()
      await expect(sheet.getByText(point.title)).toBeVisible()
      // WHOSE NOTICE IT IS, AND WHAT OURHIKE HAS NOT DONE. The route a hiker
      // builds still goes through the closure, so "does not work out detours"
      // is the load-bearing half.
      const note = sheet.getByRole('note')
      await expect(note).toContainText(
        /This is Example Trail Club’s notice, not OurHike’s/,
      )
      await expect(note).toContainText(/OurHike has not checked the trail itself/)
      await expect(note).toContainText(/does not work out detours/)
      await expect(
        sheet.getByRole('link', { name: 'Read Example Trail Club’s notice' }),
      ).toHaveAttribute('href', 'https://example.org/closures')

      // EXIT: Close, and the map is back under a thumb.
      await sheet.getByRole('button', { name: 'Close' }).click()
      await expect(page.getByRole('dialog', { name: 'Closure notice' })).toHaveCount(0)
      await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
    })

    test("a hazard area's sheet names the agency that drew it and carries no end date it does not have", async ({
      page,
    }) => {
      // NAMED FOR WHAT THE SHEET SAYS. "The agency's layer" was on the card
      // until the word-choice review of #1805 (2026-10-09) took "layer", a GIS
      // word, off it: the sheet names the publisher, and this holds it to that.
      await stubBucket(page, { [HAZARD_AREAS]: hazardAreasDocument() })
      await seedPreferences(page)
      await seedCamera(page, HAZARD_CAMERA.center as [number, number], HAZARD_CAMERA.zoom)
      await page.goto('/')
      // The steward list names OPRHP for `oprhp_hunting_areas`, and the fixture
      // release beside it is the trail the area has to be crossed by to draw.
      await seedStewards(page, plannedNoticeStewards())
      await page.reload({ waitUntil: 'load' })

      await page.getByRole('tab', { name: 'Map' }).click()
      const canvas = page.locator('canvas.maplibregl-canvas').first()
      await canvas.waitFor()
      const box = await canvas.boundingBox()
      if (box === null) throw new Error('the map canvas has no box to tap')
      const sheet = page.getByRole('dialog', { name: 'Hunting allowed' })
      await tapUntilOpen(
        page,
        canvasPointAt(HAZARD_TAP, box, HAZARD_CAMERA),
        sheet,
        'Hunting allowed',
      )

      // AN ADVISORY, NEVER A CLOSURE: the trail stays open, and the word
      // "closed" is nowhere on the card (lib/hazardAreas.ts says why that line
      // is held in both the pipeline and here).
      await expect(sheet.getByText('Advisory', { exact: true })).toBeVisible()
      await expect(sheet).not.toContainText(/closed/i)
      await expect(
        sheet.getByText('Example hunting area at 77 west (example)'),
      ).toBeVisible()
      // WHO DREW IT, by the registry's name for the key, never the raw key.
      const publisher =
        'New York State Office of Parks, Recreation and Historic Preservation'
      await expect(sheet).toContainText(`From ${publisher}`)
      await expect(sheet).not.toContainText('oprhp_hunting_areas')
      // NO DATE IT DOES NOT HAVE. The row carries no `starts_on` and no
      // `ends_on`, so the card says the publisher gives none rather than
      // printing an "until" nobody published.
      await expect(sheet).toContainText(`${publisher} gives no season dates.`)
      await expect(sheet).not.toContainText(/until/i)
      await expect(sheet.getByRole('note')).toContainText(
        `${publisher} drew this area; the advice is OurHike’s.`,
      )

      await sheet.getByRole('button', { name: 'Close' }).click()
      await expect(page.getByRole('dialog', { name: 'Hunting allowed' })).toHaveCount(0)
      await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
    })

    test('a notice touching a planned hike is listed and a notice elsewhere is not', async ({
      page,
    }) => {
      await stubBucket(page, {
        [NOTICES]: noticesDocument(),
        [NOTICE_STATES]: noticeStatesDocument(),
      })
      await seedPreferences(page)
      await page.goto('/')
      // The recipe's seeds, in its order: the stewards (no reload), the long
      // hike (reloads into long-hike mode), the day hikes (reloads again).
      await seedStewards(page, plannedNoticeStewards())
      await seedLongHike(page)
      await seedDayHikes(page, plannedDayHikes())

      const panel = await openPlannedNotices(page)

      // ON A PLANNED HIKE: the invented campground on the Canyon rim loop's
      // line, with the source's own category under its title, and BLM's
      // state-wide notice placed by its state - the two rows that need the
      // file, its states file and lib/plannedNotices.ts's rule to all land.
      const canyon = panel.getByRole('region', { name: 'Canyon rim loop (example)' })
      await expect(canyon.getByText('Canyon Rim Campground (example)')).toBeVisible()
      await expect(canyon.getByText('Listed as “Closed”', { exact: true })).toBeVisible()
      await expect(canyon.getByText('All of Utah')).toBeVisible()
      // ELSEWHERE: in the file, touching no planned hike, and so not in the
      // panel - the feed ORG_NOTICES.md §9 warns about is exactly a list that
      // forgot this half.
      await expect(
        panel.getByText('A notice from a club on no planned hike (example)'),
      ).toHaveCount(0)
      await expect(
        panel.getByText('A shooting site far from any planned hike (example)'),
      ).toHaveCount(0)
      // And the panel says when the notices were gathered, from the file's own
      // `generated_at` rather than the moment it was read.
      await expect(panel.getByText(/Gathered by OurHike on/)).toBeVisible()

      await panel.getByRole('button', { name: 'Close' }).click()
      await expect(
        page.getByRole('dialog', { name: 'Notices for your planned hikes' }),
      ).toHaveCount(0)
      await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
    })

    test('a notices download superseded by a lost signal is aborted while its answer is still held, and the next download is what the panel shows', async ({
      page,
    }) => {
      // #1870 - useConditions does not abort a superseded notices, hazard-area
      // or closures download, so a flapping connection runs two at once - fixed
      // by #1892 - Abort a superseded notices, hazard-area or closures download
      // in useConditions. lib/useConditions.notices.test.ts ('is aborted when a
      // flapping connection starts the next read') proves the abort in jsdom
      // with a mocked fetch. What it cannot see is a real download the effect
      // gave up on, still held on the wire, being stopped by the browser - and
      // that abort is all that keeps its bytes out of lib/conditionsCache.ts's
      // kept copy, the one a phone with no signal reads next. The effect's
      // `cancelled` flag keeps a late answer off the screen and nothing else:
      // lib/publishedConditions.ts's `readPublished` keeps every document that
      // parses, so without the abort the earlier download's bytes would
      // overwrite the later one's.
      //
      // ORDER BY page.route, NOT BY A STOPWATCH (features/FLOW_TESTING.md, "a
      // race is not something a flow test should chase"): the first download
      // is held on the wire until the test lets it go, so "late" is a fact of
      // the drive rather than a guess about the machine.
      const EARLIER = 'Earlier download (example)'
      const LATER = 'Later download (example)'
      const campground = noticesDocument().notices.find(
        (row: { notice_id: string }) =>
          row.notice_id === 'usfs_rec_opportunities_status:example',
      )
      /** notices.json with one notice on the Canyon rim loop's line, titled. */
      const noticesHolding = (title: string) => ({
        ...noticesDocument(),
        notices: [{ ...campground, title }],
      })

      let releaseEarlier: () => void = () => {}
      const earlierHeld = new Promise<void>((resolve) => {
        releaseEarlier = resolve
      })
      let downloads = 0
      let earlierRequest: Request | null = null
      // How each request ended, as the browser reports it: 'finished', or the
      // network error a failed one carries (`net::ERR_ABORTED` for an abort).
      const ended = new Map<Request, string>()
      page.on('requestfinished', (request) => ended.set(request, 'finished'))
      page.on('requestfailed', (request) =>
        ended.set(request, request.failure()?.errorText ?? 'failed'),
      )
      await stubBucket(page, {
        [NOTICE_STATES]: noticeStatesDocument(),
        [NOTICES]: async (request) => {
          // The HEAD a phone with nothing planned asks is answered at once.
          if (request.method() !== 'GET') return { status: 200 }
          downloads += 1
          if (downloads === 1) {
            earlierRequest = request
            await earlierHeld
            return { status: 200, body: noticesHolding(EARLIER) }
          }
          return { status: 200, body: noticesHolding(LATER) }
        },
      })
      await seedPreferences(page)
      await page.goto('/')
      await seedStewards(page, plannedNoticeStewards())
      // A planned hike is what makes the phone download the file at all.
      await seedDayHikes(page, plannedDayHikes())
      await expect.poll(() => downloads).toBe(1)

      // SIGNAL LOST: the effect's cleanup stops the download in flight, and
      // the browser reports it aborted while the wire still holds its answer -
      // the observable #1870 is about. Without the abort it stays pending and
      // this poll runs out.
      //
      // THE ABORT IS THE WHOLE PROOF. An aborted request has nowhere to
      // deliver bytes to, so however late the held answer is sent it reaches
      // neither `readPublished`, nor the kept copy, nor the screen. This test
      // used to send it afterwards and then read the kept copy, which passed
      // whatever the late answer did - the second download's copy satisfied
      // it. Nor would waiting for the stub to report its fulfil refused have
      // helped: a fulfil is refused exactly when this abort has happened, so
      // that wait could only go red where this one already had.
      await setSignal(page, page.context(), { on: false })
      await expect
        .poll(() => (earlierRequest === null ? undefined : ended.get(earlierRequest)))
        .toBe('net::ERR_ABORTED')

      // SIGNAL FOUND: the next run starts the second download, which the wire
      // answers at once, and that is what the panel shows.
      await setSignal(page, page.context(), { on: true })
      const panel = await openPlannedNotices(page)
      await expect(panel.getByText(LATER)).toBeVisible()

      // The held handler is let go so it does not outlive the test; its
      // answer has nowhere to go, and e2e/support/bucket.ts swallows the
      // refused fulfil.
      releaseEarlier()
    })
  },
)
