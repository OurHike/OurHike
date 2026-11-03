// A hiker's own Spotify, for saving an episode to it (#1683 - Offer podcast
// episodes picked for the hike, with a one-tap Spotify save and an in-app
// player).
//
// WHAT THIS CAN DO, AND FOR WHOM. One thing: put an episode in the hiker's
// Spotify library ("Your Episodes"), through Spotify's Web API
// `PUT /v1/me/library?uris=spotify:episode:<id>` with the one scope that
// needs, `user-library-modify` (Spotify's reference page for "Save Items to
// Library", read 2026-09-26). Nothing is read from the hiker's account.
//
// It works for FIVE SPOTIFY ACCOUNTS AT MOST, and that is Spotify's rule,
// not this app's. Since 2026-03-09 an app in Spotify's Development Mode
// serves up to five users its owner has added by hand, and the owner must
// have Premium; lifting that needs Spotify's "extended quota", which it
// grants only to a registered organization with at least 250,000 monthly
// users (Spotify's quota-modes page, read 2026-09-26). Everyone else gets a
// 403 from the save and is sent to the episode in Spotify instead
// (chrome/PodcastCard.tsx, `not_approved`).
//
// PKCE, SO NO SECRET AND NO BACKEND. Spotify's authorization-code flow with
// a code verifier is its documented flow for a client that cannot keep a
// secret, which a web page cannot. The client id is public by design and
// arrives as VITE_SPOTIFY_CLIENT_ID; unset, SPOTIFY_CONFIGURED is false and
// no Save button is drawn - a control that cannot do its job is not offered
// (chrome/LineSheet.tsx's rule).
//
// THE REDIRECT LANDS ON ITS OWN PAGE, spotify-callback.html, never on the
// app. The app's own sign-in reads `?error=` on its returned-to URL
// (lib/authRefusal.ts) and supabase-js watches the URL for a `code`
// (lib/supabase.ts, detectSessionInUrl), so Spotify's `?code=` or
// `?error=access_denied` arriving at the app root would be read as a
// half-finished OurHike sign-in. src/spotifyCallback/main.ts finishes the
// round trip there and links back.
//
// WEB ONLY. The Capacitor shells get a link instead (chrome/PodcastCard.tsx):
// a redirect does not return into them today (features/AUTHENTICATION.md),
// and the maintainer chose that split (poll, 2026-09-26, on #1683).
//
// WHERE THE TOKENS LIVE. localStorage, on this device, and nowhere else -
// no OurHike server sees them. What they can do if read is the scope above:
// add or remove items in the hiker's Spotify library. "Disconnect" forgets
// them here; Spotify has no endpoint to revoke a PKCE token, so the hiker's
// own spotify.com account page is where access is withdrawn for good.

const CLIENT_ID: string = (import.meta.env.VITE_SPOTIFY_CLIENT_ID ?? '').trim()

/** Whether this build was given a Spotify client id at all. */
export const SPOTIFY_CONFIGURED = CLIENT_ID !== ''

const AUTHORIZE_URL = 'https://accounts.spotify.com/authorize'
const TOKEN_URL = 'https://accounts.spotify.com/api/token'
const LIBRARY_URL = 'https://api.spotify.com/v1/me/library'
const SCOPE = 'user-library-modify'

const TOKENS_KEY = 'ourhike:spotify:tokens'
const PENDING_KEY = 'ourhike:spotify:pending'
const SAVED_KEY = 'ourhike:spotify:saved'

/** A token this close to expiry is refreshed before use rather than sent to
 *  fail. Reasoned, not measured: a minute covers a slow request on a bad
 *  connection, and refreshing early costs one extra call at most. */
const EXPIRY_MARGIN_MS = 60_000

/** The name of the page Spotify sends the hiker back to. It has to be
 *  registered, character for character, as a redirect URI on the Spotify
 *  app - once per origin this build is served from. */
export const CALLBACK_PAGE = 'spotify-callback.html'

interface Tokens {
  accessToken: string
  refreshToken: string | null
  /** Epoch milliseconds. */
  expiresAt: number
}

/** What the round trip was started for, kept across it. */
interface Pending {
  state: string
  verifier: string
  episode: { spotifyId: string; title: string }
}

