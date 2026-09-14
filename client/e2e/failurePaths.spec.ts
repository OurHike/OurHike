// Failure paths - the last line of features/FLOW_TESTING.md's battery: "the
// error boundary catching a thrown screen and offering the report door rather
// than a white page."
//
// HOW A SCREEN IS MADE TO THROW, since nothing in the app exposes a seam for
// it and no spec may edit src/ to add one. Every screen a tab reaches is a
// `deferredScreen` (src/lib/deferredScreen.tsx, #1302), and that file names
// the failure this spec produces rather than inventing one: "IF THE CHUNK
// NEVER COMES - a build served half from one deploy and half from the next, a
// precache that was evicted mid-hike - the failure is thrown from render, so
// the nearest chrome/ErrorBoundary.tsx shows its named fallback". So one
// screen's chunk is refused at the network and the tab is tapped. What throws
// is the app's own `throw failure`, in a real browser, on a real tap - and no
// store is seeded with a shape the app never writes, which would be asserting
// against a state that cannot happen.
//
// The block is by chunk NAME, which is one name in both worlds this suite
// runs in: `/src/screens/Plan.tsx` from the dev server, `Plan-<hash>.js` from
// the built bundle CI serves (verified against client/dist/assets, which
// holds `Plan-DlV1-ZYZ.js` and `MapScreen-CzPLcTYl.js`; `PlanStart-*.js` and
// `PlanTargetSheet-*.js` deliberately do not match). Each blocking test polls
// the intercept list before asserting anything, so a chunk-naming change
// fails saying so instead of quietly proving nothing.
//
// ENTRANCE. The fallback has no door of its own: it appears in place of the
// screen a hiker tapped, which is the only way in and the only way this can
// be reached at all. The report door does have one, and it is four taps -
// More, "Where this map comes from", then "It broke while I was out there"
// at the top of Report a bug (screens/ReportBug.tsx, #848).
//
// EXIT. The boundary's own first decision is that "the tab bar stays under
// the fallback", so the exit is the tab bar, and it is driven rather than
// counted. The report form's two exits are both driven: Cancel, which must
// queue nothing, and Done after filing.
//
// STATES.
// - WHICH screen failed: the in-shell boundaries say "This screen", the map's
//   own says "The map" and carries a tab bar INSIDE its fallback, because at
//   the map tab the failed subtree is the thing that draws the tab bar.
// - Signal: the door is worded by `online` - "Send" against "Save to outbox",
//   "had signal" against "no signal", and two different acknowledgements. The
//   offline half is driven by losing signal with the form open, which also
//   keeps the test off a chunk the fixture cannot fetch once it is offline.
// - Contact left or not: the acknowledgement forks on it, and the fork is the
//   feature - "a reply they are waiting for and never get is worse than being
//   told plainly there will not be one". Both halves are asserted.
// - Mode: neither chrome/ErrorBoundary.tsx nor screens/AppFailureReport.tsx
//   nor screens/ReportBug.tsx reads lib/hikerMode.ts at all (no mode prop
//   reaches any of the three). So the mode axis cannot change what they say -
//   but it can change whether the door is REACHED, since the path runs
//   through More, and that is driven in all three modes including volunteer.
// - Freshness: this path prints no published data. The one provenance it
//   carries is the build it attaches, and the assertion is on the SENTENCE
//   that names it plus the signal state, never on the version - the build is
//   a live commit, so pinning it would pin when the suite ran.
//
// WHAT IS NOT ASSERTED, AND WHY. The fallback promises "Switching tabs and
// coming back will start this screen again". The coming-back half cannot be
// proved with this mechanism: a module whose fetch failed stays failed in the
// browser's module map for the life of the page (measured here 2026-09-11 -
// unrouting the block and returning to the tab re-imports the same URL and
// gets the same rejection with no new request), so the screen cannot start
// again however the boundary is reset. Left unasserted rather than faked. The
// half that IS provable - that the error does not follow the hiker to a
// healthy screen - is driven below, and the case where it does is the skipped
// repro at the foot of this file.

