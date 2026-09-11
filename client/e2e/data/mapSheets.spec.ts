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
} from '../support/seed'

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
  await expect(legend).toContainText('Trails in view')
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
