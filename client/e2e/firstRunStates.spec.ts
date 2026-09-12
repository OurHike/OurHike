// First run's remaining states (client/src/screens/Onboarding.tsx, and the
// two fields it mounts: chrome/PlaceField.tsx and screens/DetailPicker.tsx) -
// F1 in features/FLOW_TESTING.md's battery, less what e2e/onboarding.spec.ts
// already drives.
//
// e2e/onboarding.spec.ts holds card 1's skip finishing the whole flow, the
// mode card's absent-not-disabled primary (D10), and the walk through all
// five cards. What it does not hold is what the cards SAY when the data
// behind them is not there - which is every card this suite can reach, since
// this environment has no bucket at all.
//
// ENTRANCE. First run is the one screen reached by doing nothing: a boot with
// an empty IndexedDB is card 1, and every card past it is a real tap from
// there ("Get set up", then each card's own skip). No seeding on the way in,
// because a seed past first run is a boot that never shows it.
//
// EXIT. Each card's way on is its own pair, and this file drives the half
// onboarding.spec.ts does not: card 3's "Use <place>" primary, which exists
// only once a place has been taken, and card 4's "Download" primary, which
// starts the transfer it has just sized. The flow's last exit is the one
// asserted twice below - a finished flow is not re-entered, which is an exit
// from first run for good rather than for this session.
//
// STATES. The axis that decides what these two cards print is data freshness
// (FLOW_TESTING.md), and this environment sits at its far end: no release
// manifest, no published places index. Both cards have a sentence for that
// and the assertions below are on the sentence rather than on a number,
// because a card that silently swapped "we have not been told" for a guess is
// exactly the defect a number cannot see.
//
//   - The download card prices all three rungs "Unknown offline" - #1167's
//     rule that a size is withheld rather than invented - and NOT "Not
//     offered", which is the other null and means the opposite thing.
//   - The place card's field forks three ways on lib/usePlaces.ts's `settled`
//     and the phone's own connection. Two of the three are driven here,
//     online and offline, and they are asserted against each other rather
//     than merely present.
//
// WHAT THIS FILE DELIBERATELY DOES NOT ASSERT, and why, so the next person
// does not read the gaps as oversights:
//
//   - "Looking for the list of parks and trailheads…", the third of
//     PlaceField's sentences, is not reachable as a state a spec can hold.
//     App.tsx passes `usePlaces(online, entering || …)`, so the kept read is
//     issued on the launch that shows card 1 and settles long before three
//     taps have reached card 3 - and an IndexedDB read has no seam this
//     suite can delay. Asserting it would be asserting a race. What is
//     asserted instead is its complement, which is observable: the field is
//     `disabled` exactly when nothing is searchable AND every read has
//     answered, so a disabled field is proof the looking state is over and
//     the sentence on screen is a settled one.
//     (PlaceField.tsx's own header says all three sentences "name the way
//     out: skip, and set it in More → You". The two settled ones do. The
//     looking one does not carry that clause - the card's skip is still
//     under it, so nobody is stranded, but the file's claim is wider than
//     its code. Flagged, not fixed here.)
//   - "No room on this phone" (#555) cannot happen on this card here: the
//     rung has to carry a size to be compared against the phone's free
//     bytes, and no rung has one without a manifest.

import { test, expect, type Page } from '@playwright/test'
import { seedPreferences, bootFreshPage } from './support/seed'
import { writeIDBEntries } from './support/idb'

/** The kept copy of `places.json`, as lib/conditionsCache.ts keys it
 *  (`ourhike:conditions:` + the bucket key) and lib/places.ts validates it.
 *  The key spelling is the wire contract, the same way support/seed.ts's
 *  three keys are - nothing here needs the modules themselves.
 *
 *  Nobody's data: two invented places in an invented county. The second one
 *  carries a MEASURED zero, which is not the same as an absent figure and is
 *  the row the assertions below are actually about. */
const KEPT_PLACES: readonly [string, unknown] = [
  'ourhike:conditions:places.json',
  {
    document: {
      generated_at: '2026-09-01T00:00:00Z',
      trailRadiusMiles: 10,
      trailMilesMeasured: true,
      places: [
        {
          id: 'kettle-hollow-sp',
          name: 'Kettle Hollow State Park',
          kind: 'park',
          state: 'VA',
          category: 'State Park',
          lon: -78.5,
          lat: 38.5,
          trailMiles: 42.3,
        },
        {
          id: 'kettle-falls-town',
          name: 'Kettle Falls',
          kind: 'town',
          state: 'VA',
          lon: -78.6,
          lat: 38.6,
          trailMiles: 0,
        },
      ],
    },
    storedAt: '2026-09-01T00:00:00Z',
  },
]

