// The saved day-hike card (client/src/screens/DayHikeCard.tsx) - the tail of
// F5 in features/FLOW_TESTING.md's battery, and that document's own worked
// example for the DATA FRESHNESS axis.
//
// ENTRANCE. There is one shipped door onto a saved card and it is a row on
// Plan's day room shelf: Plan tab -> "Pine Meadow loop". No URL, no injected
// navigator state (FLOW_TESTING.md, "Not a router"), and no Save either -
// this is the card opened from a shelf rather than the one that lands after
// step 3, which is why it carries no rail and no "Saved" eyebrow. It opens as
// a `dialog` named for the walk, so the entrance is asserted on that name
// rather than on the row having been clicked.
//
// EXIT. The close control ("Close the day hike" - the × beside it is
// aria-hidden), and it is driven rather than merely found. The second exit
// test is the one worth having: a tab switch is NOT an exit here. The card is
// not on a navigator stack at all - it is `openId` inside the day-hike store
// (App.tsx's `saveDayHikeOpenId`), so Today re-docks the same card and the
// close control remains the only way to put it away. A spec that tapped
// another tab and called the card closed would be asserting the opposite of
// what this app does.
//
// STATES.
//
// - DATA FRESHNESS is the axis this screen exists to demonstrate, and this
//   environment can only reach two of its three values. `resolved` is null
//   here - nothing publishes a junction graph to the dev server this suite
//   drives (FLOW_TESTING.md's "Map data" boundary) - so the card takes its
//   CACHED branch: the figures stored at save time, printed under a sentence
//   naming them as such, and deliberately no climb and no ≈time over them.
//   That null then forks again on `networkAvailable`, which App.tsx sets from
//   `graphIndex !== null`; with no graph at all this is the no-network half.
//   Both halves are asserted - the sentence that shows AND the one that does
//   not - because "which absence" is a claim about what a hiker can do next,
//   and a card that silently swapped one for the other would still print the
//   same 6.4 mi.
// - THE RESOLVED-ROUTE DOORS are absent here, which is a state rather than a
//   gap: "Walk this" and "Edit the route" are both withheld over the stored
//   cache (D10 - absent rather than disabled), and so is the "If you need to
//   get off" block, because bail-outs are read off a route this phone has
//   not got. Asserted as absences so that a door quietly appearing over the
//   cache - the display outrunning its source - fails something.
// - MODE. The card itself does not read the hiker mode in this state:
//   `leadsToday` is only consulted behind `justSaved`, which is false for a
//   card opened from a shelf. So one mode would be enough for the card - but
//   the ENTRANCE does vary, and volunteer is the value everyone forgets, so
//   it is driven: a volunteer plans in the day room (PlanHome.tsx's "VOLUNTEER
//   GETS THE DAY ROOM") and reaches the identical card through it. Long mode
//   has no day-hike shelf to tap, which is why it is absent here rather than
//   forgotten.
//
// Numbers. 6.4 mi and the one Blue-blazed leg are the fixture's own stored
// figures (preview-shots/fixtures/dayHike.mjs), and pinning them IS the
// claim in the freshness test rather than an accident of it: the cached
// branch means the saved figures are what reaches the screen, and a live
// resolution would print different miles with a climb beside them. Everywhere
// else this spec asserts the mechanism - a door, a sentence, a state - and
// says so.

import { test, expect, type Page } from '@playwright/test'
import { seedPreferences, seedHikerMode, type HikerMode } from './support/seed'
import { seedDayHikes } from '../preview-shots/fixtures/dayHike.mjs'

/** The fixture's one saved walk. Named once so the shelf row, the dialog's
 *  accessible name and the plain-text card are all read against the same
 *  string rather than three guesses at it. */
const WALK = 'Pine Meadow loop'

/** The two honest absences, verbatim from DayHikeCard.tsx. Matched as regexes
 *  because the rendered text carries `&rsquo;` and an em dash, and a locator
 *  typed with a straight apostrophe matches nothing (FLOW_TESTING.md, "Mind
 *  the punctuation"). */