/**
 * - `saved` - in the hiker's library now.
 * - `needs_connect` - no usable token; the next step is Connect.
 * - `not_approved` - Spotify refused this account (403). Reasoned from
 *   Spotify's quota-modes page ("API requests with an access token
 *   associated to that user and app will receive a 403") rather than seen:
 *   the one other cause of a 403 here would be a missing scope, and the
 *   scope is always asked for.
 * - `failed` - anything else, including no signal.
 */
export type SaveOutcome = 'saved' | 'needs_connect' | 'not_approved' | 'failed'

function read<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? null : (JSON.parse(raw) as T)
  } catch {
    return null
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Storage full or refused: the save still happened, only the memory of
    // it on this phone is lost - the card offers Save again, which is
    // harmless (saving a saved episode is a no-op on Spotify's side).
  }
}

function forget(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    /* nothing to forget */
  }
}

function tokensFrom(body: unknown, previousRefresh: string | null): Tokens | null {
  if (typeof body !== 'object' || body === null) return null
  const record = body as Record<string, unknown>
  if (typeof record.access_token !== 'string' || typeof record.expires_in !== 'number')
    return null
  return {
    accessToken: record.access_token,
    // A refresh may or may not hand back a new refresh token; when it does
    // not, the old one is still the one to use.
    refreshToken:
      typeof record.refresh_token === 'string' ? record.refresh_token : previousRefresh,
    expiresAt: Date.now() + record.expires_in * 1000,
  }
}

/** Whether this phone holds a Spotify connection. */
export function isSpotifyConnected(): boolean {
  return read<Tokens>(TOKENS_KEY) !== null
}

/** Forget the connection on this phone. */
export function disconnectSpotify(): void {
  forget(TOKENS_KEY)
}

/** Episodes saved from this phone, so a card can say "Saved" after a
 *  reload. Only ever a claim about what THIS phone did - an episode saved in
 *  Spotify's own app is not known here and reads as not saved. */
export function savedFromHere(): ReadonlySet<string> {
  const ids = read<unknown>(SAVED_KEY)
  return new Set(
    Array.isArray(ids) ? ids.filter((id): id is string => typeof id === 'string') : [],
  )
}

function rememberSaved(spotifyId: string): void {
  const ids = savedFromHere()
  if (!ids.has(spotifyId)) write(SAVED_KEY, [...ids, spotifyId])
}

/** Where Spotify returns to: the callback page beside the app. */
export function redirectUri(origin: string = window.location.origin): string {
  return new URL(`${import.meta.env.BASE_URL}${CALLBACK_PAGE}`, origin).toString()
}

const VERIFIER_ALPHABET =
  'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'

/** RFC 7636's verifier: 43-128 characters from the unreserved set. 64. */
export function randomVerifier(length = 64): string {
  const bytes = crypto.getRandomValues(new Uint8Array(length))
  return Array.from(
    bytes,
    (byte) => VERIFIER_ALPHABET[byte % VERIFIER_ALPHABET.length],
  ).join('')
}

/** RFC 7636's S256 challenge: base64url(sha256(verifier)), unpadded. */
export async function challengeFor(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
  let binary = ''
  for (const byte of new Uint8Array(digest)) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/**
 * Leave for Spotify to connect, remembering which episode to save on the
 * way back. The page is left; nothing after this runs.
 *
 * @param go How to leave - `location.assign` in the app, a spy in a test.
 */
export async function beginSpotifyConnect(
  episode: { spotifyId: string; title: string },
  go: (url: string) => void = (url) => window.location.assign(url),
): Promise<void> {
  const verifier = randomVerifier()
  const state = randomVerifier(32)
  write(PENDING_KEY, { state, verifier, episode } satisfies Pending)
  const url = new URL(AUTHORIZE_URL)
  url.search = new URLSearchParams({
    response_type: 'code',
    client_id: CLIENT_ID,
    scope: SCOPE,
    redirect_uri: redirectUri(),
    state,
    code_challenge_method: 'S256',
    code_challenge: await challengeFor(verifier),
  }).toString()
  go(url.toString())
}

async function tokenRequest(
  params: Record<string, string>,
  previousRefresh: string | null,
): Promise<Tokens | null> {
  try {
    const response = await fetch(TOKEN_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ client_id: CLIENT_ID, ...params }).toString(),
    })
    if (!response.ok) return null
    return tokensFrom(await response.json(), previousRefresh)
  } catch {
    return null
  }
}

