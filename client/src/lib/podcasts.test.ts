import 'fake-indexeddb/auto'
import { clear } from 'idb-keyval'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  PODCAST_EPISODES_KEY,
  appsEveryEpisodeOpensIn,
  episodesForHike,
  episodesForPoi,
  podcastAppsToList,
  episodesForMiles,
  formatMinutes,
  parsePodcastEpisodes,
  spotifyEmbedUrl,
  episodeUrlIn,
  spotifyEpisodeUrl,
  type PodcastEpisode,
} from './podcasts'

// What the phone makes of pipeline/export_podcasts.py's document (#1683),
// which episodes each screen picks out of it, and the read from the bucket
// root. The ids are real-shaped (22 base-62 characters) and not real episodes.

const HIKE = 'nynjtc_hike_finder:7909'
const ID_A = '0aBcDeFgHiJkLmNoPqRsTu'
const ID_B = '1aBcDeFgHiJkLmNoPqRsTu'

const DOCUMENT = {
  source: 'reference/podcast_episodes.json',
  episodes: [
    {
      spotify_id: ID_A,
      title: 'The park’s history',
      show: 'A show',
      minutes: 48,
      hikes: [HIKE],
      at_miles: [],
    },
    {
      spotify_id: ID_B,
      title: 'This section',
      show: 'A show',
      hikes: [],
      at_miles: [[480, 512]],
    },
  ],
}

function episode(overrides: Partial<PodcastEpisode>): PodcastEpisode {
  return {
    spotifyId: ID_A,
    title: 't',
    show: 's',
    hikes: [],
    atMiles: [],
    pois: [],
    links: {},
    ...overrides,
  }
}

describe('the podcasts key', () => {
  it('is podcasts/episodes.json, at the bucket root', () => {
    expect(PODCAST_EPISODES_KEY).toBe('podcasts/episodes.json')
  })
})

describe('parsePodcastEpisodes', () => {
  it('reads every published field, and leaves an unknown length undefined rather than 0', () => {
    expect(parsePodcastEpisodes(DOCUMENT)).toEqual([
      {
        spotifyId: ID_A,
        title: 'The park’s history',
        show: 'A show',
        minutes: 48,
        hikes: [HIKE],
        atMiles: [],
        pois: [],
        links: {},
      },
      {
        spotifyId: ID_B,
        title: 'This section',
        show: 'A show',
        hikes: [],
        atMiles: [[480, 512]],
        pois: [],
        links: {},
      },
    ])
    expect(parsePodcastEpisodes(DOCUMENT)?.[1]).not.toHaveProperty('minutes')
  })

  it('reads an empty list as nobody having picked anything, not as a broken document', () => {
    expect(parsePodcastEpisodes({ episodes: [] })).toEqual([])
  })

  it('answers null for a document that is not this shape at all', () => {
    expect(parsePodcastEpisodes(null)).toBeNull()
    expect(parsePodcastEpisodes({ episodes: 'none' })).toBeNull()
  })

  it.each([
    [
      'an id that is a whole link',
      { spotify_id: `https://open.spotify.com/episode/${ID_A}` },
    ],
    [
      'an id with a character a URL would need escaped',
      { spotify_id: '0aBcDeFgHiJkLmNoPqRs/"' },
    ],
    ['no title', { title: '' }],
    ['no show', { show: undefined }],
    ['no anchor at all', { hikes: [], at_miles: [] }],
  ])('drops a row with %s, and keeps the rest', (_, change) => {
    const bad = { ...DOCUMENT.episodes[0], ...change }
    const parsed = parsePodcastEpisodes({ episodes: [bad, DOCUMENT.episodes[1]] })
    expect(parsed?.map((e) => e.spotifyId)).toEqual([ID_B])
  })

  it('drops a mile range that runs backwards, and a length that is not whole minutes', () => {
    const parsed = parsePodcastEpisodes({
      episodes: [
        {
          ...DOCUMENT.episodes[1],
          at_miles: [
            [512, 480],
            [480, 512],
          ],
          minutes: 47.5,
        },
      ],
    })
    expect(parsed?.[0].atMiles).toEqual([[480, 512]])
    expect(parsed?.[0].minutes).toBeUndefined()
  })

  it('keeps the first of two rows for the same episode', () => {
    const parsed = parsePodcastEpisodes({
      episodes: [DOCUMENT.episodes[0], { ...DOCUMENT.episodes[0], title: 'second' }],
    })
    expect(parsed?.map((e) => e.title)).toEqual(['The park’s history'])
  })
})

