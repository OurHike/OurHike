# Podcasts picked for a hike

[#1683 — Offer podcast episodes picked for the hike, with a one-tap Spotify save and an in-app player](https://github.com/OurHike/OurHike/issues/1683).

A hiker looking at a hike sees a short list of podcast episodes somebody picked for it,
can play one on the screen, and can save one to their own Spotify library in one tap.

## What was decided, and against what

The maintainer, by poll on 2026-09-26, each question put with a drawn mock and, after the
first build, a photograph of the running app:

| question | chosen | offered and not taken |
|---|---|---|
| the button | Spotify's embedded player **and** a one-tap save | a plain "Open in Spotify" link (recommended at the time) |
| where | last on the hike detail screen, and under "Today on your hike" on a long hike | either one alone |
| which episodes | a hand-picked list | searching Spotify by where the hiker is |
| when the player loads | on a tap | as soon as the card shows |
| the phone apps | a link to the episode in Spotify, nothing else | the same card as the web |
| where the list lives | live, at the bucket root, so a new episode needs no app release | in the app code; in the pinned trail data |
| the buttons | icons beside each title | 44px pills, then 32px pills |
| the Spotify buttons | the maintainer asked for Spotify's icon on them; drawn as the icon beside a word ("Save", "Saved", "Listen on Spotify"), the shape Spotify's design guidelines allow | the icon inside our + circle, which the guidelines forbid (no combining the mark with another symbol); the icon alone in a white circle, which reads as "open Spotify" rather than "save" |
| other apps ([#1690](https://github.com/OurHike/OurHike/issues/1690)) | the hiker picks their podcast app once - Spotify, Apple Podcasts, Pocket Casts, Overcast or YouTube Music - and each episode opens in it | one pod.link link that asks which app; playing the podcast's own audio inside OurHike |
| before a pick | a plain Listen, and the first tap (or ↓) asks | assuming Spotify until changed |
| an episode with no link for the hiker's app | still shown, with Spotify's button and "Not linked for <app> yet." | hidden |
| ▶ | Spotify's player for everyone, whatever app they picked | only for hikers who picked Spotify |
| download | a ↓ circle like ▶ that opens the episode in the hiker's app, one tap from that app's own download | keeping the audio in OurHike for no-signal play; saving an .mp3 to the phone |

"Should be the last thing you see" is the maintainer's own line about the hike detail
placement. The alternatives are written down so the next reader knows they were considered,
not so they get re-argued.

## What it cannot do, and why

**The one-tap save works for five Spotify accounts at most.** Since 2026-03-09 an app in
Spotify's Development Mode serves up to five users its owner adds by hand, and the owner must
have Premium; Spotify grants more ("extended quota") only to a registered organization with at
least 250,000 monthly users (Spotify's quota-modes page, read 2026-09-26). Every other account
gets a 403 from the save, and the card sends that hiker to the episode in Spotify to tap +
there. Nothing in this repository can change that.

**Nothing can tell which podcast app a phone uses, so OurHike asks.** iPhone has no default
podcast app setting (Apple's list of changeable defaults names none, read 2026-09-26),
Android's old default, Google Podcasts, is shut down, and browsers hide which apps are
installed on purpose. The pick is kept on the phone (`lib/podcastApp.ts`), never in the
account, and More → Settings changes it.

**No podcast app lets another app start a download,** Spotify included: its API can save an
episode but has no download call, and the others offer no API at all. So ↓ opens the episode
in the hiker's app, and the line under the list says so.

**One-tap Save is Spotify's alone,** for the same reason: no other app lets another add an
episode to a listener's library.

**The phone apps get a link.** A sign-in redirect does not return into the Capacitor shells
today ([AUTHENTICATION.md](AUTHENTICATION.md)), and the Android shell's `useLegacyBridge`
(`client/capacitor.config.ts`) exposes the native bridge, background location included, to
any frame the WebView holds. Spotify's player is a third-party frame, so it stays out.

**Nothing reaches Spotify before a tap**, and what a tap sends is in
[IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md)'s table.

## Setting it up

The card works with no setup: it shows the player and an "Open in Spotify" link. The Save
button needs a Spotify app:

1. Create an app at developer.spotify.com, choosing the Web API. The account that owns it must
   have Spotify Premium.
2. Add one redirect URI per origin the app is served from, exactly:
   `https://ourhike.org/app/spotify-callback.html` for production, and UA's origin followed
   by `/spotify-callback.html`. A pull request preview's origin is not registered, so Save
   on a preview stops at Spotify's own "invalid redirect URI" page.
3. Add each Spotify account that may save (up to five) on the app's User Management page.
4. Put the app's client id in the repository **variable** `SPOTIFY_CLIENT_ID`. It is public
   by design (PKCE, no secret), and `.github/expected-settings.yml` declares it.

## Adding an episode

1. Add a row to `pipeline/reference/podcast_episodes.json` - its README says what each field
   is. For each other app it is in, copy that app's own share link into `links`
   (`apple_podcasts`, `pocket_casts`, `overcast`, `youtube_music`); there is no shared
   episode-link format across podcast apps, and an app left out sends its listeners to
   Spotify with a line saying so. Then open a pull request.
   `pipeline/tests/test_export_podcasts.py` fails on a row the exporter would drop.
2. After the merge, dispatch `publish-podcasts.yml` with `publish: true` and
   `data_environment: ua`, check it on UA, then again with `production`.

`scripts/pipelines.sh` does not know this path yet ([#1685 — scripts/pipelines.sh reads an edit to the podcast list as staling all six publishes, and never names the one that publishes it](https://github.com/OurHike/OurHike/issues/1685)): it reports every publishing workflow as
stale for an edit to the list, because `pipeline/reference/` is one of its shared roots, and
it never names `publish-podcasts.yml`, which does not run `publish.py`. The only workflow an
edit to the list stales is `publish-podcasts.yml`.

## Where the code is

| part | file |
|---|---|
| the reviewed list | `pipeline/reference/podcast_episodes.json` |
| the gate and the upload | `pipeline/lib/podcasts.py`, `pipeline/export_podcasts.py`, `.github/workflows/publish-podcasts.yml` |
| the phone's copy and the matching | `client/src/lib/podcasts.ts`, `client/src/lib/usePodcastEpisodes.ts` |
| Spotify | `client/src/lib/spotify.ts`, `client/spotify-callback.html`, `client/src/spotifyCallback/` |
| the card | `client/src/chrome/PodcastCard.tsx`, on `screens/HikeDetail.tsx` and `screens/Today.tsx` |
| the hiker's app | `client/src/lib/podcastApp.ts`, `client/src/chrome/PodcastAppPicker.tsx`, `PodcastAppIcon.tsx`, and the Podcast app row in `screens/Settings.tsx` |
| the pictures | `client/preview-shots/hike-detail-podcasts.mjs`, `podcast-app-picker.mjs`, `today-long-hike-podcasts.mjs` |
