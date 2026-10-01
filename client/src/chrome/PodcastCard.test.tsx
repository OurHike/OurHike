import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { PodcastApp, PodcastEpisode } from '../lib/podcasts'
import type { SaveOutcome } from '../lib/spotify'

// The podcast card (#1683, #1690), against a stubbed lib/spotify.ts. What is
// pinned: nothing reaches Spotify before a tap; the card asks which podcast
// app before assuming one; each episode opens in the hiker's app, or in
// Spotify with a line saying why; ↓ opens the episode in that app; the phone
// apps get links and nothing else; a control that cannot work is not drawn;
// and every save outcome reads as what it was.

const spotify = vi.hoisted(() => ({
  SPOTIFY_CONFIGURED: true,
  beginSpotifyConnect: vi.fn(async () => {}),
  disconnectSpotify: vi.fn(),
  isSpotifyConnected: vi.fn(() => false),
  saveEpisodeToSpotify: vi.fn(async (): Promise<SaveOutcome> => 'saved'),
  savedFromHere: vi.fn(() => new Set<string>()),
}))
vi.mock('../lib/spotify', () => spotify)

const { PodcastCard } = await import('./PodcastCard')

const APPLE_LINK = 'https://podcasts.apple.com/us/podcast/a-show/id1?i=2'

const HISTORY: PodcastEpisode = {
  spotifyId: '0aBcDeFgHiJkLmNoPqRsTu',
  title: 'The park’s history',
  show: 'A show',
  minutes: 48,
  hikes: ['nynjtc_hike_finder:7909'],
  atMiles: [],
  pois: [],
  links: { apple_podcasts: APPLE_LINK },
}
const GEOLOGY: PodcastEpisode = {
  ...HISTORY,
  spotifyId: '1aBcDeFgHiJkLmNoPqRsTu',
  title: 'The geology here',
  minutes: 72,
  links: {},
}

function pick(app: PodcastApp | null) {
  if (app === null) localStorage.removeItem('ourhike:podcast-app')
  else localStorage.setItem('ourhike:podcast-app', app)
}

function show(props: Partial<Parameters<typeof PodcastCard>[0]> = {}) {
  return render(
    <PodcastCard
      episodes={[HISTORY, GEOLOGY]}
      heading="Picked for this hike"
      online
      native={false}
      spotifyConfigured
      {...props}
    />,
  )
}

function row(title: string) {
  return screen.getByText(title).closest('li') as HTMLElement
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  spotify.isSpotifyConnected.mockReturnValue(false)
  spotify.savedFromHere.mockReturnValue(new Set())
  spotify.saveEpisodeToSpotify.mockResolvedValue('saved')
})
afterEach(cleanup)

describe('PodcastCard, before a hiker has picked an app (#1690, frame 1A)', () => {
  it('lists each episode with its show and length, and frames nothing from Spotify yet', () => {
    const { container } = show()

    expect(screen.getByRole('heading', { name: 'Picked for this hike' })).toBeTruthy()
    expect(within(row('The park’s history')).getByText('48 min')).toBeTruthy()
    expect(within(row('The geology here')).getByText('1 h 12 min')).toBeTruthy()
    expect(container.querySelector('iframe')).toBeNull()
  })

  it('assumes no app: Listen and ↓ both ask, and neither leaves the page', async () => {
    show()

    expect(screen.queryByRole('link')).toBeNull()
    expect(
      screen.getByText(
        '▶ plays it here. Listen or ↓ asks which podcast app you use, once.',
      ),
    ).toBeTruthy()

    await userEvent.click(
      screen.getByRole('button', {
        name: 'Listen to “The park’s history” in your podcast app',
      }),
    )

    expect(screen.getByText('Which app do you listen in?')).toBeTruthy()
    expect(spotify.beginSpotifyConnect).not.toHaveBeenCalled()
  })

  it('keeps the pick on this phone and comes back to the list with that app’s buttons', async () => {
    show({ offeredApps: ['spotify', 'apple_podcasts'] })
    await userEvent.click(
      screen.getByRole('button', {
        name: 'Download “The park’s history” in your podcast app',
      }),
    )

    await userEvent.click(screen.getByRole('button', { name: 'Apple Podcasts' }))

    expect(localStorage.getItem('ourhike:podcast-app')).toBe('apple_podcasts')
    expect(screen.queryByText('Which app do you listen in?')).toBeNull()
    expect(
      screen.getByRole('link', { name: 'Open “The park’s history” in Apple Podcasts' }),
    ).toBeTruthy()
  })
})

