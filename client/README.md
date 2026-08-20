# OurHike client

The PWA a hiker installs: an offline-first topo map of the Appalachian Trail,
built with React + Vite + MapLibre, reading a downloaded PMTiles archive out of
IndexedDB.

## Running it locally

```bash
npm install
npm run dev
```

Everything except the map data works with no configuration. The map itself
needs a published data bucket — see below.

| Command               | What it does                                            |
| --------------------- | ------------------------------------------------------- |
| `npm run dev`         | Dev server with HMR                                     |
| `npm run build`       | Typecheck, production build into `dist/`, then check it |
| `npm run check:build` | Re-run that check on an existing `dist/`                |
| `npm run preview`     | Serve `dist/` locally                                   |
| `npm test`            | Full test suite with coverage                           |
| `npm run typecheck`   | App and test tsconfigs                                  |
| `npm run lint`        | oxlint                                                  |

`check:build` reads the build output and asks whether the app can actually draw
a map — every asset it references is published, MapLibre's web worker among
them, and precached for offline. It is part of `build` because the failure it
guards against is silent: the map goes blank with no error anywhere. See
`scripts/check-build-output.mjs`.

## Pointing it at data

The pipeline publishes flat artifacts to R2 (`pipeline/publish.py`). The client
needs one build-time variable naming that bucket:

```bash
cp .env.example .env.local
# then edit VITE_DATA_BASE_URL
```

`VITE_DATA_BASE_URL` is the bucket's **public** base URL — the client appends
`background.pmtiles`, `trails.geojson`, `poi_shelter.geojson` and so on
directly to it. Get it from Cloudflare → R2 → your bucket → Settings → Public
access, either via the r2.dev subdomain (fine for testing; rate-limited and not
meant for production traffic) or a custom domain.

Vite inlines `VITE_*` variables at **build** time. Changing this means
rebuilding and redeploying — it is not read at runtime. With it unset, the
download window says so rather than firing requests that would 404.

## Pointing it at the backend

Reports queue in an offline outbox and are sent when there is both a connection
and an account. `VITE_API_BASE_URL` is where they are sent:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run build
```

That is `backend/`'s own FastAPI service — not the R2 bucket above, and not
Supabase. The three are separate on purpose: the bucket is static data a hiker
downloads once and reads offline forever, Supabase is where they sign in, and
this is the only one that receives anything.

**Unset is a supported state, and is what every deploy currently builds**, since
the backend is not deployed anywhere yet
([#95](https://github.com/OurHike/OurHike/issues/95)). The map,
downloads and reporting flow all work; a written report stays queued with its
authored timestamp instead of being sent, and nothing is lost. Sending starts
working when a build has somewhere to send to — no code change.

### R2 must allow cross-origin range requests

The client is served from one origin and the data from another, and PMTiles
reads the archive by byte range. The bucket's CORS policy therefore has to
allow `GET`, allow the `Range` request header, and expose `Content-Range` and
`Content-Length`. Without `Range` the archive downloads but no tile ever
renders — a failure that looks like a broken map rather than a misconfigured
bucket.

## Testing the whole flow before deploying

Worth doing before relying on this somewhere with no signal. `localhost` counts
as a secure context, so the service worker registers and the app installs — the
whole flow is testable without deploying anything.

```bash
# terminal 1 - serves data/processed/ the way R2 will, ranges and CORS included
cd pipeline && python serve_processed.py

