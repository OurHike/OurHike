// Podcast episodes picked for a hike (#1683 - Offer podcast episodes picked
// for the hike, with a one-tap Spotify save and an in-app player).
//
// WHAT THIS READS. `podcasts/episodes.json`, written by
// pipeline/export_podcasts.py from the reviewed
// pipeline/reference/podcast_episodes.json. Every row is somebody's editorial
// call; nothing here searches Spotify or ranks anything.
//
// AT THE BUCKET ROOT, NOT IN THE PINNED RELEASE (lib/dataRelease.ts's
// ROOT_SCOPED_PREFIXES). The maintainer chose a live list, 2026-09-26: a new
// episode reaches this phone on its next fetch, with no app release and no
// DATA_RELEASE bump. So the document can change under a running build, which
// is why the parse below takes nothing on trust.
//
// NO POSITION LEAVES THE PHONE. The whole list is fetched and matched here,
// against a hike id or the miles of the day a hiker planned. Spotify hears
// about an episode only when the hiker taps it (chrome/PodcastCard.tsx).
//
// NEVER FATAL, lib/mapSheets.ts's posture through the same cache: an
// unreachable bucket, a 404 from an environment nobody has published to, or
// a document this build cannot read all yield the kept copy or nothing, and
// nothing is what every screen rendered before this existed.

import { DATA_CONFIGURED, dataUrl } from './config'
import { recallPublished, rememberPublished } from './conditionsCache'

/** The key pipeline/export_podcasts.py writes. Must match exactly:
 *  pipeline/tests/test_published_key_contract.py holds the two spellings
 *  together, as it does for every other key the app fetches. */
export const PODCAST_EPISODES_KEY = 'podcasts/episodes.json'

/**
 * The podcast apps a hiker can pick (#1690 - Let a hiker pick their podcast
 * app once). The order is the picker's. Spotify first because every episode
 * is on it: the reference file requires a Spotify id, which the ▶ player and
 * the one-tap save both need, so Spotify is also the app an episode falls
 * back to when it has no link for the hiker's own.
 *
 * WHY THE APP ASKS RATHER THAN DETECTS. Nothing on a phone tells a web page
 * or an app which podcast player its owner uses: iPhone has no default
 * podcast app setting (Apple's list of changeable defaults names none, read
 * 2026-09-26), Android's old default, Google Podcasts, is shut down, and
 * browsers hide which apps are installed on purpose.
 */
export const PODCAST_APPS = [
  'spotify',
  'apple_podcasts',
  'pocket_casts',
  'overcast',
  'youtube_music',
] as const

export type PodcastApp = (typeof PODCAST_APPS)[number]

/** Each app's name as the app itself spells it. Buttons read "Listen on
 *  <name>": Apple's identity guidelines ask for "on Apple Podcasts", and
 *  Spotify's for "Listen on Spotify" (both read 2026-09-26). */
export const PODCAST_APP_NAMES: Readonly<Record<PodcastApp, string>> = {
  spotify: 'Spotify',
  apple_podcasts: 'Apple Podcasts',
  pocket_casts: 'Pocket Casts',
  overcast: 'Overcast',
  youtube_music: 'YouTube Music',
}

/** The hosts each app's own share link uses - the same table as
 *  pipeline/lib/podcasts.py's APP_LINK_HOSTS, checked again here because a
 *  phone opens these. Spotify's link is built from the id, never read. */
const APP_LINK_HOSTS: Readonly<
  Record<Exclude<PodcastApp, 'spotify'>, readonly string[]>
> = {
  apple_podcasts: ['podcasts.apple.com'],
  pocket_casts: ['pca.st', 'pocketcasts.com', 'play.pocketcasts.com'],
  overcast: ['overcast.fm'],
  youtube_music: ['music.youtube.com'],
}

export interface PodcastEpisode {
  /** Spotify's 22-character episode id - the tail of its open.spotify.com
   *  link. */
  readonly spotifyId: string
  readonly title: string
  readonly show: string
  /** Whole minutes, or undefined where nobody gave a length. Undefined
   *  prints no length - never a zero. */
  readonly minutes?: number
  /** Suggested-hike ids (lib/suggestedHikes.ts's `SuggestedHike.id`) the
   *  hike detail screen shows it on. */
  readonly hikes: readonly string[]
  /** A.T. mile ranges, [low, high], counted from Springer. Typed by hand from
   *  a guidebook (the reference file's README says so), so loose by a mile or
   *  two against this phone's own axis - which an overlap test absorbs and a
   *  podcast can afford. */
  readonly atMiles: readonly (readonly [number, number])[]
  /** Published POI ids the episode talks about (#1718), each checked against
   *  the POI ledger by the pipeline. The episode shows under "Listen here",
   *  last on each of those places' cards. */
  readonly pois: readonly string[]
  /** The episode's own link in each other app that has one (#1690). An app
   *  missing here is an app nobody has linked it for yet. */
  readonly links: Readonly<Partial<Record<Exclude<PodcastApp, 'spotify'>, string>>>
}