describe('which apps the picker offers (maintainer’s poll, 2026-09-29, frame Q1)', () => {
  async function openPicker() {
    await userEvent.click(
      screen.getByRole('button', {
        name: 'Listen to “The park’s history” in your podcast app',
      }),
    )
    const list = screen.getByRole('list', { name: 'Podcast apps' })
    return within(list)
      .getAllByRole('button')
      .map((button) => button.textContent)
  }

  it('offers only the apps it is given, in the app list’s order', async () => {
    show({ offeredApps: ['apple_podcasts', 'spotify'] })
    expect(await openPicker()).toEqual(['Spotify', 'Apple Podcasts'])
  })

  it('works them out from its own episodes when given none: Apple only while every one has an Apple link', async () => {
    show({ episodes: [HISTORY] })
    expect(await openPicker()).toEqual(['Spotify', 'Apple Podcasts'])
    cleanup()

    show({ episodes: [HISTORY, GEOLOGY] })
    expect(await openPicker()).toEqual(['Spotify'])
  })
})

describe('PodcastCard, in the hiker’s own app (#1690)', () => {
  it('opens an episode linked for their app in that app, with that app’s wording', () => {
    pick('apple_podcasts')
    show()

    const listen = within(row('The park’s history')).getByRole('link', {
      name: 'Open “The park’s history” in Apple Podcasts',
    })
    expect(listen.getAttribute('href')).toBe(APPLE_LINK)
    expect(listen.textContent).toBe('Listen on Apple Podcasts')
  })

  it('points ↓ at the same episode in the same app, since only the app can download', () => {
    pick('apple_podcasts')
    show()

    const down = within(row('The park’s history')).getByRole('link', {
      name: 'Download “The park’s history” in Apple Podcasts',
    })
    expect(down.getAttribute('href')).toBe(APPLE_LINK)
    expect(
      screen.getByText(
        '▶ plays it here. ↓ opens it in Apple Podcasts to download it there. Your app is Apple Podcasts; change it in More → Settings.',
      ),
    ).toBeTruthy()
  })

  it('still shows an episode nobody linked for their app, in Spotify, and says so (frame 2A)', () => {
    pick('apple_podcasts')
    show()

    const geology = row('The geology here')
    expect(
      within(geology)
        .getByRole('link', { name: 'Open “The geology here” in Spotify' })
        .getAttribute('href'),
    ).toBe('https://open.spotify.com/episode/1aBcDeFgHiJkLmNoPqRsTu')
    expect(within(geology).getByText('Not linked for Apple Podcasts yet.')).toBeTruthy()
    expect(within(row('The park’s history')).queryByText(/Not linked/)).toBeNull()
  })

  it('keeps ▶ for everyone, whatever app they picked (frame 3A)', () => {
    pick('overcast')
    show()
    expect(
      screen.getByRole('button', { name: 'Play “The park’s history” here' }),
    ).toBeTruthy()
  })

  it('offers one-tap Save to a hiker who picked Spotify, and to nobody else', () => {
    pick('pocket_casts')
    const { unmount } = show()
    expect(screen.queryByRole('button', { name: /^Save/ })).toBeNull()
    unmount()

    pick('spotify')
    show()
    expect(screen.getAllByRole('button', { name: /^Save .* to Spotify$/ })).toHaveLength(
      2,
    )
  })
})

