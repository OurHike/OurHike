// The rooms BEHIND the Plan tab's doors — the second half of F8 in
// features/FLOW_TESTING.md's battery.
//
// plan.spec.ts drives the two Plan homes and What's left: which room each
// mode lands in, what each says when it is empty, and that the walked shelf
// opens a hike's zoom. This file goes one level further in — the day-hike
// list behind "All N ›", a section's days as a timeline, the trip switcher,
// and a walk already done — because a room reached but never driven is a
// room that regresses silently, which is the whole argument for the ledger.
//
// ENTRANCE. Every one is a real tap from boot through the rooms above it.
// No navigator state is injected and no screen is mounted directly
// (FLOW_TESTING.md, "Not a router").
//
// EXIT. Each room is left the way it ships, and the assertion is on the
// screen behind it rather than on the back control having been clicked — a
// control that exists and does nothing passes the weaker test.
//
// WHAT IS DELIBERATELY NOT HERE. screens/FindHike.tsx, chrome/FacetSheet.tsx,
// chrome/SuggestedHikeCard.tsx, chrome/DayHikesHere.tsx, screens/HikeDetail.tsx
// and screens/StretchCard.tsx all need PUBLISHED hikes or a downloaded
// stretch, and this suite reaches no bucket (playwright.config.ts,
// FLOW_TESTING.md's boundaries). They stay `planned` in the ledger rather
// than being driven against an empty shelf and counted as covered — the rule
// the ledger's own header states: coverage is claimed where a spec asserts on
// the surface, never where it walks past.

import { test, expect, type Page } from '@playwright/test'
import { seedPreferences, seedHikerMode, type HikerMode } from './support/seed'
import { seedLongHike, finishedStore } from '../preview-shots/fixtures/longHike.mjs'
import { seedDayHikes, walkedDayHikes } from '../preview-shots/fixtures/dayHike.mjs'

/** Boot past first run in a mode, seed, and land on the Plan tab — the same
 *  entrance plan.spec.ts uses, deliberately: a spec that reached these rooms
 *  another way would be testing a door this app does not ship. */
async function planIn(
  page: Page,
  mode: HikerMode,
  seed?: (page: Page) => Promise<void>,
): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, mode)
  await page.goto('/')
  if (seed !== undefined) await seed(page)
  await page.getByRole('tab', { name: 'Plan' }).click()
  await expect(page.getByRole('tab', { name: 'Plan', selected: true })).toBeVisible()
}

