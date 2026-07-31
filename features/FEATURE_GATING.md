# OurHike — Feature Gating & Experimentation (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Overlaps deliberately with ROADMAP.md's Deferred "Multi-club admin/config tooling" — per-chapter flag control is one of the first real things that tooling needs, so this doc treats it as the same effort, not a competing one. Post-MVP: nothing here blocks the map, safety features, or launch.

**Why now, not later:** the ask itself is the reasoning — a working feature-gate makes every feature built *after* it land with real evidence behind it instead of a guess, so the earlier it exists post-launch, the more of the roadmap benefits. Recommend building this right after MVP launch stabilizes, not deferred indefinitely with everything else in Phase 5+.

**What this needs to deliver, restated up front:** local chapters can opt features in or out for their own region, independent of app-code changes. A/B/n experiments run against real evidence (club, role, device, trail segment, hike type as targeting dimensions), with sampling/holdouts to ramp safely. Results land in dashboards that explain findings, not raw dumps. Every failure mode - missing config, evaluation bug, unreachable backend - defaults to stable production behavior, never an error state, and never blocks the app. A hiker behind a gate can always find out.

---

## 1. The non-negotiable constraint, stated first because it drives every other decision

**A broken, unreachable, or misconfigured gate must never be able to stop the app from working — especially mid-hike, with no signal.** This shapes the architecture more than the choice of tool does. Three consequences, all hard requirements, not preferences:

- **Evaluation must never require a live network call.** Not "should be fast when offline" — must be structurally incapable of blocking on one. A hiker locked out of the map because a flag-evaluation request timed out on a ridge with no signal is a real, unacceptable failure mode this design has to make impossible, not just unlikely.
- **Every failure mode resolves to the same default: current production behavior.** Missing cache, stale cache, malformed payload, unreachable backend, an unknown flag key, a bug in the evaluation code itself - all of them fall through to "act like the flag doesn't exist," not to an error state, a blank screen, or a guess. One fallback path, applied universally, not a per-flag judgment call that's easy to get wrong under pressure later. Log the failure for diagnostics; never surface it to the hiker.
- **The fallback default lives in the app bundle itself, not in any fetched config.** If it were part of the synced payload, a bad sync could corrupt the fallback along with everything else. It has to be a hardcoded constant shipped with the app - the one thing that's true even if literally nothing else is reachable.

## 2. Architecture: the backend mediates, the client never talks to the flag tool directly

This is the design choice that actually delivers section 1, not the tool choice - the tool matters less than what nothing on the hiker's phone is ever allowed to depend on.

```
[Self-hosted flag/experiment tool]
        |  (backend polls periodically, or on each authenticated session)
        v
[OurHike FastAPI backend]  -- resolves club/chapter + user attributes into a targeting context,
        |                      caches the last-good evaluation result server-side too
        |  (bundled into the same sync the client already does for map/report data)
        v
[Client - PWA/Capacitor]  -- writes the flag payload into the same IndexedDB cache
        |                      already used for offline map data (same mechanism, not a new one)
        v
[FlagEvaluation.evaluate(key)]  -- a pure, synchronous, local function. Reads only the cache.
                                    Cache missing/stale/malformed/unreachable -> hardcoded default.
                                    Never awaits anything. Cannot throw in a way that breaks a caller.
```

Why route through the backend instead of the client SDK talking to the flag tool directly (the vendor-default setup for every tool researched below): it keeps a third-party JS SDK and its network behavior out of an app whose entire value proposition is reliable offline operation, gives one place (the backend) to add retries/circuit-breaking/logging instead of every client needing its own, and makes per-chapter targeting a server-side lookup against data the backend already owns (club membership) rather than something the client has to know how to compute. The backend already syncs report/closure/preference data on the same rhythm - this is one more field in that same payload, not a new sync path.

**Keep the evaluation call-site decoupled from whichever tool sits behind it.** Client and backend code should call a small OurHike-owned interface (`evaluate(key, context) -> variant`), not GrowthBook's SDK directly - either a thin internal wrapper or the real [OpenFeature](https://openfeature.dev/) standard (a vendor-neutral CNCF spec built for exactly this). The tool behind that interface is a swappable implementation detail, not something every call site needs to know about - relevant given section 3 below is a strong recommendation, not a permanent commitment.

## 3. Tool recommendation: GrowthBook (self-hosted), PostHog as the credible alternative

Researched four real candidates (GrowthBook, Unleash, Flagsmith, PostHog) against: self-hostable under a genuinely open license, works with zero live network dependency once synced, produces dashboards that explain *why* a result is significant (not just raw counts), and fits this project's established "boring, low-maintenance, reuse what we already run" preference (see TECHNICAL_ARCHITECTURE.md's DuckDB/R2 choices for the same instinct applied elsewhere).

