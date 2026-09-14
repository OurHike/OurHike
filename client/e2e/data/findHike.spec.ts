// Routes somebody published, and what the app is allowed to say about them —
// the half of F2 and F8 in features/FLOW_TESTING.md's battery that needs a
// bucket, because a shelf of published walks on a phone that downloaded
// nothing is an empty shelf.
//
// e2e/today.spec.ts and e2e/plan.spec.ts drive those screens with nothing on
// the phone, which is a real state and the only one the hermetic half can
// reach. This file drives the same screens with `suggested_hikes.json`
// under them: the shelf, the finder behind "All N ›", a facet sheet, and one
// route's whole record.
//
// WHAT IS ASSERTED, AND WHAT IS DELIBERATELY NOT. Same rule as the rest of
// e2e/data/: the release moves, so nothing here names a route, a publisher, a
// mileage or a count. Every number is read off the screen that offered it and
// checked against the screen it opened — "the door says nine, so the list
// holds nine" is a claim about the app; "there are nine" is a claim about a
// publish, and NYNJTC may post a tenth tomorrow.
//
// THE ONE RULE THIS FILE EXISTS FOR is lib/suggestedHikes.ts's, and it is an
// honesty rule rather than a UI one: "nothing in here invents a rating, and
// nothing prices a walk whose climb nobody measured," and its consequence,
// "THE FACET SHEETS ARE HONEST BECAUSE THEY COUNT… a filter is never a
// promise the list then breaks." Both are driven below against whatever the
// release actually carries.
//
// ENTRANCE. Boot, then the doors a hiker uses. No navigator state is injected
// (FLOW_TESTING.md, "Not a router").

import { test, expect, type Page, type Locator } from '@playwright/test'
import { seedPreferences, seedHikerMode } from '../support/seed'

/** Today in day mode, with the published shelf on screen. Waiting on the
 *  shelf's own door rather than on a timer: the routes arrive over the
 *  network, and every assertion here is about them. */
async function todayWithRoutes(page: Page): Promise<Locator> {
  await seedPreferences(page)
  await seedHikerMode(page, 'day')
  await page.goto('/')
  // Case-insensitive because the rule's label is upper-cased by CSS while the
  // accessible name follows the DOM text — the two disagree, and asserting
  // the rendered spelling here would be asserting a stylesheet.
  const door = page.getByRole('button', { name: /^all \d+/i })
  await expect(door).toBeVisible()
  return door
}

/** The count a door or heading is claiming, so a spec never writes one down. */
function countIn(text: string): number {
  const match = text.match(/(\d[\d,]*)/)
  if (match === null) throw new Error(`no count in ${JSON.stringify(text)}`)
  return Number(match[1].replace(/,/g, ''))
}

test.describe('the shelf of published walks', () => {
  test('states: the shelf shows a few, names who published each, and its door counts them all', async ({
    page,
  }) => {
    const door = await todayWithRoutes(page)
    const published = countIn(await door.innerText())

    // SHELF_SIZE is three and the door exists because there are more than
    // that — read off the screen rather than written down, so this holds on a
    // release with eleven routes and on one with four.
    const cards = page.locator('.today__suggested-rail .suggested-hike__name')
    const shown = await cards.count()
    expect(shown).toBeGreaterThan(0)
    expect(shown).toBeLessThan(published)

    // Every card names its publisher. That is the feature's own line — "the
    // app surfaces it and names who wrote it; it never rates, ranks or scores
    // a route itself" — and a card that lost its by-line would be the app
    // quietly claiming the walk.
    const authors = page.locator('.today__suggested-rail .suggested-hike__author')
    await expect(authors).toHaveCount(shown)
    for (let i = 0; i < shown; i += 1) {
      await expect(authors.nth(i)).not.toHaveText('')
    }
  })

  test('states: with no fix the rule over the shelf claims no distance', async ({
    page,
  }) => {
    // "No fix makes no distance claim — the rule above the shelf reads
    // 'Suggested hikes', not 'near you'." This suite grants no geolocation and
    // seeds no kept place, so this is the honest half, and the one a hiker in
    // a basement gets. The other half needs a fix and belongs with the
    // geolocation specs.
    await todayWithRoutes(page)

    await expect(page.getByText('Suggested hikes', { exact: true })).toBeVisible()
    await expect(page.getByText('Hikes near you', { exact: true })).toHaveCount(0)
  })

  test('states: the shelf offers exactly the filters the finder can answer', async ({
    page,
  }) => {
    // THE DEAD-CONTROL RULE, ACROSS TWO SCREENS. lib/suggestedHikes.ts names
    // `availableFacets` as "the one place that is decided", and the finder
    // asks it. The shelf's "Have less time?" chips did not, so on a release
    // where nothing carries a measured climb they opened the finder on
    // "0 hikes" — three taps to a dead end the screen one door along already
    // knew was dead.
    //
    // The claim is the AGREEMENT rather than either answer, so this test says
    // the same thing on a release that prices every route and on one that
    // prices none.
    const door = await todayWithRoutes(page)
    const timeChip = page.getByRole('button', { name: 'Under 2 hours' })
    const shelfOffersTime = (await timeChip.count()) > 0

    await door.click()
    await expect(page.getByRole('heading', { name: 'Find a hike' })).toBeVisible()
    const finderOffersTime =
      (await page.getByRole('button', { name: /^Time/ }).count()) > 0

    expect(shelfOffersTime).toBe(finderOffersTime)
  })
})

