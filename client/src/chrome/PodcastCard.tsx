// Podcast episodes picked for a hike, with Spotify's player and a one-tap
// save (#1683 - Offer podcast episodes picked for the hike, with a one-tap
// Spotify save and an in-app player).
//
// Drawn from the mock the maintainer chose on 2026-09-26 (frames 1-4 of the
// combined card): the last thing on the hike detail screen, and a card under
// "Today on your hike" when an episode's miles overlap the planned day.
//
// NOTHING CONTACTS SPOTIFY UNTIL A TAP (the maintainer's frame 1A). The card
// renders from the list this phone already holds; Spotify's player is an
// iframe that exists only after "Play here", and the save is a request made
// only by "Save to Spotify". So Spotify never learns which hikes a hiker
// opens, and with no signal the card still says what was picked.
//
// THE PHONE APPS GET LINKS (#1683's frame 2A). In a Capacitor shell each
// episode is ↓ and "Listen on <app>", with no player and no save: the Android shell's bridge is exposed
// to any frame the WebView holds (capacitor.config.ts, `useLegacyBridge`),
// and a sign-in redirect does not return into either shell today
// (features/AUTHENTICATION.md). A link goes through the system, which hands
// it to the app it names where one is installed.
//
// THE HIKER'S OWN PODCAST APP (#1690 - Let a hiker pick their podcast app
// once). Nothing tells a page which podcast player a phone uses, so the card
// asks: before a pick, Listen and ↓ open "Which app do you listen in?"
// (frame 1A), and afterwards each episode opens in that app. An episode
// nobody linked for that app still shows, with Spotify's button and a line
// saying so (2A). ▶ stays Spotify's player for everyone (3A). One-tap Save
// is Spotify's alone - no other app has an API to add an episode.
//
// ↓ OPENS THE EPISODE IN THAT APP, TO DOWNLOAD THERE (the maintainer's D1,
// 2026-09-26). No podcast app lets another app start its download, so the
// circle is one tap from the app's own download button, and the line under
// the list says so rather than letting the arrow promise more.
//
// A CONTROL THAT CANNOT DO ITS JOB IS NOT OFFERED (chrome/LineSheet.tsx's
// rule). No signal: no Play, no Save, one line saying why. A build with no
// Spotify client id: no Save, and the episode opens in Spotify instead.

import { Capacitor } from '@capacitor/core'
import { useState, type ReactNode } from 'react'
import {
  PODCAST_APP_NAMES,
  appsEveryEpisodeOpensIn,
  episodeUrlIn,
  formatMinutes,
  spotifyEmbedUrl,
  spotifyEpisodeUrl,
  type PodcastApp,
  type PodcastEpisode,
} from '../lib/podcasts'
import { usePodcastApp, writePodcastApp } from '../lib/podcastApp'
import { isSafeLink } from '../lib/safeLink'
import {
  SPOTIFY_CONFIGURED,
  beginSpotifyConnect,
  disconnectSpotify,
  isSpotifyConnected,
  saveEpisodeToSpotify,
  savedFromHere,
} from '../lib/spotify'
import { PodcastAppIcon } from './PodcastAppIcon'
import { PodcastAppPicker } from './PodcastAppPicker'
import './podcastCard.css'

type SaveState = 'idle' | 'saving' | 'saved' | 'not_approved' | 'failed'

export interface PodcastCardProps {
  episodes: readonly PodcastEpisode[]
  heading: string
  /** The small line above the heading, where the screen has no rule of its
   *  own to sit under (Today). */
  eyebrow?: string
  online: boolean
  /** Running inside a Capacitor shell. Read from Capacitor when absent;
   *  passed by tests. */
  native?: boolean
  /** Whether this build can save to Spotify at all. From lib/spotify.ts when
   *  absent; passed by tests. */
  spotifyConfigured?: boolean
  /** The apps the picker offers: appsEveryEpisodeOpensIn over the WHOLE
   *  published list, which App.tsx holds and this card does not. Absent, it
   *  is worked out from this card's own episodes, which is only right for a
   *  card rendered alone (tests): a subset of the list can cover an app the
   *  whole list does not. */
  offeredApps?: readonly PodcastApp[]
}