**Recommendation: [GrowthBook](https://github.com/growthbook/growthbook)**, self-hosted, MIT-licensed core.

- **The offline-safety philosophy is close to a direct match, not something bolted on.** GrowthBook states its own design principle as "your application should never depend on GrowthBook being available" - SDKs cache flag definitions with stale-while-revalidate semantics and keep evaluating correctly if connectivity drops entirely. That's the same posture section 1 requires, from the tool's own stated intent, not something OurHike has to fight the tool to get.
- **Its experimentation *analysis* is warehouse-native SQL - and OurHike already has a usable warehouse for that half.** For the statistical analysis (Bayesian/frequentist, sequential testing, guardrail metrics on the free tier - see the cost section below for what's Enterprise-only), GrowthBook queries whatever SQL source you point it at rather than running its own OLAP store - pointing it at the existing Supabase Postgres avoids standing up a *second* analytics database on top of the operational one below.
- **Real cost, stated plainly:** two things, not one - OurHike needs to design and populate its own event-logging schema in Postgres (which experiment ran, which variant, which outcome events - see section 6 below for a starting taxonomy) before GrowthBook's dashboards have anything to analyze, *and* (see cost section) GrowthBook's own operational store is a separate database it does bring with it.

**PostHog is the honest alternative, not a lesser option - a real trade-off, not a tiebreaker.** Also MIT-licensed, self-hostable, also supports local/bootstrapped offline evaluation. The difference: PostHog owns its *own* event ingestion (call `capture()`, PostHog stores and indexes it in a ClickHouse instance it provisions for you) - meaningfully less setup work to get a first experiment running end-to-end, because there's no schema to design before the first dashboard has data. The cost is a heavier self-hosted stack (ClickHouse plus supporting services, more infrastructure than GrowthBook's footprint below, not less), and an experimentation feature that's a strong module on a broader analytics platform rather than the platform's central specialty. If OurHike wants one tool to also eventually cover general product analytics and session replay - not just this ask - PostHog is worth revisiting; for "get a rigorous, safe feature-gate shipped with the least new infrastructure," GrowthBook is still the better fit, just not a *zero*-new-infrastructure fit - see below.

### Cost, specifically (corrected after checking, not assumed)

- **The software: genuinely $0.** MIT-licensed self-hosted core, unlimited seats, no GrowthBook licensing fee - you only pay for the infrastructure you run it on.
- **But GrowthBook's own operational data (flag definitions, experiment configs, user accounts) requires MongoDB specifically - not Postgres, despite the warehouse-native analysis side above.** This is a real, separate piece of infrastructure OurHike doesn't currently run. Small-scale (a few hundred flags/experiments) needs under 512MB storage and shared/modest CPU-RAM - realistically free-tier-compatible on MongoDB Atlas's perpetual free M0 tier, or a small container alongside wherever the FastAPI backend ends up hosted (Fly.io/Render/Railway, the same shortlist `LAUNCH_CHECKLIST.md` already names). Not expensive, but not "reuse what we already run" the way the warehouse side is.
- **The GrowthBook app server itself** (NextJS + Express + a Python stats engine, one Docker image) is similarly small at this scale - likely marginal cost added to whatever's already hosting the backend, possibly free-tier-compatible on its own.
- **Free tier ceiling worth knowing: 1 project, 2 environments.** This doc's per-chapter design (section 4) uses *targeting attributes* within one project (`club_id` as a rule), not separate GrowthBook projects per chapter - deliberately, so it stays inside the free tier. If that ever changes to "each chapter wants its own fully separate project," that crosses into Enterprise licensing (custom pricing, contact sales) - worth knowing now so nobody builds toward that shape by accident later.
- **Enterprise-only, and worth flagging given the safety framing in section 1:** guardrail metrics and holdout experiments - GrowthBook's own automated "is this experiment quietly hurting a metric we care about" checks - are gated behind a paid Enterprise license, not available self-hosted for free. For v1, that means guardrail-style safety has to be a manual watch (someone checking error/crash rates during a rollout) rather than an automated stop, until/unless Enterprise licensing is worth it later. SSO/SCIM are also Enterprise-only but low-relevance here - a handful of trusted maintainers logging into GrowthBook's own dashboard directly doesn't need automated identity-provider sync.

**Ruled out:** Unleash and Flagsmith are both credible, real open-source options, but neither is built around experimentation analysis the way GrowthBook is - they're feature-flag platforms first, with A/B analysis as a lighter add-on. Given "good insights is paramount" was the explicit ask, not just "ship flags safely," the two tools built experimentation-first were the right shortlist. (A third name, Flagr, came up in a separate independent pass at this same question - not included here since it wasn't independently verified against the criteria above the way these four were; worth a real look before ruling in or out, not a name to carry forward on faith.)

## 4. Per-chapter control

Each club/chapter gets a targeting attribute the backend already knows (club membership, once multi-club admin exists even in minimal form) - GrowthBook's targeting rules key off arbitrary attributes passed at evaluation time, so "NYNJTC hikers see the new elevation chart, ATC hikers don't yet" is a targeting rule, not a code branch. A chapter that wants zero involvement gets zero involvement by default - flags default to "off/current behavior" for any club that hasn't opted in, matching "easy and up to local chapters if they want it" directly: opting in is a rule a club admin sets, not a decision that touches app code.