test.describe('the finder', () => {
  test('entrance and states: the door opens every route on the phone, and says it is only those', async ({
    page,
  }) => {
    const door = await todayWithRoutes(page)
    const published = countIn(await door.innerText())
    await door.click()

    await expect(page.getByRole('heading', { name: 'Find a hike' })).toBeVisible()
    // The door's number and the list agree. This is the assertion the whole
    // file is shaped around: neither side is written down.
    // One locator, not two: a finder row carries both `.suggested-hike__name`
    // and `.find-hike__row-text`, so naming the pair counts every row twice.
    await expect(page.locator('.suggested-hike__name')).toHaveCount(published)

    // THE SENTENCE THAT MAKES THE SCREEN HONEST. A search box on a phone
    // implies the world; this one is over the download and says so, which is
    // the difference between "no results" and "no results here".
    await expect(
      page.getByText(/Only routes inside what you have downloaded can be searched/),
    ).toBeVisible()
  })

  test('exit: the finder’s back goes to Today, which is where the door was', async ({
    page,
  }) => {
    const door = await todayWithRoutes(page)
    await door.click()
    await expect(page.getByRole('heading', { name: 'Find a hike' })).toBeVisible()

    // The back is labelled for where it GOES, which is the rail's rule and
    // the reason to assert the label rather than a chevron.
    await page.getByRole('button', { name: /Today/ }).first().click()
    await expect(page.getByRole('button', { name: /^all \d+/i })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Find a hike' })).toHaveCount(0)
  })
})

test.describe('a facet sheet', () => {
  test('states: every option carries the count it would leave, and the button promises the same number', async ({
    page,
  }) => {
    // "THE FACET SHEETS ARE HONEST BECAUSE THEY COUNT. Each option says how
    // many hikes it would leave, and the primary button says the number it is
    // about to show, so a filter is never a promise the list then breaks."
    // Three surfaces have to agree — the option, the button, and the list —
    // and this drives all three rather than trusting the first.
    const door = await todayWithRoutes(page)
    const published = countIn(await door.innerText())
    await door.click()
    await page.getByRole('button', { name: /^Difficulty/ }).click()

    const sheet = page.getByRole('dialog', { name: 'Difficulty' })
    await expect(sheet).toBeVisible()
    // The publisher's scale, said to be the publisher's. The app does not
    // rate a walk, and the caveat is where it says so.
    await expect(sheet).toContainText(/never rated by the app/i)

    // The options partition the set: with no other facet on, the counts sum
    // to everything that carries a rating at all, which cannot exceed the
    // published total.
    const options = sheet.locator('.facet-sheet__count')
    const optionCount = await options.count()
    expect(optionCount).toBeGreaterThan(0)
    let summed = 0
    for (let i = 0; i < optionCount; i += 1)
      summed += countIn(await options.nth(i).innerText())
    expect(summed).toBeLessThanOrEqual(published)

    // Pick the first option and hold the button to that option's own number.
    const firstCount = countIn(await options.first().innerText())
    await sheet.locator('.facet-sheet__option-text').first().click()
    const show = sheet.getByRole('button', { name: /^Show \d+ hike/ })
    expect(countIn(await show.innerText())).toBe(firstCount)

    // And the list keeps the promise, which is the half a counting bug would
    // not show.
    await show.click()
    await expect(sheet).toHaveCount(0)
    await expect(page.getByText(new RegExp(`^${firstCount} hikes?$`))).toBeVisible()
  })

  test('exit: closing the sheet without choosing leaves the list as it was', async ({
    page,
  }) => {
    const door = await todayWithRoutes(page)
    const published = countIn(await door.innerText())
    await door.click()
    const rows = page.locator('.suggested-hike__name')
    await expect(rows).toHaveCount(published)

    await page.getByRole('button', { name: /^Difficulty/ }).click()
    const sheet = page.getByRole('dialog', { name: 'Difficulty' })
    await expect(sheet).toBeVisible()
    // THE SCRIM, TAPPED WHERE A THUMB CAN ACTUALLY REACH IT. Playwright's
    // plain `.click()` aims at an element's centre, and the scrim's centre is
    // under the sheet — the click is refused, with the sheet's own head named
    // as the thing intercepting it. That is not a Playwright artefact: it is
    // the screen. The scrim is only tappable in the strip ABOVE the sheet, and
    // the strip is what this clicks.
    //
    // WORTH KNOWING, because the sheet's other exit is Escape and a phone has
    // not got one: on a shorter phone, or with a facet carrying more options
    // than difficulty's five, that strip shrinks. Measured here so a later
    // reader can tell whether it has gone.
    const scrim = page.getByTestId('facet-scrim')
    const sheetBox = await sheet.boundingBox()
    const scrimBox = await scrim.boundingBox()
    if (sheetBox === null || scrimBox === null) throw new Error('no box to tap')
    const strip = sheetBox.y - scrimBox.y
    expect(strip).toBeGreaterThan(0)
    await scrim.click({ position: { x: scrimBox.width / 2, y: Math.min(8, strip / 2) } })

    await expect(page.getByRole('dialog', { name: 'Difficulty' })).toHaveCount(0)
    await expect(rows).toHaveCount(published)
  })
})

test.describe('one route’s record', () => {
  test('entrance and states: the card opens the route it names, and the record shows both measurements rather than choosing', async ({
    page,
  }) => {
    await todayWithRoutes(page)
    const card = page.locator('.today__suggested-rail .suggested-hike__name').first()
    const name = await card.innerText()
    await card.click()

    // Same wiring claim as the waypoint card (e2e/data/mapSheets.spec.ts):
    // the row opens the thing it named, read off the row rather than written
    // down.
    await expect(page.locator('.hike-detail__name')).toHaveText(name)

    // NEVER LET A DISPLAY OUTRUN ITS SOURCE (CLAUDE.md). The figures line
    // carries the app's OWN measurement, says what it measured against, and
    // then says what the publisher claims — rather than picking one and
    // presenting it as the distance. Two numbers that disagree, both
    // attributed, is the honest answer; one number is a decision the app is
    // not entitled to make on a hiker's behalf.
    const figures = page.locator('.hike-detail__figures')
    await expect(figures).toBeVisible()
    await expect(
      page.getByText(/measured on the trail lines this phone holds/),
    ).toBeVisible()
    await expect(page.getByText(/says [\d.]+ mi/)).toBeVisible()
  })

  test('exit: the record’s back returns to the shelf it was opened from', async ({
    page,
  }) => {
    await todayWithRoutes(page)
    await page.locator('.today__suggested-rail .suggested-hike__name').first().click()
    await expect(page.locator('.hike-detail__name')).toBeVisible()

    await page.getByRole('button', { name: /Back/ }).first().click()

    await expect(page.getByRole('button', { name: /^all \d+/i })).toBeVisible()
    await expect(page.locator('.hike-detail__name')).toHaveCount(0)
  })
})
