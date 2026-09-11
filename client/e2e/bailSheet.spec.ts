// The bail sheet (client/src/chrome/BailSheet.tsx, decision D8): "every
// exit from a half-built route shows the bail sheet."
//
// EXIT, guarded: client/src/App.pathway.test.tsx already holds these three
// branches at the rendered layer. What this file adds is the same claim
// proven "findable" - a real browser, a real tab tap, the sheet's real
// focus and real dialog semantics - not a second derivation of the guard's
// logic (features/FLOW_TESTING.md's boundaries).
//
// EXIT, the known gap: `sweepForBuilder` is the one exit the guard cannot
// see (#1374's "Gaps noticed" review comment; features/FLOW_TESTING.md's
// "Known gaps"). The last test in this file writes out the CORRECT
// behavior - that this exit should be guarded too - as a `test.skip`: it
// needs a live day-hike draft, which needs the trail network to read
// `ready`, which needs a graph-shard fixture nothing in this repo has built
// yet (#1387). Skipped rather than deleted or forced through with a fake
// seed: the test is the target, not a placeholder, and un-skipping it is
// the whole remaining change once #1387 lands.

import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { seedPreferences, seedHikerMode, seedFixAtMile } from './support/seed'

const BAIL_SHEET = { name: 'Keep this half-built route?' }

async function openStepOneLong(page: Page): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, 'long')
  await page.goto('/')
  await page
    .getByRole('group', { name: 'Find or plan a hike' })
    .getByRole('button', { name: 'Plan a hike' })
    .click()
  await page
    .getByRole('group', { name: 'Start from' })
    .getByRole('button', {
      name: 'Pick on the map',
    })
    .click()
  await expect(page.getByText('Where from?')).toBeVisible()
}

