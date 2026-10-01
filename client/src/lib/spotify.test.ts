import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// The Spotify round trip and the save (#1683), against a stubbed Spotify.
// Every request below is answered by the fetch spy; nothing reaches a network.
//
// The client id is read at module load, so each case imports the module
// fresh with the variable it needs.

const EPISODE = { spotifyId: '0aBcDeFgHiJkLmNoPqRsTu', title: 'The park’s history' }

async function load(clientId = 'test-client-id') {
  vi.resetModules()
  vi.stubEnv('VITE_SPOTIFY_CLIENT_ID', clientId)
  return await import('./spotify')
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

const TOKEN_BODY = {
  access_token: 'access-1',
  refresh_token: 'refresh-1',
  expires_in: 3600,
}

function keepTokens(expiresAt: number, refreshToken: string | null = 'refresh-1') {
  localStorage.setItem(
    'ourhike:spotify:tokens',
    JSON.stringify({ accessToken: 'access-1', refreshToken, expiresAt }),
  )
}

/** Answers each request by URL and method, and records what was asked. */
function spotify(answers: { token?: () => Response; library?: (() => Response)[] }) {
  const library = [...(answers.library ?? [])]
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.startsWith('https://accounts.spotify.com/api/token')) {
      return answers.token?.() ?? new Response('', { status: 400 })
    }
    if (url.startsWith('https://api.spotify.com/v1/me/library')) {
      return library.shift()?.() ?? new Response('', { status: 500 })
    }
    throw new Error(`unexpected request to ${url}`)
  })
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

describe('configuration', () => {
  it('draws no Save button in a build given no client id', async () => {
    expect((await load('')).SPOTIFY_CONFIGURED).toBe(false)
    expect((await load('abc')).SPOTIFY_CONFIGURED).toBe(true)
  })

  it('sends Spotify back to the callback page beside the app, never to the app itself', async () => {
    const { redirectUri } = await load()
    const uri = redirectUri('https://ourhike.org')
    expect(uri).toMatch(/^https:\/\/ourhike\.org\/.*spotify-callback\.html$/)
  })
})

describe('PKCE', () => {
  it('computes RFC 7636’s own S256 example', async () => {
    const { challengeFor } = await load()
    // RFC 7636, Appendix B.
    expect(await challengeFor('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk')).toBe(
      'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM',
    )
  })

  it('makes a 64-character verifier from the unreserved set, different every time', async () => {
    const { randomVerifier } = await load()
    const one = randomVerifier()
    expect(one).toMatch(/^[A-Za-z0-9\-._~]{64}$/)
    expect(randomVerifier()).not.toBe(one)
  })
})

describe('beginSpotifyConnect', () => {
  it('asks Spotify for the library scope alone, with a challenge, and remembers the episode', async () => {
    const { beginSpotifyConnect } = await load()
    const go = vi.fn()

    await beginSpotifyConnect(EPISODE, go)

    const url = new URL(go.mock.calls[0][0] as string)
    expect(url.origin + url.pathname).toBe('https://accounts.spotify.com/authorize')
    expect(url.searchParams.get('client_id')).toBe('test-client-id')
    expect(url.searchParams.get('scope')).toBe('user-library-modify')
    expect(url.searchParams.get('code_challenge_method')).toBe('S256')
    expect(url.searchParams.get('redirect_uri')).toMatch(/spotify-callback\.html$/)
    const pending = JSON.parse(localStorage.getItem('ourhike:spotify:pending') ?? '{}')
    expect(pending.episode).toEqual(EPISODE)
    expect(url.searchParams.get('state')).toBe(pending.state)
  })
})