const NO_NETWORK =
  /This phone has no trail network, so these are the figures from the day this hike was saved .* and ways off can.t be worked out\./
const CANNOT_PLACE = /This phone.s current trail map can.t place this walk/

/** Boot past first run in a mode, seed the saved walk, land on Plan. The
 *  fixture seeds through `page.evaluate` + reload, so it needs a navigation
 *  to have happened first - hence the goto before the seed, the same order
 *  plan.spec.ts uses. */
async function planIn(page: Page, mode: HikerMode): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, mode)
  await page.goto('/')
  await seedDayHikes(page)
  await page.getByRole('tab', { name: 'Plan' }).click()
  await expect(page.getByRole('tab', { name: 'Plan', selected: true })).toBeVisible()
}

/** The card itself. A `dialog` named for the walk (DayHikeCard.tsx's
 *  `aria-label={hike.name}`), which is also what scopes every assertion off
 *  the Plan room behind it - the room carries a `note` of its own, so an
 *  unscoped note query would match two things. */
function card(page: Page) {
  return page.getByRole('dialog', { name: WALK })
}

/** The whole entrance, as a hiker makes it. */
async function openSavedCard(page: Page, mode: HikerMode = 'day'): Promise<void> {
  await planIn(page, mode)
  await page.getByRole('button', { name: new RegExp(`^${WALK}`) }).click()
  await expect(card(page)).toBeVisible()
}

