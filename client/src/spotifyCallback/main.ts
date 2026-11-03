// The Spotify callback page's bootstrap (#1683): DOM glue only, excluded from
// coverage the way src/viewer/main.ts is - the round trip is
// lib/spotify.ts's completeSpotifyConnect and the words are
// callbackMessage.ts, both tested.

import { completeSpotifyConnect } from '../lib/spotify'
import { callbackMessage } from './callbackMessage'

const heading = document.getElementById('callback-heading')
const body = document.getElementById('callback-body')
const open = document.getElementById('callback-open') as HTMLAnchorElement | null
const back = document.getElementById('callback-back') as HTMLAnchorElement | null

const search = window.location.search
// The code is spent the moment it is read; take it out of the address bar
// and the history so a reload or a shared screenshot carries nothing.
window.history.replaceState(null, '', window.location.pathname)

if (back !== null) back.href = import.meta.env.BASE_URL

void completeSpotifyConnect(search).then((outcome) => {
  const message = callbackMessage(outcome)
  if (heading !== null) heading.textContent = message.heading
  if (body !== null) body.textContent = message.body
  if (open !== null && message.openInSpotify !== undefined) {
    open.href = message.openInSpotify
    open.hidden = false
  }
})
