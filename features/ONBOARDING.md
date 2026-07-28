# OurHike — Onboarding (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Builds on [AUTHENTICATION.md](AUTHENTICATION.md) (trail name as a real public identity depends on it existing), [UX_CUSTOMIZATION.md](UX_CUSTOMIZATION.md) (onboarding is where its settings first get a chance to surface), and [MAP_OPTIONS.md](MAP_OPTIONS.md) (the download-zoom choice already planned for Phase 2).

**Scope, since you asked for judgment rather than deciding it yourself:** split into two tiers, not one call. A **minimal Tier 1 belongs in v1 MVP** - it's really just "the smallest first-run moment needed before the app can do its one job," and one piece of it (choosing a download zoom/size) is already an MVP item in ROADMAP.md with nowhere else to live. **A richer Tier 2 is genuinely Post-MVP** - trail names depend on Authentication, and a settings walkthrough depends on UX Customization, neither of which exist as MVP features yet. Reasoning for the split below, not just the conclusion.

---

## The real constraint this doc has to satisfy, not a checklist to fill

Onboarding usually exists to explain features and collect account info. But FEATURES.md's own UX principle, pulled from the Guthook Guides case study, says close to the opposite is what makes this app work: **"fast, low-friction onboarding — minimal setup before the map is usable, no heavy signup wall blocking time-to-value."** Every screen this feature adds is friction the rest of this project has deliberately avoided elsewhere. That tension is the actual design problem here, not an oversight to work around.

## Tier 1 (v1 MVP) - the minimum required to use the app at all

- **A brief welcome/value-prop moment** - what OurHike is, that it funds the ATC and affiliated clubs, skippable in one tap. Not a multi-page pitch.
- **The download choice** - this isn't new scope, it's the first real moment for an MVP item that already exists nowhere else to live: ROADMAP.md's Phase 2 already commits to letting hikers pick a background zoom/size tradeoff (z11/z12/z13) before the whole-corridor offline download. A hiker can't use the app's core feature - the offline map - without making this choice once, so it belongs in onboarding by necessity, not by scope creep.
- **Location permission, requested in context, not upfront-and-blind.** Well-established platform guidance (both Apple's and Google's own onboarding guidance say the same thing): ask for a permission when its value is obvious, not immediately on launch before the user understands why. "You are here" GPS is the app's whole point, so asking for it right after the value-prop screen - not before it - is the right moment, not a random speed bump.

**Explicitly not in Tier 1:** account/trail name, a settings walkthrough, tutorial content. None of those have anything real to onboard into yet - Authentication and UX Customization are both still Post-MVP, and onboarding into a feature that doesn't exist isn't a v1 problem.

## Tier 2 (Post-MVP) - once there's something worth onboarding into

Everything in Tier 1, plus:

- **An optional trail name.** See below - a real hiking-culture detail, not a generic username field.
- **A one-line settings mention, not a walkthrough.** See below - deliberately not a multi-screen wizard.
- **Skippable helpful-info tips**, reusing what's already designed rather than writing new explanatory content from scratch.

## Trail name - a real hiking-culture detail, worth designing as one

A trail name isn't just a display name - it's a specific, well-known hiking convention (a nickname adopted for a hike, often given by other hikers, sometimes self-chosen) that most thru-hikers already expect to use instead of their real name. Worth designing around that reality directly rather than genericizing it into "choose a username."

**Two real tiers within this one field, worth keeping distinct:**
- **Local personalization** - a trail name stored client-side (same no-account storage model as Segments/Map Options), used to label a hiker's own device - e.g. their own Segments, their own contributions in Data Nudges/Report a Problem. Works today, needs no backend, and **is itself a small privacy feature** even before Hiker Safety's anonymity window exists: a trail name is already a partial pseudonym by convention, so defaulting to it rather than a real name is a low-friction complement to - not a replacement for - the anonymity-window mechanism [HIKER_SAFETY.md](HIKER_SAFETY.md) already designs.
- **A public, cross-device identity** - only meaningful once linked to a real [AUTHENTICATION.md](AUTHENTICATION.md) account. Worth being explicit in the UI about which tier a hiker is in ("saved on this device" vs. "linked to your account") rather than implying portability that doesn't exist yet.

Entering a trail name should stay optional at every point - even once Authentication exists, forcing it during onboarding would be exactly the "heavy signup wall" this doc is trying to avoid.

## Settings during onboarding - mention, don't force

**Deliberately not a settings walkthrough.** Every setting UX_CUSTOMIZATION.md designs already has a sensible default (auto theme, imperial units, all waypoint types shown) - onboarding's job is to say once, briefly, "you can change any of this in Settings," not march a new hiker through a wizard for preferences most people will never touch. This is the same "use the app less often, find information faster" principle FEATURES.md already commits to, applied to onboarding itself rather than just in-app usage.

## Helpful info - skippable and reused, not a new tutorial

The one piece of "helpful info" actually worth including: pointing at the waypoint icon spec / legend (already designed in [MAP_OPTIONS.md](MAP_OPTIONS.md)) so a new hiker knows what the pins mean - reusing existing design work, not writing new explanatory content. Everything else (how to plan a trip, how Segments work) is better taught contextually the first time a hiker actually opens that feature, not front-loaded into a tutorial they'll forget before they need it.

**Push-notification permission (if the wrong-way alert ships) does not belong here at all.** Consistent with "ask in context, not upfront": that permission is far better requested when its value is concretely obvious - e.g. when a hiker starts an active hike/plan - than bundled into first-run onboarding before there's any reason to say yes.

## Architecture fit

Tier 1 is entirely client-side - no backend involved, consistent with the MVP's no-account principle. Tier 2's settings mention and helpful-info tips are also client-side. Only the trail-name-as-public-identity path needs anything server-side, and only because Authentication itself does - not a separate backend dependency this feature introduces on its own.

## Data model sketch

```
OnboardingState                (client-side, IndexedDB - same storage model as Segments/Map Options)
  completed: bool
  download_choice_made: bool
  location_permission_requested: bool

TrailNameProfile                (client-side by default)
  trail_name: string, optional
  is_linked_to_account: bool     (true once/if tied to an AUTHENTICATION.md User)
```

## Open questions (for you, not decided here)

- **Whether Tier 1 needs distinct "screens" at all**, versus folding the download choice directly into the first time the map itself loads (e.g. an inline prompt rather than a separate onboarding flow) - a real minimalism question worth deciding once there's an actual app to try this in, not from this doc.
- **Trail name moderation, once it's ever public.** No content-policy question exists for a local-only name, but a public, cross-device trail name is user-generated text visible to others - worth deciding whether it needs any check before Authentication ships it as a public identity, the same moderation-conversation pattern already flagged for Hiker Safety's serious warnings.
- **Exact wording/tone of the value-prop screen** - a real copywriting decision, not a data question, best made with an actual screen in front of you.
