// The organization console and the volunteer's own screens, in a real
// browser - #1539 to #1542, against features/FLOW_TESTING.md's four rules.
//
// ENTRANCE, AND THE ONE HONEST EXCEPTION TO RULE 1. The battery asks for "an
// actual tap sequence from boot, never a URL". This surface is the one place
// that rule does not describe what shipped, and pretending otherwise would
// make these tests prove something other than the product: `lib/orgRoute.ts`
// exists precisely BECAUSE the org surface is reached by address - a link in
// a welcome email, an organization's own members area, a bookmark - and the
// hiker's app deliberately links to none of it. So the entrance under test is
// the address, and what is asserted is what rule 1 actually cares about: that
// arriving there lands on the screen, drawn, rather than on a blank frame or
// on the map with a flash of console.
//
// The rule's substance survives intact, because the failure it exists to
// catch is the same one either way: a screen that every unit test renders and
// that nobody can actually get to.
//
// EXIT. Every console screen can be left by the rail, and the rail is what
// these drive - the same control a person would use. The volunteer's screens
// exit to the app itself, which is the move a maintainer makes most often and
// the one with nothing above it to fall back on.
//
// STATES. Read off the console's own conditional rendering rather than
// guessed: signed out, an organization mid-onboarding, one that has finished,
// a route naming an organization that does not exist, and `/my/tread` with no
// organization at all. The last is the address a welcome email links to and
// the one a person is likeliest to reach with a piece missing.
//
// WHY THE DEMO ORGANIZATION. `isDemoOrg` short-circuits every fetch, so this
// suite drives real screens with real rows and touches no network - which is
// what TESTING.md asks of every test here, and is the only way to test this
// surface at all while #600 leaves the production backend unbuilt. The org is
// invented and every coordinate is the real park; `client/src/org/demoOrg.ts`
// says so at length and the console says so on screen.

import { expect, test, type Page } from '@playwright/test'
import { seedPreferences } from './support/seed'

const DEMO = 'central-park-throughikers'

/** Open one console address on a browser that has been through first run.
 *
 *  `seedPreferences` is what stops the app opening on its onboarding, which
 *  would otherwise be the only thing any of these tests photographed.
 */
async function openOrg(page: Page, path: string): Promise<void> {
  await seedPreferences(page)
  await page.goto(path)
}

test.describe('arriving at an organization console', () => {
  test('the setup hub draws the organization it names', async ({ page }) => {
    await openOrg(page, `/org/${DEMO}/setup`)

    await expect(
      page.getByRole('heading', { name: 'Central Park Throughikers' }),
    ).toBeVisible()
    // The banner is not decoration: it is the screen saying the numbers on it
    // are invented, and a reviewer reading a screenshot needs it in frame.
    await expect(page.getByText('This is the demo organization.')).toBeVisible()
  })

  test('every console address lands on its own screen rather than a default', async ({
    page,
  }) => {
    // The whole set, because a router that fell back to one screen for an
    // unrecognised `page` would pass any single-address test.
    const screens = [
      { path: `/org/${DEMO}/setup?page=approve`, heading: /approving/i },
      { path: `/org/${DEMO}/setup?page=registry`, heading: /turn your GIS/i },
      { path: `/org/${DEMO}/setup?page=signoff`, heading: /confirm it is accurate/i },
      { path: `/org/${DEMO}/setup?page=addtrail`, heading: /not a new registry/i },
      { path: `/org/${DEMO}/setup?page=embeds`, heading: /your own site/i },
      { path: `/org/${DEMO}/setup?page=emails`, heading: /three emails/i },
      { path: `/org/${DEMO}/setup?page=leaving`, heading: /on your terms/i },
      { path: `/org/${DEMO}/volunteers?page=roles`, heading: /which section/i },
      { path: `/org/${DEMO}/volunteers?page=workdays`, heading: /signups and hours/i },
      { path: `/org/${DEMO}/volunteers?page=coverage`, heading: /coverage gaps/i },
      { path: `/org/${DEMO}/volunteers?page=roster`, heading: /your roster/i },
      {
        path: `/org/${DEMO}/volunteers?page=welcome`,
        heading: /welcome your volunteers/i,
      },
    ] as const

    for (const screen of screens) {
      await openOrg(page, screen.path)
      await expect(
        page.getByRole('heading', { name: screen.heading }),
        `${screen.path} did not land on its own screen`,
      ).toBeVisible()
    }
  })

  test('the five volunteer screens each land on their own', async ({ page }) => {
    const screens = [
      { path: `/my/tread?org=${DEMO}`, heading: /The Ramble/i },
      { path: `/my/tread?org=${DEMO}&page=phone`, heading: /actually gets logged/i },
      { path: `/my/tread?org=${DEMO}&page=handback`, heading: /hand back/i },
      { path: `/my/tread?org=${DEMO}&page=ridge`, heading: /out this week/i },
      { path: `/my/tread?org=${DEMO}&page=profile`, heading: /Alex Mercer/i },
    ] as const

    for (const screen of screens) {
      await openOrg(page, screen.path)
      await expect(
        page.getByRole('heading', { name: screen.heading }),
        `${screen.path} did not land on its own screen`,
      ).toBeVisible()
    }
  })
})