export const NO_PODCAST_EPISODES: readonly PodcastEpisode[] = []

/** The same rule pipeline/lib/podcasts.py enforces, checked again here
 *  because the id is spliced into a URL this phone loads in a frame and a
 *  URI it sends to Spotify. A document that went through the pipeline always
 *  passes; this is for the one that did not. */
const SPOTIFY_ID = /^[0-9A-Za-z]{22}$/

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value.trim() : null
}

function milesPair(value: unknown): readonly [number, number] | null {
  if (!Array.isArray(value) || value.length !== 2) return null
  const [low, high] = value as unknown[]
  if (typeof low !== 'number' || typeof high !== 'number') return null
  if (!Number.isFinite(low) || !Number.isFinite(high) || low < 0 || high <= low)
    return null
  return [low, high]
}

/** One published row, or null. Junk costs the row, never the list. */
/** The other apps' links that are https on the app's own host; the rest are
 *  dropped one by one, never the episode. */
function parseLinks(value: unknown): PodcastEpisode['links'] {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return {}
  const links: Partial<Record<Exclude<PodcastApp, 'spotify'>, string>> = {}
  for (const [app, hosts] of Object.entries(APP_LINK_HOSTS) as [
    Exclude<PodcastApp, 'spotify'>,
    readonly string[],
  ][]) {
    const url = (value as Record<string, unknown>)[app]
    if (typeof url !== 'string') continue
    try {
      const parsed = new URL(url)
      if (parsed.protocol === 'https:' && hosts.includes(parsed.hostname))
        links[app] = url
    } catch {
      /* not a URL: this app has no link for the episode */
    }
  }
  return links
}

function parseEpisode(value: unknown): PodcastEpisode | null {
  if (typeof value !== 'object' || value === null) return null
  const record = value as Record<string, unknown>
  const spotifyId = typeof record.spotify_id === 'string' ? record.spotify_id : ''
  const title = text(record.title)
  const show = text(record.show)
  if (!SPOTIFY_ID.test(spotifyId) || title === null || show === null) return null

  const hikes = Array.isArray(record.hikes)
    ? record.hikes.map(text).filter((id): id is string => id !== null)
    : []
  const atMiles = Array.isArray(record.at_miles)
    ? record.at_miles.map(milesPair).filter((pair) => pair !== null)
    : []
  const pois = Array.isArray(record.pois)
    ? record.pois.map(text).filter((id): id is string => id !== null)
    : []
  // An episode anchored to nothing would show nowhere; keeping it would only
  // make a count somewhere disagree with what a hiker can find.
  if (hikes.length === 0 && atMiles.length === 0 && pois.length === 0) return null

  const minutes =
    typeof record.minutes === 'number' &&
    Number.isInteger(record.minutes) &&
    record.minutes > 0
      ? record.minutes
      : undefined
  return {
    links: parseLinks(record.links),
    spotifyId,
    title,
    show,
    hikes,
    atMiles,
    pois,
    ...(minutes === undefined ? {} : { minutes }),
  }
}

/** The published document's episodes, or null when it is not the shape this
 *  build reads at all. An empty list is a real answer: nobody has picked any. */
export function parsePodcastEpisodes(document: unknown): PodcastEpisode[] | null {
  if (typeof document !== 'object' || document === null) return null
  const episodes = (document as Record<string, unknown>).episodes
  if (!Array.isArray(episodes)) return null
  const seen = new Set<string>()
  const parsed: PodcastEpisode[] = []
  for (const value of episodes) {
    const episode = parseEpisode(value)
    if (episode === null || seen.has(episode.spotifyId)) continue
    seen.add(episode.spotifyId)
    parsed.push(episode)
  }
  return parsed
}

/** The episodes picked for one suggested hike, in the list's own order. */
export function episodesForHike(
  episodes: readonly PodcastEpisode[],
  hikeId: string,
): readonly PodcastEpisode[] {
  const found = episodes.filter((episode) => episode.hikes.includes(hikeId))
  return found.length === 0 ? NO_PODCAST_EPISODES : found
}

/** The episodes tagged to one place (#1718), in the list's own order. Exact
 *  ids only: an episode tagged to a site's summit is not offered on its
 *  privy, because the tag is somebody's call about that one point. */
export function episodesForPoi(
  episodes: readonly PodcastEpisode[],
  poiId: string,
): readonly PodcastEpisode[] {
  const found = episodes.filter((episode) => episode.pois.includes(poiId))
  return found.length === 0 ? NO_PODCAST_EPISODES : found
}