describe('each other app’s link (#1690)', () => {
  const apple = 'https://podcasts.apple.com/us/podcast/a-show/id1?i=2'

  it('keeps a link on its own app’s host, and drops one that is not, one link at a time', () => {
    const parsed = parsePodcastEpisodes({
      episodes: [
        {
          ...DOCUMENT.episodes[0],
          links: {
            apple_podcasts: apple,
            overcast: 'http://overcast.fm/+AbC',
            pocket_casts: 'https://overcast.fm/+AbC',
            youtube_music: 'javascript:alert(1)',
            castbox: 'https://castbox.fm/x',
          },
        },
      ],
    })
    expect(parsed?.[0].links).toEqual({ apple_podcasts: apple })
  })

  it('opens an episode in the app asked for, Spotify always, and the rest only where linked', () => {
    const one = episode({ spotifyId: ID_A, links: { apple_podcasts: apple } })
    expect(episodeUrlIn(one, 'spotify')).toBe(`https://open.spotify.com/episode/${ID_A}`)
    expect(episodeUrlIn(one, 'apple_podcasts')).toBe(apple)
    expect(episodeUrlIn(one, 'overcast')).toBeNull()
  })
})

describe('the apps a hiker is offered (maintainer’s poll, 2026-09-29, frame Q1)', () => {
  const apple = 'https://podcasts.apple.com/us/podcast/a-show/id1?i=2'
  const overcast = 'https://overcast.fm/+AbC'
  const linked = episode({ spotifyId: ID_A, links: { apple_podcasts: apple, overcast } })
  const appleOnly = episode({ spotifyId: ID_B, links: { apple_podcasts: apple } })

  it('offers an app only when every episode on the list opens in it, Spotify always', () => {
    expect(appsEveryEpisodeOpensIn([linked])).toEqual([
      'spotify',
      'apple_podcasts',
      'overcast',
    ])
    expect(appsEveryEpisodeOpensIn([linked, appleOnly])).toEqual([
      'spotify',
      'apple_podcasts',
    ])
  })

  it('offers Spotify alone for an empty list, rather than every app for having no exceptions', () => {
    expect(appsEveryEpisodeOpensIn([])).toEqual(['spotify'])
  })

  it('lists a pick that has since dropped out beside the apps on offer, in the app list’s order', () => {
    expect(podcastAppsToList(['spotify', 'apple_podcasts'], 'overcast')).toEqual([
      'spotify',
      'apple_podcasts',
      'overcast',
    ])
    expect(podcastAppsToList(['spotify'], null)).toEqual(['spotify'])
    expect(podcastAppsToList(['spotify', 'apple_podcasts'], 'spotify')).toEqual([
      'spotify',
      'apple_podcasts',
    ])
  })
})

describe('episodesForHike', () => {
  it('picks the episodes whose hikes name this one, in the list’s order', () => {
    const list = parsePodcastEpisodes(DOCUMENT) ?? []
    expect(episodesForHike(list, HIKE).map((e) => e.spotifyId)).toEqual([ID_A])
    expect(episodesForHike(list, 'nynjtc_hike_finder:1')).toEqual([])
  })
})

describe('episodesForPoi (#1718)', () => {
  const SHELTER = 'atc_shelters:00000000-0000-0000-0000-000000000001'
  const SUMMIT = 'atc_viewpoints:00000000-0000-0000-0000-000000000002'

  it('keeps a row tagged only to places, and reads its ids', () => {
    const parsed = parsePodcastEpisodes({
      episodes: [{ ...DOCUMENT.episodes[0], hikes: [], pois: [SHELTER, SUMMIT] }],
    })
    expect(parsed?.[0]?.pois).toEqual([SHELTER, SUMMIT])
  })

  it('reads a row published before pois existed as tagged to no place', () => {
    expect(parsePodcastEpisodes(DOCUMENT)?.[0]?.pois).toEqual([])
  })

  it('picks the episodes tagged to this exact place, in the list’s order', () => {
    const list = [
      episode({ spotifyId: ID_A, pois: [SHELTER] }),
      episode({ spotifyId: ID_B, pois: [SUMMIT, SHELTER] }),
    ]
    expect(episodesForPoi(list, SHELTER).map((e) => e.spotifyId)).toEqual([ID_A, ID_B])
    expect(episodesForPoi(list, SUMMIT).map((e) => e.spotifyId)).toEqual([ID_B])
    expect(episodesForPoi(list, 'atc_privies:nowhere')).toEqual([])
  })
})

