# Where the backend runs

**Decided 2026-08-09: a free scale-to-zero host, and no Fly.** The reasoning below is a
revision — the first version of this document concluded the opposite, and said so on
grounds that have since expired.

## What changed, and why the old answer stopped being right

The original argument, written 2026-08-08, was: the backend serves closures, a hiker walks
into a closure, so a cold start on the first request after idle is unacceptable. That made
`min_machines_running = 1` non-negotiable, which ruled out every free tier, which left Fly
as the cheapest of what remained at ~$2/month.

Every step of that holds. The premise does not, any more.

[features/CONDITIONS_DELIVERY.md](../features/CONDITIONS_DELIVERY.md) moved the safety read
off the backend entirely: verified closures are published to R2 daily and the client reads
them from there, falling back to a live `GET /closures` only when it can. **Nothing a hiker
reads on the trail DEPENDS on this service now** - the live closure refresh still touches
it when it can reach it, which is what "falling back" means, but the R2 baseline is what
the safety read stands on and it survives this service being down (#658 tightened this
sentence, which used to claim nothing touches it). The cold-start argument was about
closures, and closures left.

That was written into this document's own "Revisit if" clause at the time. This is that
revisit.

## What the backend is still for, because it is not nothing

Worth being exact, because "the read path moved" is easy to hear as "the backend is
optional". It is not:

- **Filing a report.** The client queues them in an offline outbox; the outbox needs
  somewhere to flush to.
- **Moderation** — and this one is load-bearing in a way that is easy to miss.
  `POST /closures/{id}/verify` is the **only** thing that moves a closure to `verified`,
  and the published artifact contains verified closures and nothing else. With no backend
  running anywhere, nothing is ever verified, and `conditions/closures.json` is empty
  forever. **The static read path depends on this service existing** — just not on a hiker
  being able to reach it.
- **Photo presigning**, which needs the R2 signing key and so cannot live on a phone.
- **Per-user state**: profiles, preferences, hikes.

## Why that makes the answer a free tier

Every one of those is latency-tolerant, and none is on a trail:

| | tolerates a cold start because |
| --- | --- |
| Report submission | the outbox already holds it, with its authored timestamp |
| Moderation | it is a trusted person at a desk, doing deliberate work |
| Photo load | it is a picture, not a warning — a wait is a wait |
| Preferences | same |

So the constraint that ruled out the $0 rows is gone, and the comparison that produced
"Fly, ~$2" was answering a question nobody is asking any more. The costed table from the
first version still stands on its own terms and is preserved below for whoever revisits
this again; it simply no longer decides anything, because the row that wins is now one it
had excluded.

**Render's free tier**, specifically:

- **$0**, and no card.
- **No configuration file.** A Dockerfile is all it needs, and `backend/Dockerfile` is
  already host-agnostic — it reads `PORT` from the environment for exactly this reason.
- **No CLI.** Deploys happen on push, from the connected repository. `flyctl` was never
  installed here or invoked by any workflow anyway; the deploy was always a person at a
  laptop.
- **Sleeps after 15 minutes idle**, which is the property that used to disqualify it and
  is now simply true and fine.

That is one fewer config file, one fewer CLI, and one fewer payment relationship than the
Fly answer — which is what the original question asked for and what the original answer
could not give.

## What this costs, stated plainly

**A cold start of roughly 30–60 seconds on the first request after idle**, and the honest
worst case is a hiker opening a report photo and waiting for it. That is a real
degradation and it is the price. It is paid by a picture rather than by a warning, which
is the whole reason it is affordable now and was not before.

**Free tiers are withdrawn, throttled and changed.** This is a $0 dependency, not a
contract. If Render's free tier goes away, the fallback is any other Dockerfile host —
which is the point of keeping nothing Fly-shaped, or Render-shaped, in the repository.

**Deploy configuration lives in a dashboard rather than in a reviewable file.** The first
version of this document counted that against Render, and it was right to: a setting
nobody can see in a pull request is a setting that drifts. `render.yaml` is the answer if
that becomes a problem; it is deliberately not being added pre-emptively, because a config
file nobody needs yet is the thing this change is removing.

## Which build is serving, and why the release order depends on it