export function PodcastCard({
  episodes,
  heading,
  eyebrow,
  online,
  native = Capacitor.isNativePlatform(),
  spotifyConfigured = SPOTIFY_CONFIGURED,
  offeredApps,
}: PodcastCardProps) {
  const app = usePodcastApp()
  const [picking, setPicking] = useState(false)
  const [playing, setPlaying] = useState<ReadonlySet<string>>(() => new Set())
  const [saves, setSaves] = useState<Readonly<Record<string, SaveState>>>(() =>
    Object.fromEntries([...savedFromHere()].map((id) => [id, 'saved' as const])),
  )
  const [connected, setConnected] = useState(() => isSpotifyConnected())

  if (episodes.length === 0) return null

  // One-tap Save needs a browser (no redirect returns into the shells), a
  // Spotify app this build was given, and a hiker who listens in Spotify.
  const canSave = !native && spotifyConfigured && app === 'spotify'

  const save = async (episode: PodcastEpisode) => {
    if (!isSpotifyConnected()) {
      // Leaves the page for Spotify; spotify-callback.html saves this
      // episode on the way back and says whether it worked.
      await beginSpotifyConnect({ spotifyId: episode.spotifyId, title: episode.title })
      return
    }
    setSaves((current) => ({ ...current, [episode.spotifyId]: 'saving' }))
    const outcome = await saveEpisodeToSpotify(episode.spotifyId)
    if (outcome === 'needs_connect') {
      // The connection was refused or aged out: the tap still means "save
      // this", so it goes to Spotify to connect again rather than asking
      // for a second tap on a button that just failed.
      setConnected(false)
      await beginSpotifyConnect({ spotifyId: episode.spotifyId, title: episode.title })
      return
    }
    setSaves((current) => ({ ...current, [episode.spotifyId]: outcome }))
  }

  const lede = canSave
    ? 'Save them to Spotify and download them there before you lose signal.'
    : 'Download them in your podcast app before you lose signal.'

  return (
    <section className="podcast-card" aria-label={heading}>
      <div className="podcast-card__head">
        {eyebrow !== undefined && <p className="podcast-card__eyebrow">{eyebrow}</p>}
        <h3 className="podcast-card__heading">{heading}</h3>
        {!picking && <p className="podcast-card__lede">{lede}</p>}
      </div>

      {picking ? (
        // Frame 2: asked once, in the card that needed the answer. Picking
        // returns to the list with that app's buttons rather than opening
        // the episode unasked - the next tap is the hiker's.
        <div className="podcast-card__picker">
          <p className="podcast-card__picker-heading">Which app do you listen in?</p>
          <PodcastAppPicker
            apps={offeredApps ?? appsEveryEpisodeOpensIn(episodes)}
            value={app}
            onPick={(next) => {
              writePodcastApp(next)
              setPicking(false)
            }}
          />
          <p className="podcast-card__foot">
            Kept on this phone. Change it in More → Settings.
          </p>
        </div>
      ) : (
        <>
          {canSave && connected && (
            <p className="podcast-card__status">
              Spotify connected
              <button
                type="button"
                className="podcast-card__button"
                onClick={() => {
                  disconnectSpotify()
                  setConnected(false)
                }}
              >
                Disconnect
              </button>
            </p>
          )}

          <ul className="podcast-card__list">
            {episodes.map((episode) => (
              <EpisodeRow
                key={episode.spotifyId}
                episode={episode}
                app={app}
                online={online}
                native={native}
                canSave={canSave}
                playing={playing.has(episode.spotifyId)}
                save={saves[episode.spotifyId] ?? 'idle'}
                onPlay={() =>
                  setPlaying((current) => new Set(current).add(episode.spotifyId))
                }
                onSave={() => void save(episode)}
                onAsk={() => setPicking(true)}
              />
            ))}
          </ul>

          <p className="podcast-card__foot">
            {footLine(app, native, online, canSave, connected)}
          </p>
        </>
      )}
    </section>
  )
}

/**
 * The one line under the list, which is also the key to the icons: ▶ and ↓
 * are icons beside each title (the maintainer's pick, poll 2026-09-26), so
 * what they do is said once here instead of on every row - and ↓ in
 * particular says it opens the app, because an arrow alone would promise a
 * download OurHike cannot start.
 */
function footLine(
  app: PodcastApp | null,
  native: boolean,
  online: boolean,
  canSave: boolean,
  connected: boolean,
): string {
  const yours =
    app === null
      ? ''
      : ` Your app is ${PODCAST_APP_NAMES[app]}; change it in More → Settings.`
  if (native) {
    return app === null
      ? 'Listen or ↓ asks which podcast app you use, once. Playing and saving here work in OurHike in a browser.'
      : `↓ opens it in ${PODCAST_APP_NAMES[app]} to download it there.${yours}`
  }
  if (!online) return 'Playing and downloading need signal.'
  if (app === null)
    return '▶ plays it here. Listen or ↓ asks which podcast app you use, once.'
  if (canSave) {
    const save = connected
      ? 'Save puts it in your Spotify.'
      : 'Save puts it in your Spotify; the first time asks you to connect, once.'
    return `▶ plays it here. ↓ opens it in Spotify to download it there. ${save}${yours}`
  }
  return `▶ plays it here. ↓ opens it in ${PODCAST_APP_NAMES[app]} to download it there.${yours}`
}

/** The play triangle and the download arrow, drawn rather than typed: a
 *  typed ▶ is an emoji on iOS, and an emoji in a brand-coloured circle is a
 *  different button. */
