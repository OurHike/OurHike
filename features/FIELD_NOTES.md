# OurHike — Field Notes (Feature Design Draft v1)

Companion to [../FEATURES.md](../FEATURES.md), [../OurHikeValues.md](../OurHikeValues.md) and
[../TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md). This document owns **what the
app does when upstream data and the field disagree** — the layering rule, the note that
carries a field observation, and how a hiker reads both without anyone having to adjudicate
between them.

It absorbs [DATA_NUDGES.md](DATA_NUDGES.md)'s `ConditionConfirmation` (that doc keeps the
*prompting*; this one owns the *record*), escalates into
[REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) rather than duplicating its queue, ships down
[CONDITIONS_DELIVERY.md](CONDITIONS_DELIVERY.md)'s existing path rather than building one,
routes disputes to [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md)'s stewards, and leans on
[VOLUNTEERING.md](VOLUNTEERING.md)'s `MaintainerAssignment` to know who is responsible for
a mile.

**Scope: v2, third feature** (2026-08-09), after [HIKE_PLANNING.md](HIKE_PLANNING.md) and
[VOLUNTEERING.md](VOLUNTEERING.md). It needs no new infrastructure — the backend, the
moderation roles, the R2 conditions path and the POI id contract all exist.

---

## The problem, stated as two clocks

Everything on the map comes from upstream: twelve ATC ArcGIS layers plus opentrail.org.
That data is authoritative about **what exists and where** — ATC's GIS is a survey, and a
hiker's phone is not. It is silent about **what a place is like today**, and structurally
so: ATC's own `editingInfo.dataLastEditDate` is the ceiling on its freshness, and
`publish-vector-data.yml` is `workflow_dispatch` only, so trail data reaches a phone a few
times a year.

The field runs on the other clock entirely. Hikers, maintainers and ridge runners pass
these places constantly. They are fresh and they are variable — a tired thru-hiker's
memory of which side of the trail a spring was on is not a survey.

The obvious move is to merge them into one current-truth record. **That is the move this
design refuses**, because a merge needs an adjudicator, and the adjudicator is a standing
job nobody will hold. Value #8 asks the project to survive turnover in maintainers; a
reconciliation queue is precisely the thing that stops working the first month nobody looks
at it, and it stops working *invisibly* — the map keeps rendering, it just quietly stops
being true.

So: **don't merge them, layer them.** Nothing overwrites anything, so nothing needs
adjudicating.

## The layering rule

The two sources are mostly not in conflict, because they are answering different questions:

| Question | Owner | Why |
| --- | --- | --- |
| Does this place exist, and where is it? | **Upstream** | A survey beats a recollection, and beats a ±10m GPS fix |
| What is it called, what type is it? | **Upstream** | |
| **What is it like right now?** | **The field** | Upstream has no mechanism to know, and never claimed to |
| Is it gone? | **Neither alone** | The field disputes; upstream resolves — see below |

Most of the apparent conflict dissolves on that table. "ATC says reliable spring" and
"it's dry" are not contradictory claims; they are a claim about *what is here* and a claim
about *what it is doing*, and only the second has a hiker's name and a date on it. Reading
them as a contradiction is what forces the adjudication this design is trying to avoid.

The residual real conflict is existence, and §4 is about that.

## 1. A note is a dated observation

The unit is a **field note**: what someone saw, where, and when they saw it. Not a rating,
not an opinion, not a thread.

Two things about the record earn their place, and both are cheap:

**`observed_at` is not `posted_at`.** Hikers write at camp, or in town two days later, when
they have signal and a hand free. A note stamped with its upload time is a lie the system
tells by accident — and it is the exact lie this project cares most about, since value #4's
own example is *"reported 3 days ago vs. confirmed today."* The offline outbox already
preserves an authored timestamp for reports (`9c` in [../WIREFRAMES.md](../WIREFRAMES.md),
"reports wait, with their original timestamps"); this is the same instinct, made explicit
in the schema rather than implied by when the request happened to arrive.

**A note may carry a structured observation as well as text.** The tag is what the map can
render and what [DATA_NUDGES.md](DATA_NUDGES.md)'s one-tap answer produces; the text is what
the next hiker actually needs — *"dry at the spring, but the piped source 0.4 mi north is
running well."* Neither is required. A note with only text is fine, and a note with only a
tap is fine.