**Render tracks `main`, so the backend redeploys on every merge** — the maintainer's
answer, 2026-08-28. Nothing in this repository can show that (it is the dashboard setting
above), which is exactly why it is written here: it is load-bearing for release ordering
and invisible to everyone who has not seen the dashboard.

What it buys is that **the backend is always ahead of the app**. The web build deploys to
production on the *tag* ([../RELEASING.md](../RELEASING.md) §12) and app-store builds are
slower still, while the backend is already carrying whatever merged. So a client never
meets a backend older than itself, and the skew that would actually hurt cannot happen in
that direction.

That the direction matters is not hypothetical. A v1.2.0 client against a v1.1.1 backend
would have its whole preferences document rejected — `PreferencesIn` is `extra="forbid"`,
so one unknown field 422s the PUT, and `preferencesSync.ts` logs and carries on, leaving
sync silently dead rather than degraded. A field note carrying a new `observation` member
would 422 too, and the outbox marks such a note unsendable *for the life of the build*
(`outbox.ts` — "a 422 here would drop those notes into the outbox forever"). Both are
quiet, and neither would show up in a smoke test.

**If the tracking setting ever changes, the release train gains a step**: deploy the
backend, confirm `/openapi.json` carries the new fields, and only then publish the draft.
Until then the ordering holds by construction and the train stays four buttons.

## What was removed

`backend/fly.toml` is deleted. Nothing was ever deployed to Fly — no account was created,
`fly deploy` never ran, and `app = "ourhike-backend"` was a placeholder to the end — so
this removes a plan, not a service. `backend/Dockerfile` is unchanged and is the portable
artifact any of these hosts consume.

[#424](https://github.com/OurHike/OurHike/issues/424), the attempt to deploy Fly from CI,
was already closed as not planned; [#425](https://github.com/OurHike/OurHike/pull/425) was
closed unmerged. This finishes that direction rather than starting a new one.

## The costed comparison, preserved

Gathered 2026-08-08 from secondary sources; the sandbox egress proxy blocks `fly.io`, so
its rate card could not be read directly. Cloudflare's figures came first-party through
its documentation MCP server. **These numbers priced an always-on machine and are kept for
the reasoning, not the ranking** — the always-on column is the one that stopped mattering.

| Host | Always-on | Scales to zero | Config in repo |
| --- | --- | --- | --- |
| **Render free** | — | **yes, 15 min** | **none** |
| Koyeb free | — | yes, 1 h | none |
| Fly.io | ~$1.94–2.02 | yes, at `min_machines_running = 0` | `fly.toml` |
| Render Starter | $7.00 | no | none |
| Railway Hobby | $5.00 floor | no | none |
| DigitalOcean App Platform | ~$5.00 | no | app spec |
| Google Cloud Run | ~$5–10 pinned | yes | + IAM, Artifact Registry, `gcloud` |
| Hetzner CX22 | ~€3.79–4.35 | no | a whole OS to run |

**The two consolidation options remain impossible, and that has not changed:**

- **Cloudflare Python Workers cannot run this backend at any price.** Python Workers
  execute under Pyodide, where C extensions are unavailable and cannot be made available;
  `psycopg` is named explicitly in that category, and `requirements.txt` pins it along
  with `cryptography`. The documented Postgres paths on Workers are JavaScript APIs.
- **Cloudflare Containers add configuration rather than removing it.** A container is
  driven by a Durable Object, so replacing one config file means adding a
  `wrangler.jsonc`, a Worker entrypoint and a DO subclass — three TypeScript files in a
  Python service — and container allowances require the $5/month Workers Paid plan this
  project is not on.
- **Supabase Edge Functions run Deno.** The backend is Python.

So a fourth vendor is unavoidable for as long as this service exists. That is a fact about
the stack rather than about any host, and it is why the choice came down to which fourth
vendor costs least to keep up with.

## Revisit if

The free tier is withdrawn or starts suspending the service; or the cold start turns out
to bite something that is not a photo; or the backend shrinks far enough that
PostgREST-with-policies plus a function for presigning genuinely covers it — noting that
[#393](https://github.com/OurHike/OurHike/issues/393) rejected that once already, because
`_visible_to` has drifted before when it lived in two places.