/**
 * The episodes whose A.T. range overlaps the stretch [low, high].
 *
 * Overlap rather than containment: a day from mi 486 to 497 inside an
 * episode picked for mi 480-512 is the case this exists for, and so is a day
 * that only clips its end. Touching ends count - a range that stops at the
 * shelter a day starts from is about the ground either side of it.
 */
export function episodesForMiles(
  episodes: readonly PodcastEpisode[],
  low: number,
  high: number,
): readonly PodcastEpisode[] {
  const found = episodes.filter((episode) =>
    episode.atMiles.some(([start, end]) => start <= high && end >= low),
  )
  return found.length === 0 ? NO_PODCAST_EPISODES : found
}

/** Where the episode opens in Spotify - its app, where one is installed and
 *  the link is handed to the system, or the web player. */
export function spotifyEpisodeUrl(episode: PodcastEpisode): string {
  return `https://open.spotify.com/episode/${episode.spotifyId}`
}

/** The episode in `app`, or null when nobody has linked it for that app. */
export function episodeUrlIn(episode: PodcastEpisode, app: PodcastApp): string | null {
  return app === 'spotify' ? spotifyEpisodeUrl(episode) : (episode.links[app] ?? null)
}

/**
 * The apps a hiker is offered to pick from: Spotify, which every episode has,
 * and each other app only once every episode on `list` carries its link. The
 * maintainer's rule (poll, 2026-09-29, frame Q1): "If we only support
 * Spotify, then we shouldn't have the other apps listed." An app joins by
 * itself when the list covers it - no app release - and drops out when an
 * episode without its link is added.
 *
 * Pass the WHOLE published list, not one hike's share of it: an app offered
 * on one card and missing from the next would make the pick depend on which
 * hike the hiker opened first. An empty list offers Spotify alone - "every
 * episode" of none is true of every app and says nothing.
 */
export function appsEveryEpisodeOpensIn(
  list: readonly PodcastEpisode[],
): readonly PodcastApp[] {
  return PODCAST_APPS.filter(
    (app) =>
      app === 'spotify' ||
      (list.length > 0 && list.every((episode) => episodeUrlIn(episode, app) !== null)),
  )
}

/**
 * The apps a picker lists: those on offer, plus the hiker's own pick if it
 * has since dropped out (an episode without its link was added). A pick that
 * vanished from the list would leave the hiker unable to see what they chose,
 * while the card still opens episodes in it where it can; shown, it stays
 * theirs to change. In PODCAST_APPS order either way, so the list never
 * reshuffles.
 */
export function podcastAppsToList(
  apps: readonly PodcastApp[],
  value: PodcastApp | null,
): readonly PodcastApp[] {
  return PODCAST_APPS.filter((app) => apps.includes(app) || app === value)
}

/** Spotify's own embedded player for the episode (chrome/PodcastCard.tsx
 *  loads it only once a hiker taps Play). */
export function spotifyEmbedUrl(episode: PodcastEpisode): string {
  return `https://open.spotify.com/embed/episode/${episode.spotifyId}`
}

/** `48 min`, `1 h 12 min`, or null where nobody gave a length. */
export function formatMinutes(minutes: number | undefined): string | null {
  if (minutes === undefined) return null
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`
}

/**
 * The list, from the bucket when there is signal and from the copy this
 * phone kept when there is not.
 *
 * A 404 is ordinary - an environment nobody has published a list to - and
 * falls back to the kept copy rather than clearing it: a bucket that stopped
 * serving the object is not evidence the episodes were withdrawn.
 */
export async function fetchPodcastEpisodes(
  online: boolean,
  signal?: AbortSignal,
): Promise<PodcastEpisode[] | null> {
  // The kept copy first and unconditionally, like useSuggestedHikes' recall:
  // a copy this phone holds is an answer whether or not this build could
  // fetch a fresh one.
  if (!online) return recalled()
  if (!DATA_CONFIGURED) return null
  try {
    const response = await fetch(dataUrl(PODCAST_EPISODES_KEY), { signal })
    if (!response.ok) return recalled()
    const document: unknown = await response.json()
    const parsed = parsePodcastEpisodes(document)
    // Kept only when it parsed, so a shape this build refuses never
    // overwrites the last one it could read.
    if (parsed !== null)
      void rememberPublished(PODCAST_EPISODES_KEY, document as Record<string, unknown>)
    return parsed ?? (await recalled())
  } catch {
    return recalled()
  }
}

async function recalled(): Promise<PodcastEpisode[] | null> {
  const cached = await recallPublished(PODCAST_EPISODES_KEY)
  if (cached === null) return null
  return parsePodcastEpisodes(cached.document)
}
