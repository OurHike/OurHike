# OurHike — Data Nudges (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Builds directly on [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) (the "still a problem?" check reuses its existing `status` field; the check-in model is a lighter sibling to its `Report`, not a replacement) and [MAP_OPTIONS.md](MAP_OPTIONS.md) (reuses its normalize-then-`match` rendering pattern and legend). Also closes a loop FEATURES.md left open - see "What this actually feeds" below. **[FIELD_NOTES.md](FIELD_NOTES.md) (2026-08-09) now owns the record a contribution becomes**, and this doc owns when to ask for one; the split is described under "Data model sketch".

**Terminology, pinned down before anything else, because it changes the whole design:** "nudge" here means **visual prominence on the map only** - a distinct pin treatment inviting a tap. Confirmed directly while scoping this doc, specifically because [HIKER_SAFETY.md](HIKER_SAFETY.md) already scoped the wrong-way alert as "the only notification we ever send." This feature adds **no push, no in-app banner, no alert, no message** - so it doesn't touch that rule at all, rather than becoming a second exception to it.

**Scope note:** Post-MVP (Community reporting) - builds on Report a Problem, so it needs the same Phase 2+ backend that doc already requires.

---

## The core tension, stated plainly

OurHike's whole value depends on trail data staying current, but hikers - correctly - don't want to spend their limited phone time and battery feeding an app. And value #1 (hike your own hike) rules out the standard playbook apps use to solve exactly this problem: streaks, points, leaderboards, "you're behind other hikers" pressure. This feature has to get real contributions without any of that toolkit.

## Why passive map prominence solves this without needing interrupt logic at all

Because there's no push and no in-app alert, a "wants an update" pin is only ever seen by a hiker who's already looking at the map near it - which is something hikers already do constantly (checking what's ahead is the app's whole reason to exist). That gives two things for free, without building either as a separate mechanism:

- **"Don't need everyone, just a couple a day" happens by construction.** Only whoever happens to glance at the map near a stale POI sees the prompt - there's no broadcast to throttle.
- **It's self-limiting per POI.** The moment any one hiker taps through and contributes, that POI's data is fresh again and the prominent styling drops away for the next hiker along. No quota system or "we already have enough today" tracking needed - freshness itself is the off switch.

This also means the detection side needs no special-case logic (no "did they just leave a water source" departure detection, no overnight-dwell GPS tracking) - it's just: render POIs based on how stale their data is, same as any other map layer. That sidesteps the background-GPS limitation FEATURES.md already flags for the wrong-way alert entirely, since nothing here needs to run while the app is closed.

## What actually drives the pin styling

Every water source, shelter/campsite, and resupply point gets a `last_confirmed_at` timestamp (set by a fresh check-in below, or a Report a Problem "still there?" reconfirmation). Staleness is computed at render time (`now - last_confirmed_at`), not stored - the same "derive it, don't duplicate it" approach Segments already uses for parent-completion status. **Reuses [MAP_OPTIONS.md](MAP_OPTIONS.md)'s exact rendering pattern** - a normalized tier (`fresh` / `could use an update` / `stale`) driving a MapLibre `match` expression, the same mechanism already designed for blaze colors and road walkability, not a new one. Map Options' legend reads from this scheme too, same as it already does for the other two.

## Scoped to what you named, not every POI type

**Only water sources, shelters/campsites, and resupply points** get this treatment, per "just important things like food and shelter" - explicitly not viewpoints, parking, bridges, or privies. Keeps the ask limited to logistics/safety-relevant data, the same prioritization this project has applied elsewhere (e.g. Trail Blaze Colors focusing on safety-relevant accuracy, not every cosmetic detail).

## The three moments you named, mapped onto one mechanism

- **Water conditions.** A stale water-source pin, tapped, offers a quick categorical answer (flowing / trickling / dry) plus an optional note - not a form. Directly feeds "What this actually feeds" below.
- **Overnight conditions.** A stale shelter/campsite pin offers the same quick-tap pattern (available / crowded / full, say) plus an optional note. **A real integration worth having, not fully designed here:** once Segments/Trip Planning exist, marking a day's Segment complete at a shelter is the same moment a hiker would naturally see this prompt - combining them into one interaction serves "don't want to spend a ton of time on their phone" directly, rather than asking twice.
- **Problem resolved.** No new state needed - this reuses [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md)'s existing `status: submitted | verified | resolved | dismissed` field exactly. An open (`verified`) report near the hiker renders with the same prominent treatment; a tap offers "still there?" - a "no" transitions `status` to `resolved` (the report's actual resolution path already exists, just gets a fast entry point here); a "yes" doesn't change status, it just refreshes a new `last_reconfirmed_at` field, keeping "reported 3 days ago vs. confirmed today" honest the same way FEATURES.md's water-reliability framing already insists on.

## Low-friction by design, not by accident

Every interaction above is a single tap for the common case, with an optional note/photo as an escalation path - the same "quick answer first, detail later" shape Report a Problem already uses. This is the direct answer to "hikers don't really want to spend a ton of time on their phone": the default path costs one tap, not a form.

## New: `ConditionConfirmation` - a lighter sibling to Report a Problem's `Report`, not a replacement

**Superseded 2026-08-09 — the record moved to [FIELD_NOTES.md](FIELD_NOTES.md), the reasoning below did not.** A confirmation turned out to be a field note with a tag and no text, and shipping both models would have left two near-identical things for a later reader to reconcile. Everything this section argues - that a confirmation is not a problem report, that routing it through the moderation queue would be overhead for nothing to verify, that it escalates into a real `Report` when the quick answer indicates a problem - is why `FieldNote` publishes without a queue and hands off to Report a Problem for anything safety-shaped. Read on for the argument; read that doc for the model.