describe('episodesForMiles', () => {
  const list = [episode({ spotifyId: ID_B, atMiles: [[480, 512]] })]

  it('picks an episode whose range holds the whole day', () => {
    expect(episodesForMiles(list, 486.2, 497.7)).toHaveLength(1)
  })

  it('picks one whose range only clips the day, at either end', () => {
    expect(episodesForMiles(list, 470, 481)).toHaveLength(1)
    expect(episodesForMiles(list, 511, 520)).toHaveLength(1)
  })

  it('counts a range that ends at the mile the day starts from', () => {
    expect(episodesForMiles(list, 512, 520)).toHaveLength(1)
  })

  it('leaves out a range the day never reaches', () => {
    expect(episodesForMiles(list, 520, 531)).toEqual([])
  })
})

describe('links and lengths', () => {
  const one = episode({ spotifyId: ID_A })

  it('opens the episode on open.spotify.com, and embeds Spotify’s own player', () => {
    expect(spotifyEpisodeUrl(one)).toBe(`https://open.spotify.com/episode/${ID_A}`)
    expect(spotifyEmbedUrl(one)).toBe(`https://open.spotify.com/embed/episode/${ID_A}`)
  })

  it('prints a length in minutes, then hours and minutes, and nothing for an unknown one', () => {
    expect(formatMinutes(48)).toBe('48 min')
    expect(formatMinutes(60)).toBe('1 h')
    expect(formatMinutes(72)).toBe('1 h 12 min')
    expect(formatMinutes(undefined)).toBeNull()
  })
})

// The read itself, against a stubbed bucket. config.ts reads
// VITE_DATA_BASE_URL once at module load, so each case imports fresh -
// lib/mapSheets.test.ts's pattern.
const BASE = 'https://cdn.example.org'

async function loadWithBase(base: string | undefined) {
  vi.resetModules()
  vi.stubEnv('VITE_DATA_BASE_URL', base ?? '')
  return await import('./podcasts')
}

describe('fetchPodcastEpisodes', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    await clear()
  })
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.restoreAllMocks()
  })

  it('reads podcasts/episodes.json from the bucket root, never a release folder', async () => {
    const fetched = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(
        async () => new Response(JSON.stringify(DOCUMENT), { status: 200 }),
      )
    const { fetchPodcastEpisodes } = await loadWithBase(BASE)

    const episodes = await fetchPodcastEpisodes(true)

    expect(fetched).toHaveBeenCalledWith(
      `${BASE}/podcasts/episodes.json`,
      expect.anything(),
    )
    expect(episodes?.map((e) => e.spotifyId)).toEqual([ID_A, ID_B])
  })

  it('answers null with no bucket configured, and asks nothing', async () => {
    const fetched = vi.spyOn(globalThis, 'fetch')
    const { fetchPodcastEpisodes } = await loadWithBase(undefined)

    expect(await fetchPodcastEpisodes(true)).toBeNull()
    expect(fetched).not.toHaveBeenCalled()
  })

  it('serves the kept copy offline and fires no request', async () => {
    const fetched = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(
        async () => new Response(JSON.stringify(DOCUMENT), { status: 200 }),
      )
    await (await loadWithBase(BASE)).fetchPodcastEpisodes(true)

    fetched.mockClear()
    fetched.mockImplementation(async () => new Response('', { status: 500 }))
    const episodes = await (await loadWithBase(BASE)).fetchPodcastEpisodes(false)

    expect(fetched).not.toHaveBeenCalled()
    expect(episodes).toHaveLength(2)
  })

  it('keeps the last good list through a 404, which is not evidence the episodes were withdrawn', async () => {
    const fetched = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(
        async () => new Response(JSON.stringify(DOCUMENT), { status: 200 }),
      )
    await (await loadWithBase(BASE)).fetchPodcastEpisodes(true)

    fetched.mockImplementation(async () => new Response('', { status: 404 }))
    const episodes = await (await loadWithBase(BASE)).fetchPodcastEpisodes(true)

    expect(episodes).toHaveLength(2)
  })

  it('never replaces a kept list with a document it cannot read', async () => {
    const fetched = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(
        async () => new Response(JSON.stringify(DOCUMENT), { status: 200 }),
      )
    await (await loadWithBase(BASE)).fetchPodcastEpisodes(true)

    fetched.mockImplementation(
      async () => new Response('{"episodes":"nope"}', { status: 200 }),
    )
    await (await loadWithBase(BASE)).fetchPodcastEpisodes(true)
    const kept = await (await loadWithBase(BASE)).fetchPodcastEpisodes(false)

    expect(kept).toHaveLength(2)
  })
})
