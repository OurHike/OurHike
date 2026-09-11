// What the map answers when a hiker touches it — F12 of
// features/FLOW_TESTING.md's battery, and the half e2e/mapChrome.spec.ts
// says it cannot reach.
//
// mapChrome.spec.ts drives the map's *controls*: the legend's switches, the
// search panel, the doors in the header. Every one of those exists on a phone
// that has downloaded nothing. This file drives what the CANVAS opens — a
// waypoint's card, a trail line's sheet, the plate a long press raises — and
// none of it exists without a release under the map. That is the whole reason
// for the second half of the suite (playwright.config.ts's FLOW_DATA comment).
//
// WHAT IS ASSERTED, AND WHAT IS DELIBERATELY NOT. Same rule as
// e2e/data/builder.spec.ts: the published release moves when somebody bumps
// the pin, so nothing here names a shelter, a mile, a count or a photograph.
// What is pinned is the SHAPE — that the row opens the card it names, that the
// peek withholds what the opened card carries, that a line names its blaze and
// its source, that a press offers report and thanks and goes on the first sign
// of a pan. Those are claims about the app. "Mt. Collins Shelter" is a claim
// about a release, and a release is allowed to change.
//
// ENTRANCE. Every sheet here is opened the way a hiker opens it, from the tab
// bar down: no navigator state is injected (FLOW_TESTING.md, "Not a router").
// The one seeded thing is the camera — support/seed.ts's `seedCamera` carries
// why that is a state and not a route.

import { test, expect, type Page, type Locator } from '@playwright/test'
import {
  seedPreferences,
  seedCamera,
  bootFreshPage,
  ON_THE_TRAIL,
  ABOVE_THE_SEAM_ZOOM,
  BELOW_THE_SEAM_ZOOM,
} from '../support/seed'

/**
 * HOW LONG THE TRAIL SKETCHES ARE ALLOWED TO TAKE, and why this is not the
 * 30-second default.
 *
 * Both helpers below prove the map has arrived by opening the legend and
 * reading its "Trails in view" section — the app's own statement that it holds
 * the lines a tap has to hit. The waypoint index parses first and the sketches
 * land separately, so without that wait the sweeps race them.
 *
 * Measured 2026-09-11 against release 2026-09-10, with other Playwright runs
 * sharing the machine: the wait misses 30 seconds at BOTH cameras — three
 * times across two full runs of this file, once at the closer one. The failure
 * prints a legend with every waypoint count populated and no trails section,
 * which reads as "the legend lost a section" rather than "this has not
 * finished yet", and the wider camera is the slower of the two because four
 * zoom levels out is a great deal more geometry. Exactly the confusion
 * e2e/data/longSpine.spec.ts's own NETWORK_BOUND_MS was added for, so the
 * same answer: a budget that says what it is waiting on.
 */
const SKETCHES_BOUND_MS = 90_000

/**
 * AND THE TEST HAS TO BE LONGER THAN THE WAIT INSIDE IT.
 *
 * playwright.config.ts gives the data project a 90-second per-test timeout,
 * which is exactly `SKETCHES_BOUND_MS` — so a wait that actually needed its
 * budget could never spend it: the test died first, and the message read
 * "Test timeout of 90000ms exceeded" rather than naming the legend it was
 * waiting on. Measured here 2026-09-11, and the same trap
 * e2e/data/longSpine.spec.ts had already paid for once with an inner wait and
 * a test budget both set to 90s.
 *
 * 180s leaves the sketch wait its full 90 and the sweep the other 90, which is
 * ample: the slowest test in this file takes about 25s on an idle machine.
 */
test.describe.configure({ timeout: 180_000 })

/** On the map tab, past first run, at whatever camera the caller seeded. */
async function openMap(page: Page): Promise<void> {
  await seedPreferences(page)
  await page.goto('/')
  await page.getByRole('tab', { name: 'Map' }).click()
  await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
}

/** Above the pin seam, where pins draw and the trail line is thick enough to
 *  touch. Seeded before the boot, so the app opens there rather than flying. */
