import { test, expect, type Page } from '@playwright/test'
import {
  serveMarketingSite,
  openSitePage,
} from '../preview-shots/fixtures/marketingSite.mjs'
import { serveDataQuality } from '../preview-shots/fixtures/dataQuality.mjs'
import {
  EXAMPLE_NOW,
  hourlyManyProblems,
  hourlyWithWarning,
  monthlyManyProblems,
  monthlyWithWarnings,
} from '../../site/src/lib/dataQualityExamples.mjs'

/**
 * ourhike.org/data/quality/'s controls, driven the way a reader drives them -
 * the keyboard first - against an INVENTED pair of files with 43 entries and
 * 38 series (site/src/lib/dataQualityExamples.mjs). The maintainer's round-3
 * choice (pipeline/ELT.md decision 102, 2026-10-08): every failure listed and
 * the warnings folded by kind; a Show menu above the chart; a Chart button on
 * each row with a history and on each mart, kept in step with the menu. And
 * its answers to round 3's forks (2026-10-08): the first chart's own button
 * starts pressed, and a kind with three warnings or fewer opens by itself.
 *
 * What each control SHOWS is decided in site/src/lib/dataQuality.mjs and held
 * by the site's vitest suite; this holds that the page wires it up - focus
 * goes where a reader needs it, and the menu and the buttons agree after each
 * step. sitePages.spec.ts holds the same page to the site's targets and
 * contrast. Like it, this serves site/dist, which CI builds before the flow job.
 */

const LOOK = 'section[aria-labelledby="dq-look-title"]'
const MARTS = 'section[aria-labelledby="dq-marts-title"]'

async function open(
  page: Page,
  files: { monthly: object; hourly: object } = {
    monthly: monthlyManyProblems(),
    hourly: hourlyManyProblems(),
  },
) {
  await page.clock.setFixedTime(new Date(EXAMPLE_NOW))
  await serveMarketingSite(page)
  await serveDataQuality(page, files)
  await page.goto('/', { waitUntil: 'load' })
  await openSitePage(page, '/data/quality/')
  await page.locator('[data-slot="body"][aria-busy="false"]').waitFor()
}

const title = (page: Page) => page.locator('#dq-chart-title')
const menu = (page: Page) => page.locator('[data-chart-select]')
const pressed = (page: Page) => page.locator('[data-chart-key][aria-pressed="true"]')
const row = (page: Page, table: string, kind: string) =>
  page.locator(`${LOOK} li.dq-item`).filter({ hasText: table }).filter({ hasText: kind })

test('lists every failure and folds only the warnings, a fold opening from the keyboard', async ({
  page,
}) => {
  await open(page)
  const listed = page.locator(`${LOOK} > ul.dq-items > li`)
  await expect(listed).toHaveCount(8)
  for (const item of await listed.all()) await expect(item).toBeVisible()
  const folds = page.locator(`${LOOK} details.dq-fold`)
  await expect(folds).toHaveCount(4)
  for (const fold of await folds.all()) await expect(fold).not.toHaveAttribute('open')

  const volume = page.locator('details[data-fold="volume"]')
  await volume.locator('summary').focus()
  await page.keyboard.press('Enter')
  await expect(volume).toHaveAttribute('open')
  await expect(volume.locator('li.dq-item')).toHaveCount(14)
  // The next stop after the line is the first row's Chart button inside it.
  await page.keyboard.press('Tab')
  await expect(volume.locator('[data-chart-key]').first()).toBeFocused()
})

test('a Chart button pressed from the keyboard charts its row, sets the menu, and comes back', async ({
  page,
}) => {
  await open(page)
  // The first chart's own row starts pressed: the failed null-rate check.
  const opening = row(page, 'trail_status', 'Anomalies').locator('[data-chart-key]')
  await expect(pressed(page)).toHaveCount(1)
  await expect(opening).toHaveAttribute('aria-pressed', 'true')
  await page.locator('details[data-fold="volume"] > summary').click()
  const button = row(page, 'preview_fixture_12__shelters', 'Volume').locator(
    '[data-chart-key]',
  )
  await button.focus()
  await page.keyboard.press('Enter')

  await expect(title(page)).toContainText('preview_fixture_12__shelters')
  await expect(title(page)).toBeFocused()
  expect(await menu(page).inputValue()).toContain('preview_fixture_12__shelters')
  await expect(button).toHaveAttribute('aria-pressed', 'true')
  await expect(opening).toHaveAttribute('aria-pressed', 'false')
  await expect(pressed(page)).toHaveCount(1)
  await expect(page.locator('[data-charted]')).toContainText('Charted from Needs a look')

  // From the title, the next Tab is the way back.
  await page.keyboard.press('Tab')
  const back = page.locator('[data-back]')
  await expect(back).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(button).toBeFocused()
  await expect(button).toHaveAttribute('aria-pressed', 'true')
})

