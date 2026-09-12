// Today's remaining states (client/src/screens/Today.tsx) - the rest of F2 in
// features/FLOW_TESTING.md's battery. `today.spec.ts` holds the two empty
// setup heads and the tab-switch reset; this file holds what that one leaves,
// and deliberately re-asserts none of it.
//
// ENTRANCE. Today is the tab the app boots onto, so the entrance is the boot
// itself: seed IndexedDB, `page.goto('/')`, and the column is up with the
// Today tab selected. No URL past the root and no injected navigator state
// (FLOW_TESTING.md, "Not a router"). Each test asserts the tab is the selected
// one before it asserts anything about the column, because a state test that
// began on the wrong screen would report an absence as a pass.
//
// EXIT. Today's tab-switch exit is today.spec.ts's. The exit here is the one
// only this file's mode has: in volunteer mode the crew card LEADS the column,
// so it is the first door a volunteer meets, and a lead card that swallowed
// its tap would be the whole screen failing quietly. It is driven through to
// the volunteer page and back.
//
// STATES, on the axes this screen actually varies along:
//
//   MODE, all three, and the third is the point. `setup` is a two-branch
//   ternary (`mode === 'day' && …` / `mode === 'long' && …`), so in volunteer
//   mode it is null: the column has NO setup head at all and the crew card
//   leads instead. The same card exists in long mode one voice and several
//   slots down, which is what makes the volunteer claim a contrast rather
//   than an isolated sighting.
//
//   DATA FRESHNESS, on the two of its three values this environment can
//   reach. Nothing here publishes a release manifest or a workday list, so
//   both figures are ABSENT rather than live - and each is asserted as the
//   sentence the screen prints about the absence, not as a number: the
//   download notice's body with no size in front of it, and the crew card's
//   "needs signal to load" meta. A screen that silently swapped an absence
//   for a stale figure prints the same shape and only the sentence can see it.
//
//   THE HIKE PROFILE, which is what makes a walk lead. `todaysWalk` is
//   `dayHikes.find((hike) => hike.date === today)`, so the date is the whole
//   mechanism: the same saved walk leads as its own card dated today and sits
//   on the shelf dated yesterday. Both are driven, because only the pair
//   proves the card is keyed on the date rather than on there being any walk.
//
//   THE PINNED BAR, which is the one thing PinnedBar.tsx says is on "every
//   state of this screen, forever" - so it is asserted in all three modes and
//   in the loaded state as well as the empty one.
//
// WHAT THIS FILE CANNOT DRIVE. The download notice's other half - the notice
// ABSENT once something is downloaded - needs `anySheetDownloaded`, which is
// `archiveStatusFor(pkg.idbKey).state === 'downloaded'` over real archive
// records (lib/useArchiveDownload.ts). That is the download flow's own
// fixture, not a key this suite can hand-seed honestly, and it is noted here
// rather than faked.

import { test, expect, type Locator, type Page } from '@playwright/test'
import { seedPreferences, seedHikerMode, type HikerMode } from './support/seed'
import { seedDayHikes, DAY_HIKES } from '../preview-shots/fixtures/dayHike.mjs'

/** Boot past first run in a given mode and land on Today, the app's own
 *  entry tab. The assertion is part of the helper: every test below reads an
 *  absence at some point, and an absence on the wrong screen is a pass that
 *  means nothing. */
async function todayIn(page: Page, mode: HikerMode): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, mode)
  await page.goto('/')
  await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
}

/**
 * The browser's own local day, offset by whole days - the same arithmetic
 * `lib/passedToday.ts`'s `localDay()` does, which is what Today compares a
 * saved walk's `date` against. Computed in the page rather than in Node
 * deliberately: the comparison is local-time, and a spec that formatted the
 * date on the runner's clock would drift from the browser's the moment the
 * two sat either side of midnight.
 */