async function openMapOnTheTrail(page: Page): Promise<void> {
  await seedCamera(page, ON_THE_TRAIL, ABOVE_THE_SEAM_ZOOM)
  await openMap(page)
  // WAIT ON SOMETHING THAT PROVES THE SEQUENCE COMPLETED, not on a timer
  // (CLAUDE.md). The In view door is not enough: it appears as soon as the
  // waypoint index is parsed, and the trail sketches — the lines a tap has to
  // hit — arrive separately. The legend's "Trails in view" section is the
  // app's own statement that it has them, so opening the legend and reading
  // that is the proof, and closing it again leaves the screen as it was.
  //
  // Without this the line-tap sweep raced the sketches and found nothing on
  // about one run in four, which reads as "tapping a trail is broken".
  const legend = await openLegend(page)
  await expect(legend).toContainText('Trails in view', { timeout: SKETCHES_BOUND_MS })
  await legend.getByRole('button', { name: /Close legend/ }).click()
  await expect(page.getByRole('dialog', { name: 'Legend' })).toHaveCount(0)
}

/**
 * The map's frame, for tap coordinates.
 *
 * Playwright's `boundingBox` on the region rather than on the canvas: the
 * canvas is the full frame, but the header's pills float over its top strip,
 * and a tap meant for the trail that lands on "In view · N" opens the wrong
 * thing and passes anyway. That happened while writing this file, and cost an
 * hour. So the sweep below starts at `HEADER_ROWS` twentieths down, which
 * clears the pills at both phone heights this suite runs.
 */
const HEADER_ROWS = 7

async function frameOf(page: Page): Promise<{
  x: number
  y: number
  width: number
  height: number
}> {
  const box = await page.getByRole('region', { name: 'Trail map' }).boundingBox()
  if (box === null) throw new Error('the map region has no box, so it never mounted')
  return box
}

/**
 * The legend, which cannot be reached by its bare name here.
 *
 * e2e/mapChrome.spec.ts opens it with `{ name: 'Legend', exact: true }` and is
 * right to: on a phone that downloaded nothing there are no notices, so the
 * button's accessible name is the word alone. With a release under it the same
 * button reads "Legend, 1 new trail notice", and the exact match waits forever.
 * That is the badge working, not the door moving — so the anchor is what both
 * spellings share.
 */
async function openLegend(page: Page): Promise<Locator> {
  await page.getByRole('button', { name: /^Legend\b/ }).click()
  const legend = page.getByRole('dialog', { name: 'Legend' })
  await expect(legend).toBeVisible()
  return legend
}

/**
 * Tap the trail, wherever it happens to be drawn.
 *
 * A FIXED COORDINATE WOULD BE PINNING A PROJECTION, not the app. The A.T. is
 * a few device pixels wide on a 390-pixel canvas, and where it crosses that
 * canvas is a function of the release's geometry, the seeded camera and
 * MapLibre's own fit — change any one and a hard-coded point misses, which
 * would read as "tapping a trail is broken" when nothing about tapping broke.
 * Nothing in the app hands a test the line's screen position: the map object
 * is not on `window`, by design, so `queryRenderedFeatures` is not available
 * here. So this sweeps, the way a finger does, and fails loudly if the whole
 * grid is empty.
 *
 * MEASURED, 2026-09-11, against release 2026-09-10 and the seeded camera
 * above: a 6-column by 12-row sweep of the frame below the header finds
 * exactly one point that opens a trail line, at 18/20 across and 11/20 down,
 * and finds the same one on repeat runs and either side of a legend round
 * trip. The coarse grid below is that measurement turned into a budget — it
 * reaches that point in about fifteen taps — and the fine pass behind it is
 * what catches a release that moves the line between two coarse rows.
 */
