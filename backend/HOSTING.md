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

- **$0** inside the free allowances, and no card needed to start. One is on file by the
  maintainer's choice of 2026-10-27; "What a stranger can do to the free tier" says why.
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

**What the free tier does at its limits, read from Render's own docs on 2026-10-23**
(`render.com/docs/free`, `/outbound-bandwidth`, `/deploys`), because each one bears on
something below:

- **750 free instance hours a month, shared by the whole workspace.** A sleeping service
  uses none, and one that never sleeps uses about 730. A UA backend on the free tier as
  well would share the same 750, so the day production stays awake all month is the day
  it moves to Starter and UA stays free.
- **5 GB of outbound bandwidth a month on the Hobby workspace, then $0.15/GB.** With no
  card on file, going past it suspends every free service for the rest of the month
  rather than billing. That was the ceiling
  [#395 — Put a ceiling on the bill before the app is public](https://github.com/OurHike/OurHike/issues/395)
  first chose. The maintainer then chose a card (poll, 2026-10-27), so past 5 GB is
  billed instead; "What a stranger can do to the free tier" says what that trades. Either
  way it is why the next section exists: as wired before it, the hikers' own reads would
  reach this limit.
- **The pre-deploy command is for paid instances only.** That settles one of the two
  remedies the migration-skew section below weighs: on the free tier there is no deploy
  hook, so the ordering discipline is the remedy for as long as the service is free.
- **A free service may be restarted at any time**, and it spins up in about a minute.

## In front of it: Cloudflare, with three reads cached at the edge

**Decided by the maintainer, by poll, on 2026-10-23, while planning #600 — Nothing owns standing up the production backend, and the image has never run against a real Docker daemon.** The API is served at
`api.ourhike.org`, a proxied CNAME in the `ourhike.org` zone, which is already on
Cloudflare. Three anonymous reads are cached there for five minutes: `GET /closures`,
`GET /reports` and `GET /disputes`. Everything else passes straight through to Render.
[app/core/edge_cache.py](app/core/edge_cache.py) is the code and its header is the reasoning
for each rule; this section is what the cache costs and why it is here.

**Why it is here: every hiker's app reads this service, account or not.**
`client/src/lib/useConditions.ts` asks for `GET /closures`, `/reports`, `/field-notes` and
`/disputes` when the app opens with signal, again every hour while it stays open, and again
on return after five minutes away. So the live tier's traffic grows with every hiker, not
only with those who sign in. "Nothing a hiker reads on the trail depends on this service"
(above) is true of the safety read and was never true of the bill. The cost model behind
the decision put the point where those reads use up Render's and Supabase's free 5 GB a
month at about 2,750 hikers. That figure is reasoned from usage inputs nobody has measured
(how often the app opens with signal, how many bytes each open reads); the two 5 GB limits
are the vendors' own. With the cache, this service sees at most one request per URL per
edge location every five minutes for the anonymous reads, however many hikers ask. Two
things stretch "per URL": Cloudflare keeps a separate copy per `Origin` header value (the
app's own two origins, in practice), and signed-in reads, below.

**What it costs: $0,** on Cloudflare's free plan, in a zone that already exists: one CNAME,
one cache rule, one WAF rule and the one rate-limiting rule the plan allows, all in
[LAUNCH_CHECKLIST.md](../LAUNCH_CHECKLIST.md) §6. Gzip is on in `app/main.py` for the same
bill, since it cuts the bytes Render counts.

**What it leaves uncached, and what that costs.** `GET /field-notes` and
`GET /waypoints/{poi_id}/photos` embed presigned photo URLs that expire five minutes after
signing, and `app/core/photos.py` rules out a shared copy of either. So the field-note read
still reaches this service once per hiker per open. The same model puts Supabase Free's
5 GB of egress at about 9,500 hikers a month with field notes uncached, against about
130,000 with all four reads cached. Both figures are @unvalidated: they assume field notes
are a quarter of the bytes a hiker's app reads, and nothing has measured that. The
maintainer chose this over caching field notes for 60 s (poll, 2026-10-27), on condition of
the follow-up that removes the trade: a stable photo route like reports already have, so the
list carries no signature, which is
[#1905 — GET /field-notes embeds 5-minute signed photo links, so the edge cache cannot keep it and every hiker's app open still reaches the API](https://github.com/OurHike/OurHike/issues/1905).

**Signed-in reads are the open question.** The app sends a signed-in hiker's token on all
three shared reads (`readFetch` in `client/src/lib/api.ts`), and the API answers any request
carrying one `private, no-store`. Cloudflare's docs say it does not store that answer. They
do not say outright whether it answers such a request from the anonymous copy it already
holds, and §6 step 7's last check finds out, but they point to yes: the default cache key
has no `Authorization` in it, and only Enterprise can add a header to it
(developers.cloudflare.com/cache/how-to/cache-keys), and `Authorization` is listed among
the reasons not to store a response, not among the reasons to skip the lookup
(developers.cloudflare.com/cache/concepts/cache-responses; both read 2026-10-29).

If it does, nothing private leaks, because the anonymous copy holds less, but a reporter's
own report is missing from every signed-in read answered from that copy, and the 300 s TTL
does not bound it. Only anonymous reads refill the copy, and an anonymous caller is given
only public reports that are verified or resolved (`list_reports` in
`app/routers/reports.py`). So wherever anonymous reads keep the copy warm, a report waiting
in the queue stays missing until a moderator verifies it, and one dismissed is never in the
copy at all. The app then says the list it read does not hold them: "sent under a different
account, or read before they went" (`client/src/screens/YourReports.tsx`). That is reasoned
from the code and those docs; there is no live zone to watch it on yet. If it does not,
every signed-in hiker's reads reach this service, so the origin carries the signed-in share
of all reads (1 in 5 hikers sign in, in the cost model, @unvalidated) on top of the edge's
misses. Either way the fix is a client change, so it ships with a release, and it is what
removes both:
[#1916 — A signed-in hiker's app sends its token on the three edge-cached reads, so they either skip the cache or hide the hiker's own queued report](https://github.com/OurHike/OurHike/issues/1916).

**What would undo it.** Narrowing CORS from `*` (a shared copy can carry only one answer),
or a cache rule that stops honouring the origin's `Cache-Control`. The second is the one to
watch, and a `HIT` does not show it: a rule that ignores the origin's header still answers
`HIT`, and Cloudflare passes the origin's `Cache-Control` on under it ("the original
`Cache-Control` header passes downstream from our edge even if Edge Cache TTL overrides are
present", developers.cloudflare.com/cache/concepts/cache-control, read 2026-10-29). The copy
itself shows it. `pipeline/check_deployment.py` reads `GET /closures` every day the way a
hiker's browser does, with the app's own `Origin`, and fails on a copy older than the 300 s
its `s-maxage` allows (its `Age`), on `cf-cache-status: STALE` or `UPDATING` (an expired
copy, which `s-maxage` rules out), and on any `Cache-Control` but the API's anonymous one (a
stored signed-in answer carries `private, no-store`). It misses such a rule while the copy
it reads is under 300 s old, which on a quiet zone is whenever its own first read filled
it. §6 step 7 runs the same reads once by hand.

## What a stranger can do to the free tier

**The 5 GB a month is a ceiling a stranger can reach on purpose,** and the edge cache does
not stop them. It only takes the anonymous hikers' reads off the meter. Every route the
edge does not keep still answers each request from Render. `/openapi.json` is 59,426 bytes
gzipped (257,105 raw, measured 2026-10-27 against this branch), so about 84,000 requests
spend Render's month, and `GET /field-notes` grows with the season. The cache's own key can
be varied too: Cloudflare keeps a copy per `Origin` value and per a few other headers, and
only Enterprise can change that. §6 closes the cheap routes round it: the `onrender.com`
address off, any query string on the three cached paths refused, and one address held to 50
requests in 10 seconds on the API's own paths. The plan's rate limit cannot test the
hostname, so it names the API's paths rather than all of them: a rule over every path would
also count `data.ourhike.org`, where every hiker's map downloads come from. Many addresses
at once still get through.

**What reaching it costs depends on one setting: a card on Render. The maintainer chose
the card, by poll on 2026-10-27.**
- **No card on file** (not chosen): Render spins the workspace's services down until the
  next month (`render.com/docs/outbound-bandwidth`). Hikers keep the map, and the published
  baseline still carries the closures already verified. But reports wait in outboxes, and
  no new closure can be verified, so `conditions/closures.json` gains nothing until the
  next month. On the safety read, that is the cost.
- **A card on file** (chosen): the same stranger costs $0.15 per GB past the first 5. That
  is arithmetic, not a forecast: 100 GB is $15, and the total is bounded only by their
  patience. Render's bandwidth page names no spend limit and no alert (read 2026-10-27).

**With the card, nothing in this repository notices.** The API stays up, so `/health` and
the edge check in **#738 — Deployed app reachability** stay green while the bill grows. The
workspace's Billing page in Render is where it shows, and LAUNCH_CHECKLIST.md §6 step 8
asks for a weekly look there until an alert exists. That alert belongs to **#395 — Put a
ceiling on the bill before the app is public**.

## Which build is serving, and why the release order depends on it

**Render is to track `main`, so that the backend redeploys on every merge** — the
maintainer's answer, 2026-08-28. Nothing in this repository can show that (it is the
dashboard setting above), which is exactly why it is written here: it is load-bearing for
release ordering and invisible to everyone who has not seen the dashboard.

**It is a decision, not yet a fact, and this paragraph used to say otherwise.** Confirmed
with the maintainer 2026-09-09: **no Render service exists yet**. The present tense here
("Render tracks `main`") read as a live service to anyone who had not seen the dashboard —
the one audience the paragraph was written for — while
[.github/expected-settings.yml](../.github/expected-settings.yml) said the opposite in the
same repository, and both could not be true. So: the setting below is what to configure
when the service is created, which is
[#600](https://github.com/OurHike/OurHike/issues/600) and is account work rather than
anything a branch can do. Everything after this paragraph describes what that setting buys
once it exists.

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

**If the service is created without that setting, or it changes later, the release train
gains a step**: deploy the backend, confirm `/openapi.json` carries the new fields, and
only then publish the draft. With it, the ordering holds by construction and the train
stays four buttons — which is the reason to set it at creation rather than to discover
later that it was worth setting.

### The gap this does not close: backend code against an unmigrated schema

**"Always ahead of the app" is a claim about the client/backend pair. It says nothing
about the backend and its own database**, and that is a second, different skew a
tracking Render introduces — [#1641](https://github.com/OurHike/OurHike/issues/1641)
found it during the v1.3.2 release review, deferred here because it is gated on this
same not-yet-created service.

Once Render tracks `main`, **any merge that carries a new revision under
`backend/alembic/versions/` redeploys the ORM models that expect it before the
migration has necessarily run** — `migrate.yml target: production` is a separate,
explicit dispatch (RELEASING.md §8c, [`.claude/skills/release-train/SKILL.md`](../.claude/skills/release-train/SKILL.md)'s
Phase 2), never a consequence of a merge landing. Between the deploy and that dispatch,
the live backend is running code that reads or writes a column the production database
does not have yet — a 500 on whatever request reaches it, not a 422 a client can shrug
off. The release train's own Phase 2 already puts a migration ahead of the *tagged*
release it belongs to; what it does not cover is an ordinary feature merge, outside a
release cut, that happens to carry both a migration and the code that depends on it in
the same pull request.

**`@unvalidated`: which of two remedies this becomes.** Both are real options and
nothing here has picked one:

- **An ordering discipline**: a migration's "expand" half (the new column, nullable or
  defaulted) and the ORM/route code that first reads or writes it land in *separate*
  merges, with the migration's own merge dispatched to production before the second is
  opened — the same expand-and-contract shape §8c already asks for on the *drop* side,
  extended to the *add* side for exactly this reason. Costs discipline on every PR that
  touches the schema, not tooling.
- **A deploy hook**: Render supports a pre-deploy command that runs before the new
  release takes traffic, which is precisely where `alembic upgrade head` would close
  this by construction, the same way the tracking setting itself closes the client skew.
  Costs one dashboard setting, made at the same account-work moment as #600, rather than
  discipline on every PR thereafter — but nobody here has a Render account to confirm
  the feature works as documented, or what happens to in-flight requests against the
  *previous* release while the command runs. **And it is not available on the free
  tier**: Render's docs say "the pre-deploy command is available for paid web services,
  private services, and background workers" (read 2026-10-23). So this remedy waits for
  Starter, and the ordering discipline above is the one that applies until then.

What would settle it: #600 actually creating the service, at which point this becomes a
real setting to test rather than a documented risk. Until then, a PR that adds both a
migration and the code that depends on it should say so in its own body and default to
the ordering discipline above, since it costs nothing when there is no Render service
to race yet.

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

The free tier is withdrawn or starts suspending the service; or the edge cache stops
answering `HIT`, which puts the free quotas back within reach of a few thousand hikers; or
the cold start turns out to bite something that is not a photo; or the backend shrinks far
enough that
PostgREST-with-policies plus a function for presigning genuinely covers it — noting that
[#393](https://github.com/OurHike/OurHike/issues/393) rejected that once already, because
`_visible_to` has drifted before when it lived in two places.