test.describe('The saved day hike card', () => {
  test('entrance: the day room’s shelf row opens the card as a dialog named for the walk', async ({
    page,
  }) => {
    await planIn(page, 'day')

    // The shelf, before the tap - so a failure says whether the door was
    // missing or the door was broken.
    await expect(page.getByRole('heading', { name: 'Day hikes' })).toBeVisible()
    const shelfRow = page.getByRole('button', { name: new RegExp(`^${WALK}`) })
    await expect(shelfRow).toBeVisible()

    await shelfRow.click()

    await expect(card(page)).toBeVisible()
    // A record opened from a shelf is not on the builder's spine, so it
    // carries no step rail and no "Saved" eyebrow - the two things that
    // would mean this was the just-saved landing instead.
    await expect(card(page).getByText('Saved', { exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /Back to Route, step 2/ })).toHaveCount(
      0,
    )
    // The legs the card is read for, from whichever source it has.
    await expect(card(page).getByRole('heading', { name: /^legs$/i })).toBeVisible()
  })

  test('states (freshness): the card prints the stored figures under the sentence saying so, and no climb over them', async ({
    page,
  }) => {
    await openSavedCard(page)

    // THE SENTENCE, which is the whole point of this axis. The number alone
    // cannot tell a cached card from a live one; this can.
    await expect(card(page).getByText(NO_NETWORK)).toBeVisible()
    // And WHICH absence. The other half of the same fork must not be on
    // screen: it tells a hiker their phone has a trail map that cannot place
    // this particular walk, which is a different thing to do about.
    await expect(card(page).getByText(CANNOT_PLACE)).toHaveCount(0)

    // The figures line, anchored at both ends. This is the one place this
    // spec pins the fixture's own numbers on purpose: 6.4 mi and one leg are
    // what `hike.figures` holds, so seeing them IS "the cache reached the
    // screen". The anchors are what prove nothing was appended - a climb
    // ("· +900 ft / −900 ft") and a time ("· ≈3h 10m walking") both land in
    // this same paragraph, and the cached branch deliberately prints neither
    // because the fixture stores no `climb` and nothing re-derived one.
    await expect(card(page).getByText(/^6\.4 mi · 1 leg$/)).toBeVisible()
    // The note that rides with a time estimate, absent because the estimate
    // is. Asserted separately: it is the sentence that stops "≈3h 10m" being
    // read as an arrival, and a card printing it with no figure above it
    // would be boilerplate.
    await expect(card(page).getByText(/Moving time/)).toHaveCount(0)

    // The cached legs, as the card reads them - the name a hiker walks by and
    // the blaze word underneath it for a screen reader (half the network has
    // no hue to show, so the word is not decoration).
    await expect(card(page).getByText('Pine Meadow Trail', { exact: true })).toBeVisible()
    await expect(card(page).getByText('Blue blaze', { exact: true })).toBeVisible()
    // Credit by COUNT rather than by name (#1112, #1115) - and the count is
    // read off the cached legs too, so it is part of what this branch prints.
    await expect(
      card(page).getByText(/organizations keep this loop walkable/),
    ).toBeVisible()
  })

  test('states: the doors that need a route are absent, not disabled', async ({
    page,
  }) => {
    await openSavedCard(page)

    // D10's rule, and App.tsx withholds both handlers over the cache:
    // `onFollow` and `onEdit` are gated on a resolution and a graph index,
    // and the card gates them again on `resolved !== null`. A greyed control
    // is a promise the app cannot say why it is not keeping.
    await expect(card(page).getByRole('button', { name: 'Walk this' })).toHaveCount(0)
    await expect(card(page).getByRole('button', { name: 'Edit the route' })).toHaveCount(
      0,
    )
    // The ways off go with them, and the card says so in the same sentence it
    // says the figures are cached ("and ways off can't be worked out") rather
    // than printing an empty block. The block's own heading carries the
    // decided answer for a walk that HAS a route and no bail-outs, so its
    // absence here is the state and not an omission.
    await expect(
      card(page).getByRole('heading', { name: /^if you need to get off$/i }),
    ).toHaveCount(0)

    // What IS offered over the cache, in the same assertion - the doors this
    // state actually ships, so the test says what a hiker can do and not only
    // what they cannot.
    await expect(
      card(page).getByRole('button', { name: /^Leave it with someone/ }),
    ).toBeVisible()
    await expect(
      card(page).getByRole('button', { name: 'Delete this day hike' }),
    ).toBeVisible()
  })

  test('states (mode): a volunteer reaches the same card, because Plan’s day room is theirs', async ({
    page,
  }) => {
    // The forgotten third mode. The card does not read the mode in this
    // state, so what is being claimed is about the ENTRANCE: a volunteer
    // plans as a day hiker, so the shelf and its row are there, and the card
    // behind the row is the same card with the same cached sentence.
    await openSavedCard(page, 'volunteer')

    await expect(card(page).getByText(NO_NETWORK)).toBeVisible()
    await expect(card(page).getByText(/^6\.4 mi · 1 leg$/)).toBeVisible()
    await expect(
      card(page).getByRole('button', { name: 'Delete this day hike' }),
    ).toBeVisible()
  })

  test('entrance and exit: Leave it with someone opens over the card, carries the same hedge, and gives the card back', async ({
    page,
  }) => {
    await openSavedCard(page)

    await page.getByRole('button', { name: /^Leave it with someone/ }).click()

    // One surface continuing: the plain-text card REPLACES the day-hike card
    // in the same frame, so the card's dialog is gone rather than stacked
    // under it.
    const leaveWord = page.getByRole('dialog', { name: 'Leave this with someone' })
    await expect(leaveWord).toBeVisible()
    await expect(card(page)).toHaveCount(0)

    // THE PROVENANCE TRAVELS. This is the freshness axis leaving the screen:
    // `fromCache` is handed to lib/dayHikePlanText.ts with the figures, and
    // the text hedges in words. The person holding this card is the one who
    // decides when to worry, and a number without the hedge on that artifact
    // is the display outrunning its source at the worst possible place.
    await expect(
      leaveWord.getByText(/measured when this was planned, not re-checked since/),
    ).toBeVisible()
    // The line the app refuses to compute, present as a field rather than an
    // estimate - asserted because its absence would mean an arrival clock.
    await expect(leaveWord.getByText(/We won.t guess an arrival time/)).toBeVisible()

    // And it gives the card back rather than dropping the hiker on the shelf.
    await leaveWord.getByRole('button', { name: 'Close', exact: true }).click()
    await expect(card(page)).toBeVisible()
    await expect(leaveWord).toHaveCount(0)
  })

  test('states and exit: Delete asks first — Keep it puts the door back, Delete empties the shelf', async ({
    page,
  }) => {
    await openSavedCard(page)

    // Two taps to destroy a walk somebody built. Both branches of the ask are
    // driven: a guarded move whose "stay" side is untested is a guard nobody
    // has checked can be declined.
    await page.getByRole('button', { name: 'Delete this day hike' }).click()
    await expect(card(page).getByText('Delete this day hike?')).toBeVisible()

    await card(page).getByRole('button', { name: 'Keep it', exact: true }).click()
    // The ask is gone, the walk is still open, and the door is back where it
    // was - which is the observable proof the state was reverted rather than
    // the confirm merely hidden.
    await expect(card(page).getByText('Delete this day hike?')).toHaveCount(0)
    await expect(
      card(page).getByRole('button', { name: 'Delete this day hike' }),
    ).toBeVisible()

    await card(page).getByRole('button', { name: 'Delete this day hike' }).click()
    // The ask is up BEFORE the second tap, asserted rather than assumed. The
    // first branch above already waits on this sentence and this one did not,
    // which left one tap in this file landing on a control that may still be
    // mounting - the ordering-sensitive shape FLOW_TESTING.md asks specs to
    // wait their way out of. Seen once, in a full-suite run that raced other
    // processes; four consecutive full runs since have been clean, so this is
    // hardening a gap rather than a proven fix for a reproduced race.
    await expect(card(page).getByText('Delete this day hike?')).toBeVisible()
    await card(page).getByRole('button', { name: 'Delete', exact: true }).click()

    // The card is gone AND so is the walk. Asserting only the card would pass
    // on a delete that closed the sheet and kept the hike, which is the
    // failure worth catching: the shelf is where a hiker would next look for
    // it.
    await expect(card(page)).toHaveCount(0)
    await expect(page.getByRole('button', { name: new RegExp(`^${WALK}`) })).toHaveCount(
      0,
    )
    await expect(page.getByText(/No plan yet/)).toBeVisible()
  })

  test('exit: the close control gives back the shelf row that opened it', async ({
    page,
  }) => {
    await openSavedCard(page)

    // The × is an aria-hidden glyph, so this control's accessible name is the
    // visually-hidden label alone.
    await page.getByRole('button', { name: 'Close the day hike' }).click()

    await expect(card(page)).toHaveCount(0)
    // Back on the room that opened it, with the walk still saved - closing a
    // card changes no hike (App.tsx: "the pointer only").
    await expect(page.getByRole('heading', { name: 'Day hikes' })).toBeVisible()
    await expect(page.getByRole('button', { name: new RegExp(`^${WALK}`) })).toBeVisible()
  })

  test('exit: a tab switch is not an exit — Today docks the same card, and its close still works', async ({
    page,
  }) => {
    await openSavedCard(page)

    // This card is not on a navigator stack: it is `openId` in the day-hike
    // store, which every pane that docks the card reads. So switching tabs
    // moves the card rather than dismissing it - the opposite of what a
    // screen pushed onto a tab's stack does, and the reason the close control
    // is genuinely the only exit rather than merely the obvious one.
    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    await expect(card(page)).toBeVisible()
    // Still the cached card, in the new pane - the sentence rides the store,
    // not the room.
    await expect(card(page).getByText(NO_NETWORK)).toBeVisible()

    // And the exit works from here too, landing on Today's own shelf row
    // rather than on the room the card was opened from.
    await page.getByRole('button', { name: 'Close the day hike' }).click()
    await expect(card(page)).toHaveCount(0)
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    await expect(page.getByRole('button', { name: new RegExp(`^${WALK}`) })).toBeVisible()
  })
})