test.describe('moving around the console', () => {
  test('the rail moves between screens and the address follows', async ({ page }) => {
    // A rail that changed the screen without changing the address would give
    // a person a page they cannot bookmark or send - which is the whole thing
    // #970 is about.
    await openOrg(page, `/org/${DEMO}/setup`)

    await page.getByRole('button', { name: 'Coverage report' }).click()

    await expect(page.getByRole('heading', { name: /coverage gaps/i })).toBeVisible()
    expect(page.url()).toContain('page=coverage')
  })

  test('Back returns to the screen before it', async ({ page }) => {
    // The browser's own button, which a hand-rolled router is the likeliest
    // thing in this app to break - `popstate` is the one event it answers.
    await openOrg(page, `/org/${DEMO}/setup`)
    await page.getByRole('button', { name: 'Your roster' }).click()
    await expect(page.getByRole('heading', { name: /your roster/i })).toBeVisible()

    await page.goBack()

    await expect(
      page.getByRole('heading', { name: 'Central Park Throughikers' }),
    ).toBeVisible()
  })

  test('a volunteer can leave their own screens for the app', async ({ page }) => {
    // Rule 2. The volunteer screens are where somebody spends a morning, and
    // a maintainer who cannot get back to the map is a maintainer who closes
    // the tab.
    await openOrg(page, `/my/tread?org=${DEMO}`)
    await expect(page.getByRole('heading', { name: /The Ramble/i })).toBeVisible()

    // A BUTTON, not a link. The mark leaves the console by calling the
    // router rather than by navigating, so that Back from the app returns
    // here rather than to whatever was before the console - and a locator
    // looking for a link finds nothing, which is how this was first written
    // and what the failure said.
    await page
      .getByRole('button', { name: /OurHike/i })
      .first()
      .click()

    await expect(page.getByRole('tab', { name: 'Today' })).toBeVisible()
  })
})

test.describe('the states a console can be in', () => {
  test('a person who is not signed in still reads an organization', async ({ page }) => {
    // The demo is readable signed out on purpose: the design's argument is
    // that a trails chair sees their own pages BEFORE typing anything.
    await openOrg(page, `/org/${DEMO}/setup`)

    await expect(page.getByText(/signed out/i)).toBeVisible()
    await expect(
      page.getByRole('heading', { name: 'Central Park Throughikers' }),
    ).toBeVisible()
  })

  test('an address naming an organization nobody has says so', async ({ page }) => {
    // Not a blank screen and not the demo's data under somebody else's name.
    await openOrg(page, '/org/an-organization-that-does-not-exist/setup')

    await expect(
      page.getByText(/could not load|reading your organization/i),
    ).toBeVisible()
  })

  test('`/my/tread` with no organization asks which one', async ({ page }) => {
    // The address a welcome email links to, reached without its query string.
    // It used to hold on "reading your organization" forever and then draw an
    // invented section name, which is the worst of the three possible answers.
    await openOrg(page, '/my/tread')

    await expect(page.getByText(/which organization/i)).toBeVisible()
    await expect(page.getByText('The Ramble')).toHaveCount(0)
  })

  test('an unknown page on a real organization falls back rather than blanking', async ({
    page,
  }) => {
    await openOrg(page, `/org/${DEMO}/setup?page=not-a-real-page`)

    await expect(
      page.getByRole('heading', { name: 'Central Park Throughikers' }),
    ).toBeVisible()
  })

  test('the hiker app is untouched by any of this', async ({ page }) => {
    // The console returns early from App's render, so the one risk of
    // mounting it at all is that it reaches a hiker who never asked for it.
    await seedPreferences(page)
    await page.goto('/')

    await expect(page.getByRole('tab', { name: 'Today' })).toBeVisible()
    await expect(page.locator('.org__rail')).toHaveCount(0)
  })
})