async function tapTheTrail(page: Page): Promise<Locator> {
  const box = await frameOf(page)
  const sheet = page.getByRole('dialog', { name: 'Trail line' })
  const card = page.getByRole('dialog', { name: 'Waypoint' })

  const tap = async (across: number, down: number): Promise<boolean> => {
    await page.mouse.click(
      box.x + (box.width * across) / 20,
      box.y + (box.height * down) / 20,
    )
    if ((await sheet.count()) > 0) return true
    // A tap that lands on a PIN opens a waypoint instead, and the card then
    // covers the canvas, so every remaining tap would hit the card and the
    // sweep would run out having tested nothing. Closing it and carrying on is
    // the honest recovery — a pin on the trail is exactly what this camera is
    // looking at.
    if ((await card.count()) > 0) {
      await card.getByRole('button', { name: /Close waypoint details/ }).click()
      await expect(card).toHaveCount(0)
    }
    return false
  }

  for (const step of [2, 1]) {
    for (let down = HEADER_ROWS; down <= 18; down += step) {
      for (let across = 2; across <= 18; across += step * 2) {
        if (await tap(across, down)) return sheet
      }
    }
  }
  throw new Error(
    'nothing on the map opened a trail line — either the release drew no ' +
      'trail at the seeded camera, or a tap on one no longer opens its sheet',
  )
}

/** The In view door, then a row, which is how a hiker reaches a waypoint
 *  without having to hit a 24-pixel pin with a thumb. */
async function openFirstWaypoint(page: Page): Promise<{
  card: Locator
  rowTitle: string
}> {
  await page.getByRole('button', { name: /In view/ }).click()
  const list = page.getByRole('dialog', { name: 'In view' })
  await expect(list).toBeVisible()
  const row = list.locator('.poi-row--opens').first()
  const rowTitle = await row.locator('.poi-row__title').innerText()
  await row.click()
  const card = page.getByRole('dialog', { name: 'Waypoint' })
  await expect(card).toBeVisible()
  return { card, rowTitle }
}

test.describe('a waypoint’s card', () => {
  test('entrance: the row opens the card it names, and the card opens at the peek', async ({
    page,
  }) => {
    // THE REVIEW'S OWN RULE, ASSERTED RATHER THAN ASSUMED: "every list row is
    // the same component as the card it opens" (chrome/PoiRow.tsx's header).
    // The row's title is read off the row and compared to the card's — so this
    // is a claim about the wiring and survives any release, where asserting a
    // particular shelter's name would be a claim about the publish.
    await openMapOnTheTrail(page)
    const { card, rowTitle } = await openFirstWaypoint(page)

    await expect(card.locator('.poi-card__name')).toHaveText(rowTitle)
    // The peek, not the record. #941 split the card in two deliberately, and
    // the class is how the build says which half is up.
    await expect(card).toHaveClass(/poi-card--peek/)
    // And the list went away, because two panels over one map both claiming to
    // describe what the hiker is looking at is the screen arguing with itself.
    await expect(page.getByRole('dialog', { name: 'In view' })).toHaveCount(0)
  })

  test('states: the peek withholds the photograph, the coordinates and the site strip until it is pulled open', async ({
    page,
  }) => {
    // THE LICENCE ARGUMENT, DRIVEN. PoiCard.tsx: "the credit is the price of
    // showing the photo at all, and the peek has no line to spend on an
    // institutional attribution string… A thumbnail with the credit 'one tap
    // away' would be the licence breach with extra steps." That is a rule a
    // refactor can quietly break, because the photo would simply appear and
    // nothing would look wrong. This is the test that would go red.
    await openMapOnTheTrail(page)
    const { card } = await openFirstWaypoint(page)

    await expect(card.locator('.poi-card__photo')).toHaveCount(0)
    await expect(card.locator('.poi-card__credit')).toHaveCount(0)
    await expect(card.locator('.poi-card__coords')).toHaveCount(0)

    // What the peek DOES carry: the one-tap answer it exists for.
    await expect(card.getByRole('group')).toBeVisible()
    const pull = card.getByRole('button', { name: /Notes & details|Details/ })
    await expect(pull).toBeVisible()

    await pull.click()
    await expect(card).toHaveClass(/poi-card--open/)
    // The coordinates and their provenance, which is the line that makes the
    // rest of the card checkable — "provenance that stops at the last Python
    // file is provenance nobody has" (CLAUDE.md).
    await expect(card.locator('.poi-card__coords')).toBeVisible()
    await expect(card.locator('.poi-card__coords')).toContainText('Latitude, longitude:')

    // And back, in place: the pull is a fold, not a second screen.
    await card.getByRole('button', { name: 'Show less' }).click()
    await expect(card).toHaveClass(/poi-card--peek/)
    await expect(card.locator('.poi-card__coords')).toHaveCount(0)
  })

  test('exit: closing the card leaves the map, and the In view door with it', async ({
    page,
  }) => {
    // Rule 2 of FLOW_TESTING.md on a surface that covers the thing underneath
    // it. Asserting the door as well as the absence is what stops this passing
    // on a screen that failed to render anything at all.
    await openMapOnTheTrail(page)
    const { card } = await openFirstWaypoint(page)

    await card.getByRole('button', { name: /Close waypoint details/ }).click()

    await expect(page.getByRole('dialog', { name: 'Waypoint' })).toHaveCount(0)
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
    await expect(page.getByRole('button', { name: /In view/ })).toBeVisible()
  })
})