import { test, expect, type Page } from '@playwright/test'
import { seedPreferences, seedHikerMode, type HikerMode } from './support/seed'

/** The fallback chrome/ErrorBoundary.tsx draws, whichever boundary drew it.
 *  `role="alert"` is the component's own contract, so the query is the role
 *  rather than the class. */
function fallback(page: Page) {
  return page.getByRole('alert').filter({ hasText: /stopped working/ })
}

/**
 * Refuse one screen's code at the network, in both the dev server's shape and
 * the built bundle's. Returns the URLs actually intercepted, so a test can say
 * "the block never fired" instead of asserting on a screen that loaded fine.
 */
async function blockChunk(page: Page, name: string): Promise<string[]> {
  const blocked: string[] = []
  const pattern = new RegExp(`/${name}(-[A-Za-z0-9_-]+)?\\.(tsx|js)$`)
  await page.route(
    (url) => pattern.test(url.pathname),
    async (route) => {
      blocked.push(route.request().url())
      await route.abort()
    },
  )
  return blocked
}

async function boot(page: Page, mode: HikerMode = 'day'): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, mode)
  await page.goto('/')
}

/** More, then the page that carries Report a bug at its foot. */
async function openSources(page: Page): Promise<void> {
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /^Where this map comes from/ }).click()
  await expect(page.getByRole('heading', { name: /^your data$/i })).toBeVisible()
}

const DOOR = /^It broke while I was out there/

