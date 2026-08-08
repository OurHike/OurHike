# Where the backend runs, and what else could

`backend/README.md`'s Deployment section says the backend targets Fly.io. This document is
why that choice was re-examined, what the alternatives actually cost, and what the answer
came out as. It owns the hosting decision; README.md owns the steps for carrying it out.

**Prices were gathered 2026-08-08 from secondary sources.** The sandbox's egress proxy
blocks `fly.io` and `developers.cloudflare.com`, so the vendor pricing pages could not be
read directly — except Cloudflare's, which came through its documentation MCP server and
is therefore first-party. Everything else is search-result reporting of a vendor's rate
card, not the rate card. Re-check any number before it decides a bill.

## The question

Fly is a fourth vendor, behind GitHub, Cloudflare and Supabase, and it is the only one of
the four carrying a config file in this repository. Is it worth keeping?

## What Fly actually costs us today

Worth measuring before replacing it, because the intuition and the measurement disagree.

- **`backend/fly.toml`** — 30 lines, of which 12 are comment explaining the
  `min_machines_running = 1` tradeoff. The mechanical part is about 15 lines.
- **`flyctl`** — not installed anywhere in this repository, not invoked by any workflow.
  `grep -rl fly .github/workflows/` returns nothing. Deploys are a human running
  `fly deploy` by hand.
- **A fourth place secrets live** — `fly secrets set`, alongside GitHub Actions secrets,
  Supabase's dashboard, and Cloudflare's R2 tokens. This is the real recurring cost, and
  it is a cost every alternative below also has.
- **Money: roughly $1.94–$2.02/month** for the `shared-cpu-1x` / 256 MB machine, with no
  plan fee on pay-as-you-go.

**Nothing has been deployed to it yet.** No Fly account exists, `fly deploy` has never
run, and `fly.toml`'s `app = "ourhike-backend"` is still a placeholder. So this is not a
migration question — it is a question about a commitment not yet made, which is the
cheapest possible moment to ask it.

## The constraint that drives everything

`fly.toml` pins `min_machines_running = 1` because a cold start on the first request after
idle is bad for something safety-adjacent. That is a real constraint and it is what makes
every free tier on the list unusable — but it is worth being precise about how bad, because
the precision changes which options are on the table.

The client is offline-first. Map, downloads and the reporting flow all work with the
backend entirely absent, and a written report queues in the outbox with its authored
timestamp rather than being lost. What a cold start delays is the **closures read** —
`App.tsx:508-510` calls closures "the half a hiker walks into," and holds them as
`ClosureSummary[] | null` with the null case degrading to no closure warnings rather than
an error.

So a cold start is not an outage. It is a window of tens of seconds in which a hiker who
opens the app sees no closure warnings and is not told that is why. That is a modest but
genuine safety argument for always-on, and it is the reason the free tiers below get ruled
out rather than shortlisted.

## Option A: consolidate onto a vendor we already have

The appealing answer — no fourth vendor at all. All three fail, and it is worth writing
down why so the question does not get reopened from scratch.

**GitHub Pages** serves static files. There is no server to run. Not a candidate.

**Cloudflare Workers (Python)** cannot run this backend. Python Workers execute under
Pyodide, a CPython port to WebAssembly, and packages requiring C extensions are
unavailable and cannot be made available — `psycopg` is named explicitly in that
category. `requirements.txt` pins `psycopg==3.3.4` with `psycopg-binary`, plus
`cryptography==50.0.0` under PyJWT for the ES256 verification. The documented Postgres
paths on Workers — Hyperdrive, `cloudflare:sockets` — are JavaScript APIs. Getting there
means not porting the backend but rewriting it.

**Cloudflare Containers** can run the image, and is the option that looks like
consolidation right up until you count the pieces. A container is driven by a Durable
Object: the `Container` class from `@cloudflare/containers` extends `DurableObject`, and
Wrangler's own configuration reference states you *must* also define a Durable Object
whose `class_name` matches the container config. So replacing `fly.toml` means adding a
`wrangler.jsonc`, a Worker entrypoint, and a Durable Object subclass — three files in
TypeScript, in a Python service, in a repository whose client is the only thing that
currently speaks TypeScript. That is more config to keep up with, not less.

It also costs more. Containers are billed per 10ms of running time against allowances
that come **with the $5/month Workers Paid plan** — the free plan's container allowance is
listed as N/A. We are not on Workers Paid today: there is no `wrangler` config anywhere in
the tree, and R2 is reached over its S3-compatible API with boto3, which needs no Workers
plan at all. Always-on for a month (730 h) on the `lite` instance type
(1/16 vCPU, 256 MiB, 2 GB disk):

| | calculation | cost |
| --- | --- | --- |
| Memory | (0.25 GiB × 730 h − 25 GiB-h included) × 3600 × $0.0000025 | $1.42 |
| Disk | (2 GB × 730 h − 200 GB-h included) × 3600 × $0.00000007 | $0.32 |
| CPU | billed on *actual* utilization since Nov 2025; an idle FastAPI stays inside the 375 vCPU-min allowance | ~$0.00 |
| Workers Paid | required for any container allowance at all | $5.00 |
| | | **~$6.74** |