async function localDay(page: Page, offsetDays: number): Promise<string> {
  return page.evaluate((offset) => {
    const day = new Date()
    day.setDate(day.getDate() + offset)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`
  }, offsetDays)
}

/**
 * The shared day-hike fixture, dated.
 *
 * `DAY_HIKES` pins its one walk to 2026-08-29 (measured 2026-09-11: a fixed
 * string in the fixture, not a relative date), so the fixture as shipped
 * never dates a walk today and cannot show Today's lead card on its own.
 * Rather than invent a second hike, this re-dates that one through
 * `seedDayHikes`'s own store parameter - the same seam `plan.spec.ts` uses
 * for `finishedStore()`. Everything else about the hike, including its
 * figures, is the fixture's.
 */
async function seedWalkDated(page: Page, offsetDays: number): Promise<void> {
  const date = await localDay(page, offsetDays)
  await seedDayHikes(page, {
    ...DAY_HIKES,
    hikes: DAY_HIKES.hikes.map((hike) => ({ ...hike, date })),
  })
}

/**
 * Which of two elements the column draws first, asked of the document rather
 * than of the locators.
 *
 * "The crew card LEADS" is a claim about order, and order is the one thing a
 * per-element assertion cannot see: every `toBeVisible()` below would pass
 * just as well on a column that drew the card last. `compareDocumentPosition`
 * is the mechanism, and it is used rather than `locator.or(…).first()`
 * because that reading would also pass if the union ever resolved in the
 * order the locators were written rather than in document order - a test that
 * cannot fail is worse than no test.
 */
async function drawnFirst(page: Page, a: Locator, b: Locator): Promise<boolean> {
  const first = await a.elementHandle()
  const second = await b.elementHandle()
  if (first === null || second === null) {
    throw new Error('drawnFirst: both locators must resolve before they can be ordered')
  }
  return page.evaluate(
    ([x, y]) => (x.compareDocumentPosition(y) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0,
    [first, second],
  )
}

/** The crew card, in whichever voice the mode gives it. A regex rather than
 *  the full name: the card's accessible name folds in its eyebrow and its
 *  workday meta, and the meta is a sentence about data this environment does
 *  not have. */
function crewCard(page: Page, title: 'Your day on the trail crew' | 'The trail crew') {
  return page.getByRole('button', { name: new RegExp(title) })
}

test.describe('Today, the rest of its states', () => {
  test('states (mode): volunteer gets no setup head at all, and the crew card leads', async ({
    page,
  }) => {
    await todayIn(page, 'volunteer')

    // The two-branch ternary's null branch, asserted as an absence of the
    // whole SECTION and not just of its words: `today__setup` is a
    // `<section aria-labelledby>`, which is a region with the head's own
    // name, so a head drawn in any wording would still be a region here.
    // Measured 2026-09-11: the volunteer column carries no heading of any
    // kind, which is the strongest form "no setup head" can take.
    await expect(page.getByRole('region', { name: 'Nothing planned today' })).toHaveCount(
      0,
    )
    await expect(page.getByRole('region', { name: 'You have no hike yet' })).toHaveCount(
      0,
    )
    await expect(page.getByRole('heading')).toHaveCount(0)

    // What leads instead - and in its own voice. "Your day on the trail crew"
    // rather than "The trail crew" is the mode reading itself inside the
    // card, so this is the ternary at line 566 as well as the order array.
    const crew = crewCard(page, 'Your day on the trail crew')
    await expect(crew).toBeVisible()
    await expect(crewCard(page, 'The trail crew')).toHaveCount(0)

    // Leading, as a fact about the document. The volunteer order array is
    // ['setup', 'download', 'alerts', 'volunteer', …]: the download notice
    // sits above the card by that array and the card leads everything below
    // it, so both halves are asserted rather than the convenient one.
    const download = page.getByRole('button', { name: 'Download', exact: true })
    const report = page.getByRole('button', { name: 'Report a problem' })
    expect(await drawnFirst(page, download, crew)).toBe(true)
    expect(await drawnFirst(page, crew, report)).toBe(true)

    // The note that exists only in this mode, because the bar is the same on
    // the crew's day and the column says so out loud.
    await expect(page.getByText(/Walking today as well/)).toBeVisible()
  })

  test('states (mode and freshness): the crew card is in long mode too, under the head, and says why it has no workdays', async ({
    page,
  }) => {
    await todayIn(page, 'long')

    // The same card, the other voice, and NOT leading: the long order array
    // puts 'volunteer' below the setup head, the resume card and the day.
    // Without this the volunteer test above would be one observation rather
    // than a contrast, and a card that led in every mode would satisfy it.
    const head = page.getByRole('heading', { name: 'You have no hike yet' })
    const crew = crewCard(page, 'The trail crew')
    await expect(crew).toBeVisible()
    expect(await drawnFirst(page, head, crew)).toBe(true)

    // DATA FRESHNESS, as the sentence rather than as a count. `opportunities`
    // is null here - nothing serves a workday list to this dev server - and
    // the card prints which absence that is instead of an empty list or a
    // zero. The apostrophe in "hasn't" is matched around rather than typed:
    // it is a straight quote in a JS string and a curly one elsewhere on the
    // same screen.
    await expect(crew).toHaveAccessibleName(/needs signal to load/)
  })

  for (const mode of ['day', 'long', 'volunteer'] as const) {
    test(`states (mode): the pinned Find/Plan bar is on Today in ${mode} mode`, async ({
      page,
    }) => {
      // PinnedBar.tsx: "The bar carries Find a hike and Plan on every state of
      // this screen, forever" - the fix for the review's defect D6, where a
      // hiker met three refusals before meeting a way in. All three modes,
      // because the bar is drawn once below an order array that differs in
      // all three and a mode that dropped it would look like every other.
      await todayIn(page, mode)

      const bar = page.getByRole('group', { name: 'Find or plan a hike' })
      await expect(bar).toBeVisible()
      await expect(bar.getByRole('button', { name: 'Find a hike' })).toBeVisible()
      await expect(bar.getByRole('button', { name: 'Plan a hike' })).toBeVisible()
    })
  }

  test('states (freshness): the download notice is on Today with nothing downloaded, and names which figure it has', async ({
    page,
  }) => {
    await todayIn(page, 'day')

    // `hasDownload` is `anySheetDownloaded`, false on a phone with no
    // archives, so the notice is up. Its title is the fact and its action is
    // the next step - Notice.tsx's own rule that every notice carries one,
    // which is what separates it from a dead end.
    const notice = page.getByRole('status').filter({
      hasText: 'The topo sheet is not on this phone',
    })
    await expect(notice).toBeVisible()
    await expect(
      notice.getByRole('button', { name: 'Download', exact: true }),
    ).toBeVisible()

    // THE SENTENCE, and exactly the sentence. `downloadSize` is null until
    // the published manifest has said what the sheet weighs, and nothing in
    // this environment reaches the bucket (FLOW_TESTING.md's "Map data"
    // boundary), so this is the absent branch of the freshness axis. Matched
    // with `exact` because the assertion is about what is NOT in front of the
    // body: with a manifest the same line reads "<size>. Trails and waypoints
    // work without it.", and a size invented while the manifest was unread is
    // precisely the display outrunning its source. The figure itself is never
    // pinned - only whether the screen claims to have one.
    await expect(
      notice.getByText('Trails and waypoints work without it.', { exact: true }),
    ).toBeVisible()
  })

  test('states (hike profile): a day hiker’s walk dated today leads as its own card', async ({
    page,
  }) => {
    await todayIn(page, 'day')
    await seedWalkDated(page, 0)

    // Frame 2c's loaded state: the walk is the subject of the screen rather
    // than a row in a list, so it is its own labelled region rather than the
    // shelf's button. The apostrophe in the label is a curly one in the JSX
    // attribute; matched around rather than guessed at.
    const card = page.getByRole('region', { name: /Today.s walk/ })
    await expect(card).toBeVisible()
    await expect(card.getByRole('heading', { name: 'Pine Meadow loop' })).toBeVisible()

    // The honest-absence sentence, which is this card's half of the freshness
    // axis: the fixture's saved figures carry no climb, and rather than print
    // a Naismith time over a climb nobody measured the card says why there is
    // no time. The 6.4 mi beside it is the fixture's own number and is
    // deliberately not pinned - what is asserted is what the screen SAYS
    // about the figures it has.
    await expect(card.getByText(/no climb measured, so no time/)).toBeVisible()

    // Both of the card's doors. Not driven through: the walk opens
    // screens/DayHikeCard.tsx, which is `dayHikeCard.spec.ts`'s screen, and
    // the battery is not served by two specs asserting the same card.
    await expect(card.getByRole('button', { name: 'Open the walk' })).toBeVisible()
    await expect(card.getByRole('button', { name: 'Walk this' })).toBeVisible()

    // The setup head's other branch: `todaysWalk !== null`, so the "Nothing
    // planned today" head today.spec.ts asserts is gone. The loaded state is
    // a different screen, not the empty one with a card added.
    await expect(
      page.getByRole('heading', { name: 'Nothing planned today' }),
    ).toHaveCount(0)

    // And the bar is still here, which is the "forever" in PinnedBar.tsx's
    // claim - the loaded state is where a bar that only appeared on the empty
    // one would look correct in every screenshot anybody took.
    await expect(page.getByRole('group', { name: 'Find or plan a hike' })).toBeVisible()
  })

  test('states (hike profile): the same walk dated yesterday stays on the shelf and does not lead', async ({
    page,
  }) => {
    // The contrast that makes the date the mechanism rather than the mere
    // presence of a saved walk. One fixture, one field different.
    await todayIn(page, 'day')
    await seedWalkDated(page, -1)

    await expect(page.getByRole('region', { name: /Today.s walk/ })).toHaveCount(0)
    await expect(
      page.getByRole('heading', { name: 'Nothing planned today' }),
    ).toBeVisible()
    // `otherHikes` - everything that is not today's walk - keeps it, so it is
    // reachable rather than lost. Anchored at the start: the row's accessible
    // name folds its distance in after the name.
    await expect(page.getByRole('button', { name: /^Pine Meadow loop/ })).toBeVisible()
  })

  test('exit: the volunteer column’s lead card opens the volunteer page and comes back', async ({
    page,
  }) => {
    await todayIn(page, 'volunteer')

    // The lead card is a door, driven rather than found: a swallowed tap on
    // the first thing a volunteer meets is exactly the regression rule 2
    // exists for, and nothing about the card being visible says it works.
    await crewCard(page, 'Your day on the trail crew').click()
    await expect(page.getByRole('heading', { name: /^contribute$/i })).toBeVisible()
    await expect(page.getByRole('heading', { name: /^volunteer$/i })).toBeVisible()

    // WHERE BACK LANDS, and it is not where navigator.ts's own header says.
    // That file reads "Back from Volunteer opened off Today's column lands on
    // Today, not on More's home" - true of a `push`, which records `from`
    // when `returnsToOrigin(screen)`. This door is not a push: App.tsx's
    // `setMorePage` uses `replace`, and `replace` inherits `from` only from
    // the screen it replaces, so opening the volunteer page over an empty
    // More stack carries no origin and Back lands on More's home with More
    // still selected. Measured 2026-09-11. Asserted as what the app does,
    // and flagged as a mismatch between the comment and the shipped door
    // rather than quietly written down as the intent.
    await expect(page.getByRole('tab', { name: 'More', selected: true })).toBeVisible()
    await page.getByRole('button', { name: 'More', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'More', exact: true })).toBeVisible()

    // And Today is still Today: the column comes back in the mode it was
    // left in, lead card and all.
    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    await expect(crewCard(page, 'Your day on the trail crew')).toBeVisible()
  })
})