test.describe('the rooms behind the Plan tab', () => {
  test('entrance and exit: the day-hike shelf’s door opens the whole list, and comes back', async ({
    page,
  }) => {
    // The shelf shows the recent few; the list is every one. That door is
    // the reason screens/DayHikeList.tsx exists at all ("the list that did
    // not exist" — until it, a trimmed shelf was the only way back to a
    // saved walk), so a shelf whose door stopped opening would take walks
    // away from a hiker without losing a single record.
    await planIn(page, 'day', seedDayHikes)

    await expect(page.getByRole('heading', { name: 'Day hikes' })).toBeVisible()
    await page.getByRole('button', { name: /^All \d+/ }).click()

    // The list's own title counts what it is showing — "Yours · 1 hike" —
    // which is the difference between this screen and the shelf that sent
    // the hiker here. Matched case-insensitively because the headings are
    // upper-cased by CSS and the accessible name follows the rendering
    // (more.spec.ts's note).
    await expect(page.getByRole('heading', { name: /^yours · 1 hike$/i })).toBeVisible()
    // The section the walk sits under. NOT a heading — DayHikeList draws its
    // two section labels as `plan-home__title` spans, and asserting them by
    // role would silently match the page title above instead, which is a
    // different claim that happens to pass.
    await expect(page.getByText('Ready to walk', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: /^Pine Meadow loop/ })).toBeVisible()

    // And back to the room it was opened from, which is the claim rule 2
    // makes: a list reached from a shelf that could not be left would strand
    // a hiker on their own history.
    await page
      .getByRole('button', { name: /^‹|back/i })
      .first()
      .click()
    await expect(page.getByRole('heading', { name: 'Day hikes' })).toBeVisible()
  })

  test('states: a walk already done is split off the list, and reads in the past tense', async ({
    page,
  }) => {
    // lib/dayHikeShelf.ts splits on `recorded` alone — "the only state that
    // matters at 7am: still to walk against already walked" — and
    // screens/WalkedHike.tsx is the past-tense surface, which #982 argues is
    // a different screen rather than DayHikeCard with the verbs changed.
    // Driving the same fixture in both states is what makes that a claim
    // about the SPLIT rather than about two unrelated records.
    await planIn(page, 'day', (p) => seedDayHikes(p, walkedDayHikes()))

    await page.getByRole('button', { name: /^All \d+/ }).click()

    // The door taken was the WALKED shelf's, so the list opens in its
    // walked-only face and titles itself for it: "Walked · 1 hike", where the
    // planned store's door gives "Yours · 1 hike". The title is the claim
    // that the split happened, and it is the screen's own summary of which
    // half it is showing.
    await expect(page.getByRole('heading', { name: /^walked · 1 hike$/i })).toBeVisible()
    // And no ready-to-walk section, because this phone has nothing left to
    // walk. A section label over an empty list is the failure the
    // absent-rather-than-empty rule exists to prevent.
    await expect(page.getByText('Ready to walk', { exact: true })).toHaveCount(0)

    await page.getByRole('button', { name: /^Pine Meadow loop/ }).click()

    // screens/WalkedHike.tsx, asserted on what it DRAWS rather than only on
    // what it lacks: the note field a hiker writes their own account of the
    // day into, and the day it was walked. A negative alone would pass on any
    // screen that failed to render.
    await expect(page.getByRole('heading', { name: 'Pine Meadow loop' })).toBeVisible()
    await expect(page.getByLabel('The day you walked it')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Where you went' })).toBeVisible()
    // And "Walk this" absent — the future-tense card's first button (D4's one
    // verb). #982's argument is that these are two screens rather than one
    // card in two tenses, and this is that claim in one assertion.
    await expect(page.getByRole('button', { name: 'Walk this' })).toHaveCount(0)
  })

  test('entrance and exit: a section opens its days as a timeline, and goes back to the hike', async ({
    page,
  }) => {
    // screens/Plan.tsx: the days as terrain rows, where ROW HEIGHT = WALKING
    // HOURS. That encoding is the screen's whole argument — "a hard day is
    // bigger on the screen" — and it is only true if the rows render at all,
    // which is what this drive proves and no unit test can.
    await planIn(page, 'long', seedLongHike)

    await page.getByRole('button', { name: /^Springer → Neels Gap/ }).click()

    // A day row is named for WHERE IT GOES — `stopLabel(day.start) →
    // stopLabel(day.end)` — not "D1", which is the bench's numbering and not
    // on the row. The first spec asserted "D1" and found nothing; the build's
    // naming is the better one and is what a hiker reads off the timeline.
    // Its figures are deliberately not pinned: the fixture dates itself
    // relative to today, so a pinned date passes in September and fails in
    // March (plan.spec.ts's note, same fixture).
    await expect(
      page.getByRole('button', { name: /Springer Mountain →/ }).first(),
    ).toBeVisible()

    await page
      .getByRole('button', { name: /^‹|back/i })
      .first()
      .click()
    await expect(page.getByRole('heading', { name: 'Springer → Katahdin' })).toBeVisible()
  })

  test('entrance and exit: Switch hike opens every hike kept, and lands back on one', async ({
    page,
  }) => {
    // screens/TripList.tsx, "the screen that makes 'more than one' real":
    // before it, planning a second hike overwrote the first. It is
    // deliberately small — a switcher, not the hike surface — so the claim
    // here is that it lists and that it switches, not that it explains.
    await planIn(page, 'long', seedLongHike)

    await page.getByRole('button', { name: /Switch hike/ }).click()

    // IT OPENS THE PICK SHEET, not a second list. PlanHome's own comment says
    // why — "it opens the same sheet rather than a second list of the same
    // hikes" — and the sheet titles itself for the question it is asking:
    // "Which hike are you on?" where one is already active, against "Which
    // long hike?" where none is. Scoped to the dialog, because the room
    // underneath still carries the hike's name on its Carry-on-with card and
    // an unscoped match resolves to both (strict mode says so rather than
    // quietly picking one).
    const sheet = page.getByRole('dialog', { name: 'Which hike are you on?' })
    await expect(sheet).toBeVisible()

    await sheet.getByRole('button', { name: /Springer → Katahdin/ }).click()
    await expect(sheet).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'Springer → Katahdin' })).toBeVisible()
  })

  test('entrance: the mode chip with nothing active opens the pick sheet, and a finished hike lands on its record', async ({
    page,
  }) => {
    // THE ONLY DOOR TO screens/FinishedHike.tsx, and fixtures/longHike.mjs's
    // own docstring is what names it: "tapping Long hike with nothing active
    // opens the pick sheet, and picking a finished hike lands on its record
    // rather than on a Today screen with nothing planned". App.tsx's
    // `handlePickHike` is the branch — `picked?.status === 'finished'` sets
    // the record screen — and nothing else in the app reaches it, which is
    // why this screen had no flow test until now.
    // IN DAY MODE, and that is the door rather than a detour. App.tsx opens
    // the sheet when the hiker switches INTO long mode with nothing active —
    // "Long hike means 'the hike I'm on', and with nothing active there is no
    // such thing to mean, so the sheet asks" — not on every visit to the Plan
    // tab. A spec that started in long mode never passes through that branch,
    // and this one did until the drive found the sheet never opened.
    await planIn(page, 'day', (p) => seedLongHike(p, finishedStore))

    // The mode read-out is the left chip of the tab row since #1374's room
    // audit, and it names itself for the question it asks rather than for the
    // mode it shows.
    await page.getByRole('button', { name: /Switch mode/ }).click()
    // Clicked by its visible label: the radio inputs are hidden under the
    // labels that style them, so `check()` waits on an element a thumb could
    // not hit either (settingsRooms.spec.ts's note, same idiom).
    await page.getByText('Long hike', { exact: true }).click()

    // "Which long hike?" rather than "Which hike are you on?": the sheet
    // titles itself for the question it is asking, and with nothing active
    // the question is the first one (chrome/HikePickSheet.tsx).
    const sheet = page.getByRole('dialog', { name: 'Which long hike?' })
    await expect(sheet).toBeVisible()

    await sheet.getByRole('button', { name: /Springer → Dicks Creek Gap/ }).click()

    // #1317's claim, and the one a reader is most likely to get wrong:
    // "finished" in most apps means archived, greyed, or gone from the place
    // it used to be. Here it means the walking is done and the record is not,
    // so what is asserted is that the sections are still listed under the
    // word FINISHED rather than collapsed to a line.
    // The eyebrow is "finished hike" and the HEADING is the hike's own name —
    // #1317's point in the markup: the hike keeps its identity, and the word
    // "finished" is the smaller of the two. Asserting the eyebrow as a
    // heading found nothing, because it is a span; the name is the h1.
    await expect(
      page.getByRole('heading', { name: 'Springer → Dicks Creek Gap' }),
    ).toBeVisible()
    await expect(page.getByText('finished hike', { exact: true })).toBeVisible()
    // Its sections, still listed under their own region rather than
    // collapsed to a line — which is what "the walking is done and the
    // record is not" means concretely.
    const sections = page.getByRole('region', { name: 'Sections in this hike' })
    await expect(
      sections.getByText('Springer → Neels Gap', { exact: true }),
    ).toBeVisible()
    await expect(
      sections.getByText('Neels Gap → Dicks Creek Gap', { exact: true }),
    ).toBeVisible()

    // And no "Export it": #1373 took that door off (D10, P20) because no
    // writer exists behind it, and a door is a claim.
    await expect(page.getByRole('button', { name: /^Export/ })).toHaveCount(0)
  })
})