**There are no votes, stars or ratings**, and this is settled rather than open.
[SAYING_THANKS.md](SAYING_THANKS.md) already rules them out ("Not a rating or review system.
No stars, no scores"), and [POI_PHOTOS.md](POI_PHOTOS.md) rules them out again for photo
promotion with the reason that generalises: *"a crowd reliably prefers the prettiest
sunset."* Upvotes measure agreement. What a hiker needs is recency and who said it — a
three-day-old note from the maintainer of that section beats a much-upvoted note from last
season, and sorting by recency needs nothing to be gamed. This is also the answer to
`FEATURES.md`'s "Community submission + upvoting" spam concern *for this surface*: nothing
aggregates, so there is nothing to farm.

**Writing a note needs an account; reading one never does.** Browsing has never required
one in this app and nothing here changes that — `GET /closures` and `GET /reports` are
already unauthenticated, and the baseline artifact needs no backend at all. But the
corroboration rule in §4 counts *distinct accounts*, and an anonymous note cannot be
counted, rate-limited, or hidden as part of a pattern. [../WIREFRAMES.md](../WIREFRAMES.md)
§11 previously said a one-tap confirmation "needs no account"; that predates
[AUTHENTICATION.md](AUTHENTICATION.md) moving into MVP, and is corrected there in the same
change as this doc. `DATA_NUDGES.md`'s open question about whether a confirmation needs its
own lightweight identity resolves the way that doc was already leaning: it rides on
Authentication, and gets nothing bespoke.

## 2. Absorbing `ConditionConfirmation`

[DATA_NUDGES.md](DATA_NUDGES.md) designed `ConditionConfirmation` in July as "a lighter
sibling to Report a Problem's `Report`" — a one-tap flowing/trickling/dry with an optional
note, writing `last_confirmed_at` directly with no moderation step. It was never built.

**A confirmation is a field note with a tag and no text.** Shipping both would leave two
near-identical models for a later reader to reconcile, which is the drift
[../CONTRIBUTING.md](../CONTRIBUTING.md)'s one-home rule exists to prevent — so this doc
takes the record and `DATA_NUDGES.md` keeps what it was actually about: *when* to ask, and
the passive map prominence that does the asking. That doc's central rule is unchanged and
still governs the prompt: **no push, no in-app banner, no alert.**
[HIKER_SAFETY.md](HIKER_SAFETY.md)'s wrong-way alert stays the only notification the app
ever sends.

## 3. The roll-up — what the map shows without reading the feed

A feed alone fails the test that matters: eight percent battery, one glance, is there water
in the next four miles. So three things are computed from the notes at render time — never
stored, the same derive-don't-duplicate instinct `DATA_NUDGES.md` already applies:

- **`last_confirmed_at`** — the most recent `observed_at` among visible notes. This is the
  input [`client/src/lib/staleness.ts`](../client/src/lib/staleness.ts) has been waiting
  for. [#256](https://github.com/OurHike/OurHike/issues/256) records that module as "doubly
  orphaned: no consumer… no producer"; **this feature is the producer**, and the tier it
  already computes is the consumer's half.
- **A headline** — the most recent observation, its age, and the reporter type. *"Dry — 3
  days ago, thru-hiker."* One line. No synthesis, no averaging, no model.
- **Contested** — when recent notes disagree, show **both**, labelled. Do not average, do
  not pick a winner. This is value #4 doing real work rather than decoration, and it is
  *cheaper* than resolving, not more expensive. A hiker who knows two people disagree about
  a spring carries water; a hiker shown a confident wrong answer does not.

## 4. Disputes, and the pin that says "reported missing"

The one place the field genuinely contradicts upstream on upstream's own ground: ATC says
there is a spring here, and there is no spring here.

**A dispute is an observation value, not a second model.** `not_found` sits alongside
`dry` and `flowing`. No second form, no second flow, no separate object to moderate.

### It renders on the existence axis, not a new one

[../WIREFRAMES.md](../WIREFRAMES.md) §11 pins the axes deliberately: *"a dashed pin means
**never verified to exist**; staleness means **when a human last said it was fine**."* A
dispute is a claim on the first axis — a stronger one than "unverified," but the same
question. So existence takes a third value rather than the map taking a fourth channel:

| existence | means | treatment |
| --- | --- | --- |
| verified | upstream has it, nobody disputes it | solid pin |
| unverified | `confidence: low` — never confirmed to exist | dashed pin |
| **reported missing** | corroborated `not_found` notes | dashed pin, distinct marker |

The legend already treats confidence as something a hiker filters on (its *"Verified?"* toggle,
`WIREFRAMES.md` §2 — it carried *"Unverified · 1"* rows until
[#572](https://github.com/OurHike/OurHike/issues/572) found them to be twice the panel for a
distinction a viewport count cannot act on), so this is a tier in a family that exists, not a
new section. And the card always says it in
words as well as pixels — *"2 hikers reported this missing, most recently 4 days ago"* —
because §11's own rule is that the visual channel never carries the meaning alone.

### What corroborates, and what decays

- **Enter** on two `not_found` notes from **distinct accounts on distinct days**, or on one
  from a maintainer whose `MaintainerAssignment` ([VOLUNTEERING.md](VOLUNTEERING.md)) covers
  that mile. Distinctness matters more than count: two notes from one account is one
  observation, and two from hikers walking together on the same afternoon is close to one.
- **Leave** on two independent confirming observations, or one maintainer's.
- **Decay** to normal — never to *confirmed* — after a window with no corroboration, so one
  stale claim cannot mark a place forever.
- **An upstream republish does not clear it.** ATC re-publishing its shelters layer says
  nothing about whether the spring is there. Treating a rebuild as evidence would quietly
  erase every dispute on a schedule.
- **The pin is never suppressed.** A POI that vanishes is indistinguishable from one that
  never existed — the same ambiguity [CONDITIONS_DELIVERY.md](CONDITIONS_DELIVERY.md) calls
  *"the half a hiker walks into"*
  ([#249](https://github.com/OurHike/OurHike/issues/249)). Disputed is a thing to say, not a
  thing to hide.

### Why a suppression rule is affordable here, stated plainly

Any threshold invites gaming, so it is worth naming what an attacker can actually buy. The
only state that can be manufactured is **disputed** — never *removed*, never *confirmed
present*. So the worst outcome of a successful attack on a water source is a hiker who
carries extra water. That is the safe direction for this particular error, it is
proportionate to the effort, and it is why this design will accept a threshold at all when
value #4 normally argues for saying nothing rather than saying something wrong.

The reverse mistake is not symmetric, which is the whole point: a hiker who arrives at a
dry spring they were told was reliable is the failure mode `FEATURES.md`'s Water
Reliability section already names as *wikitrail.org's founding story*.

### And it files upstream, which is the actual fix

The marking is interim. The resolution is that ATC's data changes.

A dispute routes to the **source steward** — [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md)
already designs one contact per provider and a `"steward": "org:…"` reference, and
[../pipeline/DATA_RELEASES.md](../pipeline/DATA_RELEASES.md) already sets the volume rule
these sends must obey: *one tracking issue per source, updated in place, never a second
issue, never a comment per day.*

This is the part that makes the whole design sustainable rather than merely deferred. The
app does not fork ATC's data and does not accumulate a private correction layer that a
future maintainer must reconcile forever. It becomes **ATC's field reporting channel** —
which is value #2 (built by the community that built the trail) and value #6 (belongs to
the trails, not the platform) implemented rather than asserted. The correction lands
upstream, where every other consumer of that layer gets it too.

## 5. Moderation: publish now, remove on flags

A note is visible the moment it lands. Moderators see only what is flagged.

This contradicts [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md), where nothing is public until
a moderator verifies it, so it needs an argument rather than an assumption:

- **A note that waits for review is not fresh**, and freshness is the entire feature. A
  queue between the field and the map reintroduces exactly the latency that made upstream
  data insufficient.
- **A condition note is low-stakes and self-correcting.** The next hiker's note supersedes
  it in hours. A verified closure is not like this, which is why closures keep their queue.
- **Safety-shaped content is not a note.** When the answer indicates a hazard rather than a
  condition, the flow hands off to `REPORT_A_PROBLEM.md`'s real report with its real queue
  and its `severity` escalation — the same escalation shape `DATA_NUDGES.md` already
  specifies (*tapping "dry" prompts "want to report this?"*). The queue is reserved for
  what actually needs it.
- **`bad_hikers` is never a note.** That category reports on *people*;
  `REPORT_A_PROBLEM.md` already flags it as closer to a harassment vector than a condition
  report and routes it `internal_only`. Nothing about this feature touches it.
- **Removal stays enforced in the database.** `export_conditions.py`'s reader policy filters
  `moderation_status = 'verified'` so a buggy exporter *structurally cannot* leak an
  unmoderated row. The notes policy filters `hidden_at IS NULL` — the same guarantee with
  the opposite default. A flagged note is **hidden, never deleted**, so a wrong removal is
  recoverable and a pattern of abuse is still legible to a moderator.

This also owes [SAYING_THANKS.md](SAYING_THANKS.md) an answer it deferred: that doc's
`thanks` type skips the queue too and left "abuse handling specifics" open. The flag-and-hide
path here covers both, and it should be built once.

**The honest cost, and the fallback named up front.** Steady-state work is reviewing flags,
and the bet is that flags are rare. If that bet is wrong, the degradation is not "moderate
harder" — it is **structured tags only, no free text**, which needs no moderation at all and
still produces `last_confirmed_at`, the headline, and disputes. Naming the retreat before
shipping is what makes shipping it responsible; discovering it later is how a volunteer
project acquires a job nobody signed up for.

## 6. Delivery — the path already exists

[CONDITIONS_DELIVERY.md](CONDITIONS_DELIVERY.md) built this exact round trip in August:
`pipeline/export_conditions.py` reads verified rows from Postgres as a non-owner, read-only
role, bakes them to `conditions/*.json` on R2, and the client reads them as a baseline with
a live overlay in three distinguishable states — `live`, `baseline` (with an "as of" date),
`unavailable`. A third artifact is **an artifact added, not a mechanism built**, and hiker
free text is already baked today (`export_conditions.py` selects `reports.note`), so nothing
new is being decided about publishing what someone typed.

Four constraints specific to notes:

- **Size.** Closures are a handful of rows; notes are potentially every POI times every
  season. The bake carries the **roll-up for every POI plus the most recent K notes per POI
  inside a time window**; the full history is a live-only read. A hiker offline needs *is it
  dry*, not the archive — and an artifact that grows without bound is a download that
  eventually fails on the trail.
- **`conditions/` only, never `releases/`.** [POI_PHOTOS.md](POI_PHOTOS.md) establishes the
  rule with photos: release folders are written once and never overwritten, so anything
  withdrawable cannot go in one. `conditions/` is rewritten in place daily, so a hidden note
  clears within a day — the same honest cost `CONDITIONS_DELIVERY.md` §6 already accepts for
  a dismissed closure that lingers in the baseline.
- **Photos stay backend-only**, presigned against the private bucket. Already decided for
  reports, and for the same reason: a presigned URL expires in minutes and a baked one would
  be broken by the time it was read.
- **Drop `reporter_id`**, and grant the reader role nothing on `profiles`, so the exporter
  could not resolve a person if a future edit tried to. This matters more here than for
  closures: many dated notes along a corridor from one identifier reconstruct a hike, which
  is exactly what [#252](https://github.com/OurHike/OurHike/issues/252) removed from public
  report serialisation. Public attribution is **`reporter_type` alone** —
  [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md) governs, and
  `HIKER_SAFETY.md`'s anonymity window becomes genuinely relevant here rather than
  hypothetical.

## 7. Orphaning — currently silent, and this doc should own it

Notes anchor on `poi_id`, the deterministic `f"{source}:{source_feature_id}"` that
[`pipeline/lib/poi_schema.py`](../pipeline/lib/poi_schema.py) promises *"has to stay stable
across repeated pipeline runs on unchanged input"* precisely because a future report would
reference it. The promise holds for unchanged input. Two things break it:

- ATC deletes and re-creates a feature, re-minting its `GlobalID`.
- A feature falls onto [`lib/feature_id.py`](../pipeline/lib/feature_id.py)'s
  `generated-{index}` fallback, which is **positional** — it changes whenever upstream
  reorders.

Today nothing would notice. `reports.poi_id` is a plain nullable string with no foreign key
in either direction (deliberately — the POI dataset lives outside that database entirely),
and `check_output_quality.py` compares counts and hashes, not id sets against Postgres.

So: **a check that diffs published POI ids against stored note anchors and reports the
orphans**, into one issue updated in place. Every note keeps its `lat`/`lon`, so an orphan
is re-anchorable rather than lost — which is also why the fallback anchor is in the model
rather than being derivable from the POI.

**The contract itself now has a design: [POI_IDENTITY.md](POI_IDENTITY.md)**
([#666](https://github.com/OurHike/OurHike/issues/666) — *A POI's identity is its upstream
key, so one ATC annual refresh can orphan every photo and comment*). Under its ledger, both
break modes above stop being possible — an id is minted once and carried across re-keys, and
a removed feature retires into a tombstone rather than taking its anchors with it. The check
stays this doc's, demoted to backstop: expected to find nothing, kept because it is what
proves that, and still the recovery path for anything written before the ledger existed.

## 8. What this deliberately isn't

- **Not a thread.** No replies, no mentions, no conversation. A conversation needs
  moderating, and the moderation burden is the thing this design exists to avoid. A note is
  addressed to the next hiker, not to the previous one.
- **Not a rating system.** No votes, stars, scores or "helpful" taps — settled twice already.
- **Not a notification.** Nothing here interrupts anyone; `HIKER_SAFETY.md`'s wrong-way alert
  remains the only one.
- **Not gamified.** No streaks, no contribution counts, no leaderboard, no "you haven't
  contributed lately" — the guardrail stated in four docs, with its boundary settled in
  `VOLUNTEERING.md` (it targets *comparison and pressure*, not *memory*).
- **Not a fork of ATC's data.** The app never edits an upstream fact. It annotates, and it
  files upstream.
- **Not a social feed.** `FEATURES.md` names the risk exactly — unmoderated place comments
  tip into broadcast pressure, unattended-cache posts and oversharing. Everything above is
  shaped to stay on the near side of that line: dated observations about a place, sorted by
  recency, attributed by role, with nothing to accumulate.

## Data model sketch

```
FieldNote                        (new — supersedes DATA_NUDGES.md's ConditionConfirmation)
  id               app-generated UUID, held by the client before the row is written
  poi_id           soft string ref, "atc_shelters:<GlobalID>" — nullable, no FK
                     (the precedent is backend/app/models/report.py's own poi_id)
  lat, lon, mile   fallback anchor, and what re-anchors an orphan
  observation      optional tag, by poi_type:
                     water     flowing | trickling | dry | not_found
                     shelter   fine | damaged | full | not_found
                     resupply  open | limited | closed | not_found
  note             optional free text, length-capped
  observed_at      when the hiker was there
  posted_at        when it reached the backend
  reporter_type    thru | section | day | maintainer  — the only public attribution
  reporter_id      FK to profiles; never serialised publicly, never baked
  hidden_at        set by a moderator acting on a flag; the row is hidden, never deleted
  hidden_by

NoteFlag
  id, note_id, flagged_by, reason, created_at

POI                              (derived at render time, stored nowhere)
  last_confirmed_at              max(observed_at) over visible notes -> staleness.ts
  headline                       most recent observation + age + reporter_type
  contested                      recent notes disagree -> show both
  existence                      verified | unverified | reported_missing
```

## Order of work

Each step is useful on its own, and the order is by dependency rather than by size.

1. **Set `poi_id` from the POI card.** The plumbing already runs end to end — `ReportDraft`,
   `ReportCreate`, `reports.poi_id`, the moderation screen that reads it — and **nothing in
   the client populates it**, so every report today is anchored by lat/lon alone. Small, no
   new model, and it makes the existing corpus anchorable.
2. **`FieldNote`, the write path, and the note affordance on `PoiCard.tsx`** — which is
   display-only today, by a decision its own header records: *"there is no 'last confirmed'
   line, because no published artifact carries a confirmation date yet."* This is what
   changes that.
3. **The roll-up and `last_confirmed_at`**, wired to `staleness.ts`. Closes
   [#256](https://github.com/OurHike/OurHike/issues/256) — both halves.
4. **Bake `conditions/notes.json`**, read by the client in the existing three-state model.
5. **Disputes** — `not_found`, the existence-axis rendering, and steward routing.
6. **Flag and hide, and the orphan check.**

Steps 1–3 are worth doing whether or not the rest follows: they close a real open issue and
give the map its first honest freshness signal.

## Open questions

- **The corroboration thresholds and the decay window in §4.** Two notes and how many days
  are the numbers this design is least able to guess at, and the same field-tuning caveat
  `DATA_NUDGES.md` applies to its own staleness tiers applies here. They should be settled
  against real volume, and the doc should record what they were changed *from*.
- **K, and the time window, for how many notes per POI get baked.** A number with a download
  size on one side and an offline hiker's context on the other; measurable once there is
  volume, guessable only badly before then.
- **Whether a note ever gets a reply.** Ruled out above, and worth revisiting only with
  evidence that the missing thing is *correction* rather than conversation — a later note
  already supersedes an earlier one, which covers most of what a reply would be for.
- **Whether `not_found` should be offered at all on POIs with `confidence: low`.** A hiker
  disputing something upstream never claimed to have verified may be reporting the data's
  known weakness rather than a change on the ground.
- **[#447](https://github.com/OurHike/OurHike/issues/447)** — the published baseline is
  unavailable offline, which is exactly where a hiker is. This feature makes that more
  important; it does not solve it, and should not pretend to.
