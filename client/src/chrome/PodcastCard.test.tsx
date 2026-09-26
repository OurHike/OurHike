import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { PodcastEpisode } from '../lib/podcasts'
import type { SaveOutcome } from '../lib/spotify'

// The podcast card (#1683), against a stubbed lib/spotify.ts. What is pinned:
// nothing reaches Spotify before a tap, the phone apps get a link and nothing
// else, a control that cannot work is not drawn, and every save outcome
// reads as what it was.

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

const HISTORY: PodcastEpisode = {
  spotifyId: '0aBcDeFgHiJkLmNoPqRsTu',
  title: 'The park’s history',
  show: 'A show',
  minutes: 48,
  hikes: ['nynjtc_hike_finder:7909'],
  atMiles: [],
}
const GEOLOGY: PodcastEpisode = {
  ...HISTORY,
  spotifyId: '1aBcDeFgHiJkLmNoPqRsTu',
  title: 'The geology here',
  minutes: 72,
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
  spotify.isSpotifyConnected.mockReturnValue(false)
  spotify.savedFromHere.mockReturnValue(new Set())
  spotify.saveEpisodeToSpotify.mockResolvedValue('saved')
})
afterEach(cleanup)

describe('PodcastCard, first look (frame 1)', () => {
  it('lists each episode with its show and length, and frames nothing from Spotify yet', () => {
    const { container } = show()

    expect(screen.getByRole('heading', { name: 'Picked for this hike' })).toBeTruthy()
    expect(within(row('The park’s history')).getByText('48 min')).toBeTruthy()
    expect(within(row('The geology here')).getByText('1 h 12 min')).toBeTruthy()
    expect(container.querySelector('iframe')).toBeNull()
    expect(
      screen.getByText(
        '▶ plays it here. Save puts it in your Spotify; the first time asks you to connect, once.',
      ),
    ).toBeTruthy()
  })

  it('prints no length for an episode nobody gave one', () => {
    show({ episodes: [{ ...HISTORY, minutes: undefined }] })
    expect(within(row('The park’s history')).queryByText(/min/)).toBeNull()
  })

  it('draws nothing at all for no episodes', () => {
    const { container } = show({ episodes: [] })
    expect(container.innerHTML).toBe('')
  })
})

describe('PodcastCard, playing (frame 1A)', () => {
  it('frames Spotify’s player for the tapped episode only', async () => {
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

describe('PodcastCard, saving', () => {
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

  it('saves in one tap once connected, and says so on the row (frame 2)', async () => {
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

  it('tells an account Spotify has not approved to tap + in Spotify instead (frame 4)', async () => {
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

describe('PodcastCard, the Spotify icon on its buttons', () => {
  it('puts Spotify’s icon, in Spotify Green at its 21px minimum, beside the word Save', () => {
    show()
    const save = screen.getByRole('button', {
      name: 'Save “The park’s history” to Spotify',
    })
    expect(save.textContent).toBe('Save')
    const icon = save.querySelector('svg')
    expect(icon?.getAttribute('width')).toBe('21')
    expect(icon?.querySelector('path')?.getAttribute('fill')).toBe('#1ED760')
  })

  it('says “Listen on Spotify”, Spotify’s own words, where the card opens Spotify', () => {
    show({ native: true })
    const links = screen.getAllByRole('link', { name: /in Spotify$/ })
    expect(links[0].textContent).toBe('Listen on Spotify')
    expect(links[0].querySelector('svg path')?.getAttribute('fill')).toBe('#1ED760')
  })
})

describe('PodcastCard, when a control cannot work', () => {
  it('offers no Play and no Save with no signal, and says why', () => {
    show({ online: false })

    expect(screen.queryByRole('button', { name: /Play|Save/ })).toBeNull()
    expect(screen.getByText('Playing and saving need signal.')).toBeTruthy()
    expect(screen.getByText('The park’s history')).toBeTruthy()
  })

  it('opens the episode in Spotify instead of saving, in a build with no Spotify app', () => {
    show({ spotifyConfigured: false })

    expect(screen.queryByRole('button', { name: /Save/ })).toBeNull()
    expect(
      screen
        .getByRole('link', { name: 'Open “The park’s history” in Spotify' })
        .getAttribute('href'),
    ).toBe('https://open.spotify.com/episode/0aBcDeFgHiJkLmNoPqRsTu')
    expect(
      screen.getByRole('button', { name: 'Play “The park’s history” here' }),
    ).toBeTruthy()
  })

  it('gives the phone apps a link per episode and nothing else (frame 2A)', () => {
    const { container } = show({ native: true })

    expect(screen.queryByRole('button', { name: /Play|Save/ })).toBeNull()
    expect(container.querySelector('iframe')).toBeNull()
    expect(screen.getAllByRole('link', { name: /in Spotify$/ })).toHaveLength(2)
    expect(
      screen.getByText(
        'Listen on Spotify opens it in the Spotify app. Playing and saving here work in OurHike in a browser.',
      ),
    ).toBeTruthy()
  })
})
