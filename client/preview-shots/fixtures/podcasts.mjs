// Fixtures for the podcast recipes (#1683): a published episode list, as
// pipeline/export_podcasts.py writes it, answered over the network and kept
// in the copy the app reads with no signal (lib/podcasts.ts, through the
// conditions cache under `ourhike:conditions:podcasts/episodes.json`).
//
// NOBODY'S EPISODES. The ids are 22 base-62 characters that name no real
// episode, and the titles and shows are invented. No recipe taps Play or
// Save: either would reach Spotify from CI, and the shots are evidence about
// the card before a tap, which is the state the maintainer's mock drew.
//
// Not a recipe: shared fixtures live one directory down, where the runner's
// top-level `preview-shots/*.mjs` pattern does not reach.

/** Two episodes on Wapiti to Docs Knob (fixtures/suggestedHikes.mjs), and one
 *  on the A.T. from Neels Gap to Dicks Creek Gap - which holds the leg
 *  fixtures/longHike.mjs plans for today, Low Gap to Tray Mountain. */
export const PODCAST_EPISODES_DOCUMENT = {
  source: 'reference/podcast_episodes.json',
  episodes: [
    {
      spotify_id: 'Fixture0HistoryEpisode',
      title: 'Episode about this park’s history',
      show: 'Show name',
      minutes: 48,
      hikes: ['nynjtc_hike_finder:7909'],
      at_miles: [],
    },
    {
      spotify_id: 'Fixture1GeologyEpisode',
      title: 'Episode about the geology here',
      show: 'Show name',
      minutes: 72,
      hikes: ['nynjtc_hike_finder:7909'],
      at_miles: [],
    },
    {
      spotify_id: 'Fixture2SectionEpisode',
      title: 'Episode about this section',
      show: 'Show name',
      minutes: 36,
      hikes: [],
      at_miles: [[31.7, 69.6]],
    },
  ],
}

/**
 * Answer the bucket and seed the kept copy, then leave the reload to the
 * seed that follows (seedSuggestedHikes and seedLongHike both reload).
 *
 * Both halves for the reason fixtures/suggestedHikes.mjs gives at length: the
 * kept copy stands only until the real `podcasts/episodes.json` answers, and
 * in CI the preview is built against real data - so the route is what makes
 * the shot hold, and the seed is what makes it hold on a build with no
 * bucket at all.
 */
export async function seedPodcastEpisodes(page, document = PODCAST_EPISODES_DOCUMENT) {
  await page.route(/\/podcasts\/episodes\.json(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(document),
    }),
  )
  await page.evaluate(
    (document) =>
      new Promise((done, fail) => {
        const open = indexedDB.open('keyval-store')
        open.onupgradeneeded = () => open.result.createObjectStore('keyval')
        open.onerror = () => fail(open.error)
        open.onsuccess = () => {
          const write = open.result
            .transaction('keyval', 'readwrite')
            .objectStore('keyval')
            .put(
              { document, storedAt: '2026-09-26T12:00:00.000Z' },
              'ourhike:conditions:podcasts/episodes.json',
            )
          write.onsuccess = () => done(undefined)
          write.onerror = () => fail(write.error)
        }
      }),
    document,
  )
}