test.describe('the bail sheet (D8)', () => {
  test('a tab tap away from a live route draft opens it; Stay here stays', async ({
    page,
  }) => {
    await openStepOneLong(page)

    await page.getByRole('tab', { name: 'Today' }).click()
    const sheet = page.getByRole('dialog', BAIL_SHEET)
    await expect(sheet).toBeVisible()
    // Still on the map, the draft still up - nothing applied yet.
    await expect(page.getByRole('tab', { name: 'Map', selected: true })).toBeVisible()

    await sheet.getByRole('button', { name: 'Stay here' }).click()
    await expect(sheet).toHaveCount(0)
    await expect(page.getByRole('tab', { name: 'Map', selected: true })).toBeVisible()
    await expect(page.getByText('Where from?')).toBeVisible()
  })

  test('Discard it drops the draft and proceeds to where the tap was headed', async ({
    page,
  }) => {
    await openStepOneLong(page)

    await page.getByRole('tab', { name: 'Today' }).click()
    await page
      .getByRole('dialog', BAIL_SHEET)
      .getByRole('button', { name: 'Discard it' })
      .click()

    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    // Nothing waits on Plan: its primary offers a new plan, not a way back
    // to a route that is gone.
    await page.getByRole('tab', { name: 'Plan' }).click()
    await expect(page.getByRole('button', { name: 'Back to your route' })).toHaveCount(0)
  })

  test('Keep it for later leaves the draft parked, and Plan offers the way back', async ({
    page,
  }) => {
    await openStepOneLong(page)

    await page.getByRole('tab', { name: 'Plan' }).click()
    await page
      .getByRole('dialog', BAIL_SHEET)
      .getByRole('button', { name: 'Keep it for later' })
      .click()

    await expect(page.getByRole('tab', { name: 'Plan', selected: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Back to your route' })).toBeVisible()
  })

  test("the app's own moves are never asked about: opening a builder is not an exit", async ({
    page,
  }) => {
    await openStepOneLong(page)
    // openStepOneLong's own last move - landing on the map for the builder
    // it just opened - must not itself have parked a bail ask.
    await expect(page.getByRole('dialog', BAIL_SHEET)).toHaveCount(0)
  })

  // STALE AS WRITTEN, and that is a change of status rather than a new
  // excuse (2026-09-11). Two things blocked this; one is gone and the other
  // turned out to be the test itself.
  //
  // A LIVE DAY-HIKE DRAFT IS REACHABLE NOW. "Edit the route" on a saved
  // walk's card loads its legs into step 2, which is the same state a hiker
  // reaches by tapping — e2e/data/builder.spec.ts drives it, and proves R3
  // keeps every leg across the rail's back. So the graph-shard fixture this
  // note asks for is no longer what stands in the way.
  //
  // THE DRIVE BELOW NO LONGER MATCHES THE SCREEN. It was written against an
  // older step 1 — a "Start from" doors group, a "Where I am" door, a "Where
  // from?" heading — and this build's step 1 is "Where do you want to go?"
  // with "Pick on the map" and "Draw it myself". Switching mode from the mode
  // chip lands on Today in long mode, where there is no "Pick on the map" at
  // all. The gap it describes may still be real; nobody can tell from this
  // test as it stands, which is the worse state to leave it in.
  //
  // AND ONE THING IS SETTLED, narrowing what the gap is about: a day-hike
  // draft under step 1 is PARKED rather than swept. Leaving by the tab bar
  // asks nothing and Plan carries "Back to your route", which restores every
  // leg (both halves pinned in e2e/data/builder.spec.ts). So the dangerous
  // move is the SWEEP — where the draft is dropped and unrecoverable — not
  // the park, and a rewrite should target that.
  //
  // Kept rather than deleted for the same reason as before: the test is the
  // target. features/FLOW_TESTING.md's "Known gaps" carries the measurements.
  //
  // The original note follows.
  //
  // BLOCKED, not written off: reproducing this needs a day-hike draft, and
  // "Where I am" - the door that starts one without a map tap - lives behind
  // PlanStart.tsx's OWN refusal gate in day mode
  // (`dayRefused = planMode === 'day' && network.kind !== 'ready'`), which
  // replaces the whole "Start from" doors group with a sentence until the
  // trail network reads `ready`. Confirmed empirically, not assumed: seeding
  // a real GPS fix and granting geolocation still left the doors group empty
  // in day mode in this suite's own environment.
  //
  // `ready` only comes from a real fetch (unreachable from this sandbox and
  // from CI's dev server alike, per FLOW_TESTING.md's boundaries) or from a
  // stored graph shard already in IndexedDB (`trailGraphStore.ts`,
  // `isGraphShard`) - and no synthetic shard fixture exists yet anywhere in
  // this codebase for that. `client/preview-shots/day-hike-builder.mjs`'s
  // own header names the identical limit: "whether a walk is in it depends
  // on whether the preview's bucket serves the junction graph," with no
  // fixture offered either. Building one is its own piece of work, worth
  // doing because it would unblock this test AND give the day-hike builder a
  // deterministic (non-network) path for every future spec that needs a
  // live day-hike draft - filed as **#1387**.
  //
  // Written as the target rather than deleted: the moment a graph-shard
  // fixture exists, this becomes seedPreferences + seedHikerMode('day') +
  // seedGraphShard(...) + the "Where I am" door, and the skip below comes
  // off in the same change.
  test.skip('known gap: switching mode then Pick on the map sweeps a live day-hike draft with no ask (should be guarded) - #1387, and this drive is now stale against step 1', async ({
    page,
  }) => {
    await seedPreferences(page)
    await seedHikerMode(page, 'day')
    await seedFixAtMile(page, 5)
    await page.goto('/')

    await page
      .getByRole('group', { name: 'Find or plan a hike' })
      .getByRole('button', { name: 'Plan a hike' })
      .click()
    await page
      .getByRole('group', { name: 'Start from' })
      .getByRole('button', {
        name: 'Where I am',
      })
      .click()
    await expect(page.getByRole('region', { name: 'Build a day hike' })).toBeVisible()

    // Back to step 1 with the draft kept live behind it (rule R3) - the
    // exact premise the "Gaps noticed" comment states: "a live day-hike
    // draft under step 1 on Plan".
    await page.getByRole('button', { name: 'Back to Hike, step 1' }).click()
    await expect(
      page.getByRole('heading', { name: 'Where do you want to go?' }),
    ).toBeVisible()

    // CONTROL: the ordinary exit is guarded, proving the draft is live
    // and would normally be asked about.
    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(page.getByRole('dialog', BAIL_SHEET)).toBeVisible()
    await page
      .getByRole('dialog', BAIL_SHEET)
      .getByRole('button', { name: 'Stay here' })
      .click()

    // THE GAP: switch mode, then take the same "Pick on the map" door -
    // now wired to the route builder, not the day-hike one - with the
    // same live draft still behind it.
    await page.getByRole('button', { name: /^Today I.m .*\. Switch mode$/ }).click()
    await page
      .getByRole('radiogroup', { name: "Today I'm" })
      .getByRole('radio', {
        name: /^Long hike/,
      })
      .click()
    await page
      .getByRole('group', { name: 'Start from' })
      .getByRole('button', {
        name: 'Pick on the map',
      })
      .click()

    // This is the claim that should hold and does not yet: the day-hike
    // draft this test built is exactly as live as the control case above,
    // and this move drops it with nobody asked.
    await expect(page.getByRole('dialog', BAIL_SHEET)).toBeVisible()
  })
})
