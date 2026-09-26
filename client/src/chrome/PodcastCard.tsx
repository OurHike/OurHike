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
// THE PHONE APPS GET A LINK (frame 2A). In a Capacitor shell each episode is
// "Open in Spotify ↗" and nothing else: the Android shell's bridge is exposed
// to any frame the WebView holds (capacitor.config.ts, `useLegacyBridge`),
// and a sign-in redirect does not return into either shell today
// (features/AUTHENTICATION.md). The link goes through the system, which
// hands open.spotify.com to the Spotify app where one is installed.
//
// A CONTROL THAT CANNOT DO ITS JOB IS NOT OFFERED (chrome/LineSheet.tsx's
// rule). No signal: no Play, no Save, one line saying why. A build with no
// Spotify client id: no Save, and the episode opens in Spotify instead.

import { Capacitor } from '@capacitor/core'
import { useState } from 'react'
import {
  formatMinutes,
  spotifyEmbedUrl,
  spotifyEpisodeUrl,
  type PodcastEpisode,
} from '../lib/podcasts'
import {
  SPOTIFY_CONFIGURED,
  beginSpotifyConnect,
  disconnectSpotify,
  isSpotifyConnected,
  saveEpisodeToSpotify,
  savedFromHere,
} from '../lib/spotify'
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
}

export function PodcastCard({
  episodes,
  heading,
  eyebrow,
  online,
  native = Capacitor.isNativePlatform(),
  spotifyConfigured = SPOTIFY_CONFIGURED,
}: PodcastCardProps) {
  const [playing, setPlaying] = useState<ReadonlySet<string>>(() => new Set())
  const [saves, setSaves] = useState<Readonly<Record<string, SaveState>>>(() =>
    Object.fromEntries([...savedFromHere()].map((id) => [id, 'saved' as const])),
  )
  const [connected, setConnected] = useState(() => isSpotifyConnected())

  if (episodes.length === 0) return null

  const canSave = !native && spotifyConfigured

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

  const lede = native
    ? 'Download them in Spotify before you lose signal.'
    : canSave
      ? 'Save them to Spotify and download them there before you lose signal.'
      : null

  return (
    <section className="podcast-card" aria-label={heading}>
      <div className="podcast-card__head">
        {eyebrow !== undefined && <p className="podcast-card__eyebrow">{eyebrow}</p>}
        <h3 className="podcast-card__heading">{heading}</h3>
        {lede !== null && <p className="podcast-card__lede">{lede}</p>}
      </div>

      {canSave && connected && (
        <p className="podcast-card__status">
          Spotify connected
          <button
            type="button"
            className="podcast-card__button podcast-card__button--quiet"
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
            online={online}
            native={native}
            canSave={canSave}
            playing={playing.has(episode.spotifyId)}
            save={saves[episode.spotifyId] ?? 'idle'}
            onPlay={() =>
              setPlaying((current) => new Set(current).add(episode.spotifyId))
            }
            onSave={() => void save(episode)}
          />
        ))}
      </ul>

      {native ? (
        <p className="podcast-card__foot">
          Playing and saving here work in OurHike in a browser.
        </p>
      ) : !online ? (
        <p className="podcast-card__foot">Playing and saving need signal.</p>
      ) : (
        canSave &&
        !connected && (
          <p className="podcast-card__foot">
            The first Save asks you to connect Spotify, once.
          </p>
        )
      )}
    </section>
  )
}

interface EpisodeRowProps {
  episode: PodcastEpisode
  online: boolean
  native: boolean
  canSave: boolean
  playing: boolean
  save: SaveState
  onPlay: () => void
  onSave: () => void
}

function EpisodeRow({
  episode,
  online,
  native,
  canSave,
  playing,
  save,
  onPlay,
  onSave,
}: EpisodeRowProps) {
  const length = formatMinutes(episode.minutes)
  const openLink = (
    <a
      className="podcast-card__button"
      href={spotifyEpisodeUrl(episode)}
      target="_blank"
      rel="noreferrer"
      aria-label={`Open “${episode.title}” in Spotify`}
    >
      Open in Spotify ↗
    </a>
  )

  return (
    <li className="podcast-card__episode">
      <p className="podcast-card__show">{episode.show}</p>
      <p className="podcast-card__title">{episode.title}</p>
      {length !== null && <p className="podcast-card__length">{length}</p>}

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

      {native ? (
        <div className="podcast-card__actions">{openLink}</div>
      ) : online ? (
        <div className="podcast-card__actions">
          {!playing && (
            <button
              type="button"
              className="podcast-card__button"
              onClick={onPlay}
              aria-label={`Play “${episode.title}” here`}
            >
              ▶ Play here
            </button>
          )}
          {!canSave ? (
            openLink
          ) : save === 'saved' ? (
            <span className="podcast-card__button podcast-card__button--done">
              ✓ Saved
            </span>
          ) : save === 'not_approved' ? null : (
            <button
              type="button"
              className="podcast-card__button podcast-card__button--solid"
              onClick={onSave}
              disabled={save === 'saving'}
              aria-label={`Save “${episode.title}” to Spotify`}
            >
              {save === 'saving' ? 'Saving…' : '+ Save to Spotify'}
            </button>
          )}
        </div>
      ) : null}

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