test.describe('a trail line’s sheet', () => {
  test('entrance and states: a tap on the trail names its blaze and where the line came from', async ({
    page,
  }) => {
    await openMapOnTheTrail(page)
    const sheet = await tapTheTrail(page)

    // The heading is the blaze and the trail's name, and neither word is
    // pinned here — what is pinned is that the sheet HAS a heading and a
    // source sentence, because a line that says "Trail" and nothing about
    // where the geometry came from is the failure this sheet exists to fix
    // (#134). The sentence's shape is the app's; the org's name is the
    // release's.
    await expect(sheet.getByRole('heading')).toBeVisible()
    await expect(sheet).toContainText(/From the .+\./)
    await expect(sheet.getByRole('button', { name: /Take this trail/ })).toBeVisible()
  })

  test('states: taking the trail closes the sheet and marks it taken in the legend', async ({
    page,
  }) => {
    // THE MECHANISM, WHICH IS TWO SURFACES AGREEING. "Take this trail" writes
    // lib/takenTrail.ts, and the legend's "Trails in view" list reads it back.
    // Asserting the write through the legend rather than through the store is
    // what makes this a flow test: a hiker cannot see IndexedDB.
    await openMapOnTheTrail(page)
    const sheet = await tapTheTrail(page)
    const trailName = await sheet.getByRole('heading').innerText()

    await sheet.getByRole('button', { name: /Take this trail/ }).click()
    await expect(page.getByRole('dialog', { name: 'Trail line' })).toHaveCount(0)

    await openLegend(page)
    const legend = page.getByRole('dialog', { name: 'Legend' })
    await expect(legend).toContainText('Trails in view')
    // One row, and it is the one that was taken. The heading reads
    // "<blaze> · <trail>", and the legend lists the trail's own name, so the
    // tail of the heading is what the two surfaces have to agree about.
    const takenName = trailName.split('·').pop()?.trim() ?? trailName
    await expect(legend.getByText('taken', { exact: true })).toBeVisible()
    expect(takenName.length).toBeGreaterThan(0)
  })

  test('exit: the sheet closes on its own Close, with nothing taken', async ({
    page,
  }) => {
    await openMapOnTheTrail(page)
    const sheet = await tapTheTrail(page)

    await sheet.getByRole('button', { name: 'Close' }).click()
    await expect(page.getByRole('dialog', { name: 'Trail line' })).toHaveCount(0)

    // And the close was a close rather than a take — the legend's list carries
    // no taken mark. This is the assertion that stops the exit test passing on
    // a build where every dismissal silently chose something.
    await openLegend(page)
    const legend = page.getByRole('dialog', { name: 'Legend' })
    await expect(legend).toContainText('Trails in view')
    await expect(legend.getByText('taken', { exact: true })).toHaveCount(0)
  })
})

