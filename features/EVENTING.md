# OurHike — Eventing & Measurement (Feature Design Draft v1)

Companion to [FEATURE_GATING.md](FEATURE_GATING.md), [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md) and [OurHikeValues.md](../OurHikeValues.md). **v2.** Nothing here ships in v1 and nothing here blocks launch.

Two docs, one subject, split on a line worth stating up front: **FEATURE_GATING.md owns the gate — what a hiker sees. This doc owns the measurement — what we learn from it.** That doc's §6 sketched a starting event taxonomy and then deferred its own fourth open question, "how to minimize the privacy footprint of the event taxonomy above while still preserving useful experiment signal … not assumed safe by default." This is that pass, and the answer changed the taxonomy rather than trimming it.

**What this has to deliver:** MAU, WAU and DAU. Evidence about which features work and which do not. Something A/B tests and feature gates can be measured against rather than a second parallel system beside them. Collected client-side, because the app is offline-first and a server-side scheme sees almost nothing. And none of it may cost a hiker their privacy.

---

## 1. The constraint that shaped everything else

Measurement wants an identifier. This app cannot safely have one.

That is not a general privacy preference, it is a specific finding this repository has already made and paid for. [#252](https://github.com/OurHike/OurHike/issues/252) removed `reporter_id` from the public report serialisation because a stable account UUID served next to a trail position and a time is a hiker's route down the corridor, recoverable with `curl` and no account — see [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md). The dangerous pair was *stable identifier* + *where and when*. An analytics scheme is exactly a machine for producing that pair, several times a day, for every hiker, forever.

So the design starts from the hard version of the question: **what can be measured with no identifier at all?** More than expected — enough that the identifier turns out to be unnecessary for the whole of §2 and §3, and avoidable for most of §5. Where one is genuinely required, §5 makes it a per-experiment decision with a scope and an expiry, not a standing fact about a hiker.

Four rules, and everything below is a consequence of them:

1. **No identifier is sent — not an account id, not a device id, not a session id, not a rotating pseudonym.** Deduplication happens on the device, which is the only party that already knows its own history and therefore the only one that learns nothing new by doing it.
2. **No geography, ever.** No coordinates, no mile, no segment id, no POI id, no region. This is the #252 half of the pair, and on a trail app it is the more dangerous half.
3. **No free text, and no timestamp finer than a date.** Date, not time; a bounded enum from a reviewed registry, never a string a hiker typed.
4. **Nothing measurement-related may compete with a hiker's queued report** — not for storage, not for bandwidth, not for the sync that gets a blowdown to a moderator. Measurement is the first thing dropped and the last thing sent.

## 2. DAU, WAU and MAU without an identifier

The reflex is that unique-user counts *require* a stable id: the server has to tell whether two visits a fortnight apart came from one phone or two. The reflex is wrong, and the reason is that the server is the wrong party to ask. **The device already knows. Let it answer, and send the answer instead of the evidence.**

Once a day at most, on a day it was used, the client emits one **heartbeat** carrying a date and three booleans:

```
active_day
  date          2026-08-09          the day being described, not the day it uploaded
  week_first    true | false        first active day this ISO week
  month_first   true | false        first active day this calendar month
  ever_first    true | false        first active day, full stop
```

That is the entire payload. The server counts:

| | |
|---|---|
| **DAU** for a day | heartbeats carrying that date |
| **WAU** for a week | heartbeats in that week with `week_first` |
| **MAU** for a month | heartbeats in that month with `month_first` |
| **New devices** | heartbeats with `ever_first` |
| **Stickiness** | DAU ÷ MAU, from the three above |

A device active four days in a week sends four heartbeats and exactly one of them says `week_first`, so the week's count is a count of devices without anybody ever having distinguished one device from another. The numbers are exact, not estimated — no HyperLogLog sketch, no sampling error, and nothing to re-identify because the heartbeats carry nothing that differs between two devices active on the same day.

**Four things this costs, stated rather than discovered later:**

- **Calendar windows, not rolling ones.** This yields MAU for August, not MAU for the trailing 28 days. ISO weeks are deliberate — they start Monday, so a Saturday–Sunday weekend hike lands inside one week rather than being counted twice. A Sunday-to-Monday trip still straddles. Rolling windows can be reconstructed by adding a bucketed gap-since-last-active to the heartbeat, at the cost of a weak chaining channel (a run of gaps sketches one device's history), so it is deliberately not in v1.
- **Late arrivals are the normal case, not the exception.** A hiker offline for nine days uploads nine heartbeats when they next get signal, each carrying its own date. Every dashboard therefore treats the most recent fortnight as provisional and says so on the chart. A design that assumed same-day delivery would show a cliff at the right-hand edge and somebody would eventually read it as a decline.
- **A batch is momentarily linkable at the ingest boundary.** Nine heartbeats arriving in one request obviously came from one device. The guarantee is that the joinable form is never *written*: the ingest path increments counters and discards the request grouping, which is a property a test can assert rather than a promise in a doc. It is a real narrowing of the claim and worth knowing — "unlinkable in the store", not "unlinkable on the wire".
- **A wrong device clock produces a wrong date.** Reject future dates, clamp anything absurd, accept the residue. It is an accuracy problem, not a privacy one.

**"Active" needs a definition, because an offline-first app can inflate this by accident.** A heartbeat means *a foreground session with at least one hiker interaction*. A background sync is not activity, a service-worker wake is not activity, and a phone that opened the app in a pocket is a problem for whoever writes the interaction check.

## 3. Which features are working

Counts alone answer "is this used", which is the easier and less useful question. Two families, and the second is the one that earns its keep.

**Counters — one row per feature per device per day, not one per tap.**

```
feature_day
  date, feature (from the registry), uses (bucket: 1 | 2 | 3-10 | 11-50 | 51+)
```

Bucketing the count is not tidiness: an unbucketed 383 is rare enough to be a fingerprint, and nothing is lost, because no decision anybody makes here turns on 383 versus 400.

**Outcomes — did the thing the feature exists for actually happen.**

```
task_outcome
  date, task (from the registry),
  outcome  completed | abandoned | failed,
  duration (bucket: <10s | 10-60s | 1-5m | >5m),
  offline  true | false
```

Summarised **on the device, at the end of the attempt**, and sent as one row. There is no session identifier because there is no need to stitch a session together server-side once the device has already answered the question the stitching was for.

The cost is real and cuts the other way from every hosted analytics product: **a question nobody thought to ask cannot be asked of old data.** No exploratory funnel over last quarter's stream, because there is no stream. Adding a question means adding it to the app and waiting weeks for it to answer. Two things make that trade acceptable here rather than merely tolerable — a stream that could answer arbitrary later questions is precisely a stream that could answer "where was this hiker in March", and this project already believes a feature should know what it is for before it ships, which §7 turns into the rule that makes it work.

**The registry is code, not convention.** `task` and `feature` are members of a TypeScript union in the client and a matching enum in the backend, and the ingest route rejects anything outside it. That is what stops rule 3 — no free text — from being a thing everyone remembers until the afternoon somebody interpolates a POI name into an event key.

**One error signal, deliberately narrow.** [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md)'s error-boundary decision says "Nothing is recorded… a deliberate no, revisitable if a real need appears." A screen that turns white for some hikers and nobody hears about it is that need. What v2 adds is a count — `screen_crashed{screen}` — and specifically **not** the message, the stack, or anything derived from them, since a stack trace is exactly the unbounded string rule 3 exists to keep out. A count says *the map screen died 40 times last week*; that is enough to go looking, and it is all this is allowed to say.

## 4. Do not instrument what the server already knows

Client-side collection is forced by the architecture, not preferred. Panning the map, reading a waypoint card, following a route in a valley with no signal — none of it reaches a server, so a server-side-only scheme is blind to nearly everything worth learning.

But some of it *does* reach the server, and those things must not be sent twice:

| Already a server-side record | Do not add an event for |
|---|---|
| A report, closure or thanks submitted | "report submitted" |
| A sync performed | "app synced" |
| A map package downloaded from R2 | "download completed" |
| An account created or signed in | "signed up" |

Counting these from the records that already exist is more accurate (it survives an opt-out and a dropped queue), cheaper, and smaller — and every event not sent is a payload not carrying anything. The rule: **the client instruments only what no server-side record can answer.**

## 5. Experiments, and the identifier they turn out not to need

[FEATURE_GATING.md](FEATURE_GATING.md) already settles the mechanism: variants are evaluated locally from a cached manifest, synchronously, with a hardcoded fallback, so a hiker on a ridge is never waiting on a flag service. Nothing here changes that. What this section settles is how the result gets measured.

**A/B test on a binary outcome needs no per-user data at all.** Exposures per variant and successes per variant are two proportions, and a two-proportion test wants four integers, not four hundred thousand rows. Aggregate is not a degraded input to that test; it is a sufficient one. So an experiment adds one field to §3's shapes:

```
task_outcome + variant        (from the local evaluation; "control" when unenrolled)
exposure_day: date, experiment, variant     (deduped on the device, one per day)
```

For ratio metrics — uses per active device, say — aggregates alone lose the variance the test needs, and the fix is still not an identifier: the device sends its bucketed per-device count (§3 already does), and a histogram per variant carries the distribution. **Send histograms, not rows.**

**Where that genuinely does not stretch, the escape hatch is scoped and expires.** Some metric one day will need per-unit data — variance reduction against pre-period behaviour, most likely. The answer then is an **experiment-scoped random id**: generated at enrolment, used by that experiment only, never reused across experiments so two of them cannot be joined into a profile, and deleted with the experiment's data when it ends. Identity scoped to a single question and destroyed with it is a different object from an analytics id, and the difference has to be enforced by the schema rather than remembered. Taking the hatch is a per-experiment decision with a written reason, not a default.

**This partly unpicks FEATURE_GATING.md's tool choice, and the doc should say so rather than let somebody discover it during setup.** GrowthBook's warehouse-native analysis expects a row per user per metric; this shape has no such rows and will not grow them. Its *flagging* half — manifest, targeting rules, local evaluation, the per-chapter rules in that doc's §4 — is unaffected and still the recommendation. Its *analysis* half sits unused until either an experiment takes the hatch above or somebody decides the hatch should be the default. The arithmetic GrowthBook would have done is a two-proportion test with a Bayesian posterior, which is a short script in `pipeline/` against the same DuckDB the data platform already runs. Choosing that first is consistent with how this repository has chosen everything else in the data platform.

**At club scale, most A/B tests cannot answer the question they are asked.** For 80% power at α = 0.05 against a 20% baseline conversion:

| Effect to detect | Devices per arm |
|---|---|
| 20% → 30% (a big change) | ~260 |
| 20% → 22% | ~6,400 |
| 20% → 21% (a 5% relative lift) | ~25,600 |

A beta with NYNJTC members can find the first row and cannot find the third — not slowly, not at all. **So the default for a change that is probably an improvement is a staged rollout watched against guardrails, not an experiment**, and A/B is reserved for genuine disagreements about big effects. This also lands on the same practical footing FEATURE_GATING.md already noted from the other direction: GrowthBook's automated guardrails are Enterprise-only, so guardrail watching is a person reading a weekly summary either way.

**No experiment arm may withhold, delay, or de-emphasise safety information.** Closures, serious warnings and the wrong-way alert are never the "off" arm of anything. Presentation can be tested — wording, placement, which of two equally prominent treatments reads faster — provided no arm shows a hiker *less* than control, or later than control. This is [OurHikeValues.md](../OurHikeValues.md) #4 stated as a schema constraint: a flag key marked `safety_surface` is refused an experiment, in the manifest, rather than trusted to a reviewer noticing.

## 6. What is deliberately never collected

Worth a list, because "we are careful" is not a specification and the absent things are the whole design:

Location of any kind, at any resolution · mile or segment or POI id · report contents, drafts, or anything a hiker typed · search terms · account id, email, or trail name · device id, install id, advertising id · IP address (see §8) · cookies · user-agent strings · session replay or screen recording · anything from a third-party SDK, because there are none · timestamps finer than a date · unbounded numbers where a bucket does.

**And one on the output side: no published or stored cell below k = 25 devices.** A count of three is a description of three people, especially when it is broken down by club. Suppression is at the query layer, applied to every breakdown, so that the interesting-looking slice nobody thought about is covered too. Whether 25 is right for a beta whose chapters may not reach it is §11's problem, not a reason to omit the floor.

## 7. What the numbers are allowed to mean

This app is unusual in what it wants: [HIKER_SAFETY.md](HIKER_SAFETY.md) and [FEATURES.md](../FEATURES.md) both commit to hikers using it *less often*, finding what they need faster, with "no reason to manufacture engagement." **Engagement metrics therefore point the wrong way here, and DAU is not a goal.** A rising session length may mean the map got confusing. Time-on-elevation-profile going up may mean the ribbon got harder to read.

Two rules keep the numbers honest:

- **Every engagement metric is read next to a task-success metric, never alone.** Uses of the water-source filter mean nothing; uses paired with `completed` versus `abandoned` mean something. §3's two families exist as a pair for this reason.
- **A feature ships with its success measure named in its own design doc, or ships unmeasured on purpose.** One or two sentences: what this is for, what it would look like if it were working, what would make us withdraw it. Written before it ships, because a measure chosen afterwards is chosen knowing the answer. §3's registry is where those measures become code, and "unmeasured on purpose" is a perfectly good answer for a feature whose value was never in doubt.

The failure this is guarding against is not a wrong number. It is the ordinary one where a metric goes up, everybody is pleased, and nobody notices it went up because the app got worse in a way that made people look at it more.

## 8. Where it lands

```
[Client]  in-memory during the day; one summarised batch appended to the existing outbox
   |      capped (~32 KB / 200 rows); oldest measurement rows dropped first;
   |      never displaces a queued report; sent after reports, fire-and-forget,
   |      credentials: 'omit'; failure is silent and never retried aggressively
   v
[POST /events]  FastAPI, first-party, no cookies, no auth.
   |            Validates every field against the registry; rejects anything else.
   |            Does not log the IP for this route and does not persist request grouping.
   v
[Postgres]  received rows, 35-day retention (late arrivals, corrections), then dropped
   |        by a scheduled job that is tested rather than remembered
   v
[Nightly rollup] -> daily aggregates kept indefinitely (small) + Parquet in R2
   v
[DuckDB]  the weekly summary, and the experiment arithmetic from §5 — the same
          stack pipeline/ already runs, queried by a script, not a dashboard product
```

**Volume, so nobody has to guess at cost:** 3,000 daily devices × one heartbeat plus ~10 summary rows ≈ 33k rows/day, ~1.2M rows in the 35-day window, and daily aggregates measured in kilobytes per day. This is a small table in the Postgres that already exists, and the rollups fit in a repository file if it ever came to that.

**No dashboard product in v1.** A generated weekly summary — the counts from §2, the task outcomes from §3, the opt-out rate from §9, the crash counts, each with its k-floor applied — read by a person. Boring, cheap, and it fails visibly. A dashboard nobody opens is the same collection with a worse excuse.

**The privacy claim is only as good as the ingest route**, so it needs its own tests rather than its own paragraph: an event carrying an unregistered key is rejected; an event carrying coordinates is rejected; the IP is absent from what is written; the retention job actually deletes; a k-floor breakdown suppresses. That is a small suite, and it is the load-bearing part of this whole document.

## 9. Consent, disclosure, and the off switch

The site's Privacy Policy already made the promise this has to keep: "We don't currently run any analytics… We're likely to add some limited, aggregated analytics in the future… we'll update this page when it happens rather than after the fact." **The page is updated in the same change that ships the first event, not after** — and the design above was shaped so the update can be short and true: no identifiers, no location, no free text, dates not times, nothing shared with anyone, nothing sold, no third parties.

- **Default on for everything in §2 and §3**, which carry no identifier and no location. Off in one tap in Settings, and off means collection stops, not that it is anonymised harder.
- **Any future addition that carries an identifier of any kind is opt-in instead.** Including §5's escape hatch. The rule is mechanical — *identifier ⇒ consent* — because that is the one that survives being applied by whoever is here in two years.
- **Publish the opt-out rate next to the numbers.** An opt-out is a hole in the denominator and the hole is not random: the hikers who switch it off are not an average slice of the hikers. DAU that quietly undercounts by a drifting amount is worse than DAU that says so.
- **What the shape is aiming at, without claiming it has arrived:** the audience-measurement exemptions European regulators grant to first-party, non-tracking, aggregate measurement (CNIL's is the clearest) describe roughly this design. Data with no identifier is largely outside GDPR's subject matter, but ePrivacy governs *storing anything on a device* regardless — and §2's dedupe needs a local counter. Nobody with a licence to say so has reviewed this. Somebody should before it ships to a general audience, and the design is deliberately the version most likely to survive that review.

## 10. Data model

```
# Client, IndexedDB — alongside the existing outbox, never ahead of it
MeasurementState
  last_active_date        date | null
  last_week_key           ISO year-week | null      (drives week_first)
  last_month_key          year-month | null         (drives month_first)
  has_ever_been_active    bool                      (drives ever_first)
  pending                 MeasurementRow[]          (capped; oldest dropped first)
  enabled                 bool                      (default true; §9)

MeasurementRow = ActiveDay | FeatureDay | TaskOutcome | ExposureDay
  # every variant carries a date and nothing that identifies a device

# Backend, Postgres
event_received            35-day retention, then deleted by a scheduled job
  date, kind, key, bucket, outcome, variant, experiment, platform, app_version
  # no user column exists — the absence is the schema, not an omission

event_daily               indefinite; what the weekly summary reads
  date, kind, key, variant, dimension values, count
  # rows below the k floor are suppressed at query time, not stored pre-suppressed
```

`UserPreferences` in [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md) gains one field under Safety / privacy — `measurement_enabled: bool` (default true) — and that doc's identity model gains a fourth kind of identity whose value is *none*, deliberately, so that the next doc to need a hiker's identity finds this one already answered.

## 11. Phased rollout

Ordered so the privacy machinery exists before the data does, which is the opposite of how this usually goes.

**Phase A — the heartbeat, and nothing else.** §2's four booleans, the ingest route with its rejection tests, the retention job, the k floor, the Settings switch, and the Privacy Policy update. Answers DAU/WAU/MAU and new-device counts, which is the stated minimum, and proves the collection path with a payload that could not leak anything if it tried.

**Phase B — features and outcomes.** §3's registry, counters and task outcomes, plus `screen_crashed`. Gated on the §7 rule being real: a feature enters the registry when its design doc names what success looks like. The first weekly summary is written here.

**Phase C — experiments.** Wire §5's `variant` and `exposure_day` to FEATURE_GATING.md's local evaluation, the aggregate arithmetic in `pipeline/`, and the `safety_surface` refusal in the manifest. FEATURE_GATING.md's Phase 3 is this phase seen from the other side; they are one piece of work, not two.

**Phase D — only if a real metric demands it.** The §5 escape hatch, and with it whatever of GrowthBook's analysis half becomes worth running. Reaching Phase D should require an argument, and this document is the place that argument gets written down.

## 12. What this changes elsewhere

- **[FEATURE_GATING.md](FEATURE_GATING.md) §6's taxonomy is replaced, not refined.** It proposed events carrying `user_id`, `club_id`, `hike_id | segment_id` and a timestamp — a stable identifier next to a trail position and a time, which is the exact pair [#252](https://github.com/OurHike/OurHike/issues/252) removed from the report API three days before this was written. Nothing was wrong with the *questions* it wanted answered; §2, §3 and §5 answer all four of them without the identifier. That doc's fourth open question is answered here and its §6 now points here instead of specifying its own shape.
- **[TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md)'s "Nothing is recorded" stands for v1 and stands permanently for error *detail*.** What v2 adds is a count with no message and no stack (§3).
- **[IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md)** gains measurement as the identity that is deliberately absent, and one preference field.
- **The Privacy Policy's "Usage analytics" paragraph** is rewritten in the change that ships Phase A, per the promise it already carries.

## Open questions (for you, not decided here)

- **Default on or default off.** §9 recommends on for a payload with no identifier and no location, because opt-in measurement at this scale returns a sample too small and too skewed to act on — which is collection with the privacy cost and none of the benefit. It is still a values call rather than a technical one, and [OurHikeValues.md](../OurHikeValues.md) #1 could be read either way.
- **k = 25 against a beta that may not reach it.** A chapter with nine active devices produces nothing but suppressed cells, and the temptation will be to lower the floor for exactly the breakdown that most needs it. Better answer is probably to compare clubs only on the aggregate and accept that per-chapter evidence arrives later, but that is worth deciding before the first person wants a number.
- **What counts as "active" on an iOS PWA**, where the app can be resumed by the OS without a hiker touching it. §2's definition is right; whether it is implementable there is a question for whoever writes it, and getting it wrong inflates DAU permanently and invisibly.
- **Whether `club_id` may appear on aggregate rows at all.** FEATURE_GATING.md's per-chapter targeting wants the comparison; a club is also a place, and a place is the thing rule 2 keeps out. Aggregate-only plus the k floor is the proposed compromise, not a settled one.
- **Who reads the weekly summary, and what happens when nobody has for a month.** A metric nobody looks at is a privacy cost with no benefit on the other side of the ledger, and the honest response to that state is to switch the collection off, not to let it accumulate against a future that might want it. Worth agreeing in advance who notices.