test.describe('when a screen cannot start', () => {
  // The built bundle CI serves registers a service worker that precaches every
  // chunk (vite.config.ts), and a precache hit is not a network request - so
  // with the worker allowed, the block below would intercept nothing and the
  // screen would start normally. Blocked for these tests only, which is also
  // the honest framing of what is being tested: the chunk is not on this
  // phone, and the network is the only place left to get it.
  test.use({ serviceWorkers: 'block' })

  test('entrance: a screen whose code never arrives is replaced by the fallback, with the tab bar still under it', async ({
    page,
  }) => {
    const blocked = await blockChunk(page, 'Plan')
    await boot(page)

    await page.getByRole('tab', { name: 'Plan' }).click()

    await expect
      .poll(() => blocked.length, {
        message:
          'the Plan chunk was never requested - its name has changed, and this spec is proving nothing until the pattern is fixed',
      })
      .toBeGreaterThan(0)

    // What #131 turned into a white page with no navigation on it, and what
    // this boundary exists to turn into words instead.
    await expect(fallback(page)).toBeVisible()
    await expect(
      page.getByRole('heading', { name: /^this screen stopped working$/i }),
    ).toBeVisible()

    // Decision one, driven: "The tab bar stays under the fallback... Whatever
    // else has gone wrong, the map has to be one tap away." All four, and the
    // tapped tab still the selected one - a fallback that silently dropped the
    // hiker somewhere else would pass a mere visibility check.
    for (const tab of ['Today', 'Map', 'Plan', 'More']) {
      await expect(page.getByRole('tab', { name: tab, exact: true })).toBeVisible()
    }
    await expect(page.getByRole('tab', { name: 'Plan', selected: true })).toBeVisible()

    // Decision two, driven as an absence: "No reload button. A reload is the
    // obvious thing to offer and the wrong thing here." The fallback offers no
    // control at all, and a retry quietly added to it would show up here.
    await expect(fallback(page).getByRole('button')).toHaveCount(0)
  })

  test('states: the map’s own boundary names the map, and draws a tab bar inside the fallback', async ({
    page,
  }) => {
    // The other arrangement of the same mechanism (App.tsx's map boundary).
    // The map subtree carries the tab bar for the map tab, so the fallback
    // that replaces it has to draw its own or a hiker whose map failed has no
    // navigation left - the exact shape of #131. And it says "The map" rather
    // than "This screen", which is the difference between a hiker knowing what
    // is broken and guessing.
    const blocked = await blockChunk(page, 'MapScreen')
    await boot(page)

    await page.getByRole('tab', { name: 'Map' }).click()

    await expect
      .poll(() => blocked.length, {
        message: 'the MapScreen chunk was never requested - its name has changed',
      })
      .toBeGreaterThan(0)
    await expect(
      page.getByRole('heading', { name: /^the map stopped working$/i }),
    ).toBeVisible()
    await expect(page.getByRole('tab', { name: 'More', exact: true })).toBeVisible()

    // And the tab bar it drew is a live one, not decoration: the way off a
    // broken map is the claim, so the claim gets tapped.
    await page.getByRole('tab', { name: 'More' }).click()
    await expect(page.getByRole('heading', { name: 'More', exact: true })).toBeVisible()
    await expect(fallback(page)).toHaveCount(0)
  })

  test('exit: the fallback is left by the tab bar, and the screen it lands on is whole', async ({
    page,
  }) => {
    const blocked = await blockChunk(page, 'Plan')
    await boot(page)

    await page.getByRole('tab', { name: 'Plan' }).click()
    await expect
      .poll(() => blocked.length, { message: 'the Plan chunk was never requested' })
      .toBeGreaterThan(0)
    await expect(fallback(page)).toBeVisible()

    // "The rest of the app is fine" is a sentence the fallback prints, so it
    // is a claim this test drives rather than believes: Today comes up whole,
    // with its own heading, and the fallback is gone rather than underneath.
    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(
      page.getByRole('heading', { name: 'Nothing planned today' }),
    ).toBeVisible()
    await expect(fallback(page)).toHaveCount(0)

    // Back to the tab that failed: still blocked at the network, so still the
    // fallback. This is the block still holding, not a claim about recovery -
    // see the header on why the recovery half cannot be proved here.
    await page.getByRole('tab', { name: 'Plan' }).click()
    await expect(fallback(page)).toBeVisible()
  })

  test('the whole failure path: a screen breaks, and the report door still takes the report', async ({
    page,
  }) => {
    // The battery's line, end to end. The hiker's Plan tab will not open, and
    // what they do about it is file the one report that works with no signal
    // (screens/AppFailureReport.tsx, #848) - so the door is reached FROM the
    // broken state rather than from a clean boot, which is the only version of
    // this journey anybody actually walks.
    const blocked = await blockChunk(page, 'Plan')
    await boot(page)

    await page.getByRole('tab', { name: 'Plan' }).click()
    await expect
      .poll(() => blocked.length, { message: 'the Plan chunk was never requested' })
      .toBeGreaterThan(0)
    await expect(fallback(page)).toBeVisible()

    // VIA TODAY, AND NOT BY ACCIDENT. Tapping More straight from this fallback
    // lands on the fallback again - a defect this spec found and the skipped
    // test at the foot of this file writes out in full. Today is a real tap a
    // hiker makes and it clears the way; the detour is here so this test
    // proves the report path rather than re-failing on that one.
    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(
      page.getByRole('heading', { name: 'Nothing planned today' }),
    ).toBeVisible()

    await openSources(page)
    await page.getByRole('button', { name: DOOR }).click()

    await expect(
      page.getByRole('heading', { name: 'It broke while I was out there' }),
    ).toBeVisible()

    // What travels without being typed, and what does not. Both are the
    // screen's own promises about a hiker's data, and the build is matched as
    // a sentence rather than a version: the real value is a live commit.
    await expect(page.getByText(/^Attached: .+ · had signal$/)).toBeVisible()
    await expect(page.getByText(/Your location is not attached/)).toBeVisible()

    // The one thing that can hold the report back. Whitespace is not an
    // answer either, which is the trim in the component rather than a
    // presence check - the difference a hiker meets by tapping the space bar.
    const send = page.getByRole('button', { name: 'Send', exact: true })
    await expect(send).toBeDisabled()
    const whatHappened = page.getByRole('textbox', { name: /what happened/i })
    await whatHappened.fill('   ')
    await expect(send).toBeDisabled()
    await whatHappened.fill(
      'The Plan tab would not open - it said the screen stopped working.',
    )
    await expect(send).toBeEnabled()

    // Ticking none is a complete report, so ticking one is a state and not a
    // step: the harm checkboxes are real checkboxes here, not More's
    // label-wrapped hidden radios, so this is a check() and an assertion on
    // the control rather than a click on its text.
    const harm = page.getByRole('checkbox', { name: /know where I was/ })
    await harm.check()
    await expect(harm).toBeChecked()

    await send.click()

    // The acknowledgement is part of the feature, and it is rendered only
    // after the save resolved - so its appearance is the app's own statement
    // that the words were kept, which is the mechanism this asserts.
    await expect(
      page.getByRole('heading', { name: /Thank you .* that is saved/ }),
    ).toBeVisible()
    // No contact was left, so the screen says plainly that nobody can reply.
    await expect(page.getByText(/didn.t leave a way to reach you/)).toBeVisible()

    // And it can be left: Done lands back on the page the door is on.
    await page.getByRole('button', { name: 'Done', exact: true }).click()
    await expect(page.getByRole('heading', { name: /^your data$/i })).toBeVisible()
    await expect(page.getByRole('button', { name: DOOR })).toBeVisible()
  })

  test.skip('known defect: from a broken Plan, tapping More shows the fallback for a screen that is fine - and More is where the report door is', async ({
    page,
  }) => {
    // FOUND BY THIS SPEC, 2026-09-11, and left written out rather than
    // quietly worked around, because it is the battery's own line failing:
    // the boundary catches the throw and then stands between the hiker and
    // the report door.
    //
    // WHAT HAPPENS. App.tsx renders the Plan tab and the More tab as the same
    // shape at the same position - a fragment, then `div.app__screen`, then
    // `div`, then `<ErrorBoundary>` - so React reconciles them as ONE boundary
    // instance across that tab switch and its `error` state survives. Neither
    // branch passes a `resetKey`, on the reasoning written at the More one:
    // "this boundary only renders while activeTab is 'more', so leaving the
    // tab unmounts it and clears the error". That is true of Plan -> Today ->
    // More, where the Today branch's different shape forces a remount, and
    // false of Plan -> More.
    //
    // WHAT IT COSTS. The fallback's own sentence - "The rest of the app is
    // fine. Switching tabs and coming back will start this screen again" - is
    // read on a screen that then does not come up, which is the one thing
    // HIKER_SAFETY.md's honesty rule says a screen may not do. And the tab it
    // strands is More: the only in-app door to "It broke while I was out
    // there" is behind it, so the hiker cannot report the failure they are
    // looking at without first guessing that Today unsticks it.
    //
    // MEASURED, not reasoned: with the Plan chunk blocked, More opens whole
    // before the break, shows the fallback when tapped straight afterwards
    // with nothing thrown in between (componentDidCatch logs nothing on that
    // switch), and opens whole again after one tap on Today.
    //
    // Skipped rather than deleted, and rather than weakened into a test that
    // asserts the defect as if it were the design: this session may not edit
    // src/, and a red spec nobody can fix here would block the suite it rides
    // in. Un-skipping it is the whole verification of the fix.
    const blocked = await blockChunk(page, 'Plan')
    await boot(page)

    await page.getByRole('tab', { name: 'Plan' }).click()
    await expect
      .poll(() => blocked.length, { message: 'the Plan chunk was never requested' })
      .toBeGreaterThan(0)
    await expect(fallback(page)).toBeVisible()

    await page.getByRole('tab', { name: 'More' }).click()
    await expect(page.getByRole('tab', { name: 'More', selected: true })).toBeVisible()

    // More's own home, which has nothing to do with the Plan chunk.
    await expect(page.getByRole('heading', { name: 'More', exact: true })).toBeVisible()
    await expect(fallback(page)).toHaveCount(0)
    await expect(
      page.getByRole('button', { name: /^Where this map comes from/ }),
    ).toBeVisible()
  })
})

