# Feature Gating & Experimentation

## Why this matters for OurHike

Feature gating is the right platform-level investment for OurHike because it:

- makes every future feature safer to ship.
- lets local chapters opt in only when they are ready.
- allows evidence to drive product decisions instead of guesswork.
- keeps wild experiments from affecting the whole trail network.
- enables transparent communication for hikers who are seeing a new experience.

The goal is not to gate the app itself, but to gate feature rollout. The default experience must remain the current production behavior, and any gating or experiment failure must degrade gracefully to stable functionality.

---

## Requirements

1. Local chapter control
   - Chapters should be able to opt features in or out for their own region.
   - Chapter targeting must be a first-class dimension in the gate model.

2. Experimentation and evidence
   - Support A/B/n experiments with clear metrics.
   - Allow multiple influencers: club, user role, device type, trail section, hike type, and other attributes.
   - Support sampling and holdouts so we can ramp features safely.

3. Dashboard-driven analysis
   - Provide clear dashboards for results, not raw data dumps.
   - Translate findings into easy-to-read outcomes: which variant performed better, where, and why.

4. Fail-safe defaults
   - The app must never be stopped by a gate, especially on trail.
   - Any evaluation error or missing config must default to the stable production path.

5. Clear communication
   - Users should know when they are behind a feature gate or participating in an experiment.
   - Messaging should explain that the feature is being tested and what to expect.

---

## Recommendation

### Primary recommendation: GrowthBook (self-hosted)

**GrowthBook is the strongest fit for OurHike's needs.** It is open source, supports both feature flags and experimentation, and includes analysis dashboards for A/B tests.

Why GrowthBook?

- Built for experimentation, not just flags.
- Supports percentage rollouts, phased releases, and feature flag targeting by attributes.
- Lets us define metrics and view experiment results in dashboards.
- Open-source server and SDKs are available for both browser and Python.
- Can be self-hosted in the same volunteer-friendly stack as the rest of the project.

How it helps OurHike:

- Local chapters can be a targeting attribute (`chapter_id`, `club_id`, `region`).
- A/B tests can use multiple attributes to measure influence across chapters, hiker type, device, and route.
- Sampling is built in: start with 10% of eligible users for a new experience, then widen.
- Data lives in our control, avoiding vendor lock-in.

### Secondary option: Unleash + Metabase/Superset

If we want a leaner first step for pure feature gating, **Unleash** is a solid open-source feature flag server with strong targeting and rollout strategies.

Why Unleash?

- Open-source and mature.
- Supports strategy-based targeting by user attributes and percentage rollout.
- Good when the immediate need is safe rollout rather than deep experiment analytics.

Analytics would be added separately via a dashboard tool such as **Metabase** or **Apache Superset**.

### Alternative option: Flagr for strong A/B capabilities

**Flagr** is worth considering if we want a single open-source platform with built-in experiment analytics and statistical reporting. It is less widely known than GrowthBook, but it delivers both flags and A/B evaluation.

---

## Strong recommendation summary

1. Start with **GrowthBook self-hosted** for integrated flags + experiments.
2. Use **GrowthBook dashboards** for initial experiment reporting.
3. Complement with **Metabase** or **Superset** on top of Postgres for business-level dashboards if we want additional query power.
4. Use **OpenFeature** or a small internal abstraction layer to keep the runtime evaluation implementation decoupled from the selected backend.

---

## Proposed architecture

### 1. Feature gate model

Define feature gates as first-class objects.

Example fields:

- `key`: stable feature identifier, e.g. `new-closure-flow`.
- `description`: why the gate exists and what we are testing.
- `defaultVariant`: the stable, production-safe behavior.
- `rules`: ordered rules that target chapters, user roles, device types, or other attributes.
- `rolloutPct`: how much traffic is exposed when a rule matches.
- `variants`: named variants such as `control`, `enabled`, or `preview`.
- `status`: draft / running / paused / retired.

### 2. Targeting dimensions

At minimum, support:

- `chapter_id`/`club_id`
- `user_id` / anonymous device id
- `role` (`hiker`, `maintainer`, `club_admin`)
- `device_type` (`web`, `ios`, `android`)
- `trail_segment` / `region`
- `app_version`
- `locale`

This supports multiple influencers and lets us measure whether an experiment behaves differently by chapter, device, or user role.

### 3. Safe fallback logic

The core safety rule is:

- evaluate the gate when possible;
- if evaluation fails, use the stable control/default path;
- never allow a flag error to prevent the app from loading or the feature from rendering.

Implementation guidance:

- Keep feature flag evaluation off the critical app startup path when possible.
- If config is unavailable, treat the user as `control` and continue.
- Log failure details for diagnostics, but do not expose them to the hiker.
- For offline clients, cache the latest feature manifest and use it; if stale or missing, continue with stable behavior.

### 4. Offline-first support

Because OurHike is offline-capable, the gate system must also be tolerant of offline or intermittent connectivity.

- Fetch a minimal gate manifest on app startup or sync.
- Cache it locally in IndexedDB or the service worker cache.
- Evaluate gates locally with the cached manifest.
- If the device is offline or the manifest cannot be fetched, use the last-known config or stable default.

This keeps gating safe on trail and still lets chapters control behavior when the hiker has had at least one online sync.

### 5. Chapter-level control

Make chapter/club an explicit targeting attribute.

- Store `club_id` or `chapter_id` on the user profile when available.
- For unauthenticated hikers, infer chapter from the downloaded trail package or selected region.
- Let chapter admins choose gate settings for their own region.
- Use chapter-level rules as a first pass, then apply user-level or percentage-based overrides.

This means a chapter can say:

- `club_id = atc` gets `new-closure-flow` enabled for 100%.
- `club_id = nynjtc` gets `new-closure-flow` enabled for 25%.
- everyone else sees the stable control.

### 6. Transparently communicate to users

Every gate should carry a presentation contract.

- If the user is in a non-control variant, show a short banner or badge.
- Example text: "This feature is currently in preview for your chapter. If you notice anything unexpected, please let us know." 
- If local chapter admins are running experiments, consider a chapter-specific note like: "Your chapter has enabled an experimental hiking route preview for this trail."
- For any new gate, define a `helpUrl` or `learnMore` endpoint so the app can link to a short explanation.

---

## Evidence & analytics

### Event tracking

Track events tied to gates and user outcomes.

Primary event categories:

- `feature_gate_exposed` - user evaluated by the gate.
- `feature_gate_viewed` - user saw the gated UI.
- `feature_gate_action` - user performed the core action under test.
- `feature_gate_error` - evaluation or fallback occurred.
- `feature_gate_outcome` - whether the result was positive, negative, or neutral.

Example event payload:

- `feature_key`
- `variant`
- `user_id` or anonymous identifier
- `club_id` / `chapter_id`
- `hike_id` / `segment_id`
- `app_version`
- `device_type`
- `timestamp`
- outcome-specific attributes (e.g. `reported_closure`, `route_saved`)

### Dashboard & analysis

GrowthBook can consume the event store and deliver built-in experiment dashboards.

For additional business-level analysis, add an open-source BI layer:

- **Metabase** for simple query + dashboard creation.
- **Apache Superset** if we want more advanced SQL exploration.

The fastest path is:

1. Store feature events in Postgres or a dedicated analytics dataset.
2. Let GrowthBook read a derived metric table for experiment reporting.
3. Use Metabase/Superset for chapter-level, trail-level, and cohort reports.

### What to measure first

- adoption and engagement for the gated feature.
- crash / fallback / error rates.
- chapter-level performance differences.
- retention of users exposed to the experiment.
- any safety or usability regressions.

---

## Phased rollout plan

### Phase 1: Basic gate infrastructure

- Add a `features/FEATURE_GATING.md` design doc.
- Define a simple feature gate manifest format.
- Add a backend endpoint to serve gate config and a client runtime to cache it.
- Implement the safe fallback pattern in the client and backend.
- Add a stable `control` variant for every new gate.

### Phase 2: Chapter targeting and local control

- Extend the profile model with `club_id` / `chapter_id`.
- Allow chapter-level gate rules in the backend.
- Add an admin UI or simple config mechanism for chapter admins to control their own gates.
- Surface transparent messages for users behind gates.

### Phase 3: Evidence collection and dashboards

- Instrument gate exposure and outcome events.
- Self-host GrowthBook, connect it to the event store, and build initial dashboards.
- Run the first A/B test on a low-risk surface.
- Review results before widening the rollout.

---

## Open questions

- Should the first rollout be a self-hosted GrowthBook server or a smaller Unleash deployment?
- How will club/chapter ownership be represented for offline users who are not signed in?
- Which early metrics are the minimum required before a feature graduates from experiment to stable?
- How will we minimize the privacy footprint of event tracking while preserving useful experiment signal?

---

## Why this is the right opportunity now

A feature gate platform is not just a nice-to-have add-on. For OurHike it is a leverage point:

- It protects safety-sensitive features from broad release too early.
- It gives chapters agency over their own rollout pace.
- It makes product decisions measurable and defensible.
- It supports the projects values of low-maintenance, open-source, and trustworthy software.

If we build it early, every later feature becomes easier to ship and safer to operate.