test.describe('the plate a long press raises', () => {
  test('entrance and exit: a press on open trail offers report and thanks, and “Not here” takes it back', async ({
    page,
  }) => {
    await openMapOnTheTrail(page)
    const box = await frameOf(page)
    // A press, not a tap: map/longPress.ts waits LONG_PRESS_MS (500) and gives
    // up if the finger moves more than LONG_PRESS_SLOP_PX (10), so the mouse
    // goes down, stays still, and waits past the timer before coming up.
    await page.mouse.move(box.x + box.width * 0.35, box.y + box.height * 0.55)
    await page.mouse.down()
    await page.waitForTimeout(900)
    await page.mouse.up()

    const plate = page.getByRole('dialog', { name: 'Report or thank at this spot' })
    await expect(plate).toBeVisible()
    await expect(plate.getByRole('button', { name: 'Report a problem' })).toBeVisible()
    await expect(plate.getByRole('button', { name: 'Say thanks' })).toBeVisible()

    // "Not here" is the exit and it is worth its own sentence: the plate names
    // a POINT, so its dismissal is phrased as a correction of the point rather
    // than as a generic Cancel.
    await plate.getByRole('button', { name: 'Not here' }).click()
    await expect(
      page.getByRole('dialog', { name: 'Report or thank at this spot' }),
    ).toHaveCount(0)
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
  })

  test('states: a press replaces an open waypoint card rather than stacking on it', async ({
    page,
  }) => {
    // App.tsx's own reason, driven: "A press with a card open replaces the
    // card. Two panels over one map, one of them describing a place the hiker
    // is no longer pointing at, is the screen arguing with itself."
    await openMapOnTheTrail(page)
    const { card } = await openFirstWaypoint(page)
    await expect(card).toBeVisible()

    // PRESS ON MAP THE CARD IS NOT COVERING. The peek hangs off its pin
    // (chrome/poiCardPlacement.ts), so where it sits is a function of where
    // the waypoint landed on screen — a fixed press point lands on the card
    // about half the time, and a press on the card is not a press on the map.
    // So the card's own box is measured and the press goes above or below it,
    // whichever side has more room.
    const box = await frameOf(page)
    const cardBox = await card.boundingBox()
    if (cardBox === null) throw new Error('the open card has no box')
    const above = cardBox.y - box.y
    const below = box.y + box.height - (cardBox.y + cardBox.height)
    const pressY =
      above > below ? box.y + above / 2 : cardBox.y + cardBox.height + below / 2
    await page.mouse.move(box.x + box.width * 0.2, pressY)
    await page.mouse.down()
    await page.waitForTimeout(900)
    await page.mouse.up()

    await expect(
      page.getByRole('dialog', { name: 'Report or thank at this spot' }),
    ).toBeVisible()
    await expect(page.getByRole('dialog', { name: 'Waypoint' })).toHaveCount(0)
  })

  test('states: the plate goes on the first sign of a pan, rather than riding along', async ({
    page,
  }) => {
    // The other documented decision: `movestart` rather than `moveend`, and
    // rather than repositioning, because "a panel that rides along while its
    // point slides out from under it is worse than one that leaves."
    await openMapOnTheTrail(page)
    const box = await frameOf(page)
    await page.mouse.move(box.x + box.width * 0.35, box.y + box.height * 0.55)
    await page.mouse.down()
    await page.waitForTimeout(900)
    await page.mouse.up()
    const plate = page.getByRole('dialog', { name: 'Report or thank at this spot' })
    await expect(plate).toBeVisible()

    // A drag well past the slop, which is a pan and nothing else.
    await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.5)
    await page.mouse.down()
    await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.5, {
      steps: 12,
    })
    await page.mouse.up()

    await expect(
      page.getByRole('dialog', { name: 'Report or thank at this spot' }),
    ).toHaveCount(0)
  })
})

