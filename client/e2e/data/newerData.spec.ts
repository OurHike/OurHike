// The two surfaces that exist because published data moves on: the ask before
// a hiker's map is replaced (chrome/TrailDataUpdate.tsx, #919, D11 — "nothing
// is replaced without the hiker being asked") and the card for a place that
// has left the map since (chrome/RemovedPoiCard.tsx).
//
// WHY THIS NEEDS THE SECOND HALF OF THE SUITE. The offer is a comparison
// between what this phone stored and what `latest.json` says is published, so
// it cannot be reached at all without a bucket to read. Everything else here is
// local.
//
// HOW THE STATE IS REACHED, AND WHY IT IS NOT A CHEAT. A phone that has
// downloaded release A while B is published is an ordinary state and an
// unreachable one for a suite that pins a single release: `lib/trailData.ts`
// calls `rememberRelease` the moment it commits the bytes, so a boot always
// leaves this phone holding exactly what the bucket just served. Measured
// 2026-09-11: seeding an older record and letting the app boot normally
// overwrites the seed within about nine seconds, and the ask never appears.
//
// So the commit path is refused instead — `page.route` aborting the trail and
// waypoint artifacts — which leaves the seeded record standing and asks the
// same question the app would ask a hiker whose download predates the publish.
// The same move e2e/data/builder.spec.ts makes for the route builder's
// entrance: refuse the artifact and the state stops being a race.
//
// WHAT IT COSTS, SAID PLAINLY: the map underneath has no trail line and no
// waypoints, because those are the fetches being refused. That is fine for
// this file and would not be for any other — the card is about the release
// comparison, not about what is drawn behind it.
//
// NOTHING HERE PRESSES "Update". It would start a real download of the whole
// release through the proxy, and the assertion worth having is the opposite
// one anyway: that the app ASKS, and that leaving the ask alone changes
// nothing.

import { test, expect, type Page } from '@playwright/test'
import { seedPreferences, bootFreshPage } from '../support/seed'
import { writeIDBEntries } from '../support/idb'
import { releaseArtifactUrl } from '../support/dataPreflight'

/** `lib/dataRefresh.ts`'s RELEASE_KEY — the wire contract this spec writes,
 *  not a module it imports, for the reason support/seed.ts gives about its
 *  own three keys. */
const RELEASE_KEY = 'ourhike:trail-data-release'

/**
 * A release record that cannot match whatever the bucket is serving today.
 *
 * Both halves are deliberately impossible rather than merely old. `version` is
 * not a UUID, so `stored.version === snapshot.version` can never be true; the
 * hash is sixty-four zeroes, so the changed-artifact filter can never come
 * back empty. A record carrying a real past version would go stale the day UA
 * republishes and would then silently assert nothing — `availableRefresh`
 * returns null when the version moved but no artifact did, which is a real and
 * correct behaviour that would be indistinguishable here from a broken test.
 *
 * `poi_shelter.geojson` because it is one of the keys the app actually stores
 * (`REFRESHABLE_KEYS`) and one every release publishes.
 */
const A_DOWNLOAD_THAT_PREDATES_THE_PUBLISH = {
  version: 'the-release-this-phone-downloaded',
  hashes: { 'poi_shelter.geojson': '0'.repeat(64) },
  at: 1_700_000_000_000,
}

/** The fetches whose success would rewrite the seeded record. Refused on the
 *  page rather than the context so a sibling page can refuse them too — the
 *  cold-boot test needs the same refusal or the ask comes back for the wrong
 *  reason. */
async function refuseTheCommitPath(page: Page): Promise<void> {
  await page.route('**/trails.*', (route) => route.abort())
  await page.route('**/poi_*.*', (route) => route.abort())
}

async function aPhoneHoldingAnOlderRelease(page: Page): Promise<void> {
  await seedPreferences(page)
  await writeIDBEntries(page, [[RELEASE_KEY, A_DOWNLOAD_THAT_PREDATES_THE_PUBLISH]])
  await refuseTheCommitPath(page)
  await page.goto('/')
  await page.getByRole('tab', { name: 'Map' }).click()
  await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
}

