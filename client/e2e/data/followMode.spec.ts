// Walking it — F6 of features/FLOW_TESTING.md's battery, and the part of this
// app that is on the trail with somebody rather than at a kitchen table.
//
// WHY THIS FILE IS THE ONE TO GET RIGHT. CLAUDE.md names four ways this app
// can hurt somebody — lost, out of water, in front of something dangerous, or
// unable to get off the trail quickly — and three of the four run through
// this screen. The next turn is what stops a hiker walking a mile the wrong
// way; the junction card is what is left of the wrong-way alert after #93/#308
// removed it; the off-route card is what a lost hiker is looking at. Every
// assertion below is on what those screens SAY, because on this path the words
// are the feature.
//
// NONE OF IT EXISTS WITHOUT A JUNCTION GRAPH, which is why this is in
// e2e/data/. A saved walk only becomes followable once `resolveDayHike`
// places both ends on published tread, so on a phone that has downloaded
// nothing the card correctly offers no Follow door at all and every screen
// here is unreachable.
//
// THE WALK IS THE PREVIEW RECIPE'S, imported rather than re-derived:
// preview-shots/following-a-day-hike.mjs measured its ends against published
// artifacts (and carries the two wrong explanations that came before the
// measurement). A second copy here would be two answers to "which walk
// resolves", which CONTRIBUTING.md's one-home rule exists to stop.
//
// WHAT IS ASSERTED, AND WHAT IS NOT. The route's figures come from the live
// graph, so no mileage, leg count or bearing is written down — only their
// shape, and the sentences the app chooses around them. "1.8 mi in" is a
// claim about a release; "the header says how far in and how far to go" is a
// claim about the app.
//
// ENTRANCE. Boot, the Plan tab, the walk's own card, its Follow door. No
// navigator state is injected (FLOW_TESTING.md, "Not a router"). The fix is a
// real one through Playwright's geolocation, not a stub — support/seed.ts's
// `seedFixAtMile` makes the same argument.

import { test, expect, type Page } from '@playwright/test'
// A shot recipe is plain JavaScript, so these arrive untyped and that is the
// point: the fixture's shape is the app's contract with IndexedDB, and
// restating it here as a type would be a second answer that can go stale
// (tsconfig.e2e.json's `allowJs` is what lets the spec read it at all).
import {
  FOLLOWED_HIKE_STORE,
  FOLLOWED_HIKE_FIX,
} from '../../preview-shots/following-a-day-hike.mjs'
import { seedPreferences, seedHikerMode } from '../support/seed'
import { writeIDBEntries } from '../support/idb'

const DAY_HIKES_KEY = 'ourhike:day-hikes'

/** Far enough off the route that the app has to say so — measured from the
 *  on-route fix rather than written as a coordinate, so it moves with it. */
const OFF_ROUTE = {
  longitude: FOLLOWED_HIKE_FIX.longitude - 0.05,
  latitude: FOLLOWED_HIKE_FIX.latitude + 0.03,
}

/**
 * Following the saved walk, from boot.
 *
 * THE WAIT IS ON THE DOOR, NOT ON A TIMER, and the recipe's own header
 * explains why that distinction cost it a CI run: the card prints its LEGS
 * heading off the cached figures long before the graph arrives, so anything
 * waiting on the card counts a door that has not appeared yet. "Walk this" is
 * present only once `resolveDayHike` has placed the walk on live tread, which
 * makes it the only honest signal that this screen is reachable at all.
 *
 * Generous, because the graph is fetched as cells over the network — measured
 * 2026-09-11 against release 2026-09-10 through the local proxy: the door
 * appears inside fifteen seconds, over four cell requests.
 */
async function followTheWalk(page: Page): Promise<void> {
  await seedPreferences(page, { location_permission_requested: true })
  await seedHikerMode(page, 'day')
  await writeIDBEntries(page, [[DAY_HIKES_KEY, FOLLOWED_HIKE_STORE]])
  await page.context().grantPermissions(['geolocation'])
  await page.context().setGeolocation(FOLLOWED_HIKE_FIX)
  await page.goto('/')

  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('button', { name: /Ramapo-Dunderberg to Timp-Torne/ }).click()
  const walk = page.getByRole('button', { name: 'Walk this' })
  await walk.waitFor({ timeout: 60_000 })
  await walk.click()
  await expect(page.locator('.next-turn')).toBeVisible()
}