test.describe('a day already walked, and the trail it sits on', () => {
  /** A section's timeline, which is where both surfaces below live: the
   *  ribbon at the head of the hike view, the day summary behind a grey row. */
  async function aSectionsTimeline(page: Page): Promise<void> {
    await planIn(page, 'long', seedLongHike)
    await page.locator('.plan-home__row-open').first().click()
    await expect(page.getByRole('button', { name: 'Days', exact: true })).toBeVisible()
  }

  test('entrance and states: a walked day opens its own record, backward-looking only', async ({
    page,
  }) => {
    await aSectionsTimeline(page)

    // The row is grey and says so — "walked · not a plan any more" — which is
    // what marks it as a door to a record rather than to an editable day.
    // Case-insensitive: the chip is upper-cased by CSS, so `innerText` shouts
    // and the DOM text does not.
    await page
      .getByRole('button', { name: /Springer Mountain → Gooch Mountain Shelter/ })
      .click()

    const summary = page.getByRole('dialog', { name: 'Your day' })
    await expect(summary).toBeVisible()

    // EVERYTHING HERE IS BEHIND THE HIKER, which is Plan.tsx's guardrail and
    // the one this card is most likely to break: it arrives at the end of a
    // day, when the next one is the tempting thing to offer. So the figures
    // are the day's own, the photos are what was kept, and the note is for
    // future you rather than a plan for tomorrow.
    await expect(summary.getByText(/your day, from what you filed/i)).toBeVisible()
    await expect(summary.getByText(/Photos you kept/)).toBeVisible()
    await expect(summary.getByRole('button', { name: 'Keep' })).toBeVisible()
  })

  test('exit: closing the day summary leaves the timeline underneath', async ({
    page,
  }) => {
    await aSectionsTimeline(page)
    await page
      .getByRole('button', { name: /Springer Mountain → Gooch Mountain Shelter/ })
      .click()
    const summary = page.getByRole('dialog', { name: 'Your day' })
    await expect(summary).toBeVisible()

    await summary.getByRole('button', { name: /^Close/ }).click()

    await expect(summary).toHaveCount(0)
    // Back on the timeline rather than on the hike above it — a close that
    // unwound one level too far would lose the place a hiker was reading.
    await expect(page.getByRole('button', { name: 'Days', exact: true })).toBeVisible()
  })

  test('states: the ribbon is an orientation — every band is named in words, and none of it is a figure', async ({
    page,
  }) => {
    await aSectionsTimeline(page)
    await page.getByRole('button', { name: 'Hike', exact: true }).click()

    // THE WHOLE POINT OF THE RIBBON IS THAT IT CANNOT BE READ (TrailRibbon.tsx:
    // roughly 7½ miles per pixel on a phone, so a three-day trip is eight
    // pixels). What carries the meaning is therefore the accessible name on
    // each band, not its width — and that is what this asserts.
    await expect(
      page.getByRole('button', { name: 'Springer → Neels Gap, walked' }),
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'Neels Gap → Dicks Creek Gap, part walked' }),
    ).toBeVisible()

    // A gap says what is NOT walked and between which two places, rather than
    // being a stretch of empty track a hiker has to interpret.
    await expect(
      page.getByRole('button', { name: /^Not walked: Dicks Creek Gap to / }),
    ).toBeVisible()

    // The two ends are labelled, so the ribbon is anchored to real places.
    await expect(page.getByText(/^Springer Mountain$/i)).toBeVisible()
    await expect(page.getByText(/mi walked · [\d.,]+ mi to go/)).toBeVisible()
  })
})
