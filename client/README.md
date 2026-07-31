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

| Command             | What it does                                  |
| ------------------- | --------------------------------------------- |
| `npm run dev`       | Dev server with HMR                           |
| `npm run build`     | Typecheck, then production build into `dist/` |
| `npm run preview`   | Serve `dist/` locally                         |
| `npm test`          | Full test suite with coverage                 |
| `npm run typecheck` | App and test tsconfigs                        |
| `npm run lint`      | oxlint                                        |

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
Downloads screen says so rather than firing requests that would 404.

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

`.github/workflows/pages.yml` publishes to GitHub Pages on every push to
`main` — the beta landing page (`site/`) at `/OurHike/` and this app at
`/OurHike/app/`. Enable it once under Settings → Pages → Source →
**GitHub Actions**, and set `DATA_BASE_URL` as a repository _variable_ (not a
secret — it is public either way, and secrets are unavailable to the build in
the form Vite needs).

Any other static host works too; the build output is `dist/`, the build
command is `npm run build`.

### Serving from a subpath

`VITE_BASE_PATH` controls where the app expects to live, trailing slash
required. This matters more for a PWA than for an ordinary site: `scope` and
`start_url` in the manifest decide which pages the installed app owns, so a
manifest claiming `/` while served from `/OurHike/app/` either fails install
validation or installs an app that opens the wrong page. It defaults to `/`, so
a root-domain deploy needs nothing set.

One Windows gotcha: Git Bash rewrites a leading-slash value into a Windows
path, so `VITE_BASE_PATH=/OurHike/app/ npm run build` silently produces
`C:/Program Files/Git/OurHike/app/`. Use PowerShell, or prefix with
`MSYS_NO_PATHCONV=1`.

**HTTPS is not optional.** Android only offers "Install app" for a page served
over HTTPS with a manifest, a service worker and the two icons — all of which
`vite-plugin-pwa` emits into `dist/` already. Localhost counts as secure for
development, so `npm run preview` is installable too.

## Installing on Android for a field test

1. Open the deployed URL in Chrome.
2. Menu → **Add to Home screen** / **Install app**.
3. Open the installed app, go through onboarding, and pick a detail level.
   Light is 64 MB, Standard 314 MB, Fine 1.18 GB.
4. On **Downloads**, tap "Download the map" — trail lines and POIs come first,
   then the raster archive. A dropped connection resumes rather than restarts.
5. Turn on airplane mode and confirm the map still draws. This is the test that
   matters; everything else can be checked at home.

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