function Glyph({ shape }: { shape: 'play' | 'down' }) {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">
      {shape === 'play' ? (
        <path d="M5 3.5v9l7.5-4.5z" fill="currentColor" />
      ) : (
        <path
          d="M8 2.5v8M4.5 7.5L8 11l3.5-3.5M3 13.5h10"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
    </svg>
  )
}

interface EpisodeRowProps {
  episode: PodcastEpisode
  app: PodcastApp | null
  online: boolean
  native: boolean
  canSave: boolean
  playing: boolean
  save: SaveState
  onPlay: () => void
  onSave: () => void
  onAsk: () => void
}

function EpisodeRow({
  episode,
  app,
  online,
  native,
  canSave,
  playing,
  save,
  onPlay,
  onSave,
  onAsk,
}: EpisodeRowProps) {
  const length = formatMinutes(episode.minutes)

  // Where this episode opens for this hiker: their app when somebody linked
  // it there, otherwise Spotify, which every episode is on (2A). Every href
  // here is from the published list and passes the same gate as every other
  // link the app fills from data (lib/safeLink.ts).
  const linked = app === null ? null : episodeUrlIn(episode, app)
  const opensIn: PodcastApp =
    linked !== null && isSafeLink(linked) ? (app ?? 'spotify') : 'spotify'
  const href = opensIn === 'spotify' ? spotifyEpisodeUrl(episode) : (linked as string)
  const name = PODCAST_APP_NAMES[opensIn]

  const play = !native && online && !playing && (
    <button
      type="button"
      className="podcast-card__icon"
      onClick={onPlay}
      aria-label={`Play “${episode.title}” here`}
      title="Play here"
    >
      <Glyph shape="play" />
    </button>
  )

  let actions: ReactNode = null
  if (native || online) {
    if (app === null) {
      // Frame 1A: nothing assumed; both doors ask first.
      actions = (
        <>
          {play}
          <button
            type="button"
            className="podcast-card__icon"
            onClick={onAsk}
            aria-label={`Download “${episode.title}” in your podcast app`}
            title="Download in your podcast app"
          >
            <Glyph shape="down" />
          </button>
          <button
            type="button"
            className="podcast-card__pill"
            onClick={onAsk}
            aria-label={`Listen to “${episode.title}” in your podcast app`}
          >
            <span>Listen</span>
          </button>
        </>
      )
    } else {
      actions = (
        <>
          {play}
          <a
            className="podcast-card__icon"
            href={href}
            target="_blank"
            rel="noreferrer"
            aria-label={`Download “${episode.title}” in ${name}`}
            title={`Download in ${name}`}
          >
            <Glyph shape="down" />
          </a>
          {canSave ? (
            save === 'saved' ? (
              <span
                className="podcast-card__pill podcast-card__pill--done"
                role="img"
                aria-label={`“${episode.title}” is saved to Spotify`}
              >
                <PodcastAppIcon app="spotify" />
                <span>Saved</span>
              </span>
            ) : save === 'not_approved' ? null : (
              <button
                type="button"
                className="podcast-card__pill"
                onClick={onSave}
                disabled={save === 'saving'}
                aria-label={`Save “${episode.title}” to Spotify`}
              >
                <PodcastAppIcon app="spotify" />
                <span>{save === 'saving' ? 'Saving…' : 'Save'}</span>
              </button>
            )
          ) : (
            // Each app's own wording: "Listen on Spotify" (Spotify's
            // guidelines), "on Apple Podcasts" (Apple's).
            <a
              className="podcast-card__pill"
              href={href}
              target="_blank"
              rel="noreferrer"
              aria-label={`Open “${episode.title}” in ${name}`}
            >
              <PodcastAppIcon app={opensIn} />
              <span>Listen on {name}</span>
            </a>
          )}
        </>
      )
    }
  }

  return (
    <li className="podcast-card__episode">
      <div className="podcast-card__row">
        <div className="podcast-card__meta">
          <p className="podcast-card__show">{episode.show}</p>
          <p className="podcast-card__title">{episode.title}</p>
          {length !== null && <p className="podcast-card__length">{length}</p>}
        </div>
        {actions !== null && <div className="podcast-card__actions">{actions}</div>}
      </div>

      {app !== null && opensIn !== app && (
        <p className="podcast-card__note">Not linked for {PODCAST_APP_NAMES[app]} yet.</p>
      )}

      {playing && (
        // Spotify's own player, framed only after a tap and only here - the
        // content security policy allows open.spotify.com in frame-src and
        // nothing else (client/scripts/csp.mjs).
        <iframe
          className="podcast-card__player"
          title={`Spotify player: ${episode.title}`}
          src={spotifyEmbedUrl(episode)}
          height={152}
          loading="lazy"
          allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
        />
      )}

      {save === 'not_approved' && (
        <p className="podcast-card__warning" role="status">
          Spotify hasn’t approved this account for OurHike.{' '}
          <a href={spotifyEpisodeUrl(episode)} target="_blank" rel="noreferrer">
            Open it in Spotify ↗
          </a>{' '}
          and tap + there.
        </p>
      )}
      {save === 'failed' && (
        <p className="podcast-card__warning" role="status">
          That didn’t reach Spotify. Try again when you have a steady signal.
        </p>
      )}
    </li>
  )
}