/** A token good for the next request, refreshing it first when it is about
 *  to expire; null when there is none, or the refresh was refused. */
async function usableToken(): Promise<Tokens | null> {
  const tokens = read<Tokens>(TOKENS_KEY)
  if (tokens === null) return null
  if (tokens.expiresAt - EXPIRY_MARGIN_MS > Date.now()) return tokens
  return refreshed(tokens)
}

async function refreshed(tokens: Tokens): Promise<Tokens | null> {
  if (tokens.refreshToken === null) {
    forget(TOKENS_KEY)
    return null
  }
  const next = await tokenRequest(
    { grant_type: 'refresh_token', refresh_token: tokens.refreshToken },
    tokens.refreshToken,
  )
  if (next === null) {
    // A refused refresh means the hiker withdrew access or the token aged
    // out. Keeping it would make every later Save fail the same way; the
    // honest next step is Connect again.
    forget(TOKENS_KEY)
    return null
  }
  write(TOKENS_KEY, next)
  return next
}

async function putInLibrary(spotifyId: string, token: string): Promise<number> {
  const url = new URL(LIBRARY_URL)
  url.searchParams.set('uris', `spotify:episode:${spotifyId}`)
  const response = await fetch(url.toString(), {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.status
}

/** Save one episode to the hiker's Spotify library. Never throws. */
export async function saveEpisodeToSpotify(spotifyId: string): Promise<SaveOutcome> {
  try {
    let tokens = await usableToken()
    if (tokens === null) return 'needs_connect'
    let status = await putInLibrary(spotifyId, tokens.accessToken)
    if (status === 401) {
      // Expired early, or revoked: one refresh, one retry, then Connect.
      tokens = await refreshed(tokens)
      if (tokens === null) return 'needs_connect'
      status = await putInLibrary(spotifyId, tokens.accessToken)
      if (status === 401) {
        forget(TOKENS_KEY)
        return 'needs_connect'
      }
    }
    if (status >= 200 && status < 300) {
      rememberSaved(spotifyId)
      return 'saved'
    }
    return status === 403 ? 'not_approved' : 'failed'
  } catch {
    return 'failed'
  }
}

/**
 * What the callback page reports.
 *
 * - `declined` - the hiker said no on Spotify's page, or Spotify refused.
 * - `lost` - no round trip this phone started, or its `state` does not match
 *   the one sent: a stale or forged link, and nothing is exchanged.
 * - `failed` - the code could not be exchanged for a token.
 * - `connected` - a token is kept, and `saved` says what became of the
 *   episode the round trip was for.
 */
export type ConnectOutcome =
  | { kind: 'declined' | 'lost' | 'failed' }
  | {
      kind: 'connected'
      episode: { spotifyId: string; title: string }
      saved: SaveOutcome
    }

/** Finish the round trip Spotify just returned from. `search` is the
 *  callback page's `location.search`. */
export async function completeSpotifyConnect(search: string): Promise<ConnectOutcome> {
  const params = new URLSearchParams(search)
  const pending = read<Pending>(PENDING_KEY)
  // Read once and dropped at once: a verifier is good for one exchange, and
  // a reload of this page must not try a second.
  forget(PENDING_KEY)
  if (pending === null || params.get('state') !== pending.state) return { kind: 'lost' }
  const code = params.get('code')
  if (params.get('error') !== null || code === null) return { kind: 'declined' }

  const tokens = await tokenRequest(
    {
      grant_type: 'authorization_code',
      code,
      redirect_uri: redirectUri(),
      code_verifier: pending.verifier,
    },
    null,
  )
  if (tokens === null) return { kind: 'failed' }
  write(TOKENS_KEY, tokens)
  return {
    kind: 'connected',
    episode: pending.episode,
    saved: await saveEpisodeToSpotify(pending.episode.spotifyId),
  }
}