describe('completeSpotifyConnect', () => {
  async function started() {
    const module = await load()
    const go = vi.fn()
    await module.beginSpotifyConnect(EPISODE, go)
    const state = new URL(go.mock.calls[0][0] as string).searchParams.get('state')
    return { module, state }
  }

  it('exchanges the code, keeps the token, and saves the episode the trip was for', async () => {
    const { module, state } = await started()
    const fetched = spotify({ token: () => json(TOKEN_BODY), library: [() => json({})] })

    const outcome = await module.completeSpotifyConnect(`?code=abc&state=${state}`)

    expect(outcome).toEqual({ kind: 'connected', episode: EPISODE, saved: 'saved' })
    const body = new URLSearchParams(String(fetched.mock.calls[0][1]?.body))
    expect(body.get('grant_type')).toBe('authorization_code')
    expect(body.get('code')).toBe('abc')
    expect(body.get('code_verifier')).toMatch(/^[A-Za-z0-9\-._~]{64}$/)
    expect(body.get('redirect_uri')).toMatch(/spotify-callback\.html$/)
    const saveUrl = new URL(String(fetched.mock.calls[1][0]))
    expect(saveUrl.searchParams.get('uris')).toBe(`spotify:episode:${EPISODE.spotifyId}`)
    expect(fetched.mock.calls[1][1]?.method).toBe('PUT')
    expect(module.isSpotifyConnected()).toBe(true)
  })

  it('reports an account Spotify has not approved, after connecting it', async () => {
    const { module, state } = await started()
    spotify({
      token: () => json(TOKEN_BODY),
      library: [() => new Response('', { status: 403 })],
    })

    const outcome = await module.completeSpotifyConnect(`?code=abc&state=${state}`)

    expect(outcome).toMatchObject({ kind: 'connected', saved: 'not_approved' })
  })

  it('exchanges nothing for a state it did not send', async () => {
    const { module } = await started()
    const fetched = spotify({ token: () => json(TOKEN_BODY) })

    expect(await module.completeSpotifyConnect('?code=abc&state=forged')).toEqual({
      kind: 'lost',
    })
    expect(fetched).not.toHaveBeenCalled()
  })

  it('exchanges nothing when this phone started no round trip', async () => {
    const module = await load()
    const fetched = spotify({ token: () => json(TOKEN_BODY) })

    expect(await module.completeSpotifyConnect('?code=abc&state=x')).toEqual({
      kind: 'lost',
    })
    expect(fetched).not.toHaveBeenCalled()
  })

  it('reads a refusal on Spotify’s page as declined, and a second load of the page as lost', async () => {
    const { module, state } = await started()
    const fetched = spotify({})

    expect(
      await module.completeSpotifyConnect(`?error=access_denied&state=${state}`),
    ).toEqual({
      kind: 'declined',
    })
    expect(
      await module.completeSpotifyConnect(`?error=access_denied&state=${state}`),
    ).toEqual({
      kind: 'lost',
    })
    expect(fetched).not.toHaveBeenCalled()
  })

  it('reports a code Spotify would not exchange, and keeps no token', async () => {
    const { module, state } = await started()
    spotify({ token: () => new Response('', { status: 400 }) })

    expect(await module.completeSpotifyConnect(`?code=abc&state=${state}`)).toEqual({
      kind: 'failed',
    })
    expect(module.isSpotifyConnected()).toBe(false)
  })
})

describe('saveEpisodeToSpotify', () => {
  it('asks for a connection when this phone holds none, and sends nothing', async () => {
    const module = await load()
    const fetched = spotify({})

    expect(await module.saveEpisodeToSpotify(EPISODE.spotifyId)).toBe('needs_connect')
    expect(fetched).not.toHaveBeenCalled()
  })

  it('saves with the kept token and remembers it saved here', async () => {
    const module = await load()
    keepTokens(Date.now() + 3_600_000)
    const fetched = spotify({ library: [() => json({})] })

    expect(await module.saveEpisodeToSpotify(EPISODE.spotifyId)).toBe('saved')
    expect(fetched.mock.calls[0][1]?.headers).toEqual({
      Authorization: 'Bearer access-1',
    })
    expect(module.savedFromHere().has(EPISODE.spotifyId)).toBe(true)
  })

  it('refreshes a token about to expire before using it', async () => {
    const module = await load()
    keepTokens(Date.now() + 10_000)
    const fetched = spotify({
      token: () => json({ access_token: 'access-2', expires_in: 3600 }),
      library: [() => json({})],
    })

    expect(await module.saveEpisodeToSpotify(EPISODE.spotifyId)).toBe('saved')
    const refresh = new URLSearchParams(String(fetched.mock.calls[0][1]?.body))
    expect(refresh.get('grant_type')).toBe('refresh_token')
    expect(refresh.get('refresh_token')).toBe('refresh-1')
    expect(fetched.mock.calls[1][1]?.headers).toEqual({
      Authorization: 'Bearer access-2',
    })
    // Spotify handed back no new refresh token, so the old one is kept.
    expect(
      JSON.parse(localStorage.getItem('ourhike:spotify:tokens') ?? '{}').refreshToken,
    ).toBe('refresh-1')
  })

  it('refreshes once on a 401 and retries', async () => {
    const module = await load()
    keepTokens(Date.now() + 3_600_000)
    spotify({
      token: () => json({ access_token: 'access-2', expires_in: 3600 }),
      library: [() => new Response('', { status: 401 }), () => json({})],
    })

    expect(await module.saveEpisodeToSpotify(EPISODE.spotifyId)).toBe('saved')
  })

  it('forgets a connection Spotify will no longer refresh, and asks for Connect', async () => {
    const module = await load()
    keepTokens(Date.now() - 1)
    spotify({ token: () => new Response('', { status: 400 }) })

    expect(await module.saveEpisodeToSpotify(EPISODE.spotifyId)).toBe('needs_connect')
    expect(module.isSpotifyConnected()).toBe(false)
  })

  it('reads a 403 as an account Spotify has not approved', async () => {
    const module = await load()
    keepTokens(Date.now() + 3_600_000)
    spotify({ library: [() => new Response('', { status: 403 })] })

    expect(await module.saveEpisodeToSpotify(EPISODE.spotifyId)).toBe('not_approved')
    expect(module.savedFromHere().has(EPISODE.spotifyId)).toBe(false)
  })

  it('answers failed, never throws, when there is no signal', async () => {
    const module = await load()
    keepTokens(Date.now() + 3_600_000)
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))

    expect(await module.saveEpisodeToSpotify(EPISODE.spotifyId)).toBe('failed')
  })

  it('disconnects by forgetting the token on this phone', async () => {
    const module = await load()
    keepTokens(Date.now() + 3_600_000)

    module.disconnectSpotify()

    expect(module.isSpotifyConnected()).toBe(false)
  })
})