describe('PodcastCard, playing (#1683, frame 1A)', () => {
  it('frames Spotify’s player for the tapped episode only', async () => {
    pick('spotify')
    const { container } = show()

    await userEvent.click(
      screen.getByRole('button', { name: 'Play “The park’s history” here' }),
    )

    const frames = container.querySelectorAll('iframe')
    expect(frames).toHaveLength(1)
    expect(frames[0].getAttribute('src')).toBe(
      'https://open.spotify.com/embed/episode/0aBcDeFgHiJkLmNoPqRsTu',
    )
    expect(frames[0].getAttribute('title')).toBe('Spotify player: The park’s history')
    expect(
      screen.queryByRole('button', { name: 'Play “The park’s history” here' }),
    ).toBeNull()
    expect(
      screen.getByRole('button', { name: 'Play “The geology here” here' }),
    ).toBeTruthy()
  })
})

describe('PodcastCard, saving to Spotify (#1683)', () => {
  beforeEach(() => pick('spotify'))

  it('goes to Spotify to connect on the first Save, carrying the episode', async () => {
    show()

    await userEvent.click(
      screen.getByRole('button', { name: 'Save “The park’s history” to Spotify' }),
    )

    expect(spotify.beginSpotifyConnect).toHaveBeenCalledWith({
      spotifyId: HISTORY.spotifyId,
      title: HISTORY.title,
    })
    expect(spotify.saveEpisodeToSpotify).not.toHaveBeenCalled()
  })

  it('saves in one tap once connected, and says so on the row', async () => {
    spotify.isSpotifyConnected.mockReturnValue(true)
    show()

    expect(screen.getByText('Spotify connected')).toBeTruthy()
    await userEvent.click(
      screen.getByRole('button', { name: 'Save “The park’s history” to Spotify' }),
    )

    expect(spotify.saveEpisodeToSpotify).toHaveBeenCalledWith(HISTORY.spotifyId)
    expect(
      within(row('The park’s history')).getByRole('img', {
        name: '“The park’s history” is saved to Spotify',
      }),
    ).toBeTruthy()
    expect(
      within(row('The geology here')).getByRole('button', { name: /Save/ }),
    ).toBeTruthy()
  })

  it('remembers an episode this phone saved before', () => {
    spotify.savedFromHere.mockReturnValue(new Set([GEOLOGY.spotifyId]))
    show()
    expect(
      within(row('The geology here')).getByRole('img', {
        name: '“The geology here” is saved to Spotify',
      }),
    ).toBeTruthy()
  })

  it('tells an account Spotify has not approved to tap + in Spotify instead', async () => {
    spotify.isSpotifyConnected.mockReturnValue(true)
    spotify.saveEpisodeToSpotify.mockResolvedValue('not_approved')
    show()

    await userEvent.click(
      screen.getByRole('button', { name: 'Save “The park’s history” to Spotify' }),
    )

    const status = within(row('The park’s history')).getByRole('status')
    expect(status.textContent).toContain(
      'Spotify hasn’t approved this account for OurHike.',
    )
    expect(
      within(status)
        .getByRole('link', { name: 'Open it in Spotify ↗' })
        .getAttribute('href'),
    ).toBe('https://open.spotify.com/episode/0aBcDeFgHiJkLmNoPqRsTu')
    expect(
      within(row('The park’s history')).queryByRole('button', { name: /Save/ }),
    ).toBeNull()
  })

  it('says a failed save failed, and leaves Save to try again', async () => {
    spotify.isSpotifyConnected.mockReturnValue(true)
    spotify.saveEpisodeToSpotify.mockResolvedValue('failed')
    show()

    await userEvent.click(
      screen.getByRole('button', { name: 'Save “The park’s history” to Spotify' }),
    )

    expect(within(row('The park’s history')).getByRole('status').textContent).toContain(
      'That didn’t reach Spotify.',
    )
    expect(
      within(row('The park’s history')).getByRole('button', { name: /Save/ }),
    ).toBeTruthy()
  })

  it('goes back to Spotify to connect when the kept connection no longer works', async () => {
    spotify.isSpotifyConnected.mockReturnValue(true)
    spotify.saveEpisodeToSpotify.mockResolvedValue('needs_connect')
    show()

    await userEvent.click(
      screen.getByRole('button', { name: 'Save “The park’s history” to Spotify' }),
    )

    expect(spotify.beginSpotifyConnect).toHaveBeenCalledTimes(1)
  })

  it('forgets the connection on Disconnect', async () => {
    spotify.isSpotifyConnected.mockReturnValue(true)
    show()

    await userEvent.click(screen.getByRole('button', { name: 'Disconnect' }))

    expect(spotify.disconnectSpotify).toHaveBeenCalled()
    expect(screen.queryByText('Spotify connected')).toBeNull()
  })
})

