# OurHike — what's left to ship the v1 MVP

Everything in the plan is built and tested. What remains is almost entirely **accounts, credentials and hosting** — things that need a human with a card and an email address, not more code.

This is ordered so that each step unblocks the next. Steps 1–3 get a working map in a browser; 4–6 add contributions; 7 ships it.

**Status at time of writing:** pipeline, backend and client all green (pipeline 152 tests, backend 85, client 490). All artifacts built locally. Nothing is published anywhere yet.

---

## What is already done

| | |
|---|---|
| Pipeline | 12 ATC layers, 1,654 topo quads, opentrail water/resupply, all fetched |
| Background archives | All three tiers built: 64 MB / 314 MB / 1.18 GB, each within 0.6% of the size the app advertises |
| Trails | 4,224 features, simplified to 1 m, 12 MB GeoJSON |
| POIs | water, shelters, campsites, resupply, crossings |
| Elevation | 139,219 points at 25 m, 0% DEM gaps, 0.87 MB gzipped |
| Backend | FastAPI + SQLAlchemy, reports/closures/moderation/hikes/preferences/wrong-way, Supabase JWT auth |
| Client | Every MVP screen, offline outbox, resumable download, 490 tests |

---

## 1. Cloudflare R2 — the biggest single unblock

Everything downstream needs this. Without it the app has no data to fetch.

**1.1 Create the bucket.** ✅ **Done** — bucket `your-hike` created 2026-07-31. (Cloudflare dashboard → R2 → Create bucket, for reference.)

**1.2 Create an API token.** Still manual — dashboard-only, since minting credentials isn't something to automate. R2 → Manage API Tokens → Create → **Object Read & Write**, scoped to `your-hike`. You get an Access Key ID and a Secret Access Key. The secret is shown **once**.

**1.3 Set four repository secrets in GitHub** (not just local env vars — publishing now runs in CI, see 1.6): Settings → Secrets and variables → Actions → **Secrets** tab → New repository secret, one each for:

```
R2_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com
R2_BUCKET=your-hike
R2_ACCESS_KEY_ID=<from 1.2>
R2_SECRET_ACCESS_KEY=<from 1.2>
```

Use **repository** secrets, not environment-scoped ones: `r2-credentials-check.yml` (see below) runs with no `environment:` set, so environment-scoped secrets would be invisible to it. `publish-vector-data.yml`'s job runs under the `production` environment but still resolves repository secrets fine — no conflict either way.

`pipeline/publish.py` reads these and nothing else. It is written and tested against mocked S3, so it should work first time.

Once the four secrets are set, dispatch the **"R2 credentials check"** workflow (Actions tab → workflow_dispatch) to confirm they're valid before attempting a real publish — it only calls `head_bucket`, so it's safe to run any time.

**1.4 Configure CORS — this one is easy to miss and fails confusingly.** The client reads PMTiles via HTTP **range requests**. Without CORS exposing the right headers, the map fails in a way that looks like a corrupt archive rather than a permissions problem.

