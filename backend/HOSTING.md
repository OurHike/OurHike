# Where the backend runs, and what else could

`backend/README.md`'s Deployment section says the backend targets Fly.io. This document is
why, what the alternatives cost, and what would make the answer different. README.md owns
the steps for carrying the choice out; this owns the choice.

## What this document is not

**[#393](https://github.com/OurHike/OurHike/issues/393) owns the money.** It holds the
whole running-cost model — per-user cost, the curve at 200K and 1MM MAU, the three
architectural properties holding ~97% of the bill down, and a "Non-options, considered and
rejected" list that already covers rewriting onto Workers or Edge Functions and deleting
the backend in favour of PostgREST. None of that is restated here.

Its single most important finding for this document, and the reason this one stays short:

> The backend host is ~3% of the bill at 1MM. Authentication is ~75%. Any effort spent
> choosing between Fly, Cloudflare Workers and Supabase Edge Functions is effort spent on
> the wrong line by a factor of about thirty.

So **this document answers a different question than #393 does** — not "what does the host
cost" but "is Fly a fourth tool worth keeping up with." That question was asked
independently, it is a fair one, and the answer is not the same shape as the money answer.

**Prices below were gathered 2026-08-08 from secondary sources**, with the same caveat
#393 records: the sandbox egress proxy blocks `fly.io`, so its rate card could not be read
directly. Cloudflare's numbers are the exception — they came through its documentation MCP
server and are first-party.

## What Fly actually costs us today

Worth measuring before replacing it, because the intuition and the measurement disagree.

- **`backend/fly.toml`** — 30 lines, of which 12 are comment explaining the
  `min_machines_running = 1` tradeoff. The mechanical part is about 15 lines.
- **`flyctl`** — not installed anywhere in this repository and invoked by no workflow;
  `grep -rl fly .github/workflows/` returns nothing. Deploys are a human running
  `fly deploy` by hand, which is the gap
  [#424](https://github.com/OurHike/OurHike/issues/424) exists to close.
- **A fourth place secrets live**, alongside GitHub Actions, Supabase and Cloudflare. This
  is the real recurring cost — and every alternative below has it too.
- **Money: roughly $1.94–$2.02/month** for the `shared-cpu-1x` / 256 MB machine, no plan
  fee on pay-as-you-go. Matches the ~$2/month #393 already records as the pre-launch
  position.

**Nothing has been deployed to it yet.** No Fly account exists, `fly deploy` has never
run, and `fly.toml`'s `app = "ourhike-backend"` is still a placeholder. This is not a
migration question — it is a commitment not yet made, which is the cheapest possible
moment to ask about it.

## The constraint that rules out every free tier

`fly.toml` pins `min_machines_running = 1` because a cold start on the first request after
idle is bad for something safety-adjacent. Worth being precise about how bad, because the
precision is what decides whether the free tiers are on the table.

The client is offline-first: map, downloads and the reporting flow all work with the
backend absent, and a written report queues in the outbox with its authored timestamp
rather than being lost. What a cold start delays is the **closures read** — `App.tsx:508-510`
calls closures "the half a hiker walks into," and holds them as `ClosureSummary[] | null`
with the null case degrading to no closure warnings rather than an error.

So a cold start is not an outage. It is a window of tens of seconds in which a hiker who
opens the app sees no closure warnings and **is not told that is why**. That is a modest
but real safety argument for always-on, and it is why the $0 rows below are listed as ruled
out rather than shortlisted.

## Can a vendor we already have host it?

The appealing answer — no fourth vendor at all. #393 already rejects the rewrites on cost
grounds. What follows is the *mechanical* reason they are not close calls, which is new,
and which matters more than the money for a question about tooling.

**GitHub Pages** serves static files. No server. Not a candidate.

**Cloudflare Workers (Python) cannot run this backend at all** — this is a hard blocker,
not a cost tradeoff. Python Workers execute under Pyodide, a CPython port to WebAssembly,
where packages needing C extensions are unavailable and cannot be made available;
`psycopg` is named explicitly in that category. `requirements.txt` pins `psycopg==3.3.4`
with `psycopg-binary`, plus `cryptography==50.0.0` under PyJWT for ES256 verification. The
documented Postgres paths on Workers — Hyperdrive, `cloudflare:sockets` — are JavaScript
APIs.

**Cloudflare Containers can run the image, and still make the tooling worse.** A container
is driven by a Durable Object: the `Container` class from `@cloudflare/containers` extends
`DurableObject`, and Wrangler's configuration reference states you *must* also define a
Durable Object whose `class_name` matches the container config. Replacing `fly.toml` means
adding a `wrangler.jsonc`, a Worker entrypoint and a Durable Object subclass — three
TypeScript files, in a Python service, in a repository where the client is currently the
only thing that speaks TypeScript. For a question whose premise is "one more tool and
config to keep up with," that is the wrong direction.

It also costs more, which is worth recording because #393 costed Workers but not
Containers. Container allowances come **with the $5/month Workers Paid plan** — the free
plan's container allowance is listed as N/A — and we are not on it: there is no `wrangler`
config anywhere in the tree, and R2 is reached over its S3-compatible API with boto3, which
needs no Workers plan. Always-on for a month (730 h) on `lite` (1/16 vCPU, 256 MiB, 2 GB
disk):

| | calculation | cost |
| --- | --- | --- |
| Memory | (0.25 GiB × 730 h − 25 GiB-h included) × 3600 × $0.0000025 | $1.42 |
| Disk | (2 GB × 730 h − 200 GB-h included) × 3600 × $0.00000007 | $0.32 |
| CPU | billed on *actual* utilization since Nov 2025; an idle FastAPI stays inside the 375 vCPU-min allowance | ~$0.00 |
| Workers Paid | required for any container allowance at all | $5.00 |
| | | **~$6.74** |

Against Fly's ~$2. And the sleep model runs against the always-on constraint: `sleepAfter`
is a core property of the `Container` class, charges "stop after the container instance
goes to sleep," and keeping one awake means fighting the platform's default with
heartbeats rather than setting `min_machines_running = 1`.

**Supabase Edge Functions** run Deno. The backend is 3,615 lines of Python behind 6,999
lines of pytest (measured 2026-08-08; #393 quotes the smaller figures it measured the day
before). Not a port. #393's rejection stands on cost; the language boundary is why it is
not even close.

## Swapping Fly for a different PaaS

If a fourth vendor is unavoidable, is there a better one? Always-on, 256–512 MB class,
~730 h/month.

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

**The original comparison was not apples to apples.** `backend/README.md` used to say Fly
was "picked over Render specifically to avoid Render's free-tier sleep-on-idle behavior" —
free Render against paid Fly. Render's $7 Starter tier does not sleep. The honest
comparison is $7 against $2, and Fly still wins it. The old sentence is corrected rather
than deleted because the conclusion survived the correction; if it had not, this document
would say so.

**Nothing here is a reduction.** Every row is a fourth vendor with a fourth place for
secrets. Render and Railway can carry zero config files, which is a real if small win over
`fly.toml` — bought at roughly 3.5× and 2.5× the money, and by moving deploy configuration
into a dashboard where no pull request can review it. For a repository that writes 12 lines
of comment explaining one setting, that trade is backwards.

## Recommendation

**Keep Fly.** Every alternative examined is more expensive, more configuration, in a
language this service is not written in, or a free tier ruled out by a constraint chosen
deliberately. It is the cheapest option on the list by roughly 2.5×, and the part that
feels like overhead — `fly.toml` — is 15 mechanical lines no workflow depends on.

**The fourth vendor is not Fly's fault.** GitHub, Cloudflare and Supabase do not host a
long-running Python process between them. Anything running FastAPI + psycopg is a new
account somewhere. That is a fact about the stack, not about Fly.

**And the tooling answer agrees with #393's money answer, by a different route.** #393 says
the host is the wrong line to optimize because it is 3% of the bill. This says it is the
wrong line to optimize because every move costs more configuration than it removes. Two
independent arguments, same conclusion — which is the strongest reason to stop asking.

**What is worth doing instead:**

1. **Make the client say when the backend is unreachable.** It cannot currently
   distinguish "no closures" from "could not reach the backend" — the same ambiguity
   [#249](https://github.com/OurHike/OurHike/issues/249) records for maintainer
   assignments, applied to the one read a hiker walks into. It is a correctness fix on its
   own terms, and it is the precondition that would make a scale-to-zero host thinkable,
   which is the only path that deletes the line item rather than moving it.
2. **Leave `fly.toml` alone**, and let [#424](https://github.com/OurHike/OurHike/issues/424)
   move the deploy off a laptop as planned. Reopening the host choice costs more than the
   file does.

**Revisit if:** Cloudflare Containers gain a first-class always-on mode with no Durable
Object wrapper; or the client learns to show an unreachable-backend state, making the free
tiers viable; or real traffic shows the always-on machine idle enough that the constraint
was never worth $2.
