# How closures and verified reports reach a hiker

Companion to [MAP_OPTIONS.md](MAP_OPTIONS.md) (what a closure *is*) and
[REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) (what a report *is*). This document owns the
**delivery path** for both: how public safety data gets from the moderation queue onto a
phone, and why that path should not run through an always-on server.

It does not restate the closure or report designs, and it does not own hosting —
[backend/HOSTING.md](../backend/HOSTING.md) does, and its "Revisit if" clause names this
document as the thing that would change its answer.

## The problem, stated as a value rather than a bill

Today `GET /closures` is served by the FastAPI backend. That makes the safety-critical
read path depend on the single most fragile component in the system: one container, on one
host, on one account, on one person's card.

That is not primarily a cost problem — it is about **$2/month**, and
[#393](https://github.com/OurHike/OurHike/issues/393) is emphatic that the host line is the
wrong thing to optimize. It is a values problem, and three of them:

- **#4 Trustworthy above all.** Today, if the backend is unreachable, a hiker gets *no
  closure warnings and no indication that is why*. `App.tsx` holds closures as
  `ClosureSummary[] | null` and the null branch renders nothing. "No closures" and "could
  not ask" are indistinguishable on screen — the same ambiguity
  [#249](https://github.com/OurHike/OurHike/issues/249) records for maintainer assignments,
  on the read `App.tsx:508-510` calls "the half a hiker walks into."
- **#8 Sustainable.** *"Design so the project can survive turnover in maintainers."* A
  lapsed card silently removes closure warnings for everyone.
- **#3 Open by default / #7 Built to be inherited.** A club forking this inherits the code
  but not the running service. The safety data arrives only if they stand up a backend.

Worth noting this is a *return*, not a departure:
[TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md)'s Hosting section already calls
the backend "a real, deliberate cost/complexity increase over the original 'no servers to
run' MVP framing."

## The seam already exists

`moderation_status == verified` is the line the public/private split already runs along.
`closures.py`'s docstring: browsing needs no account; `reports.py` filters public queries
on the same flag.

So **everything a hiker reads without signing in is already public, unauthenticated and
read-mostly** — which is the exact shape of the trail data this project already serves
brilliantly as static bytes on R2 with free egress. The safety data is being served
dynamically because it happens to live in Postgres, not because it needs to be.

## The design

**Split by read versus write, not by feature.** The read path becomes a published
artifact; the write path stays on the backend and becomes latency-tolerant.

### 1. What gets baked

A new artifact family published by the existing pipeline, alongside the trail exports:

```
conditions/closures.json      verified closures
conditions/reports.json       verified, publicly-visible reports
conditions/atc_updates.json   the ATC's own trail notices
```

The third arrives by a different road and [ATC_TRAIL_UPDATES.md](ATC_TRAIL_UPDATES.md) owns
why: it is baked from a file in git that a person reviewed, not queried out of the database,
so it needs no credential and carries a `reviewed_at` alongside the `generated_at` the other
two make do with. Everything below about delivery applies to it unchanged.

All three referenced from `latest.json` with a sha256, exactly like every other artifact —
`pipeline/publish.py` (399 lines, with `lib/r2_keys.py` enforcing the key rules) already
does this and needs an artifact added, not a mechanism built. That matters for **value #8's
preference for boring technology**: this is not new machinery.

**Fields the bake must drop: `reported_by` and `verified_by`.** They are Supabase auth
user ids — stable identifiers tying a person to a place and a time. `SAYING_THANKS.md`
declines to publish that a named volunteer is at a known place on a predictable schedule
without consent, and a published artifact is the most permanent form of publishing
available here.

*Separately and more urgently:* `ClosureOut` currently returns both fields on the
unauthenticated `GET /closures`. That is a live question about the existing endpoint, not
something this design introduces, and it wants its own issue rather than a quiet fix
buried in this one.

**Fields kept:** `id`, `trail_id`, `start_mile_marker`, `end_mile_marker`, `reason_type`,
`note`, `status`, `closed_since`, `expected_reopen`, `reroute_url`, `verified_at`.

**Reports track what `ReportOut.for_viewer` sends an anonymous caller** (#436), which is
why the artifact has no `reporter_id`, `received_at`, `maintainer_id` or `club_id` — those
are withheld from anonymous responses — and no `verified_by`/`verified_at`, which the
public report schema never carries at all.

**`photo_url` is absent from the reports artifact, decided rather than deferred**
(#436, option one of the three it weighed): the live endpoint answers it with a
presigned URL whose expiry is measured in minutes, against a private bucket, and a baked
artifact is rewritten daily — a published signature would be broken by the time it was
read, and a long-lived one would defeat the private bucket. So the baseline supplies the
warning and the live tier supplies the photo; a baseline report simply renders without
one. Revisit only if field testing shows a photo changes what a hiker does about a
warning, and then via the stable-indirection option, not a longer signature.

### 2. How it is produced

A scheduled job reads verified rows from Postgres and writes the artifacts — the same
shape as `publish-vector-data.yml`, on a daily schedule.

**Daily is the maintainer's stated tolerance** (2026-08-08): *"a closure can be latent by a
day. we won't be adjusting minute by minute."* Recorded here because it is the number the
whole design rests on, and because a future reader will otherwise assume it was guessed.

**It needs a read-only database credential, distinct from the two that already exist.**
The repository already draws this distinction twice — `*_MIGRATION_DATABASE_URL` is not
`DATABASE_URL`, and the report-photo credentials carry an `R2_PHOTO_` prefix precisely so
they cannot be confused with the publishing ones. A job that only ever reads verified rows
should hold a credential that can only do that. Declared as
`PRODUCTION_CONDITIONS_DATABASE_URL` in `.github/expected-settings.yml`.

**And it needs an RLS policy, which is the part that would otherwise be found the hard
way.** `enable_row_level_security` turns RLS on for every table with *no policies*, and
its own docstring explains why the backend is unaffected: *"RLS does not apply to a
table's owner, and the backend connects with the Postgres connection string as the
owner."* A reader role is not the owner. So `GRANT SELECT` alone returns **zero rows
rather than an error** — which, published unchecked, is an empty closures artifact, a
client treating it as a valid baseline, and hikers shown no closure warnings. A
permissions mistake wearing the costume of a quiet trail.

That migration anticipated this: *"Add policies if and only if something is later built
that genuinely needs direct table access."* This is that case, and the policy earns its
keep twice — it is also where the moderation filter belongs, so the database refuses to
show the publisher anything unverified and a buggy exporter structurally cannot leak an
unmoderated row:

```sql
CREATE ROLE ourhike_conditions_reader LOGIN PASSWORD '<generated>';
GRANT CONNECT ON DATABASE postgres TO ourhike_conditions_reader;
GRANT USAGE  ON SCHEMA public      TO ourhike_conditions_reader;

-- Two tables. Deliberately not `profiles`: the artifact names nobody (#430),
-- and no grant means the exporter could not resolve a person if it tried.
GRANT SELECT ON public.closures, public.reports TO ourhike_conditions_reader;

CREATE POLICY conditions_reader_closures
  ON public.closures FOR SELECT TO ourhike_conditions_reader
  USING (moderation_status = 'verified');

-- Reports differ from closures: `status` + `visibility`, mirroring
-- `_MODERATED_STATUSES` and excluding internal_only and club_only.
CREATE POLICY conditions_reader_reports
  ON public.reports FOR SELECT TO ourhike_conditions_reader
  USING (status IN ('verified', 'resolved') AND visibility = 'public');
```

String literals rather than enum casts because those columns are `native_enum=False`, so
they are `VARCHAR(20)`.

**The connection string's username must be tenant-qualified.** Supabase's pooler routes on
the part after the dot, so it wants `ourhike_conditions_reader.<project-ref>`, not the bare
role name. A bare role is refused at connect with
`FATAL: (ENOTFOUND) tenant/user ... not found` — a message that reads like the role was
never created, and sends you back to re-check SQL that is already correct. The first real
run of `publish-conditions.yml` failed on exactly this (2026-08-08); `export_conditions.py`
now catches it and says so rather than passing the raw error through.

Setting the secret took three dispatches, every failure in the username field, and each of
the three outcomes is diagnostic (#438 — the role goes before the dot, the project ref
after it, and `postgres` in the repository's other examples is a role *name*, not a pooler
keyword):

| Username | What happens |
|---|---|
| `postgres.<project-ref>` | **Connects, then fails misleadingly.** `export_conditions.py` exits saying `closures` has RLS on and no policy it can read through — accurate about `current_user`, misleading about the database, because both policies exist and are correct. `pg_policies` is filtered by `current_user`, so connecting as the owner makes the reader's policies invisible rather than absent. If you see the missing-policy message, check who you connected as before re-checking SQL. |
| `postgres.ourhike_conditions_reader` (halves swapped) | `FATAL: (ENOTFOUND) tenant/user ... not found` |
| `ourhike_conditions_reader.<project-ref>` | Works |

**`export_conditions.py` refuses to run unless both are in place**, asking the catalog
rather than trusting the configuration, so that a genuinely empty result is trustworthy.
`pipeline/tests/test_export_conditions.py` proves the underlying trap is real by
reproducing it against a live Postgres — a verified closure that reads fine, then reads as
nothing the moment RLS is on without a policy.

### 3. How the client reads it

Two tiers, and the second is optional:

1. **Baseline** — fetch `conditions/closures.json` from R2 at startup, with the map data.
   No account, no backend, CDN-backed, free egress. Always available.
2. **Live refresh** — if `VITE_API_BASE_URL` is set *and* reachable, `GET /closures` for
   fresher data, overlaid on the baseline.

**The state model has to change, and this is the part that is not optional.** Closures stop
being `ClosureSummary[] | null` and become three distinguishable states:

| State | Meaning | What a hiker sees |
| --- | --- | --- |
| `live` | fetched from the backend just now | closures, no staleness note |
| `baseline` | from the published artifact | closures, **"as of <date>"** |
| `unavailable` | neither reachable | an explicit "conditions unavailable" |

That third row is the #249 fix, and the second row is **value #4 doing real work** —
*"honesty about uncertainty (e.g., 'reported 3 days ago' vs 'confirmed today')."* A
staleness stamp is not decoration here; it is the feature that makes a day-old baseline
trustworthy instead of misleading.

Note the failure mode this removes: today, an unreachable backend means *no warnings at
all*. With a baseline, the worst case is *day-old warnings, labelled as day-old*. That is
strictly safer.

### 4. What this does to hosting

Once closures come from R2, the safety argument for `min_machines_running = 1` is gone,
because nothing a hiker reads on the trail touches the backend any more. What remains is
latency-tolerant by construction:

- **Report submission** already queues in an offline outbox with its authored timestamp.
  A cold start is invisible to it.
- **Moderation** is a handful of trusted people doing deliberate work at a desk.
- **Photo loads** tolerate a few seconds.

So the backend can scale to zero, and the free tiers HOSTING.md ruled out come back into
scope. **This is a consequence, not the goal** — the saving is ~$2/month, and chasing that
would be exactly the mistake #393 warns about.

### 5. What stays on the backend, and why it is irreducible

- **All writes** — `POST /closures`, `POST /reports`, the role-gated `PATCH`.
- **`_visible_to`** — the unmoderated/private view. **This does not move into SQL policies.**
  #393 rejected PostgREST-with-RLS precisely because that rule has drifted once already
  when it lived in two places. This design *shrinks* the surface it governs rather than
  relocating it: everything public is baked, so `_visible_to` only ever answers for
  authenticated, unmoderated reads.
- **Photo presigning** — needs the R2 signing key, which cannot live on a phone.
- **Per-user private state** — profiles, preferences, hikes.
- **`GET /moderation/queue`.**

### 6. Honest costs

- **Up to a day of staleness**, accepted above.
- **A dismissed closure lingers.** If a moderator dismisses a verified closure, the
  baseline keeps showing it until the next bake. The live tier corrects it whenever the
  backend is reachable, and dismissal-after-verification is rarer than creation — but this
  is the one case where the baseline is *wrong* rather than merely old, and it should be
  named rather than discovered.
- **A new scheduled job**, with a credential and a failure mode of its own. A bake that
  silently stops produces a baseline that ages without saying so — so the artifact carries
  its own generation timestamp, and the client renders it. Staleness must be visible in
  the data, not inferred from the schedule.
- **It removes no vendor.** Supabase, R2 and a (now scale-to-zero) host all remain.

### 7. What it buys, restated

A fork points at its own R2 bucket and the safety read path works, with no account handoff
and no backend at all. That is **#3 and #7 implemented** rather than aspired to — and it is
the thing switching hosts could never have delivered.

## Order of work

The ordering is load-bearing: **do not relax `min_machines_running` until the baseline is
actually being served and read.** Until then the always-on machine is the only thing
delivering closures.

1. Bake and publish `conditions/closures.json` (pipeline + scheduled workflow + read-only
   credential). **Built.** `pipeline/export_conditions.py` and
   `.github/workflows/publish-conditions.yml`; the workflow skips with a warning until the
   credential above exists, so nothing here is waiting on it.
2. Client reads the baseline, with the three-state model and the staleness stamp.
   **Built** (#435).
3. Extend to `conditions/reports.json`. **Built** (#436): `export_conditions.py` bakes
   both artifacts and refuses to run unless *both* tables' grants and policies are in
   place, so a half-configured database publishes nothing rather than one artifact of
   two. The client holds reports in the same three-state model as closures, and the
   status strip's one conditions line reports the *worst* of the two states — a live
   closures read next to unreachable reports is a map silently missing its warning pins,
   and no caveat would claim a completeness the screen does not have.
4. Only then revisit hosting — HOSTING.md's "Revisit if" clause, with its own decision.

The privacy question in §1 about `ClosureOut` is not in this sequence deliberately: it
concerns the endpoint as it exists today and should not wait for any of this.