test.describe('following a walk', () => {
  test('entrance: the Follow door turns the map into the walk, and the header stops counting Springer miles', async ({
    page,
  }) => {
    await followTheWalk(page)

    // CASE-INSENSITIVE THROUGHOUT, and the reason is worth one note rather
    // than six: the read-outs here are upper-cased by CSS, so `innerText`
    // shouts and the DOM text does not. Matching the rendered spelling would
    // be asserting a stylesheet.
    //
    // THE HEADER IS THE WALK'S OWN, which is the change #1041 made and the
    // one a hiker notices: mid-walk the question is "how far is left of THIS"
    // rather than "which mile of the A.T. am I on". Both halves, because a
    // header printing only distance-in would answer the easier question.
    await expect(page.getByText(/day hike · leg \d+ of \d+/i)).toBeVisible()
    await expect(page.getByText(/[\d.]+ mi in · [\d.]+ mi to go/)).toBeVisible()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
  })

  test('states: the next turn names the distance, the instruction and what is left', async ({
    page,
  }) => {
    await followTheWalk(page)
    const card = page.locator('.next-turn')

    // A DISTANCE AND AN INSTRUCTION, never one without the other. "Straight
    // on" with no distance is not an instruction, and a distance with no
    // instruction is a number.
    await expect(card.locator('.next-turn__distance')).toHaveText(/In [\d.]+ (mi|ft)/)
    await expect(card.locator('.next-turn__instruction')).not.toHaveText('')

    // WHAT IS LEFT, WHICH IS THE OTHER QUESTION. A hiker deciding whether they
    // beat the dark needs the remainder, not the turn.
    await expect(card).toContainText(/What’s left today/)
    await expect(card).toContainText(/The finish/)

    // The blaze, which is the thing actually painted on the trees — the app's
    // instruction is only checkable against it.
    await expect(card.locator('.next-turn__on')).toContainText(/blaze/)
  })

  test('states: the junction card names every other way out of it, and says how to catch a wrong one', async ({
    page,
  }) => {
    // WHAT IS LEFT OF THE WRONG-WAY ALERT. #93/#308 removed that feature, and
    // CLAUDE.md keeps its asymmetry as a standing rule: "False negatives are
    // acceptable; false positives are the failure this whole module exists to
    // prevent." This card is the honest replacement — it does not claim to
    // notice a wrong turn, it tells a hiker how to notice one themselves.
    await followTheWalk(page)
    await page.getByRole('button', { name: 'This turn' }).click()

    const junction = page.getByRole('button', { name: /Close the junction/ })
    await expect(junction).toBeVisible()

    // EVERY OTHER WAY OUT, each said to be not the route. A junction card
    // naming only the route would leave a hiker to work out for themselves
    // that the other two paths are wrong, standing at the junction.
    await expect(page.getByText(/not your route/).first()).toBeVisible()
    await expect(page.getByText(/the way you came/)).toBeVisible()

    // THE SENTENCE THAT DOES THE WORK. It hands the check back to the hiker
    // and puts a time on it, which is what makes it actionable rather than
    // reassuring.
    await expect(page.getByText(/Check the blazes as you go/)).toBeVisible()
    await expect(
      page.getByText(/within a few minutes, you took a different trail/),
    ).toBeVisible()
  })

  test('exit: closing the junction returns to following, not to a stopped walk', async ({
    page,
  }) => {
    await followTheWalk(page)
    await page.getByRole('button', { name: 'This turn' }).click()
    await expect(page.getByRole('button', { name: /Close the junction/ })).toBeVisible()

    await page.getByRole('button', { name: /Close the junction/ }).click()

    await expect(page.getByRole('button', { name: /Close the junction/ })).toHaveCount(0)
    await expect(page.locator('.next-turn')).toBeVisible()
    await expect(page.getByText(/day hike · leg \d+ of \d+/i)).toBeVisible()
  })
})