test('the first chart’s button starts pressed inside its closed fold, and Back to the row opens it', async ({
  page,
}) => {
  // Without the null-rate failure's history, the first chart is the first
  // Volume warning's, and Volume's 14 warnings stay folded.
  const monthly = monthlyManyProblems()
  monthly.series = monthly.series.filter((series) => series.column !== 'trail_status')
  await open(page, { monthly, hourly: hourlyManyProblems() })
  const volume = page.locator('details[data-fold="volume"]')
  await expect(volume).not.toHaveAttribute('open')
  const button = row(page, 'preview_fixture_07__water_sources', 'Volume').locator(
    '[data-chart-key]',
  )
  await expect(button).toHaveAttribute('aria-pressed', 'true')
  await expect(title(page)).toContainText('preview_fixture_07__water_sources')
  await expect(page.locator('[data-charted]')).toContainText(
    'Charted from Needs a look · preview_fixture_07__water_sources',
  )

  await page.locator('[data-back]').click()
  await expect(volume).toHaveAttribute('open')
  await expect(button).toBeFocused()
})

test('a kind with three warnings or fewer is open as the page loads', async ({
  page,
}) => {
  await open(page, { monthly: monthlyWithWarnings(), hourly: hourlyWithWarning() })
  const folds = page.locator(`${LOOK} details.dq-fold`)
  await expect(folds).toHaveCount(4)
  for (const fold of await folds.all()) await expect(fold).toHaveAttribute('open')
  await expect(page.locator(`${LOOK} li.dq-item`).first()).toBeVisible()
})

test('a choice in the Show menu clears the pressed button and the line naming it', async ({
  page,
}) => {
  await open(page)
  await page.locator('details[data-fold="volume"] > summary').click()
  await row(page, 'preview_fixture_12__shelters', 'Volume')
    .locator('[data-chart-key]')
    .click()
  await expect(pressed(page)).toHaveCount(1)

  await menu(page).selectOption({ label: 'Rows in trail_network · Monthly' })
  await expect(title(page)).toContainText('trail_network')
  await expect(pressed(page)).toHaveCount(0)
  await expect(page.locator('[data-charted]')).toBeHidden()
})

test('a mart charts from under its name on a phone, and the chart says "Charted from By finished table"', async ({
  page,
}) => {
  await open(page)
  const mart = page.locator(`${MARTS} tr`).filter({ hasText: 'trail_network' })
  // One button per width; on a phone the one under the name is the one shown.
  const shown = mart.locator('[data-chart-key]').filter({ visible: true })
  await expect(shown).toHaveCount(1)
  await expect(shown).toHaveClass(/dq-chart-btn--inline/)
  await shown.click()
  await expect(title(page)).toContainText('trail_network')
  expect(await menu(page).inputValue()).toContain('trail_network')
  await expect(page.locator('[data-charted]')).toContainText(
    'Charted from By finished table',
  )
  await expect(mart.locator('[data-chart-key]').first()).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

test('By finished table keeps every table name to one line on a phone, its schedule and check count under it', async ({
  page,
}) => {
  await open(page)
  const names = page.locator(`${MARTS} tbody td:first-child code`)
  await expect(names).toHaveCount(11)
  // One line box each. Beside a Checks column, points_of_interest broke in
  // two at 390 px; the maintainer chose the count under the name, 2026-10-08.
  const broken = await names.evaluateAll((codes) =>
    codes
      .filter((code) => code.getClientRects().length !== 1)
      .map((code) => code.textContent),
  )
  expect(broken).toEqual([])
  await expect(page.locator(`${MARTS} th.dq-col-checks`)).toBeHidden()
  await expect(
    page
      .locator(`${MARTS} tr`)
      .filter({ hasText: 'trail_lines' })
      .locator('.dq-lane-tag'),
  ).toHaveText('Monthly · 412 checks')
})

test('the Show menu chooses from the keyboard on a laptop @desktop', async ({ page }) => {
  await open(page)
  const before = await title(page).textContent()
  await menu(page).focus()
  // Space opens the list (Enter does not, measured in Chromium 141's
  // base-select, 2026-10-08), ArrowDown moves one series down it, Enter takes it.
  await page.keyboard.press('Space')
  await expect
    .poll(() => menu(page).evaluate((select) => select.matches(':open')))
    .toBe(true)
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await expect(title(page)).not.toHaveText(before ?? '')
  await expect(title(page)).toContainText('preview_fixture_07__water_sources')
  expect(await menu(page).inputValue()).toContain('preview_fixture_07__water_sources')
})

test('a mart charts from its own column on a laptop @desktop', async ({ page }) => {
  await open(page)
  const mart = page.locator(`${MARTS} tr`).filter({ hasText: 'elevation' })
  const shown = mart.locator('[data-chart-key]').filter({ visible: true })
  await expect(shown).toHaveCount(1)
  await expect(shown).not.toHaveClass(/dq-chart-btn--inline/)
  await shown.click()
  await expect(title(page)).toContainText('elevation')
  await expect(shown).toHaveAttribute('aria-pressed', 'true')
})
