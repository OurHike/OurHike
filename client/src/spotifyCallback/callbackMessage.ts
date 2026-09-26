// What the Spotify callback page says, for each way the round trip can end
// (#1683). Separate from the page's bootstrap so every sentence is tested;
// src/spotifyCallback/main.ts is only the DOM glue.
//
// EVERY ANSWER SAYS WHETHER ANYTHING WAS SAVED. That is the one question a
// hiker has on landing here, and a page that said "Connected!" over a save
// Spotify refused would be the display outrunning its source.

import type { ConnectOutcome } from '../lib/spotify'

export interface CallbackMessage {
  heading: string
  body: string
  /** The episode in Spotify, offered where saving from OurHike did not work
   *  - so the hiker can tap + there instead. */
  openInSpotify?: string
}

const episodeLink = (spotifyId: string) => `https://open.spotify.com/episode/${spotifyId}`

export function callbackMessage(outcome: ConnectOutcome): CallbackMessage {
  switch (outcome.kind) {
    case 'declined':
      return {
        heading: 'Spotify isn’t connected',
        body: 'Nothing was saved. Connecting is only needed for the Save button; the episodes still play in OurHike.',
      }
    case 'lost':
      return {
        heading: 'This link has already been used',
        body: 'Nothing was saved from it. Tap Save on the episode again to connect Spotify.',
      }
    case 'failed':
      return {
        heading: 'Spotify couldn’t be connected',
        body: 'Nothing was saved. Try Save on the episode again when you have a steady signal.',
      }
    case 'connected':
      switch (outcome.saved) {
        case 'saved':
          return {
            heading: 'Saved to your Spotify',
            body: `“${outcome.episode.title}” is in Your Library, under Your Episodes. Download it there before you lose signal. Spotify stays connected on this phone, so the next Save is one tap.`,
          }
        case 'not_approved':
          return {
            heading: 'Spotify hasn’t approved this account for OurHike',
            body: `Spotify only lets a few accounts save from OurHike, and this isn’t one of them, so “${outcome.episode.title}” was not saved. Open it in Spotify and tap + there.`,
            openInSpotify: episodeLink(outcome.episode.spotifyId),
          }
        case 'needs_connect':
        case 'failed':
          return {
            heading: 'Spotify is connected, but the episode wasn’t saved',
            body: `“${outcome.episode.title}” didn’t reach your library. Tap Save on it again, or open it in Spotify and tap + there.`,
            openInSpotify: episodeLink(outcome.episode.spotifyId),
          }
      }
  }
}