R2 → `your-hike` → Settings → CORS policy. The app is hosted on GitHub Pages (see step 3 — that's settled now, unlike when this list was first written), so the real origin to allow is:

```json
[{
  "AllowedOrigins": ["https://jaimito-asuntos-gringuenos.github.io", "http://localhost:5173"],
  "AllowedMethods": ["GET", "HEAD"],
  "AllowedHeaders": ["range", "if-match", "content-type"],
  "ExposeHeaders": ["content-length", "content-range", "etag", "accept-ranges"],
  "MaxAgeSeconds": 3600
}]
```

`ExposeHeaders` matters as much as `AllowedHeaders`: the resumable download reads `content-range` to know whether the server honoured a range request, and treats a missing/200 response as "start over" rather than corrupting the file.

**1.5 Enable public read access**, either R2's public bucket URL or a custom domain. A custom domain is worth it — the URL ends up baked into the client build as `DATA_BASE_URL` (step 2 below).

**Decided 2026-07-31: start with the R2.dev subdomain, not a custom domain.** Gets a working map faster with no DNS to set up. Cloudflare documents the r2.dev subdomain as meant for testing/light use, not sustained production traffic, so this is a deliberate stopgap — **switch `DATA_BASE_URL` to `https://data.ourhike.app` once that domain is set up as a custom domain on this bucket.** Nothing else about steps 2/3 changes when that happens: swapping the repository variable and redeploying Pages is the whole migration, no code change.

**1.6 Publish — now a CI workflow, not a local script.** Dispatch **"Publish vector data"** (Actions tab → workflow_dispatch) with `publish` ticked. Leaving it unticked does a dry run: builds and quality-checks everything without uploading, useful for checking upstream still parses. `include_elevation` adds ~25 min and isn't read by any client code yet, so leave it off unless you're specifically testing that.

Local publish (`cd pipeline && .venv/Scripts/python publish.py` with the four vars from 1.3 set locally) still works identically — CI just runs the same script.

Roughly 1.6 GB on the first run (all three background tiers plus trails, POIs and elevation). Subsequent runs upload only what changed — it diffs SHA-256 per artifact against the bucket's `latest.json`.

**Verify:** the bucket should contain `background_z11.pmtiles`, `background.pmtiles`, `background_z13.pmtiles`, `trails.geojson`, `trails.fgb`, the `poi_*` files, `elevation_profile.json`, and a `latest.json` manifest.

---

## 2. Point the client at the bucket

No longer a code change — the client already reads the bucket URL from a build-time variable (`client/src/lib/config.ts`'s `VITE_DATA_BASE_URL`), not a hardcoded value in `App.tsx`.

Set it as a **repository variable** (not a secret — it's a public URL): Settings → Secrets and variables → Actions → **Variables** tab → New repository variable → `DATA_BASE_URL` = the public URL from 1.5. `.github/workflows/pages.yml` picks it up as `VITE_DATA_BASE_URL` at build time.

**Currently the R2.dev subdomain (see 1.5); revisit once `data.ourhike.app` is set up as a custom domain** and update `DATA_BASE_URL` to `https://data.ourhike.app`, then redeploy Pages (step 3) to pick it up.

**This is the step that turns the repo into a working map**, and it needs nothing but the URL, set once.

---

## 3. Host the client

✅ **Already done, and automatic** — `.github/workflows/pages.yml` builds and deploys the client to GitHub Pages on every push to `main`: the beta landing page at `https://jaimito-asuntos-gringuenos.github.io/OurHike/` and the installable app at `.../OurHike/app/`. Cloudflare Pages was the original plan when this list was written, but GitHub Pages is what actually got wired up (it's what gives the PWA the HTTPS a browser requires before offering "Install app").

Nothing to configure — but after setting `DATA_BASE_URL` (step 2), the site needs a **redeploy** to pick it up, since it's baked in at build time. Either push any commit to `main`, or dispatch **"Deploy Pages"** manually (Actions tab → workflow_dispatch) to redeploy with no code change.

Two things to check after that redeploy:
- The PWA installs (service worker registers, manifest loads). iOS Web Push **only** works for home-screen installs, which matters for the wrong-way alert later.
- The Downloads screen actually fetches data instead of saying "data source not configured" (that message means `DATA_BASE_URL` didn't make it into the build).

**After step 3 you have a working offline map.** Steps 4–6 are only needed for contributions — reporting, closures, accounts.

---

## 4. Supabase — authentication

The backend verifies Supabase-issued JWTs. Browsing never needs an account; this is only for contributing.

**4.1** Create a project at supabase.com. Free tier covers 500 MB / 50k monthly active users, comfortably past MVP scale.

**4.2** Project Settings → API. Collect:

```
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=<anon public key>
SUPABASE_JWT_SECRET=<Settings > API > JWT Secret>
```

**4.3 Configure OAuth providers** (Authentication → Providers). Each needs its own developer registration, and these are the slowest items on this list because they involve external approval:

- **Google** — Google Cloud Console → OAuth 2.0 Client ID. Redirect URI is `https://<ref>.supabase.co/auth/v1/callback`.
- **Apple** — Apple Developer Program, **$99/year**. Needs a Services ID and a signing key. If you want to defer cost, ship with Google + email and add Apple later; nothing in the code assumes all three.
- **Email** — on by default, no setup.

**4.4 Flag on the JWT verification method.** `backend/app/core/auth.py` currently verifies **HS256 using the JWT secret**. Supabase has been migrating projects toward asymmetric keys (JWKS/RS256). If your project issues RS256, that function needs changing — it was deliberately built as a single seam so this is a contained change, but it is the one thing here I could not settle without a real project to look at. **Check this before assuming auth works.**

---

## 5. First database migration

There are no Alembic migrations — `backend/alembic/versions/` holds only `.gitkeep`. Tests create tables directly from the models, which is why this has not surfaced.

Before the backend can run against a real Postgres:

```
cd backend
# with DATABASE_URL pointed at your Supabase Postgres
.venv/Scripts/alembic revision --autogenerate -m "initial schema"
.venv/Scripts/alembic upgrade head
```

**Review the generated migration before applying it.** Autogenerate is good but not infallible, and several models use `Enum(..., native_enum=False)` for DuckDB/Postgres portability — worth confirming that renders as expected.

Tables it should create: `profiles`, `reports`, `closures`, `hikes`, `preferences`, `clubs`, `maintainer_assignments`.

---

## 6. Host the backend

**Nothing exists for this yet** — no Dockerfile, no Procfile, no platform config. It is the largest genuinely unstarted piece.

FastAPI + sync SQLAlchemy runs anywhere that runs Python. Fly.io, Render and Railway all work; Render's free tier sleeps, which is survivable for MVP but will make the first request after idle slow.

It needs:

```
DATABASE_URL=postgresql://...        # your Supabase Postgres connection string
SUPABASE_JWT_SECRET=...
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
```

Then point the client's API base URL at it, and add its origin to Supabase's allowed redirect URLs.

I can write the Dockerfile and platform config once you pick a host — the choice affects the file.

---

## 7. Before you tell anyone about it

**Legal and licensing, all previously flagged:**

- **OpenStreetMap attribution is required by ODbL** and is already rendered by `MapScreen`. Do not remove it. It currently only matters once the Protomaps context basemap ships, but the code is already correct.
- **opentrail.org licensing is unconfirmed** — [#98](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/98) tracks contacting the maintainer. Their water and resupply data is in the build. Worth resolving before a public launch, not after.
- USGS topo, USGS 3DEP and PAD-US are all public domain. ATC data is used with attribution.

**Verify before launch:**

```
cd pipeline && .venv/Scripts/python check_freshness.py
```

Confirms all four upstream sources are unchanged since the last fetch. Exits non-zero if anything is stale **or unverifiable** — an unreachable source reports `UNKNOWN`, never `fresh`.

---

## Things I know are not done, stated plainly

Each of these is now an issue, so that fixing one closes it here too rather than leaving this list to be remembered. The [`v1-mvp`](https://github.com/jaimito-asuntos-gringuenos/OurHike/labels/v1-mvp) label is the current version of this list.

- **Real OAuth login has never been exercised end to end** ([#92](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/92)). The auth code path is fully tested against a mocked Supabase client, but no real Google or Apple sign-in has happened, because that needs credentials only you can create. Expect to find something here.
- **The wrong-way alert's thresholds (90 ft / 12 min / 25 min) are wireframe placeholders** ([#93](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/93)), not validated numbers. `HIKER_SAFETY.md` explicitly declines to guess them pending field testing under tree canopy. The mechanism is tested; the numbers are not trustworthy yet, and this is the one feature where a false alarm costs the most.
- **Cumulative ascent from the 25 m elevation profile over-counts** ([#91](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/91)) — 594,520 ft against the ~510,000 ft consensus, because dense sampling accumulates DEM noise as fake climbing. The profile is correct for drawing; anything computing total ascent should decimate first.
- **No end-to-end test against real published artifacts** ([#94](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/94)). Everything is verified against local files and mocks.
- **Backend has never run against real Postgres outside CI** ([#95](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/95)).
- **The report photo picker accepts a photo and discards it** ([#89](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/89)), and **POIs are never drawn on the map** ([#90](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/90)) — both found after this list was first written.

## Rough ordering if you want a working map fastest

Steps **1 → 2 → 3** only, and 3 is already automatic. Concretely: finish R2 (API token, secrets, CORS, public access, publish), set the `DATA_BASE_URL` repository variable, then redeploy Pages — and you have the offline topo map, trails, POIs and elevation profile working on a phone, with no accounts, no backend and no database. Everything in 4–6 exists to support contributing, which nobody can do until people are using the map anyway.