Against Fly's ~$2. And the sleep model runs against the grain of the always-on
constraint: `sleepAfter` is a core property of the `Container` class, charges "stop after
the container instance goes to sleep," and keeping one awake indefinitely means fighting
the platform's default with heartbeats rather than setting `min_machines_running = 1`.

**Supabase Edge Functions** run Deno. The backend is 3,615 lines of Python across 39
files, eight routers, seven SQLAlchemy models and two Alembic migrations. Not a port.

There is a narrower version of this idea worth naming: `enable_row_level_security` locked
the tables against PostgREST, and *unlocking* them with real policies would let Supabase's
own REST front door serve the plain CRUD without any backend at all. But moderation,
warning escalation, wrong-way detection, hike direction and the R2 photo signing are
genuine application logic with tests behind them, and PostgREST does not host logic. It
would shrink the backend, not remove it, and the remaining piece still needs somewhere to
run.

## Option B: swap Fly for a different PaaS

If a fourth vendor is unavoidable, is there a better fourth vendor? Costs are for an
always-on service in the 256–512 MB class, ~730 h/month.

| Host | Monthly | Sleeps? | Config in repo | Notes |
| --- | --- | --- | --- | --- |
| **Fly.io** (current) | **~$1.94–2.02** | no, `min_machines_running = 1` | `fly.toml`, 30 lines | cheapest on the list |
| Render Starter | $7.00 | no | none required | Hobby workspace is $0; deploys on git push |
| Railway Hobby | $5.00 floor | no | none required | $5 plan fee includes $5 usage; ~256 MB lands inside it |
| DigitalOcean App Platform | ~$5.00 | no | app spec | Basic/Professional tiers were removed; re-check current shape |
| Google Cloud Run (`min-instances=1`) | ~$5–10 | no, when pinned | + IAM, Artifact Registry, `gcloud` | free tier offsets some; much larger surface |
| Hetzner CX22 | ~€3.79–4.35 | no | none | a bare VPS — OS patching, TLS, Docker, systemd are yours |
| Koyeb free | $0 | **yes, after 1 h idle** | none | scale-to-zero cannot be disabled on free |
| Render free | $0 | **yes, after 15 min idle** | none | the exact behavior Fly was chosen over |

Two things fall out of that table.

**The original comparison was not apples to apples.** `backend/README.md` says Fly was
"picked over Render specifically to avoid Render's free-tier sleep-on-idle behavior" —
free Render against paid Fly. Render's $7 Starter tier does not sleep. The honest
comparison is $7 against $2, and Fly still wins it.

**Nothing here is a reduction.** Every row is a fourth vendor with a fourth place for
secrets. Render and Railway can carry zero config files in the repository, which is a real
if small win over `fly.toml` — paid for at roughly 3.5× and 2.5× the money respectively,
and by moving deploy configuration into a dashboard where it is not reviewable in a pull
request. For this repository, which writes down the reasoning behind a 30-line file, that
trade is probably backwards.

## Option C: drop the always-on requirement

The only option that genuinely removes a vendor's cost rather than moving it. Render free
or Koyeb free at $0, accepting a cold start on the first request after 15 or 60 minutes
idle.

Not recommended, but for a narrower reason than "safety." The client already degrades
correctly when the backend is unreachable — the null-closures path is written and tested.
What it does *not* do is distinguish "no closures exist" from "could not reach the
backend," which is the same ambiguity [#249](https://github.com/OurHike/OurHike/issues/249)
records for maintainer assignments. Until a hiker can tell those apart on screen, a host
that is predictably unreachable for the first request after idle is buying $2/month with a
silence the app cannot explain. Fix the ambiguity first and this option gets much more
attractive — it would then be a visible "reconnecting" state rather than a blank map.

## Recommendation

**Keep Fly.** Not because it is exciting, but because every alternative examined is either
more expensive, more configuration, in a language this service is not written in, or a
free tier ruled out by a constraint we chose deliberately. It is the cheapest option on
the list by roughly 2.5×, and the thing that feels like overhead — `fly.toml` — is 15
mechanical lines that no workflow depends on.

**The fourth vendor is not really Fly's fault.** Cloudflare, Supabase and GitHub simply do
not host a long-running Python process between them, and that is a fact about the stack
rather than about Fly. Anything that runs FastAPI + psycopg is a new account somewhere.

**What is worth doing instead**, if the goal is less to keep up with:

1. **Make the client say when the backend is unreachable** (the #249 ambiguity, applied to
   closures). This is the highest-value item here — it is a correctness fix on its own
   terms, and it is the precondition that would make Option C real, which is the only path
   that actually deletes the line item.
2. **Leave `fly.toml` alone.** Reopening this costs more than the file does.

**Revisit if:** Cloudflare Containers gain a first-class always-on mode that does not need
a Durable Object wrapper; or the backend shrinks enough that PostgREST-with-policies plus
a handful of Edge Functions covers it; or real traffic shows the always-on machine is idle
enough that the constraint was never worth $2.
