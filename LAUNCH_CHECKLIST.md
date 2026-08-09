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

Whether they're still *there* is checked continuously after that: `.github/expected-settings.yml` declares these four and `DATA_BASE_URL` below, and the **"Settings check"** workflow confirms weekly that each is configured — a revoked token is otherwise noticed by a publish failing partway through. Adding a repository secret or variable means adding it to that manifest too, or the check will flag the workflow reading a setting nothing vouches for.

**1.4 Configure CORS — this one is easy to miss and fails confusingly.** The client reads PMTiles via HTTP **range requests**. Without CORS exposing the right headers, the map fails in a way that looks like a corrupt archive rather than a permissions problem.

R2 → `your-hike` → Settings → CORS policy. The app is hosted on GitHub Pages (see step 3 — that's settled now, unlike when this list was first written), and its previews on Cloudflare Pages (3a), so there are **two** origins to allow plus local dev:

```json
[{
  "AllowedOrigins": [
    "https://ourhike.github.io",
    "https://*.ourhike-preview.pages.dev",
    "http://localhost:5173",
    "http://localhost:4173"
  ],
  "AllowedMethods": ["GET", "HEAD"],
  "AllowedHeaders": ["range", "if-match", "content-type"],
  "ExposeHeaders": ["content-length", "content-range", "etag", "accept-ranges"],
  "MaxAgeSeconds": 3600
}]
```

**The `pages.dev` wildcard is not optional, and its absence is easy to misread.** Every pull request previews from a hostname of its own, so each one is a distinct origin as far as a browser is concerned — a wildcard is the only entry that can cover a pull request that does not exist yet. Without it the preview renders but the download fails with `NetworkError when attempting to fetch resource`, which looks like R2 being down rather than R2 declining to answer this particular origin.

This was missed when previews moved off GitHub Pages, and the reason is worth keeping: previews used to be served from the *same* GitHub Pages origin as production, so the one entry covered both and there was nothing here that looked origin-specific. Moving previews to their own hostnames split one origin into many. Supabase's redirect allow-list (4.3b) needed the identical change for the identical reason — if one of these two lists is ever updated for a new origin, the other one needs it too.

`ExposeHeaders` matters as much as `AllowedHeaders`: the resumable download reads `content-range` to know whether the server honoured a range request, and treats a missing/200 response as "start over" rather than corrupting the file.

**1.5 Enable public read access**, either R2's public bucket URL or a custom domain. A custom domain is worth it — the URL ends up baked into the client build as `DATA_BASE_URL` (step 2 below).

**Decided 2026-07-31: start with the R2.dev subdomain, not a custom domain.** Gets a working map faster with no DNS to set up. Cloudflare documents the r2.dev subdomain as meant for testing/light use, not sustained production traffic, so this is a deliberate stopgap — **switch `DATA_BASE_URL` to `https://data.ourhike.app` once that domain is set up as a custom domain on this bucket.** Nothing else about steps 2/3 changes when that happens: swapping the repository variable and redeploying Pages is the whole migration, no code change.

**1.6 Publish — now a CI workflow, not a local script.** Dispatch **"Publish vector data"** (Actions tab → workflow_dispatch) with `publish` ticked. Leaving it unticked does a dry run: builds and quality-checks everything without uploading, useful for checking upstream still parses. `include_elevation` adds ~25 min and isn't read by any client code yet, so leave it off unless you're specifically testing that.

Local publish (`cd pipeline && .venv/Scripts/python publish.py` with the four vars from 1.3 set locally) still works identically — CI just runs the same script.

Roughly 1.6 GB on the first run (all three background tiers plus trails, POIs and elevation). Subsequent runs upload only what changed — it diffs SHA-256 per artifact against the bucket's `latest.json`.

**Verify:** the bucket should contain `background_z11.pmtiles`, `background.pmtiles`, `background_z13.pmtiles`, `trails.geojson`, `trails.fgb`, the `poi_*` files, `elevation_profile.json`, and a `latest.json` manifest.

**1.7 A SECOND bucket, private, for report photos (#234).** Not the one above, and this is the one step on this page where reusing what is already set up would be actively harmful.

Everything in 1.1–1.6 is *published* data, and 1.5 turns public read on for exactly that reason. A report photo is not published data. `bad_hikers` reports are routed `internal_only` because they concern a person, `thanks` is `club_only`, and every type is photographed at submit time — before a moderator has looked, which [#229](https://github.com/OurHike/OurHike/issues/229) established is not publicly visible. Putting those objects in a world-readable bucket publishes the image while the report it belongs to stays private.

1. **Create the bucket.** R2 → Create bucket, e.g. `your-hike-photos`. **Leave public access off** — do not do 1.5 for this one. **No CORS entry either, and that is still true now that the moderation queue renders these photos** ([#385](https://github.com/OurHike/OurHike/issues/385)): what reaches the bucket is an `<img src>` holding a signed URL the backend authorised, and images are exempt from CORS. The alternative — a cross-origin `fetch` of the bytes — would have needed a policy here, which is why it is not what got built.
2. **Create a second API token**, Object Read & Write, **scoped to this bucket alone.** Same reason 1.2's is scoped to `your-hike`: a token that can reach both buckets is one bug away from writing a photo of a person into the public one.
3. **Set five variables on the backend's host, not in GitHub Actions** (see `backend/README.md`'s Deployment section for which host, and 6 below):

```
R2_PHOTO_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com
R2_PHOTO_BUCKET=your-hike-photos
R2_PHOTO_ACCESS_KEY_ID=<from 1.7.2>
R2_PHOTO_SECRET_ACCESS_KEY=<from 1.7.2>
R2_PHOTO_WRITE_ENABLED=true
```

**The `R2_PHOTO_` prefix is not decoration.** The backend used to read the same `R2_*` names as 1.3, which meant any environment carrying the publishing credentials configured it to store report photos in the published bucket. The prefix is what makes that impossible to do by accident; `backend/tests/test_report_photos.py` holds it.

**Skipping this whole step is a supported state**, unlike most of this page: a backend with no photo bucket answers 503 on all three photo endpoints, the client keeps the photo queued, and every other feature works. Nothing here blocks a launch — it blocks photos.

---

## 2. Point the client at the bucket

No longer a code change — the client already reads the bucket URL from a build-time variable (`client/src/lib/config.ts`'s `VITE_DATA_BASE_URL`), not a hardcoded value in `App.tsx`.

Set it as a **repository variable** (not a secret — it's a public URL): Settings → Secrets and variables → Actions → **Variables** tab → New repository variable → `DATA_BASE_URL` = the public URL from 1.5. `.github/workflows/pages.yml` picks it up as `VITE_DATA_BASE_URL` at build time.

**Currently the R2.dev subdomain (see 1.5); revisit once `data.ourhike.app` is set up as a custom domain** and update `DATA_BASE_URL` to `https://data.ourhike.app`, then redeploy Pages (step 3) to pick it up.

**This is the step that turns the repo into a working map**, and it needs nothing but the URL, set once.

---

## 3. Host the client

✅ **Already done, mostly automatic** — `.github/workflows/pages.yml` builds and deploys the client to GitHub Pages on every push to `main`: the beta landing page at `https://ourhike.github.io/OurHike/` and the installable app at `.../OurHike/app/`. Cloudflare Pages was the original plan when this list was written, but GitHub Pages is what actually got wired up (it's what gives the PWA the HTTPS a browser requires before offering "Install app").

**One manual step, once:** Settings → Pages → Build and deployment → Source must be **"Deploy from a branch"**, branch `gh-pages`, folder `/ (root)`. The workflow pushes to that branch itself; nothing publishes until the source is pointed at it.

### 3a. Preview deployments (Cloudflare Pages)

✅ **Done 2026-08-06** — project `ourhike-preview`, verified by a real deploy on PR #281: 274 files uploaded in 2.1 s. `.github/workflows/pr-preview.yml` builds every pull request and deploys it to its own URL — `https://pr-<n>.ourhike-preview.pages.dev`, linked from a comment on the PR — so a change can be tried on a phone instead of read as a diff. If the three settings below ever go missing the workflow says so in the run log and skips; pull requests still get their full test run, just no preview.

**Learned on that first deploy, and worth knowing before it looks like a broken deploy:** Cloudflare mints the `pr-<n>` alias when a pull request first deploys, and its edge answers **522** for a minute or two before that alias routes anywhere. Uploading and being reachable are not the same event. The workflow now waits for the URL to answer 200 before posting the comment, so the link is trustworthy by the time anyone sees it — but a 522 on a freshly-created alias is propagation, not misconfiguration. Every deploy also gets an immutable `https://<hash>.ourhike-preview.pages.dev` that is live the moment the upload finishes, and the workflow falls back to advertising that if the alias never comes up.

Previews used to live on the `gh-pages` branch alongside the production site. They moved because five to ten pull requests are open at once here as a matter of course, and every preview was a competing write to that one git ref — so previews failed for no reason other than each other being busy. A Cloudflare preview is its own deployment rather than a commit on a shared branch, so there is no ordering between two of them.

**Cost: none at this size.** The free plan places no limit on how many preview deployments a project keeps, and static requests and bandwidth are not metered. The limit that *would* bite — 500 builds a month, one at a time — applies only to Cloudflare's own builders, and this workflow does not use them: it builds in Actions and uploads the finished directory, so nothing queues behind anyone else's build.

1. **Create the project.** Cloudflare dashboard → Workers & Pages → Create → Pages → **Use direct upload**. Name it; that name goes in the middle of every preview URL. Nothing needs to be uploaded by hand — the first pull request does it.
2. **Mint an API token** (My Profile → API Tokens → Create Token) with the **Cloudflare Pages: Edit** permission and nothing else. It should not be the R2 token from step 1.2: a token that publishes previews has no business overwriting the live map data.
3. **Set the three settings**, in Settings → Secrets and variables → Actions:

```
CLOUDFLARE_API_TOKEN=<the token>       # Secrets tab
CLOUDFLARE_ACCOUNT_ID=<account id>     # Secrets tab
CLOUDFLARE_PAGES_PROJECT=<project>     # Variables tab — it is in every preview URL
```

4. **Allow the preview URLs back** in Supabase — see 4.3b, which covers this and the production URL together. Without it, signing in from a preview ends in a redirect mismatch.
5. **Allow the preview origin on the R2 bucket** — see 1.4. Without it the preview loads but the map download fails with `NetworkError when attempting to fetch resource`.

Steps 4 and 5 are the same mistake waiting to happen twice: both are origin allow-lists that previously needed only one entry, because previews used to share production's origin. A preview hostname that is not in **both** is a preview that either cannot sign in or cannot download.

A pull request from a fork gets no secrets and so gets no preview; the workflow notices and says so rather than failing.

Cloudflare now steers new projects toward **Workers static assets** rather than Pages, and that would work here too. Pages was chosen because a preview needs nothing but a directory uploaded to a URL, and Pages does that without a `wrangler.jsonc`, a `main` entry point or a compatibility date to keep current. Worth revisiting if the app ever grows a server-side part.

After setting `DATA_BASE_URL` (step 2), the site needs a **redeploy** to pick it up, since it's baked in at build time. Either push any commit to `main`, or dispatch **"Deploy Pages"** manually (Actions tab → workflow_dispatch) to redeploy with no code change.

Two things to check after that redeploy:
- The PWA installs (service worker registers, manifest loads). iOS Web Push **only** works for home-screen installs, which matters for the wrong-way alert later.
- The download window actually fetches data instead of saying "data source not configured" (that message means `DATA_BASE_URL` didn't make it into the build). It opens from the "Choose what to download" link at the foot of the legend, or at the foot of Settings under the More tab.

**After step 3 you have a working offline map.** Steps 4–6 are only needed for contributions — reporting, closures, accounts.

---

## 4. Supabase — authentication

The backend verifies Supabase-issued JWTs. Browsing never needs an account; this is only for contributing.

**4.1** Create a project at supabase.com. Free tier covers 500 MB / 50k monthly active users, comfortably past MVP scale.

**4.2** Project Settings → API. Collect:

```
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=<publishable key, sb_publishable_...>
```

**`SUPABASE_JWT_SECRET` is not on that list, and for a hosted project there is nothing to put there.** Hosted projects sign asymmetrically and publish the public half; no shared secret exists. The backend treats it as optional for exactly that reason. Set it only when pointing at a **self-hosted** Supabase, which does sign HS256 — see 4.4.

**4.3 Configure OAuth providers** (Authentication → Providers). Each needs its own developer registration, and these are the slowest items on this list because they involve external approval:

- **Google** — Google Cloud Console → OAuth 2.0 Client ID. Redirect URI is `https://<ref>.supabase.co/auth/v1/callback`.
- **Apple** — Apple Developer Program, **$99/year**. Needs a Services ID and a signing key. If you want to defer cost, ship with Google + email and add Apple later; nothing in the code assumes all three.
- **Email** — on by default, no setup.

**4.3a Set the client's build variables** in **Settings → Secrets and variables → Actions → Variables** (the Variables tab, not Secrets — see why below). `.github/workflows/pages.yml` and `pr-preview.yml` read them and pass them to the build:

```
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=<anon public key>
AUTH_PROVIDERS=google,email          # optional; defaults to google,email
```

**Variables, not Secrets.** Neither is secret. The anon key is *designed* to be public — Vite inlines it into a JS bundle that anyone can read with view-source, so hiding it in a Secret buys nothing and costs a readable build log, exactly as the comment above `DATA_BASE_URL` in `pages.yml` explains. Both workflows accept either, and warn if you picked Secrets. What is **not** here, and must never be, is `SUPABASE_JWT_SECRET`: that one is real, it belongs only to the backend's runtime environment, and a `VITE_`-prefixed copy would be inlined into a public file.

Prefer the **publishable** key (`sb_publishable_…`) over the legacy `anon` JWT if the project offers both — Supabase deprecates the legacy keys at the end of 2026.

`AUTH_PROVIDERS` must list only providers actually configured in 4.3. A name here whose credentials do not exist is a button that reaches an error page. Leaving all of these unset is safe: the app builds, the map works, and the sign-in controls say the build has no project rather than offering a round trip that cannot finish.

**4.3b Allow the app's own URLs back** (Authentication → URL Configuration). The client redirects to the path it was served from, not the bare origin — a redirect to the origin lands on the project site with the code in its URL and no app there to read it.

That means more than one origin. GitHub Pages serves the app at `/OurHike/app/`, and every PR preview gets a hostname of its own on Cloudflare (3a). Supabase's allow-list takes glob patterns, where `**` matches across `/` and `*` matches a subdomain, so three entries cover everything:

```
https://<user>.github.io/OurHike/**
https://*.<project>.pages.dev/**
http://localhost:5173/**
http://localhost:4173/**
```

Both local ports, because they are different servers: `npm run dev` is Vite on **5173**, and `npm run preview` serves the *built* bundle on **4173**. The second is the one you reach for to check something behaves the same after a production build, which makes it exactly the wrong one to have working differently from the others.

Adding an entry per PR by hand is not a plan, and without a matching entry every provider round trip from a preview ends in a redirect mismatch. Supabase recommends pinning the exact path for the production **Site URL** even so — set that to `https://<user>.github.io/OurHike/app/`.

**4.3c Custom SMTP, before real traffic.** The magic-link sign-in and the account-confirmation email both go through Supabase's built-in sender, which is rate-limited to a handful of messages per hour and is explicitly not for production. Fine for testing; a hiker hitting "email me a sign-in link" and silently getting nothing is not. Configure real SMTP under Authentication → Emails when this stops being a test deployment.

**4.4 The JWT verification method — settled.** This was the open question here, flagged as the one thing that could not be answered without a real project. There is one now, and it answered: a token it issued carries `{"alg": "ES256", "kid": "..."}` — **asymmetric, with the public half published as a JWKS.** A backend verifying HS256 against a shared secret would have returned 401 to every signed-in hiker, with the token, the signature and the secret all perfectly correct.

`backend/app/core/auth.py` now reads the algorithm off the token and verifies accordingly: ES256/RS256 against the project's published keys, HS256 against `SUPABASE_JWT_SECRET`. Both are real — a **self-hosted** Supabase signs HS256, and that is the path OurHikeValues.md leans on for inheritability. Nothing here needs configuring for a hosted project; it works out of the box.

**4.5 Run the config check.** Actions → **Supabase config check** → Run workflow. It reads the live project and reports what only a live project can show:

- whether `SUPABASE_URL` / `SUPABASE_ANON_KEY` are set and valid (and it names the no-`VITE_`-prefix trap, which is a real one — the prefix belongs on the build variable, not the repository variable);
- whether the algorithm the project signs with is one the backend accepts;
- whether every provider in `AUTH_PROVIDERS` is actually enabled in the dashboard — a mismatch there is a button that reaches an error page, and nothing else in the system compares those two lists;
- whether the anon key is the legacy JWT rather than the publishable key.

Read-only, and safe to run any time. It does **not** check the redirect allow-list — the public API does not expose it, so 4.3b stays a manual step.

**4.6 The free plan pauses a project nobody touches — handled.** Supabase pauses a Free plan project that shows too little activity over a rolling seven-day window, and restoring one is a manual click in the dashboard. For a trail app that is a hiker who cannot sign in, on a Saturday, because nothing happened all week — the failure arrives precisely when the project is least used and nobody is looking.

`.github/workflows/supabase-keepalive.yml` does something about it, at 00:50 and 20:50 UTC daily. Nothing to configure: it reads the same `SUPABASE_URL` and `SUPABASE_ANON_KEY` 4.3a already sets.

**What it measures is the part worth knowing.** Supabase's rule is *database* activity, not requests to the project in general ([Project Pausing](https://supabase.com/docs/guides/platform/free-project-pausing)) — so the obvious keepalive, a ping of the health or settings endpoint, does not work. `/auth/v1/settings` is answered by GoTrue from its own configuration and Postgres never hears about it, which would give you a green run every time and a paused project anyway. `backend/supabase_keepalive.py` reads all seven tables over PostgREST instead, because that is a query Postgres actually runs.

**The cadence follows Supabase's own wording**, which is "a few user requests to the database each day over the previous week" — a per-day measure, and the reason this is not the weekly job it started as. The cron reads `50 */20 * * *`, which is as close to "every 20 hours" as cron gets: its hour field repeats within the day, so the runs land 20 hours apart and then 4, not on a steady 20-hour cycle. **The number that matters is the larger gap** — the project is never untouched for more than 20 hours, so every calendar day gets a sweep and one failed or late run cannot open a hole. The test asserts that gap rather than the string, so re-spelling the schedule is safe and lengthening it is not.

Two things about the schedule are worth knowing before either looks like a bug: GitHub runs scheduled workflows **only from the default branch**, so this does nothing until it is on `main`; and GitHub disables schedules in a repository with **no activity for 60 days**, which would take the keepalive with it. After a long quiet spell, check the Actions tab. The thing that actually *guarantees* no pausing is the Pro plan; this is the free-tier answer.

The reads double as the live RLS check — see 5a.

---

## 5. First database migration

The initial migration now exists — `backend/alembic/versions/0f79a37f9358_initial_schema.py` — and, with the row-level-security revision on top of it, now runs against a real Postgres as part of the test suite (`backend/tests/test_migrations.py`: `upgrade head`, RLS flags read back from `pg_class`, `downgrade base`, and `alembic check` for drift). It has still never been applied to *Supabase's* Postgres, which is what this step is.

**This is now two repository secrets, not a command you run.** `.github/workflows/migrate.yml` applies the chain; what is left for you is pasting the connection strings once, the same shape of job as the R2 credentials in 1.3:

```
UA_MIGRATION_DATABASE_URL=postgresql+psycopg://postgres.mksewhxtaqlghtvucfsk:<pw>@aws-0-us-east-1.pooler.supabase.com:5432/postgres
PRODUCTION_MIGRATION_DATABASE_URL=postgresql+psycopg://postgres.fehctqdwdjwryzgxzywc:<pw>@aws-0-us-east-1.pooler.supabase.com:5432/postgres
```

Settings → Secrets and variables → Actions → **Secrets** tab. Get each one from the Supabase dashboard: **Connect** (top of the project) → **Session pooler**, and copy the host and region from there rather than trusting the `aws-0-` above — the prefix and region are per project. The password is set at project creation and is only visible there (Project Settings → Database → Reset database password, if it has been lost), which is the one part of this nothing in the repository can do for itself.

**Two edits to make to what the dashboard gives you**, both of which fail confusingly if skipped, and both of which `check_schema_drift.py --url-only` now refuses by name before any migration runs:

- **`postgresql://` → `postgresql+psycopg://`.** `app/config.py` uses `DATABASE_URL` exactly as given, and SQLAlchemy resolves a bare `postgresql://` to psycopg2, which this backend does not install. The failure is an import error naming a driver nobody chose.
- **Note it is `postgres.<project-ref>` as the username**, not bare `postgres` — the pooler routes by that prefix.

After that: UA follows `main` automatically whenever a revision lands, and production is a **dispatch** — Actions → **Migrate** → Run workflow → target `production`, which runs the UA leg first and then waits on the `production` environment's reviewers. Running `revision --autogenerate` again would produce an empty second migration on top of the existing one; there is nothing to generate.

**Which of the three connection strings, because they look interchangeable and are not.** Supabase's Connect panel offers all of them:

| | Reachable over | For a migration |
|---|---|---|
| Direct — `db.<ref>.supabase.co:5432` | **IPv6** only, unless the project buys the IPv4 add-on | Best target, but **times out from GitHub Actions**, whose hosted runners are IPv4-only. Fine from your laptop if your ISP does IPv6. |
| **Session pooler — `aws-<region>.pooler.supabase.com:5432`** | IPv4 | **This one.** One backend per connection for its whole life, which is the property the direct endpoint was wanted for. |
| Transaction pooler — same host, `:6543` | IPv4 | **Wrong.** A different backend per transaction, so `CREATE TABLE`, `ALTER TABLE` and Alembic's advisory lock stop sharing a session. This is the string the *running app* wants (see 6.2), and the backend is built for it. |

That is why these two settings are `*_MIGRATION_DATABASE_URL` and not the `DATABASE_URL` the running service holds — two different values, both correct for their own job, the same reason the report-photo credentials carry an `R2_PHOTO_` prefix (1.7). Supabase's own guidance is the same: direct connections are best for long-lived sessions, and *"if IPv4 is required for those sessions, Supavisor session mode can be used as an alternative."*

**What still is not automatic, on purpose:** *when*. §8c of [RELEASING.md](RELEASING.md) requires expand-and-contract across two releases because the previous release is still serving traffic during a rollout, so a migration that drops a column breaks it. No workflow can know when that is safe, which is why production is dispatched and reviewed rather than applied on merge. What has been removed is the hand-typed connection string, not the judgement.

**A hand-edit in the dashboard is now noticed within a day.** `.github/workflows/schema-drift.yml` runs `backend/check_schema_drift.py` against both databases at 08:10 UTC daily. It fails only on a database that is at head and *still* differs from the models, or one sitting at a revision this repository has never heard of. Being behind head is normal — that is every moment between a migration merging and you choosing to dispatch it — so it is reported and never failed.

**Checked 2026-08-07, read-only, against the real project (`fehctqdwdjwryzgxzywc`):** it is Postgres **17.6**, and its migration list is **empty** — nothing has been applied, so this step is genuinely still ahead of you rather than half-done. The security advisors report no RLS problems, which follows from there being no tables in `public` yet; re-run them after this step, when the answer means something (5a).

**Read the migration before applying it**, the same way you would review any migration against real data. Several models use `Enum(..., native_enum=False)`. Inspecting the applied schema on a real Postgres for the first time shows what that renders as: a bare `VARCHAR(20)`, with **no** `CHECK` constraint — SQLAlchemy has defaulted `create_constraint` to `False` since 1.4, so the allowed values are enforced in Python and not by the database. Nothing is broken by that (every write goes through the API's pydantic schemas), but it is worth knowing before you assume the database will reject a bad `role` or `visibility`. See `backend/app/models/profile.py`.

Tables it should create: `clubs`, `profiles`, `closures`, `hikes`, `maintainer_assignments`, `reports`, `user_preferences`.

---

## 5a. Confirm the tables are locked down

**This is now part of step 5, not a step after it.** Migration `b3d1c7a94e02` enables Row Level Security on all seven tables in the same transaction that creates them, so there is no window between the schema existing and being locked. Nothing to run by hand; what follows is why, and how to check it really happened.

Supabase serves every table in the `public` schema over PostgREST, at `https://<ref>.supabase.co/rest/v1/`, to anyone holding the anon key. That key is *meant* to be public — it ships inside the client's JS bundle, and no amount of treating it as a secret changes that. What makes publishing it safe is **Row Level Security**, not the key being hard to find. Supabase's own wording: the key is safe to expose *because* RLS is enabled on the database.

Alembic does not enable RLS on its own. It creates plain tables — which is exactly why the revision above exists. Without it, all seven, including `reports`, `profiles` and `closures`, would be readable and writable by anyone who opens the app, views source, copies the key and calls the REST endpoint directly.

**The backend's own auth does not prevent this.** `get_current_user` guards FastAPI's routes, and PostgREST is a second front door into the same database that never passes through FastAPI. Locking the front door does nothing about a second one nobody remembered was there.

The backend keeps working regardless: it connects with the Postgres connection string as the table owner, and RLS does not apply to an owner. **That is also why `force row level security` must never be added** — it applies RLS to the owner too, and would take every endpoint down at once while looking like a tightening.

The tables get RLS with **no policies**, which rejects every anon request. That is the right default here: nothing in the client talks to PostgREST. The client uses Supabase for authentication only and reaches its data through the backend, so there is no query to keep working and nothing to grant. Add policies later if and only if something is built that genuinely needs direct table access.

**A new table is not covered automatically.** Alembic will keep creating plain ones, so a model added later needs its own revision enabling RLS on it. `backend/tests/test_migration_rls.py` fails until it has one — that test is what stops this section from quietly becoming untrue.

**The alternative not taken:** moving the schema out of `public`, since PostgREST only exposes schemas it is configured for. Structurally immune rather than maintained, but it means an Alembic `version_table_schema` change and a search-path decision, so it stays the larger change.

**Verify rather than assume.** Database → Advisors in the dashboard flags every table that has RLS off; it should list none of these seven. Or check from outside with the anon key, which is the actual threat model:

```
curl "https://<ref>.supabase.co/rest/v1/reports?select=*" \
  -H "apikey: <anon or publishable key>"
```

An empty array or a permission error is what you want. Rows are the failure.

**That check now runs itself, twice a day.** The keepalive in 4.6 makes exactly this request against all seven tables, for its own reasons, and fails the run if any of them returns a row. It is the only thing in this repository that asks the question of the *deployed* project rather than of the migrations — `backend/tests/test_migration_rls.py` proves a revision enables RLS, which is a different claim from the live database still having it on, through the front door that is actually open to anyone holding the key in the client bundle.

**While you are in Advisors:** it also flags **leaked password protection as disabled**, and will keep flagging it. That check — Supabase's [HaveIBeenPwned integration](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection) — is **a paid-plan feature, confirmed 2026-08-06 against this project's own dashboard**. It is not a free toggle somebody forgot, so treat that advisor line as known and unactionable rather than as an outstanding task. An earlier version of this section said to go and switch it on; that was wrong, and re-discovering it costs somebody the same trip to the dashboard every time.

It matters at all because email/password is a real sign-in path here — `VITE_AUTH_PROVIDERS` defaults to `google,email`, and `screens/EmailSignIn.tsx` offers a password as the fallback behind its magic-link default. Without the check, an account secured by a password reused from a breached site is exactly as reachable as that password, and these accounts can file `bad_hikers` reports about named people.

**The mitigation that costs nothing is to have no passwords**, not to buy the check — and specifically an emailed **6-digit code**, not the magic link already sent. `EmailSignIn.tsx` keeps the password because a link "means leaving for an email client and coming back, and on a ridge with one bar that round trip is the fragile part"; that is an argument against links, not for passwords. A typed code has the one property the password was kept for — finishing without leaving the app — with nothing to remember, leak or reuse. It also sidesteps a real PWA mechanic: a link tapped in a mail client opens the browser, which on iOS may not share storage with the installed app, so the session can land where the app cannot see it.

See [#279](https://github.com/OurHike/OurHike/issues/279) — `verifyOtp` is already in the installed SDK, so this is an email-template change plus one field, and it deletes more code than it adds. Until it is decided, the paywalled check is a known accepted risk rather than a gap nobody noticed.

---

## 6. Host the backend

The host type is picked and there is no config file to write: `backend/Dockerfile` is the whole of it, and it reads `PORT` from the environment so any Dockerfile host runs it unchanged. [backend/HOSTING.md](backend/HOSTING.md) is the reasoning — **a free scale-to-zero tier, revised 2026-08-09**, after [features/CONDITIONS_DELIVERY.md](features/CONDITIONS_DELIVERY.md) moved the safety read off this service and the always-on requirement that had ruled out every free tier went with it. Fly was the previous answer, nothing was ever deployed to it, and `fly.toml` is gone.

What is left is account work, in this order:

1. **Create the service** on the chosen host, pointed at `backend/`'s Dockerfile. Deploys happen on push from the connected repository; there is no CLI to install.
2. **Set the runtime environment** in the host's own secret store. Never committed, never baked into the image:
   ```
   DATABASE_URL=postgresql://...   # the POOLED string, port 6543
   SUPABASE_URL=...  SUPABASE_ANON_KEY=...
   ```
   `SUPABASE_JWT_SECRET` is **not** in that list for a hosted project — see 4.4. Set it only against a self-hosted Supabase.

   **The pooled string is deliberate here, and the app is built for it.** A transaction pooler hands each transaction whatever backend is free, which breaks anything a driver leaves on a connection — psycopg's automatic prepared statements above all, and that failure appears only in production and only once an endpoint is warm. `backend/app/db/session.py` turns them off, and `backend/tests/test_pooler.py` proves it against a real transaction pooler rather than asserting it. If you use the direct string instead, nothing breaks; you can set `DATABASE_PREPARED_STATEMENTS=true` to get the plan caching back.
3. **Apply the migration** — dispatch **Migrate** (step 5), then **confirm RLS is on** (step 5a — the migration does it, but check rather than assume). Deliberately separate from deploying, and it stays that way now that a workflow does it: a migration is a reviewed action, not something that fires on every container start. Note that the secret this job holds is the **session** pooler (port 5432), while the `DATABASE_URL` above is the **transaction** pooler (6543) — two different values on the same host, both correct for their own job.
4. **Point the client at it** and add its origin to Supabase's allowed redirect URLs (4.3b).

**Expect a cold start.** The service sleeps when idle and the first request after that takes 30-60 seconds. Every remaining caller tolerates it — reports wait in the outbox, moderation is a person at a desk, and closures do not come from here at all any more — with one visible exception: opening a report photo after a quiet period will wait.

**Do not skip step 3 on the grounds that nothing is filed yet.** `POST /closures/{id}/verify` is the only thing that moves a closure to `verified`, and the published artifact carries verified closures and nothing else — so until this service is running and a moderator can act, `conditions/closures.json` is empty by construction rather than because the trail is clear.

**The image has never been built or run against a real Docker daemon.** It follows a standard FastAPI/uvicorn pattern, but "should work" is not "confirmed working" — budget for the first real deploy to surface something no local check could. See [backend/README.md](backend/README.md) for the reasoning behind each choice.

---

## 7. Before you tell anyone about it

**Legal and licensing, all previously flagged:**

- **OpenStreetMap attribution is required by ODbL** and is already rendered by `MapScreen`. Do not remove it. **This stopped being theoretical on 2026-08-03**: the live topographic background ships OSM vector tiles by default, so the credit is load-bearing now rather than pending the Protomaps context basemap. Two further conditions of use came with it, both already in the rendered string — OpenFreeMap's own terms for the hosting, and AWS Terrain Tiles' attribution requirement for the elevation behind the hillshade and contours.
- **opentrail.org licensing is unconfirmed** — [#98](https://github.com/OurHike/OurHike/issues/98) tracks contacting the maintainer. Their water and resupply data is in the build. Worth resolving before a public launch, not after.
- USGS topo, USGS 3DEP and PAD-US are all public domain. ATC data is used with attribution.

**Verify before launch:**

```
cd pipeline && .venv/Scripts/python check_freshness.py
```

Confirms all four upstream sources are unchanged since the last fetch. Exits non-zero if anything is stale **or unverifiable** — an unreachable source reports `UNKNOWN`, never `fresh`.

---

## Things I know are not done, stated plainly

Each of these is now an issue, so that fixing one closes it here too rather than leaving this list to be remembered. The [`v1-mvp`](https://github.com/OurHike/OurHike/labels/v1-mvp) label is the current version of this list.

- **Real OAuth login has never been exercised end to end** ([#92](https://github.com/OurHike/OurHike/issues/92)). The auth code path is fully tested against a mocked Supabase client, but no real Google or Apple sign-in has happened, because that needs credentials only you can create. Expect to find something here.
- **The wrong-way alert's thresholds (90 ft / 12 min / 25 min) are wireframe placeholders** ([#93](https://github.com/OurHike/OurHike/issues/93)), not validated numbers. `HIKER_SAFETY.md` explicitly declines to guess them pending field testing under tree canopy. The mechanism is tested; the numbers are not trustworthy yet, and this is the one feature where a false alarm costs the most.
- **Cumulative ascent needs one real validation run** ([#91](https://github.com/OurHike/OurHike/issues/91)). The over-count is fixed in code: `pipeline/lib/elevation_gain.py` and `client/src/lib/elevationGain.ts` count a climb only once the ground reverses by more than the DEM can resolve, so noise is dropped and real climbs are still counted whole. What has *not* happened is the check — `pipeline/check_elevation_gain.py` compares the result against published figures section by section, and `pipeline/reference/published_gain.json` has no sections in it yet, so the check deliberately fails. It needs a full `export_elevation.py` run plus two or three cited section figures; until then the threshold is derived rather than confirmed.
- **No end-to-end test against real published artifacts** ([#94](https://github.com/OurHike/OurHike/issues/94)). Everything is verified against local files and mocks.
- **Backend has never run against real Postgres outside CI** ([#95](https://github.com/OurHike/OurHike/issues/95)).
- **The report form cannot attach a photo** ([#89](https://github.com/OurHike/OurHike/issues/89)) — no longer silently: the picker is disabled and says so, rather than accepting a file and throwing it away. Making it work needs one decision, R2 or Supabase Storage, and then the client half; the backend half is already built.
- **POIs are never drawn on the map** ([#90](https://github.com/OurHike/OurHike/issues/90)).

Both of the above were found after this list was first written.

## Rough ordering if you want a working map fastest

Steps **1 → 2 → 3** only, and 3 is already automatic. Concretely: finish R2 (API token, secrets, CORS, public access, publish), set the `DATA_BASE_URL` repository variable, then redeploy Pages — and you have the offline topo map, trails, POIs and elevation profile working on a phone, with no accounts, no backend and no database. Everything in 4–6 exists to support contributing, which nobody can do until people are using the map anyway.