test.describe('what the screens refuse to do', () => {
  test('a land-manager alert carries no way to close it', async ({ page }) => {
    // The one rule on the volunteer's screens a hiker's safety turns on, and
    // it is an ABSENCE - which is exactly the kind of thing a unit test can
    // assert and a person cannot see in a diff.
    await openOrg(page, `/my/tread?org=${DEMO}`)

    const alerts = page.locator('.org-callout[data-tone="stop"]')
    await expect(alerts.first()).toBeVisible()
    await expect(alerts.first().getByRole('button')).toHaveCount(0)
  })

  test('the coverage report never tells a hiker a section is unmaintained', async ({
    page,
  }) => {
    // A gap is a recruiting line. The word this screen must not use about a
    // section is the one a hiker would read as a routing decision.
    await openOrg(page, `/org/${DEMO}/volunteers?page=coverage`)
    await expect(page.getByRole('heading', { name: /coverage gaps/i })).toBeVisible()

    await expect(page.getByText(/unmaintained/i)).toHaveCount(0)
  })

  test('the embed paste never carries a secret', async ({ page }) => {
    // What an organization pastes goes into page source on their own site.
    await openOrg(page, `/org/${DEMO}/setup?page=embeds`)

    const paste = page.locator('pre.org-code').first()
    await expect(paste).toBeVisible()
    await expect(paste).not.toContainText('data-secret')
    await expect(paste).toContainText('data-org')
  })

  test('the assist panel says it suggests rather than changes', async ({ page }) => {
    await openOrg(page, `/org/${DEMO}/volunteers?page=coverage`)

    await expect(page.getByText('suggestions, not changes')).toBeVisible()
  })
})

test.describe('the console at desk width', () => {
  test('@desktop the rail is a column beside the screen, not a band above it', async ({
    page,
  }) => {
    // The console's own CSS forks at 900px: below it the rail stacks and
    // above it the rail is a fixed column. That fork is a behaviour the phone
    // project cannot see at all, and the wireframes are drawn at 1440 - so a
    // console that only ever worked at 390px would look correct in every
    // other test here and wrong to every person who uses it.
    await openOrg(page, `/org/${DEMO}/setup`)
    await expect(
      page.getByRole('heading', { name: 'Central Park Throughikers' }),
    ).toBeVisible()

    const rail = await page.locator('.org__rail').boundingBox()
    const body = await page.locator('.org__body').boundingBox()
    expect(rail).not.toBeNull()
    expect(body).not.toBeNull()

    // Beside: the rail's right edge is at or before the body's left edge.
    expect(rail!.x + rail!.width).toBeLessThanOrEqual(body!.x + 1)
    // And a column rather than a sliver - the rail carries eighteen labels.
    expect(rail!.width).toBeGreaterThan(200)
  })

  test('@desktop the registry table and its map sit side by side', async ({ page }) => {
    // The sign-off screen's whole argument is that an organization reads the
    // table against the drawing. Stacked, they are two screens.
    await openOrg(page, `/org/${DEMO}/setup?page=signoff`)
    await expect(
      page.getByRole('heading', { name: /confirm it is accurate/i }),
    ).toBeVisible()

    const table = await page.locator('table').first().boundingBox()
    // By its aria-label, not by `svg[role="img"]`: the page header's glyph is
    // an svg too and is 41px tall, which is what the first version of this
    // matched and why it reported the map above the table.
    const map = await page.locator('svg[aria-label*="sections"]').first().boundingBox()
    expect(table).not.toBeNull()
    expect(map).not.toBeNull()

    // Their vertical ranges overlap, which is what "beside" means and what
    // stacking would break.
    expect(map!.y).toBeLessThan(table!.y + table!.height)
    expect(table!.y).toBeLessThan(map!.y + map!.height)
  })
})