# terminal 2
cd client
VITE_DATA_BASE_URL=http://localhost:8787 npm run build
npm run preview
```

Then open the preview URL, download the map, and switch off networking. The map
should still draw. `pipeline/serve_processed.py` exists because Python's
`http.server` ignores `Range` entirely, which PMTiles depends on — testing
against it would prove nothing about production.

## Deploying

`.github/workflows/pages.yml` publishes to GitHub Pages when a `v*` tag is
pushed — the beta landing page (`site/`) at `https://ourhike.org/` and this app
at `/app/`, with `site/CNAME` putting the site on that domain (#733). A push to
`main` deploys to UA instead (`ua.yml`); see
[RELEASING.md](../RELEASING.md) §2 for why those are two different things.
Enable Pages once under Settings → Pages → Source → **GitHub Actions**, and set
`DATA_BASE_URL` as a repository _variable_ (not a secret — it is public either
way, and secrets are unavailable to the build in the form Vite needs).

Any other static host works too; the build output is `dist/`, the build
command is `npm run build`.

### Serving from a subpath

`VITE_BASE_PATH` controls where the app expects to live, trailing slash
required. This matters more for a PWA than for an ordinary site: `scope` and
`start_url` in the manifest decide which pages the installed app owns, so a
manifest claiming `/` while served from `/app/` either fails install
validation or installs an app that opens the wrong page. It defaults to `/`, so
a preview at the root of its own hostname needs nothing set.

Production sets `/app/`, because `ourhike.org` serves the landing page at its
root and the app beneath it (#733). It was `/OurHike/app/` while the site was a
GitHub Pages _project_ site, which is where the examples below come from.

One Windows gotcha: Git Bash rewrites a leading-slash value into a Windows
path, so `VITE_BASE_PATH=/app/ npm run build` silently produces
`C:/Program Files/Git/app/`. Use PowerShell, or prefix with
`MSYS_NO_PATHCONV=1`.

**HTTPS is not optional.** Android only offers "Install app" for a page served
over HTTPS with a manifest, a service worker and the two icons — all of which
`vite-plugin-pwa` emits into `dist/` already. Localhost counts as secure for
development, so `npm run preview` is installable too.

### Which build is this

Settings ends with **About this build** — the version, the commit and the build
time, with a button that copies all three. Ask for that when somebody reports a
problem; it is the difference between a bug report about "the app" and one
about a build you can check out.

Nothing needs configuring for it. `vite.config.ts` reads the version out of
`package.json` and the commit out of `git rev-parse HEAD` (falling back to
`GITHUB_SHA`), and `define`s all three into the bundle, so production, UA, a
pull request preview and a laptop all report themselves correctly with no
workflow variable to set or forget. A build with neither git nor `GITHUB_SHA`
— a tarball outside CI — says `unknown` rather than guessing.

The version stays `0.0.0` until the first release tag, which means `main`,
every preview and every laptop share it. That is why the commit is shown
beside it, and why the section says out loud that an untagged build is not a
release. `pages.yml` refuses to deploy a `v*` tag that disagrees with
`package.json`, so a released build's version is the tag's.

## Installing on Android for a field test

1. Open the deployed URL in Chrome.
2. Menu → **Add to Home screen** / **Install app**.
3. Open the installed app, go through onboarding, and pick a detail level.
   The choice is the hiking sheet's own Standard (recommended) or Fine
   (#277) - the screen shows each level's exact published size. (This step
   used to quote the USGS raster tiers as the main download; that sheet is
   the optional full-detail alternative now, configured later from
   Downloads.)
4. On **More → Downloads**, tap "Download the map" — trail lines and POIs
   come first, then the sheet's archives. A dropped connection resumes
   rather than restarts.
5. Turn on airplane mode and confirm the map still draws. This is the test that
   matters; everything else can be checked at home.

## Native shells (Capacitor)

`ios/` and `android/` are the app-store shells around this same build (#101 —
Wrap the PWA with Capacitor; TECHNICAL_ARCHITECTURE.md's packaging line: "the
same codebase, not parallel implementations"). They were generated by
`npx cap add` (Capacitor 8.5.0, pinned exactly in package.json so the CLI and
the committed scaffolds cannot drift apart) and are committed as source, which
is Capacitor's own convention: the manifest, the Info.plist and the Gradle
files are edited by hand. What `cap sync` writes into them — the copied web
assets, the config copies, the Cordova plugin scaffolding — is generated, and
each tree's own `.gitignore` keeps all of it out of commits. Prettier and
oxlint skip both trees (`.prettierignore`, `.oxlintrc.json`): their layout is
owned by the platform tools.

Nothing goes through a Capacitor plugin. Geolocation stays
`navigator.geolocation` (MapLibre's GeolocateControl runs its own watch
internally, so a plugin swap could never cover both callers), and the offline
archive stays IndexedDB (`lib/archiveStore.ts`). The shells only add what the
web APIs need to function in a WebView: the two location permissions in
`android/app/src/main/AndroidManifest.xml` and the usage string in
`ios/App/App/Info.plist` — each carries its reasoning where it sits.

The loop, on a machine with Xcode or Android Studio (**#102 — iOS build and
TestFlight beta** and **#103 — Android build and internal testing track**;
neither tool runs in CI or the web sandbox):

```
cd client
npm run build          # default VITE_BASE_PATH=/ — never a pages.yml /app/ build,
                       # which references /app/assets/... no WebView serves
npx cap sync           # copy dist/ into both shells
npx cap open ios       # or: npx cap open android
```

App icons and splash screens are generated from `resources/` — see
[resources/README.md](resources/README.md) for provenance and the pinned
regeneration command.

Known limits of the shells today, stated rather than discovered on a device:
in-shell origins are `capacitor://localhost` (iOS) and `https://localhost`
(Android), which no R2 CORS rule or Supabase redirect allowlist includes yet —
so archive downloads and OAuth sign-in inside a shell wait on those two
issues deciding the allowlists. The service worker is inert on iOS (WKWebView
has none on a custom scheme; the app shell ships in the binary,
`registerSW.js`'s guard makes it a clean no-op) and untested-but-harmless on
Android. And the shells add no background location: the app-level watch
pauses itself when the app is hidden, a backgrounded WebView gets no JS time
for MapLibre's own watch, and nothing native changes either fact.

## What is not wired up yet

- **Sign-in and identity.** There is no deployed backend, so reports save to
  the outbox and stop there rather than showing provider buttons that cannot
  authenticate. `lib/contributionFlow.ts`'s `stepAfterSaving()` is where they
  slot in.
- **Sync, export, and the account row** in Settings are inert for the same
  reason.
- **The wrong-way alert.** Its thresholds are unvalidated placeholders (see
  `features/HIKER_SAFETY.md`) and it is deliberately not driving anything.
- **Elevation ribbon and waypoint lanes.** Omitted rather than stubbed — an
  empty ribbon claims "nothing ahead of you," which is a different and worse
  statement than "we don't have the profile for this stretch."

## Looking at built map artifacts

`viewer.html` (its own entry point, not part of the app) renders `.pmtiles`
archives from pipeline workflow runs with the real hiking cartography: drop
any combination of a vector basemap, a DEM, or a raster sheet onto the page
and it recognises each from the archive itself. On a PR preview it lives at
`https://pr-<n>.<project>.pages.dev/viewer.html`; locally, `npm run dev` serves it at
`/viewer.html`. The bytes never leave your machine — download an artifact
from a run, unzip, drop. See issue #202.