test.describe('when the bucket has moved on', () => {
  test('entrance and states: the app asks rather than replacing, and says what accepting costs', async ({
    page,
  }) => {
    await aPhoneHoldingAnOlderRelease(page)

    // THE ASK ITSELF. Network-bound: the check is one `latest.json` read that
    // happens after the screen is already up, so the default expect window is
    // not the right budget for it.
    await expect(
      page.getByText('The map data has changed since this was downloaded.'),
    ).toBeVisible({ timeout: 60_000 })

    // TWO ANSWERS, NEITHER TAKEN. D11 is the whole point: the bytes are not
    // fetched and nothing on this phone is replaced until somebody presses.
    await expect(page.getByRole('button', { name: 'Update' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Not now' })).toBeVisible()

    // AND THE COST IS NAMED BEFORE THE BUTTON. `warnsAboutData` treats an
    // unknown size and an unknown connection as large, "the only direction
    // that cannot quietly spend somebody's allowance" — and this browser is
    // exactly that case, so the caution is deterministic here rather than
    // incidental: Chromium exposes `navigator.connection` with no `type`, which
    // `connectionKind()` reads as 'unknown'.
    await expect(page.getByText(/may use mobile data/)).toBeVisible()
  })

  test('states: leaving the ask alone leaves the phone exactly as it was', async ({
    page,
  }) => {
    await aPhoneHoldingAnOlderRelease(page)
    await expect(
      page.getByText('The map data has changed since this was downloaded.'),
    ).toBeVisible({ timeout: 60_000 })

    // Doing nothing is a real answer and the one most hikers give. The record
    // this phone holds must be untouched by having been asked — an offer that
    // quietly re-recorded the published version would make the next launch
    // believe it had bytes it does not have.
    const held = await page.evaluate(
      (key) =>
        new Promise<string | null>((resolve) => {
          const open = indexedDB.open('keyval-store')
          open.onsuccess = () => {
            const read = open.result
              .transaction('keyval', 'readonly')
              .objectStore('keyval')
              .get(key)
            read.onsuccess = () =>
              resolve((read.result as { version?: string })?.version ?? null)
            read.onerror = () => resolve(null)
          }
          open.onerror = () => resolve(null)
        }),
      RELEASE_KEY,
    )
    expect(held).toBe(A_DOWNLOAD_THAT_PREDATES_THE_PUBLISH.version)
  })

  test('states: “Not now” silences this release and not the next one', async ({
    page,
  }) => {
    await aPhoneHoldingAnOlderRelease(page)
    await expect(page.getByRole('button', { name: 'Not now' })).toBeVisible({
      timeout: 60_000,
    })

    await page.getByRole('button', { name: 'Not now' }).click()
    await expect(page.getByRole('button', { name: 'Update' })).toHaveCount(0)

    // IT HAS TO STAY GONE, or the offer is a nag — `dismissRelease` keys the
    // answer by the version declined for exactly that reason. A cold boot
    // rather than a reload, for the trap bootFreshPage() documents; the
    // sibling page needs the same refusal, or the ask would come back because
    // the record was rewritten rather than because the answer was forgotten.
    const rebooted = await bootFreshPage(page)
    try {
      await refuseTheCommitPath(rebooted)
      await rebooted.reload({ waitUntil: 'load' })
      await rebooted.getByRole('tab', { name: 'Map' }).click()
      await expect(rebooted.getByRole('region', { name: 'Trail map' })).toBeVisible()

      // Waits on something that proves the check has RUN before claiming the
      // ask is absent: the status strip's conditions line is the other thing
      // this boot fetches, so its arrival means the network round trip this
      // assertion depends on has happened.
      await expect(rebooted.getByText(/Conditions as of|Trail conditions/)).toBeVisible({
        timeout: 60_000,
      })
      await expect(rebooted.getByRole('button', { name: 'Update' })).toHaveCount(0)
    } finally {
      await rebooted.close()
    }
  })
})

/**
 * A place that has left the map, and the hiker's own note still pointing at it.
 *
 * THE DOCUMENTED BLOCKER FOR THIS WAS WRONG, and correcting it is most of why
 * this describe exists. features/FLOW_TESTING.md said the card "needs a
 * tombstone — a waypoint a NEWER release retired — so it needs two releases,
 * and this suite pins one". It does not: `retired_poi.geojson` ships INSIDE
 * each release, carrying the places that release retired, so the single pinned
 * one already holds them. Measured 2026-09-11 against release 2026-09-10: the
 * artifact's first feature is a water point retired on 2026-08-19.
 *
 * THE DOOR IS NOT THE CANVAS. A retired waypoint draws no pin — that is what
 * being retired means — so the way in is a row in the hiker's own work, which
 * App.tsx's own comment already names: "the same door a pin is: the waypoint
 * card for a live place, the removed-place card for one that has left the map".
 * A field note waiting in the outbox against that id is the smallest honest
 * version of that, and it is a state a hiker really reaches: they wrote
 * something down at a spring, and the spring left the published set before the
 * note could send.
 *
 * NOTHING NAMES A PLACE. The id, the name and the date are all read off the
 * artifact at run time, because every one of them is a claim about a release
 * rather than about the app.
 */
test.describe('a place that has left the map', () => {
  /** The release's own first tombstone. Fails loudly rather than skipping: an
   *  empty artifact would mean the export stopped publishing retirements,
   *  which is worth a red test and not a quiet pass. */
  async function firstRetiredPlace(
    request: import('@playwright/test').APIRequestContext,
  ): Promise<{ id: string; name: string }> {
    const url = releaseArtifactUrl('retired_poi.geojson')
    expect(url, 'no data origin configured — see playwright.config.ts').not.toBeNull()
    const response = await request.get(url as string)
    expect(response.ok(), `retired_poi.geojson answered ${response.status()}`).toBe(true)
    const collection = (await response.json()) as {
      features?: { properties?: { id?: string; name?: string } }[]
    }
    const first = collection.features?.[0]?.properties
    expect(
      first?.id,
      'the pinned release publishes no tombstones, so nothing here can be driven',
    ).toBeTruthy()
    return { id: first?.id as string, name: first?.name ?? '' }
  }

  test('entrance and states: the hiker’s own note opens the tombstone, which says who retired it and what became of it', async ({
    page,
    request,
  }) => {
    const retired = await firstRetiredPlace(request)

    await seedPreferences(page)
    await writeIDBEntries(page, [
      [
        'ourhike:outbox',
        [
          {
            id: 'a-note-that-outlived-its-place',
            authoredAt: new Date(Date.UTC(2026, 8, 11, 12)).toISOString(),
            fieldNote: { poi_id: retired.id, observation: 'dry', reporter_type: 'day' },
          },
        ],
      ],
    ])
    await page.goto('/')

    // More → You → the list of what this phone holds of the hiker's own work.
    await page.getByRole('tab', { name: 'More' }).click()
    await page.locator('.more__row').filter({ hasText: 'You' }).first().click()
    await page.getByRole('button', { name: 'Your photos and notes' }).click()

    // THE ROW STILL NAMES THE PLACE, from the tombstone rather than from the
    // waypoint set — `placeLabelFor` falls back to a retired place's last
    // known name before it falls back to "A place not on this map". So the
    // note does not become anonymous the day its subject is retired.
    const row = page
      .locator('button')
      .filter({
        hasText: new RegExp(
          retired.name.slice(0, 20).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'),
        ),
      })
    await expect(row.first()).toBeVisible({ timeout: 60_000 })
    await row.first().click()

    const card = page.getByRole('dialog', { name: 'Removed waypoint' })
    await expect(card).toBeVisible()

    // WHO RETIRED IT AND WHEN, in their own words rather than "removed". The
    // publisher is named because a hiker deciding whether to trust the absence
    // needs to know whose measurement it left — D9's rule, on the one card
    // that is entirely about an absence.
    await expect(
      card.getByText(/no longer in the .+, as of \w+ \d+, \d{4}\./),
    ).toBeVisible()

    // WHAT BECAME OF IT, said either way. "Nothing took its place" is a real
    // answer and the one a successor-less retirement gets; a card that simply
    // omitted the line would leave a hiker wondering whether it had been moved.
    await expect(card.getByText(/Nothing took its place\.|in its place/)).toBeVisible()

    // AND THE PROMISE THAT MATTERS. A place leaving the published set must not
    // read as the hiker's own photos and notes leaving with it.
    await expect(card.getByText(/still yours and still on this phone/)).toBeVisible()

    // The position is kept rather than dropped: a hiker standing where a
    // spring used to be is the person most in need of it.
    await expect(card.getByText(/Last known position/)).toBeVisible()
  })
})