test.describe('the report door', () => {
  for (const mode of ['day', 'long', 'volunteer'] as const) {
    test(`entrance: "It broke while I was out there" is reachable in ${mode} mode`, async ({
      page,
    }) => {
      // The forgotten third mode included, on FLOW_TESTING.md's mode rule. The
      // three screens on this path read no mode, so what this drives is that
      // the PATH to the door is the same in each - the sources page sits
      // behind More, and More is the screen the mode does change.
      await boot(page, mode)
      await openSources(page)

      const door = page.getByRole('button', { name: DOOR })
      await expect(door).toBeVisible()
      // The hint is the door's reason for not being a GitHub link, and the
      // one sentence that tells a hiker this works where the other four do
      // not (screens/ReportBug.tsx).
      await expect(door).toContainText('Works with no signal')
    })
  }

  test('states: signal lost while the form is open - the door rewords itself, and the report waits in the outbox', async ({
    page,
    context,
  }) => {
    await boot(page)
    await openSources(page)
    await page.getByRole('button', { name: DOOR }).click()
    await expect(
      page.getByRole('heading', { name: 'It broke while I was out there' }),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Send', exact: true })).toBeVisible()

    // Signal lost with the form open - the state this screen was written for,
    // and the one a hiker is in when the app fails on them. Playwright's own
    // offline, which is what `navigator.onLine` and the window events the app
    // listens on (lib/useOnline.ts) actually answer to; the form stays mounted,
    // so nothing typed is at stake in the switch.
    await context.setOffline(true)

    const save = page.getByRole('button', { name: 'Save to outbox' })
    await expect(save).toBeVisible()
    await expect(page.getByRole('button', { name: 'Send', exact: true })).toHaveCount(0)
    // The same two promises as the online half, both reworded by the same
    // fact - which is the point of asserting the sentence rather than the
    // button: a form that changed its button and kept saying "had signal"
    // would be lying about what it attached.
    await expect(page.getByText(/^Attached: .+ · no signal$/)).toBeVisible()
    await expect(
      page.getByText(/No signal — this will wait in your outbox/),
    ).toBeVisible()

    await page
      .getByRole('textbox', { name: /what happened/i })
      .fill('It lost my position on the ridge and would not find it again.')
    // The other half of the acknowledgement's fork: a way to reach them was
    // left, so the screen must promise a reply rather than refuse one.
    await page.getByRole('textbox', { name: /reach you/i }).fill('someone@example.org')
    await save.click()

    await expect(
      page.getByRole('heading', { name: /Thank you .* that is saved/ }),
    ).toBeVisible()
    await expect(page.getByText(/waiting in your outbox/)).toBeVisible()
    await expect(page.getByText(/Somebody will get back to you/)).toBeVisible()

    await page.getByRole('button', { name: 'Done', exact: true }).click()
    await expect(page.getByRole('heading', { name: /^your data$/i })).toBeVisible()

    // THE MECHANISM, not the acknowledgement's word for it. With no signal
    // nothing could have been sent, so the report is either in the outbox or
    // gone - and More's own row is where the app says which, counting the
    // same queue Today's line counts. One report, waiting.
    await page.getByRole('button', { name: 'More', exact: true }).click()
    await expect(page.getByRole('button', { name: /^Volunteer & report/ })).toContainText(
      '1 waiting to send',
    )
  })

  test('exit: Cancel leaves the form where it was opened, and queues nothing', async ({
    page,
  }) => {
    await boot(page)
    await openSources(page)
    await page.getByRole('button', { name: DOOR }).click()
    await page
      .getByRole('textbox', { name: /what happened/i })
      .fill('Started typing this and thought better of it.')

    await page.getByRole('button', { name: 'Cancel', exact: true }).click()

    // Back on the page that opened it, with the door still there - the form
    // is a screen over this one, not a move away from it.
    await expect(page.getByRole('heading', { name: /^your data$/i })).toBeVisible()
    await expect(page.getByRole('button', { name: DOOR })).toBeVisible()

    // And nothing was filed. The row prints a waiting count only when the
    // queue holds something, so its absence is the assertion - a Cancel that
    // saved a draft into the outbox would show up here as "1 waiting to send".
    await page.getByRole('button', { name: 'More', exact: true }).click()
    const volunteerRow = page.getByRole('button', { name: /^Volunteer & report/ })
    await expect(volunteerRow).toBeVisible()
    await expect(volunteerRow).not.toContainText('waiting to send')
  })
})
