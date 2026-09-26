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
   is - and open a pull request. `pipeline/tests/test_export_podcasts.py` fails on a row the
   exporter would drop.
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
| the pictures | `client/preview-shots/hike-detail-podcasts.mjs`, `today-long-hike-podcasts.mjs` |