test.describe('off the route', () => {
  test('states: the app says how far off and in which direction, and refuses to draw a line back', async ({
    page,
  }) => {
    // THE FLAGSHIP ASSERTION OF THIS FILE, and the one worth the whole
    // network cost. A lost hiker is the case where a confident answer is most
    // tempting and most dangerous, and this screen refuses to give one: it
    // says where the route is, and then says in so many words that it will
    // not draw a line to it, and why. CLAUDE.md's "an honest unknown outranks
    // a confident answer" is an abstraction until a screen turns down the
    // chance to be useful.
    await followTheWalk(page)
    await page.context().setGeolocation(OFF_ROUTE)

    await expect(page.getByText('You are not on your route')).toBeVisible()
    await expect(page.getByText(/day hike · off the route/i)).toBeVisible()
    // How far, and which way — a bearing to the nearest point, which is a
    // fact rather than a route.
    await expect(
      page.getByText(/The nearest point of your route is [\d.]+ (mi|ft) away, [\w-]+\./),
    ).toBeVisible()

    await expect(page.getByText('We will not draw you a line back')).toBeVisible()
    await expect(
      page.getByText(/a line across open ground would look like a path/),
    ).toBeVisible()
    // And the alternative it does offer, which is the safe one: ground the
    // hiker has already walked.
    await expect(
      page.getByText(/Walking back the way you came is ground you know is walkable/),
    ).toBeVisible()
  })

  test('states: both ways out of the off-route card are offered, and neither is a route', async ({
    page,
  }) => {
    // D10 read the other way round: the two controls here are the only two
    // honest ones. "Show the whole route" is a camera move, not a direction,
    // and "Stop following" is the hiker deciding the walk is over. Neither
    // claims to know a way back.
    await followTheWalk(page)
    await page.context().setGeolocation(OFF_ROUTE)
    await expect(page.getByText('You are not on your route')).toBeVisible()

    await expect(page.getByRole('button', { name: 'Show the whole route' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Stop following' })).toBeVisible()
    // Nothing offering to navigate, which is the absence the sentence above
    // promises. Asserted rather than assumed, because a future build adding a
    // "Take me back" button would break the promise without touching the copy.
    await expect(
      page.getByRole('button', { name: /take me back|route me|navigate/i }),
    ).toHaveCount(0)
  })
})

test.describe('the finish ask', () => {
  test('states: it asks, says what has been walked, and promises never to close the walk itself', async ({
    page,
  }) => {
    await followTheWalk(page)
    await page.getByRole('button', { name: /Finish here instead/ }).click()

    await expect(page.getByText('Done for the day?')).toBeVisible()
    await expect(page.getByText(/[\d.]+ mi walked/)).toBeVisible()
    // THE PROMISE. An app that closed somebody's walk for them would lose a
    // record they cannot re-walk, so the ask says out loud that ignoring it
    // is a complete answer.
    await expect(
      page.getByText(
        /this asks again tomorrow morning and never closes the walk for you/,
      ),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Finish this walk' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Still going' })).toBeVisible()
  })

  test('exit: “Still going” puts the hiker back on the walk with it still live', async ({
    page,
  }) => {
    // The half of the promise a spec can check. Declining has to leave the
    // walk exactly as it was — not stopped, and not finished.
    await followTheWalk(page)
    await page.getByRole('button', { name: /Finish here instead/ }).click()
    await expect(page.getByText('Done for the day?')).toBeVisible()

    await page.getByRole('button', { name: 'Still going' }).click()

    await expect(page.getByText('Done for the day?')).toHaveCount(0)
    await expect(page.locator('.next-turn')).toBeVisible()
    await expect(page.getByText(/day hike · leg \d+ of \d+/i)).toBeVisible()
  })

  test('exit: Stop leaves follow mode, and the map is a map again', async ({ page }) => {
    await followTheWalk(page)

    await page.getByRole('button', { name: 'Stop', exact: true }).click()

    await expect(page.locator('.next-turn')).toHaveCount(0)
    await expect(page.getByText(/day hike · leg \d+ of \d+/i)).toHaveCount(0)
    // The plain map's own read-out, which is how a hiker knows they are off
    // the walk rather than looking at a broken one.
    await expect(page.getByText(/no trail taken/i)).toBeVisible()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
  })
})