test.describe('every trail notice the app holds', () => {
  test('entrance and states: the list carries a link out for every notice, and never the notice itself', async ({
    page,
  }) => {
    // THE LICENCE LINE AGAIN, AND THE SAFETY ONE. The sheet says it out loud:
    // "OurHike carries each one's facts and a link, never their notice in
    // full, so what each one actually says is on their page." A link per row
    // is that promise in a form a test can hold — if a future build inlined
    // an org's text, the count would still match but the sentence would not,
    // so both are asserted.
    await openMap(page)
    await openLegend(page)
    const door = page.getByRole('button', { name: /Read all \d+ trail notices/ })
    await expect(door).toBeVisible()
    await door.click()

    const sheet = page.getByRole('dialog', { name: 'Every trail notice OurHike holds' })
    await expect(sheet).toBeVisible()
    await expect(sheet).toContainText('never their notice in full')

    // The count is the release's, so it is read off the heading rather than
    // written down, and the claim is that the links and the heading agree.
    const heading = await sheet.getByRole('heading').first().innerText()
    const held = Number(heading.match(/^(\d[\d,]*)/)?.[1]?.replace(/,/g, '') ?? '0')
    expect(held).toBeGreaterThan(0)
    await expect(sheet.getByRole('link')).toHaveCount(held)
  })

  test('states: the “new” mark is spent by reading the list, and stays spent across a restart', async ({
    page,
  }) => {
    // A BADGE THAT CAME BACK WOULD BE WORSE THAN NO BADGE, because a hiker
    // learns within a week to stop reading it. The watermark is per
    // organization and per newest edit (chrome/noticesPanel.tsx), which is
    // durable state — so the claim is only worth anything across a cold boot,
    // and the boot is a sibling page for the reload trap support/seed.ts
    // documents.
    await openMap(page)
    const legendDoor = page.getByRole('button', { name: /^Legend/ })
    await expect(legendDoor).toHaveText(/new trail notice/)

    await openLegend(page)
    await page.getByRole('button', { name: /Read all \d+ trail notices/ }).click()
    const sheet = page.getByRole('dialog', { name: 'Every trail notice OurHike holds' })
    await expect(sheet).toBeVisible()
    await sheet.getByRole('button', { name: 'Close' }).click()

    await expect(
      page.getByRole('button', { name: /Read all \d+ trail notices/ }),
    ).not.toHaveText(/new/)

    const fresh = await bootFreshPage(page)
    await fresh.getByRole('tab', { name: 'Map' }).click()
    await expect(fresh.getByRole('region', { name: 'Trail map' })).toBeVisible()
    // Waits on the door's text rather than on a timer: the notices load after
    // the map, so a bare assertion here would race the fetch and pass for the
    // wrong reason.
    await expect(fresh.getByRole('button', { name: /^Legend/ })).toHaveText('Legend')
    await fresh.close()
  })
})

