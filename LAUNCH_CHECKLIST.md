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

**1.1 Create the bucket.** Cloudflare dashboard → R2 → Create bucket. Any name; you'll put it in an env var. R2 has no egress fees, which is why it was chosen — a 314 MB download per hiker would be ruinous on S3.

**1.2 Create an API token.** R2 → Manage API Tokens → Create → **Object Read & Write**, scoped to that bucket. You get an Access Key ID and a Secret Access Key. The secret is shown **once**.

**1.3 Set four environment variables** where you run the pipeline:

```
R2_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com
R2_BUCKET=<your bucket name>
R2_ACCESS_KEY_ID=<from 1.2>
R2_SECRET_ACCESS_KEY=<from 1.2>
```

`pipeline/publish.py` reads these and nothing else. It is written and tested against mocked S3, so it should work first time.

**1.4 Configure CORS — this one is easy to miss and fails confusingly.** The client reads PMTiles via HTTP **range requests**. Without CORS exposing the right headers, the map fails in a way that looks like a corrupt archive rather than a permissions problem.

R2 → your bucket → Settings → CORS policy:

```json
[{
  "AllowedOrigins": ["https://<your-domain>", "http://localhost:5173"],
  "AllowedMethods": ["GET", "HEAD"],
  "AllowedHeaders": ["range", "if-match", "content-type"],
  "ExposeHeaders": ["content-length", "content-range", "etag", "accept-ranges"],
  "MaxAgeSeconds": 3600
}]
```

`ExposeHeaders` matters as much as `AllowedHeaders`: the resumable download reads `content-range` to know whether the server honoured a range request, and treats a missing/200 response as "start over" rather than corrupting the file.

**1.5 Enable public read access**, either R2's public bucket URL or a custom domain. A custom domain is worth it — the bucket URL ends up baked into the client.

**1.6 Publish.**

```
cd pipeline
.venv/Scripts/python publish.py
```

Roughly 1.6 GB on the first run (all three background tiers plus trails, POIs and elevation). Subsequent runs upload only what changed — it diffs SHA-256 per artifact against the bucket's `latest.json`.

**Verify:** the bucket should contain `background_z11.pmtiles`, `background.pmtiles`, `background_z13.pmtiles`, `trails.geojson`, `trails.fgb`, the `poi_*` files, `elevation_profile.json`, and a `latest.json` manifest.

---

## 2. Point the client at the bucket

Once 1.5 gives you a URL, this is a small code change — tell me the URL and I'll do it, or:

`client/src/App.tsx` currently renders a scaffold placeholder. It needs to render `MapScreen` with:

```
topoArchiveUrl = pmtiles://<your-r2-url>/background.pmtiles
trailsUrl      = <your-r2-url>/trails.geojson
```

**This is the step that turns the repo into a working map**, and it needs nothing but the URL.

---

## 3. Host the client

A static build — no server needed.

```
cd client && npm run build     # outputs to client/dist
```

Cloudflare Pages is the natural fit (same account as R2, and same-origin avoids a second CORS surface). Vercel or Netlify work identically.

**Set the build command to `npm run build`, output directory `dist`, root directory `client`.**

Two things to check after deploying:
- The PWA installs (service worker registers, manifest loads). iOS Web Push **only** works for home-screen installs, which matters for the wrong-way alert later.
- HTTPS. Geolocation and service workers both require it.

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
- **opentrail.org licensing is unconfirmed** — `ROADMAP.md` Phase 1 has an open item to contact the maintainer. Their water and resupply data is in the build. Worth resolving before a public launch, not after.
- USGS topo, USGS 3DEP and PAD-US are all public domain. ATC data is used with attribution.

**Verify before launch:**

```
cd pipeline && .venv/Scripts/python check_freshness.py
```

Confirms all four upstream sources are unchanged since the last fetch. Exits non-zero if anything is stale **or unverifiable** — an unreachable source reports `UNKNOWN`, never `fresh`.

---

## Things I know are not done, stated plainly

- **Real OAuth login has never been exercised end to end.** The auth code path is fully tested against a mocked Supabase client, but no real Google or Apple sign-in has happened, because that needs credentials only you can create. Expect to find something here.
- **The wrong-way alert's thresholds (90 ft / 12 min / 25 min) are wireframe placeholders**, not validated numbers. `HIKER_SAFETY.md` explicitly declines to guess them pending field testing under tree canopy. The mechanism is tested; the numbers are not trustworthy yet, and this is the one feature where a false alarm costs the most.
- **Cumulative ascent from the 25 m elevation profile over-counts** — 594,520 ft against the ~510,000 ft consensus, because dense sampling accumulates DEM noise as fake climbing. The profile is correct for drawing; anything computing total ascent should decimate first. Not yet done.
- **No end-to-end test against real published artifacts.** Everything is verified against local files and mocks.
- **Backend has never run against real Postgres outside CI.**

## Rough ordering if you want a working map fastest

Steps **1 → 2 → 3** only. That is R2, one URL change, and a static deploy — and it gives you the offline topo map, trails, POIs and elevation profile working on a phone, with no accounts, no backend and no database. Everything in 4–6 exists to support contributing, which nobody can do until people are using the map anyway.