describe('PodcastCard, each app’s icon on its buttons (#1683, #1690)', () => {
  it('puts Spotify’s icon, in Spotify Green at its 21px minimum, beside the word Save', () => {
    pick('spotify')
    show()
    const save = screen.getByRole('button', {
      name: 'Save “The park’s history” to Spotify',
    })
    expect(save.textContent).toBe('Save')
    const icon = save.querySelector('svg')
    expect(icon?.getAttribute('width')).toBe('21')
    expect(icon?.querySelector('path')?.getAttribute('fill')).toBe('#1ED760')
  })

  it('draws the chosen app’s own icon beside “Listen on” its name', () => {
    pick('apple_podcasts')
    show()
    const listen = screen.getByRole('link', {
      name: 'Open “The park’s history” in Apple Podcasts',
    })
    expect(listen.querySelector('svg')?.getAttribute('width')).toBe('21')
    expect(listen.querySelector('svg path')?.getAttribute('fill')).toBe('#9933CC')
  })
})

describe('PodcastCard, when a control cannot work', () => {
  it('offers no Play, no ↓ and no Save with no signal, and says why', () => {
    pick('spotify')
    show({ online: false })

    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.getByText('Playing and downloading need signal.')).toBeTruthy()
    expect(screen.getByText('The park’s history')).toBeTruthy()
  })

  it('opens the episode in Spotify instead of saving, in a build with no Spotify app', () => {
    pick('spotify')
    show({ spotifyConfigured: false })

    expect(screen.queryByRole('button', { name: /^Save/ })).toBeNull()
    expect(
      screen
        .getByRole('link', { name: 'Open “The park’s history” in Spotify' })
        .getAttribute('href'),
    ).toBe('https://open.spotify.com/episode/0aBcDeFgHiJkLmNoPqRsTu')
    expect(
      screen.getByRole('button', { name: 'Play “The park’s history” here' }),
    ).toBeTruthy()
  })

  it('gives the phone apps ↓ and a link per episode, with no player and no save', () => {
    pick('spotify')
    const { container } = show({ native: true })

    expect(screen.queryByRole('button', { name: /Play|Save/ })).toBeNull()
    expect(container.querySelector('iframe')).toBeNull()
    expect(screen.getAllByRole('link', { name: /^Open .* in Spotify$/ })).toHaveLength(2)
    expect(
      screen.getAllByRole('link', { name: /^Download .* in Spotify$/ }),
    ).toHaveLength(2)
  })
})

describe('PodcastCard, under a section title of its own (#1718, the place card)', () => {
  it('keeps its heading for a screen reader and hides it from the eye', () => {
    show({ heading: 'Episodes about this place', headingHidden: true })

    const heading = screen.getByRole('heading', { name: 'Episodes about this place' })
    expect(heading).toHaveClass('visually-hidden')
    expect(
      screen.getByRole('region', { name: 'Episodes about this place' }),
    ).toBeInTheDocument()
  })

  it('shows its heading wherever the screen has no title of its own', () => {
    show()

    expect(screen.getByRole('heading', { name: 'Picked for this hike' })).not.toHaveClass(
      'visually-hidden',
    )
  })
})