**Minimum useful targeting dimensions** (what GrowthBook's rules should be able to key off, at launch): `club_id`/`chapter_id`, `user_id` or anonymous device id, `role` (hiker / maintainer / club_admin), `device_type` (web / iOS / Android), `trail_segment` or region, `app_version`. Concrete worked example of what a rule set looks like: `club_id = atc` → `new-closure-flow` enabled 100%; `club_id = nynjtc` → same flag at 25%; everyone else → stable control. This is standard GrowthBook rule configuration, not custom code OurHike has to build.

**For unauthenticated hikers** (browsing needs no account, per this project's own standing rule), chapter can't come from a login - infer it from the downloaded trail package/selected region instead, same signal the client already has for other region-scoped behavior.

## 5. Clear communication when a hiker is behind a gate

Two layers, not one, because they serve different moments:

- **In-context, at the point of use:** a small, non-blocking marker directly on or near the gated UI element itself - e.g. a quiet "Preview" tag, not a popup or interrupt. This is what actually satisfies "clear communication" in the moment it matters, and it's a different thing from a notification: it's passive, local information sitting where a hiker's eyes already are, not something pushed at them. Doesn't conflict with the app's standing anti-interruption posture (see below) because nothing fires, nothing requires acknowledgment, nothing appears unless they're already looking at the affected feature.
- **On request, for the full picture:** a quiet, permanent Settings entry ("Experimental features: 2 active" or similar) that opens a detail view listing exactly which flags are active for them and what each one changes, in plain language. Consistent with the app's existing UX principle, already stated elsewhere in this project: "use the app less often, and find information faster when you do... no reason to manufacture engagement" (HIKER_SAFETY.md) - same posture as how the app already handles staleness indicators elsewhere: visible on request, never in the way.

## 6. Evidence: what to track, and where results show up

**A starting event taxonomy** (answers what to log without over-specifying before real features exist to measure against - expect this to evolve once there's a first real experiment):

- `feature_gate_exposed` - a user was evaluated by the gate (the raw exposure count experiments are measured against).
- `feature_gate_viewed` - the user actually saw the gated UI, not just got assigned a variant.
- `feature_gate_action` - the user performed the core action under test.
- `feature_gate_error` - evaluation fell through to the fallback default (this is the signal that tells you section 1's safety net is firing in practice, not just in theory - worth its own dashboard panel from day one).

Each event carries `feature_key`, `variant`, `user_id`/anonymous id, `club_id`, relevant hike/segment context, `app_version`, and a timestamp - written to Postgres, which is what GrowthBook's warehouse-native analysis queries directly (section 3). **What to measure first**, once there's a real experiment running: adoption/engagement for the gated feature, the `feature_gate_error` rate specifically, chapter-level differences, and any usability regression - in that order of priority, safety signal before growth signal.

## Data model additions

```
FeatureFlagCache            (client-side, IndexedDB - same mechanism as offline map data)
  flags: { [key]: { variant: string, payload: any } }
  synced_at: timestamp
  last_sync_failed_at: timestamp | null   (drives a quiet staleness indicator only -
                                            never affects evaluation itself)

FlagEvaluation.evaluate(key, context)    (client-side, pure, synchronous, offline-safe by construction)
  -> cache has key AND cache is well-formed AND synced_at is recent enough:
       return cache.flags[key].variant
  -> anything else at all (missing, stale, malformed, key unknown):
       return HARDCODED_DEFAULTS[key]    (shipped in the app bundle, never fetched, never overridden)

ClubFlagTarget               (backend, Postgres - extends the eventual multi-club admin model)
  club_id, flag_key, enabled: bool        (opt-in per chapter, defaults to false/current-behavior)

FeatureGateEvent              (backend, Postgres - what GrowthBook's warehouse-native analysis queries)
  event_type: exposed | viewed | action | error
  feature_key, variant, user_id, club_id, hike_id | segment_id, app_version, timestamp
```

## Open questions (for you, not decided here)

- **Sync cadence and "recent enough" threshold** for FlagEvaluation's staleness check - needs to balance getting hikers onto new experiments promptly against not treating a hiker who's been offline for a multi-day stretch as suddenly ineligible for cached flags they were already correctly assigned to. A field-testing question, similar to the wrong-way alert's thresholds.
- **Who administers flags day to day** - a full admin UI is real scope; a minimal v1 (a maintainer editing GrowthBook's own dashboard directly, backend just proxies/caches) is probably enough to start, with a proper in-app "chapter admin" surface as later work once multi-club tooling exists for real.
- **Self-hosting GrowthBook alongside the existing backend** - same host as FastAPI, or a separate small service (which also decides whether the new MongoDB requirement rides alongside it or lives separately)? An infra/ops choice for whoever sets up hosting, not a data-model question.
- **How to minimize the privacy footprint of the event taxonomy above** while still preserving useful experiment signal - this project has a consistently privacy-conscious stance elsewhere (IDENTITY_AND_PRIVACY.md); worth a real pass once real events exist, not assumed safe by default.