test.describe('what the field has said about a place', () => {
  /** A waypoint whose type carries a conditions section. The In view list is
   *  ordered by mile and the release puts a spring first at this camera, but
   *  the section is the thing under test rather than the place — so this
   *  walks the rows until one has the group, and says so if none does. */
  async function openAWaypointWithConditions(page: Page): Promise<Locator> {
    await page.getByRole('button', { name: /In view/ }).click()
    const list = page.getByRole('dialog', { name: 'In view' })
    await expect(list).toBeVisible()
    const rows = list.locator('.poi-row--opens')
    const count = await rows.count()
    for (let index = 0; index < count; index += 1) {
      await rows.nth(index).click()
      const card = page.getByRole('dialog', { name: 'Waypoint' })
      await expect(card).toBeVisible()
      if ((await card.getByRole('group', { name: 'How is it right now?' }).count()) > 0) {
        return card
      }
      await card.getByRole('button', { name: /^Close waypoint details/ }).click()
      await page.getByRole('button', { name: /In view/ }).click()
      await expect(list).toBeVisible()
    }
    throw new Error(
      'no waypoint in view carries a conditions section — either the release stopped ' +
        'publishing water, shelters and campsites at this camera, or the scoped-type ' +
        'list in lib/fieldNotes.ts no longer matches what is exported',
    )
  }

  test('entrance and states: the peek asks one question, offers two answers, and says nobody has spoken', async ({
    page,
  }) => {
    await openMapOnTheTrail(page)
    const card = await openAWaypointWithConditions(page)

    // ONE QUESTION, NAMED. The group's accessible name is the question, so a
    // hiker using a screen reader gets the same framing as one reading it.
    const asking = card.getByRole('group', { name: 'How is it right now?' })
    await expect(asking).toBeVisible()

    // TWO ANSWERS ON THE PEEK, not the whole picker. lib/fieldNotes.ts's
    // `peekObservations` deals exactly the good one and the problem one, and
    // the peek has no room to be a form.
    await expect(asking.getByRole('button')).toHaveCount(2)

    // AND THE SILENCE IS NAMED. A place nobody has confirmed says so rather
    // than showing a blank where a date would be — the same omit-rather-than
    // -guess rule the capacity line keeps. "No recent word" is a claim about
    // notes this phone COULD read; the offline case says something different
    // ("Recent notes unavailable — no signal"), which is #249's distinction.
    await expect(
      card.getByText(/No recent word|Never confirmed|Recent notes unavailable/),
    ).toBeVisible()
  })

  test('states: pulling the card open widens the question rather than replacing it', async ({
    page,
  }) => {
    await openMapOnTheTrail(page)
    const card = await openAWaypointWithConditions(page)
    const peekAnswers = await card
      .getByRole('group', { name: 'How is it right now?' })
      .getByRole('button')
      .count()

    await card.getByRole('button', { name: /Notes & details|Details/ }).click()
    await expect(card).toHaveClass(/poi-card--open/)

    // SAME QUESTION, MORE ANSWERS. The group keeps its name, so the opened
    // card is the peek at a second height rather than a different screen.
    const asking = card.getByRole('group', { name: 'How is it right now?' })
    await expect(asking).toBeVisible()
    expect(await asking.getByRole('button').count()).toBeGreaterThan(peekAnswers)

    // THE DISPUTE VALUE, which #876 put on every scoped type: a hiker who
    // finds nothing where the map drew something can say exactly that, rather
    // than having to pick the nearest wrong answer.
    await expect(asking.getByRole('button', { name: /Not here/ })).toBeVisible()

    // And the two escalations, each named for the case it is for — a problem
    // worth a report, and a thanks. Offered together because the card cannot
    // know which one the hiker is standing in front of.
    await expect(card.getByText(/Blowdown, damage, trash/)).toBeVisible()
    await expect(card.getByText(/Say thanks to whoever keeps it up/)).toBeVisible()
  })

  // NOT TESTED HERE, AND THE REASON IS A MEASUREMENT (2026-09-11). #1122's
  // rotation deals the affirmative answer from a list of synonyms and says it
  // is "PICKED ONCE PER WAYPOINT AND HELD". The first version of this describe
  // asserted exactly that across a fold and went red: measured against release
  // 2026-09-10, the word is stable while the card stays at one height (8 reads,
  // 0 changes, the card re-placed by a map nudge between each) and re-rolls
  // when the card is pulled open and folded back (5 changes in 8 folds on one
  // run, 3 in 8 on another — about what a uniform re-roll over four words
  // gives). PoiCard.tsx renders `conditions('peek')` and `conditions('open')`
  // at different positions in its tree, so the fold unmounts the section and
  // takes the held rotation with it. See features/FLOW_TESTING.md's known gaps;
  // the property is real and the build does not have it, so there is no green
  // assertion to write until it does.
})