A "water's flowing fine" or "shelter was fine" check-in is a **confirmation**, not a problem report - routing it through the same moderation queue Report a Problem uses for accusations/hazards would be real overhead for no reason (there's nothing to verify about "someone confirmed normal conditions"). So it's a separate, lighter model that writes directly to the POI's `last_confirmed_at` with no moderation step. **It can still escalate into a real `Report`** when the quick answer actually indicates a problem (tapping "dry" or "full" prompts "want to report this?") - reusing Report a Problem's machinery exactly where it's actually needed, rather than duplicating problem-handling logic here too.

## What this actually feeds - closing a loop FEATURES.md already left open

FEATURES.md's Water Reliability Prediction section already names its needed input: "historical hiker reports (frequency/recency of 'dry' vs 'flowing' reports at a source)" - but nothing before this doc actually designed how that data would get collected. This feature is that collection mechanism. Worth having front of mind when that feature is eventually built: it doesn't need its own data-gathering design, this is already it.

## The opt-in mode — added 2026-08-06, when this became v2's Phase A

[VOLUNTEERING.md](VOLUNTEERING.md) scopes this doc as the first phase of the Volunteer tab, which adds a `contribute_conditions` toggle to [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md)'s `UserPreferences` (default off). Everything above is what a hiker who has *not* opted in sees, and it stays exactly as designed — passive prominence, nothing else. Three things change for a hiker who has:

- **A photo becomes the default rather than the escalation.** The one-tap rule above exists because the passive version interrupts someone who never asked. Someone who opted in has consented to the longer version, and a photo of a dry spring is worth more to the next hiker than the word "dry." Still skippable, never required — the escalation path just runs in the other direction.
- **Two more surfaces, both places the hiker already looks.** A stale water source in the next ten miles carries the same tier styling in the waypoint lanes beside the elevation ribbon (`client/src/chrome/WaypointLanes.tsx`) — the most-looked-at strip in the app, and it costs a `match` expression because the lane is already drawn. And a "places you passed today" list in the Volunteer tab, for logging from memory at camp.
- **Water first, then shelters and campsites, then everything else** — an explicit priority order rather than treating the three scoped types as equal. A spring with no data is a hiker carrying the wrong amount of water.

**The "places you passed today" list has a trap in it**, and it is the one thing in this addition that could undo the section below: a list of missed opportunities is a guilt mechanic wearing a helpful hat. The rule that keeps it honest is that **it never counts, and never mentions what was skipped**. If it cannot be built without a number on it, it should not be built.

None of this adds a notification. The opt-in is consent to be *asked more thoroughly when you are already looking*, not consent to be interrupted — so the rule this doc opens with is unchanged, and [HIKER_SAFETY.md](HIKER_SAFETY.md)'s wrong-way alert stays the only notification the app ever sends.

## The anti-gamification guardrail - a pattern this project keeps needing, worth naming as one

This is the third feature that has had to say this explicitly: Segments ("deliberately simple, not gamified"), Volunteering ("no leaderboard of volunteer hours... no public volunteer profile"), and now this one. **Where its boundary actually falls was settled 2026-08-06 in [VOLUNTEERING.md](VOLUNTEERING.md)**, when a personal impact record ran straight into the sentence below: the guardrail targets *comparison and pressure*, not *memory*, and that doc carries the four rules keeping the distinction real. Read it before concluding this paragraph forbids something. **No streaks, no per-hiker contribution counts shown anywhere, no leaderboard, no "you haven't contributed lately" messaging, no visible count of how many other hikers already passed without updating.** The entire mechanism is passive map styling - nothing gamified layered on top of it, ever.

## Architecture fit

The write path (submitting a check-in, or reconfirming/resolving a report) needs the same Phase 2+ backend Report a Problem already requires - user-submitted data needs somewhere to land, and the same "minimal identity for reporters" open question that doc already raised applies here too, not a new one. The read path (which pins render as stale) can most likely piggyback on however Report a Problem's own condition-report display ends up being served, rather than needing a separate decision here.

## Open questions (for you, not decided here)

- **Exact staleness thresholds per POI type** - a water source's flow probably goes stale faster than a shelter's general condition. A real field-tuning question once there's real usage data, not something this doc can responsibly guess at.
- **Whether `ConditionConfirmation` needs its own lightweight rate-limiting/identity**, or can ride entirely on whatever Report a Problem and Authentication eventually settle on - leaning toward the latter, not designed twice.
- **Whether a stale pin should ever hint "a few hikers have passed without updating"** - flagged as a real risk of backsliding into the gamification/guilt-messaging this doc explicitly rules out above. Leaning no, but not force-decided here.
- **The Segments day-complete integration** - a real opportunity named above, but it depends on Segments/Trip Planning existing first, and isn't designed in full here.

## Data model sketch

**The record lives in [FIELD_NOTES.md](FIELD_NOTES.md) as of 2026-08-09** - `ConditionConfirmation` became `FieldNote`, which is the same thing with room for free text and a dispute value. What a quick tap writes is unchanged: an observation, a `reporter_type`, and the timestamp that `last_confirmed_at` is derived from. This doc owns *when to ask*; that one owns *what is stored*.

What this feature still needs from that model, and what remains its own:

```
POI                                (water/shelter/resupply - derived, stored nowhere)
  last_confirmed_at                max(observed_at) over visible FieldNotes
  staleness tier                   computed at render time: fresh | could_use_an_update | stale
                                     -> drives this doc's pin prominence

Report                             (REPORT_A_PROBLEM.md's existing model, one addition)
  + last_reconfirmed_at            (distinct from the original timestamp - "still there as of X",
                                     not "originally reported on X")
```