/** Card 3, by the taps a hiker makes: card 1's primary, then the mode card's
 *  skip. Asserted on each card's own heading rather than on the click, so a
 *  card that stopped advancing fails here instead of three assertions later. */
async function toPlaceCard(page: Page): Promise<void> {
  await page.goto('/')
  await page.getByRole('button', { name: 'Get set up' }).click()
  await page
    .getByRole('button', { name: 'Skip — day hike for now, change it on Today' })
    .click()
  await expect(page.getByRole('heading', { name: 'Where do you hike?' })).toBeVisible()
}

/** Card 4, one skip further on. */
async function toDownloadCard(page: Page): Promise<void> {
  await toPlaceCard(page)
  await page.getByRole('button', { name: 'Skip — I’ll set this later' }).click()
  await expect(
    page.getByRole('heading', { name: 'Take the whole trail with you' }),
  ).toBeVisible()
}

test.describe('first run, and what its cards say with nothing behind them', () => {
  test('states: with no manifest every rung reads “Unknown offline”, and none reads “Not offered”', async ({
    page,
  }) => {
    await toDownloadCard(page)

    // The sentence, on every rung, as part of the option's own accessible
    // name - so it is what a screen reader announces when the rung is
    // reached, not a caption sitting near it. Exact names rather than a
    // substring: "Standard Unknown offline Recommended" is the whole of what
    // this option says about itself, and a size appearing would change it.
    const ladder = page.getByRole('group', { name: /^map detail$/i })
    await expect(
      ladder.getByRole('radio', { name: 'Light Unknown offline' }),
    ).toBeVisible()
    await expect(
      ladder.getByRole('radio', { name: 'Standard Unknown offline Recommended' }),
    ).toBeVisible()
    await expect(
      ladder.getByRole('radio', { name: 'Fine Unknown offline' }),
    ).toBeVisible()

    // The ladder is three rungs whatever the sheet has (DetailPicker.tsx's
    // "every level, always"), so three is the count the sentence appears at -
    // a rung that vanished rather than greying would take its sentence with it.
    await expect(ladder.getByText('Unknown offline')).toHaveCount(3)

    // The OTHER null, and the one this state is not (#1167). "Not offered"
    // is a fact about the map - this level does not exist, or its artifacts
    // are not in the bucket - and a hiker who read it here would go looking
    // for a different map instead of waiting for a manifest.
    await expect(ladder.getByText('Not offered')).toHaveCount(0)

    // And the primary says the verb alone. The label is built from the chosen
    // rung's own figure ("Download 458.4 MB") where there is one, so a button
    // carrying a number here would be a size this phone has not been told.
    await expect(
      page.getByRole('button', { name: 'Download', exact: true }),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: /^Download .+/ })).toHaveCount(0)

    // One sheet on offer since the raster was withdrawn (#855), so the strip
    // is not drawn at all and the picker is the card's whole body - the
    // download window's own rule that "a single tab is a heading pretending
    // to be a control", asserted where a newcomer meets it.
    await expect(page.getByRole('tablist')).toHaveCount(0)
  })

  test('states and exit: an unpriced rung is still choosable, and taking it leaves the card', async ({
    page,
  }) => {
    await toDownloadCard(page)

    // Standard is the one this build pre-selects, so a hiker who skips still
    // has a usable map chosen - asserted before it is changed, because a
    // choice test that starts on the value it ends on proves nothing.
    const ladder = page.getByRole('group', { name: /^map detail$/i })
    await expect(
      ladder.getByRole('radio', { name: 'Standard Unknown offline Recommended' }),
    ).toBeChecked()

    // The tap a finger makes is on the label - each option is a `<label>`
    // wrapping its own radio, so clicking the input times out against the
    // label intercepting the pointer. The assertion stays on the radio.
    await ladder.getByText('Light', { exact: true }).click()
    await expect(
      ladder.getByRole('radio', { name: 'Light Unknown offline' }),
    ).toBeChecked()

    // The mechanism #1167 is actually about: "withholding the size is not
    // withholding the map". An unpriced rung is not greyed, it can be taken,
    // and the primary that starts the transfer still works over it - the exit
    // onboarding.spec.ts does not drive, since its walk declines with "Decide
    // this later" instead.
    await expect(
      page.getByRole('button', { name: 'Download', exact: true }),
    ).toBeEnabled()
    await page.getByRole('button', { name: 'Download', exact: true }).click()

    await expect(
      page.getByRole('heading', { name: 'Show where you are on it?' }),
    ).toBeVisible()
    await expect(
      page.getByRole('heading', { name: 'Take the whole trail with you' }),
    ).toHaveCount(0)
  })

  test('states: with no index and a connection, the place card says it has not been published', async ({
    page,
  }) => {
    await toPlaceCard(page)

    // Disabled is the observable proof that every read has answered
    // (PlaceField.tsx disables on `nothingToSearch && settled`), which is
    // what makes the sentence below a settled answer rather than a frame of
    // "still looking" caught mid-flight.
    await expect(
      page.getByRole('searchbox', { name: 'Where do you hike' }),
    ).toBeDisabled()
    await expect(page.getByText(/Looking for the list of parks/)).toHaveCount(0)

    // The sentence for online-and-nothing-published, and the way out it
    // names. Matched with wildcards where the punctuation is JSX's rather
    // than a plain apostrophe or arrow.
    await expect(
      page.getByText(/The list of places has not been published yet/),
    ).toBeVisible()
    await expect(page.getByText(/Skip for now and set this in More . You/)).toBeVisible()
    // The other absence's sentence, which this is not.
    await expect(page.getByText(/it arrives with signal/)).toHaveCount(0)

    // And the card is never blocked by its own field: the skip is the way on
    // whatever the field says.
    await expect(
      page.getByRole('button', { name: 'Skip — I’ll set this later' }),
    ).toBeVisible()
  })

  test('states: offline, the same absence gets its own sentence — it arrives with signal', async ({
    page,
    context,
  }) => {
    // Playwright's own offline, not a stubbed `navigator.onLine`: the app
    // reads the browser's answer through lib/useOnline.ts's event listeners,
    // and this is the event a phone losing signal actually fires. Set after
    // the boot, because the app has to be served before it can be cut off.
    await page.goto('/')
    await context.setOffline(true)

    await page.getByRole('button', { name: 'Get set up' }).click()
    await page
      .getByRole('button', { name: 'Skip — day hike for now, change it on Today' })
      .click()
    await expect(page.getByRole('heading', { name: 'Where do you hike?' })).toBeVisible()

    await expect(
      page.getByRole('searchbox', { name: 'Where do you hike' }),
    ).toBeDisabled()
    await expect(
      page.getByText(/No list of places on this phone yet .* it arrives with signal/),
    ).toBeVisible()
    await expect(page.getByText(/Skip for now and set this in More . You/)).toBeVisible()
    // The fork, asserted from both sides: a phone with no signal is not told
    // the list "has not been published", because what it can do about it
    // differs - wait for signal, rather than wait for a release.
    await expect(
      page.getByText(/The list of places has not been published yet/),
    ).toHaveCount(0)
  })

  test('states and exit: a kept index gives the field rows, and a taken place becomes the way on', async ({
    page,
  }) => {
    // The other end of the same axis: the places document is CACHED on this
    // phone rather than absent, which is the branch that proves the two
    // sentences above are about the data and not about a broken field.
    await writeIDBEntries(page, [KEPT_PLACES])
    await toPlaceCard(page)

    const field = page.getByRole('searchbox', { name: 'Where do you hike' })
    await expect(field).toBeEnabled()
    await field.fill('kettle')

    // What each row prints is lib/places.ts's rule about its own source, and
    // the figures are deliberately not pinned: a measured row prints A figure
    // (this one is the fixture's), and a MEASURED ZERO prints the sentence
    // instead, because "0 mi of trail held" is a number where the design has
    // a fact. Absent would print neither - no clause at all.
    await expect(
      page.getByRole('button', {
        name: /^Kettle Hollow State Park, VA .* \d+ mi of trail held$/,
      }),
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: /^Kettle Falls, VA .* no trail data held$/ }),
    ).toBeVisible()

    // No primary until there is a place to use (D10, the same rule the mode
    // card keeps): the state before the tap is part of the claim.
    await expect(page.getByRole('button', { name: /^Use / })).toHaveCount(0)
    await page.getByRole('button', { name: /^Kettle Hollow State Park, VA/ }).click()
    await expect(
      page.getByRole('button', { name: 'Use Kettle Hollow State Park', exact: true }),
    ).toBeVisible()

    // The exit this card grows once it has an answer.
    await page
      .getByRole('button', { name: 'Use Kettle Hollow State Park', exact: true })
      .click()
    await expect(
      page.getByRole('heading', { name: 'Take the whole trail with you' }),
    ).toBeVisible()

    // And the place is CARRIED, not merely displayed: two cards later the
    // last card's fallback is named after it rather than reading "Not now",
    // which is the only thing on screen that can tell a pick that landed in
    // the flow's state from one that painted and was dropped.
    await page.getByRole('button', { name: 'Decide this later' }).click()
    await expect(
      page.getByRole('heading', { name: 'Show where you are on it?' }),
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'Use Kettle Hollow State Park instead' }),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Not now' })).toHaveCount(0)
  })

  test('states: a hiker who has already finished first run is never shown the cards again', async ({
    page,
  }) => {
    // The returning boot, which is every boot after the first. The battery
    // asks that the flow "cannot be re-entered once finished" and there is no
    // control anywhere that re-enters it - so the claim is asserted where it
    // is decided: the shell reads the stored preference and renders the tabs
    // instead of the cards.
    await seedPreferences(page)
    await page.goto('/')

    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    // Card 1, card 3 and card 4 by their own headings - one absence per card
    // rather than one for the flow, so a single card leaking back is caught.
    await expect(
      page.getByRole('heading', { name: 'A map that works where there is no signal.' }),
    ).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'Where do you hike?' })).toHaveCount(0)
    await expect(
      page.getByRole('heading', { name: 'Take the whole trail with you' }),
    ).toHaveCount(0)
    // And the step counter, which is the one piece of furniture common to all
    // five cards - lib/onboardingSteps.ts's own progress, so a card rendering
    // under a different heading would still be caught here.
    await expect(page.getByText(/^\d \/ 5$/)).toHaveCount(0)
  })

  test('states: finishing the flow writes the choice, and a cold restart does not ask again', async ({
    page,
  }) => {
    // The same claim as above without the seed: first run is walked for real,
    // and the restart is a sibling page in the same context - cold, sharing
    // IndexedDB, carrying no init script that could re-seed what the app
    // wrote (support/seed.ts's bootFreshPage, and the reload trap it exists
    // for). A `page.reload()` here would prove nothing about persistence.
    await page.goto('/')
    await page.getByRole('button', { name: 'Get set up' }).click()
    await page.getByRole('radio', { name: /^Long hike/ }).click()
    await page.getByRole('button', { name: 'Continue as long hike' }).click()
    await page.getByRole('button', { name: 'Skip — I’ll set this later' }).click()
    await page.getByRole('button', { name: 'Decide this later' }).click()
    await page.getByRole('button', { name: 'Not now' }).click()
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()

    const rebooted = await bootFreshPage(page)
    try {
      await expect(
        rebooted.getByRole('tab', { name: 'Today', selected: true }),
      ).toBeVisible()
      await expect(
        rebooted.getByRole('heading', {
          name: 'A map that works where there is no signal.',
        }),
      ).toHaveCount(0)
      await expect(rebooted.getByText(/^\d \/ 5$/)).toHaveCount(0)
      // The mode taken on card 2 is on the phone, which is what makes the
      // absence above a FINISHED flow rather than a forgotten one: a shell
      // that had lost the store would show the cards, and one that had kept
      // it but dropped the answer would open in the default day mode.
      //
      // The tab bar's read-out, by its aria-label rather than its face:
      // chrome/TabBar.tsx labels the control "Today I’m <mode>. Switch mode"
      // and the visible word sits inside it, so a locator matching the face
      // alone matches nothing. The apostrophe is a wildcard because it is
      // JSX's curly one.
      await expect(
        rebooted.getByRole('button', { name: /^Today I.m long hike\. Switch mode$/ }),
      ).toBeVisible()
    } finally {
      await rebooted.close()
    }
  })
})