test.describe('who looks after this stretch', () => {
  /**
   * Below the seam, and sweep for the club sheet rather than the line sheet.
   *
   * Deliberately its own sweep and not a parameter on `tapTheTrail`: the two
   * are looking for different things. `tapTheTrail` wants ANY trail line and
   * stops at the first sheet of either kind; this wants the A.T. specifically,
   * because `clubDetail` is null unless `mileOnTrail` can place the tapped
   * point on the published centerline — so a tap that lands on a side trail is
   * a miss here and a hit there. Measured at this camera (support/seed.ts):
   * the side trails are hit more often than the A.T. on the way, which is why
   * this closes whatever it opened and keeps going.
   */
  async function tapTheAppalachianTrail(page: Page): Promise<Locator> {
    const box = await frameOf(page)
    const club = page.getByRole('dialog', { name: 'Who maintains this trail' })
    const line = page.getByRole('dialog', { name: 'Trail line' })

    for (let down = HEADER_ROWS; down < 20; down += 1) {
      for (let across = 1; across < 20; across += 1) {
        await page.mouse.click(
          box.x + (box.width * across) / 20,
          box.y + (box.height * down) / 20,
        )
        // Read straight after the click, the way `tapTheTrail` does. The
        // first version of this waited a beat with `expect.poll`, which was
        // both pointless — the predicate it polled was always true — and
        // actively harmful: on a loaded machine two `count()` calls can
        // outlast the poll's own timeout, so the wait invented a failure the
        // app had nothing to do with.
        if ((await club.count()) > 0) return club
        if ((await line.count()) > 0) {
          await line.getByRole('button', { name: /^Close/ }).click()
          await expect(line).toHaveCount(0)
        }
      }
    }
    throw new Error(
      'no tap on the whole frame opened the club sheet — either the release moved the ' +
        'A.T. out of this camera, or the club-section artifact stopped publishing',
    )
  }

  async function openMapBelowTheSeam(page: Page): Promise<void> {
    await seedCamera(page, ON_THE_TRAIL, BELOW_THE_SEAM_ZOOM)
    await openMap(page)
    const legend = await openLegend(page)
    await expect(legend).toContainText('Trails in view', { timeout: SKETCHES_BOUND_MS })
    await legend.getByRole('button', { name: /Close legend/ }).click()
    await expect(page.getByRole('dialog', { name: 'Legend' })).toHaveCount(0)
  }

  test('entrance and states: below the seam a tap names the club, its miles, and where both facts came from', async ({
    page,
  }) => {
    await openMapBelowTheSeam(page)
    const sheet = await tapTheAppalachianTrail(page)

    // WHAT IS PINNED IS THE SHAPE, not the release. A club's name, its mile
    // range and its maintained mileage all move when the ATC redraws a
    // section, so the assertions are on the sentences' form.
    await expect(sheet.getByText(/^mi [\d,.]+ – [\d,.]+$/)).toBeVisible()
    await expect(
      sheet.getByText(/[\d,.]+ mi maintained, in \d+ sections?$/),
    ).toBeVisible()

    // TWO SOURCES, NOT ONE, and this is the assertion worth having. WHICH club
    // maintains a mile comes from the ATC's centerline; HOW that club's name
    // is spelled comes from their club-section polygons — two layers, edited
    // on different days (lib/clubSections.ts's header). A sheet that printed
    // one date for both would be claiming a currency it does not have.
    await expect(sheet.getByText(/^Who maintains it: .+, \d/)).toBeVisible()
    await expect(sheet.getByText(/^Club name: .+, \d/)).toBeVisible()
  })

  test('states: the club sheet and the line sheet never stack — one tap asks one question', async ({
    page,
  }) => {
    await openMapBelowTheSeam(page)
    await tapTheAppalachianTrail(page)

    // chrome/tappedLinePanel.tsx makes them mutually exclusive by
    // construction, and this is that property from outside: with the club
    // sheet up there is no "Trail line" dialog anywhere behind it.
    await expect(page.getByRole('dialog', { name: 'Trail line' })).toHaveCount(0)
  })

  test('states: the same question is not asked above the seam, where a tap is about the line', async ({
    page,
  }) => {
    // The other half of "which question depends on the zoom". At the closer
    // camera the line sheet is what a tap on the A.T. opens, so the club sheet
    // must be absent — asserted here rather than assumed, because a club sheet
    // that leaked upward would answer a question nobody asked while hiding the
    // blaze and the source a hiker at that zoom is actually reading.
    await openMapOnTheTrail(page)
    const sheet = await tapTheTrail(page)
    await expect(sheet).toBeVisible()
    await expect(
      page.getByRole('dialog', { name: 'Who maintains this trail' }),
    ).toHaveCount(0)
  })

  test('exit: closing the club sheet leaves the map, and a second tap can ask again', async ({
    page,
  }) => {
    await openMapBelowTheSeam(page)
    const sheet = await tapTheAppalachianTrail(page)

    await sheet.getByRole('button', { name: /^Close/ }).click()
    await expect(sheet).toHaveCount(0)
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()

    // Re-openable rather than a one-shot: the close clears the selection, so
    // the next tap is a fresh question rather than a dead control.
    await expect(await tapTheAppalachianTrail(page)).toBeVisible()
  })
})
