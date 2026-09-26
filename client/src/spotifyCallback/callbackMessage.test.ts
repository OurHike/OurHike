import { describe, expect, it } from 'vitest'
import { callbackMessage } from './callbackMessage'

// What the page Spotify returns to says (#1683). The rule under test: every
// answer says whether the episode was saved, and offers the episode in
// Spotify wherever saving from OurHike did not work.

const EPISODE = { spotifyId: '0aBcDeFgHiJkLmNoPqRsTu', title: 'The park’s history' }

describe('callbackMessage', () => {
  it('names the episode and where it went when the save worked', () => {
    const message = callbackMessage({
      kind: 'connected',
      episode: EPISODE,
      saved: 'saved',
    })
    expect(message.heading).toBe('Saved to your Spotify')
    expect(message.body).toContain(
      '“The park’s history” is in Your Library, under Your Episodes',
    )
    expect(message.openInSpotify).toBeUndefined()
  })

  it('says plainly when Spotify has not approved the account, and offers the episode in Spotify', () => {
    const message = callbackMessage({
      kind: 'connected',
      episode: EPISODE,
      saved: 'not_approved',
    })
    expect(message.heading).toBe('Spotify hasn’t approved this account for OurHike')
    expect(message.body).toContain('was not saved')
    expect(message.openInSpotify).toBe(
      `https://open.spotify.com/episode/${EPISODE.spotifyId}`,
    )
  })

  it.each(['failed', 'needs_connect'] as const)(
    'never reads as saved when the save came back %s after connecting',
    (saved) => {
      const message = callbackMessage({ kind: 'connected', episode: EPISODE, saved })
      expect(message.heading).toContain('wasn’t saved')
      expect(message.openInSpotify).toBeDefined()
    },
  )

  it.each(['declined', 'lost', 'failed'] as const)(
    'says nothing was saved when the round trip ended %s',
    (kind) => {
      expect(callbackMessage({ kind }).body).toContain('Nothing was saved')
    },
  )
})
