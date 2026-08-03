# OurHike — Identity & Privacy (Consolidated Reference, v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). **Not a new feature - a consolidated reference**, written 2026-07-28 during a cross-feature alignment review, tying together identity/privacy design that had accumulated independently across [AUTHENTICATION.md](AUTHENTICATION.md), [ONBOARDING.md](ONBOARDING.md), [HIKER_SAFETY.md](HIKER_SAFETY.md), [COMMUNITY_BUILDING.md](COMMUNITY_BUILDING.md), and [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md), and five separate small client-side settings models scattered across [MAP_OPTIONS.md](MAP_OPTIONS.md), [UX_CUSTOMIZATION.md](UX_CUSTOMIZATION.md), and Onboarding/Hiker Safety. Nothing here changes what those docs already designed - this says it in one place and gives the settings one canonical model, rather than five.

---

## Why this doc exists

Five separate docs each independently added a piece of identity or privacy design as they were written, in this order: Authentication (real accounts), Report a Problem (reporter identity, originally a device-local-id stopgap), Hiker Safety (the anonymity window), Onboarding (trail name), Community Building (check-in/mention privacy). Each made a locally sensible decision. None of them, read on its own, tells you how a hiker's identity actually looks to other people across every surface of the app - that requires reading all five and mentally merging them. This doc is that merge.

## The identity model, in one place

- **Real accounts** ([AUTHENTICATION.md](AUTHENTICATION.md)) - email/OAuth-based, needed for anyone who wants to contribute (report a problem, mark a closure) or use Community Building. Browsing the map, water, shelters, elevation profile, and even closures/warnings themselves needs no account.
- **Trail name** ([ONBOARDING.md](ONBOARDING.md)) - the identity actually *shown* to others, never a hiker's real name by default. Starts local-only (a device personalization, no backend); becomes `User.display_name` only once linked to a real account.
- **The anonymity window** ([HIKER_SAFETY.md](HIKER_SAFETY.md)) - a display-layer redaction *on top of* trail name, for a configurable number of days, masking name and exact date on **public** reports/comments. Governs the "anyone browsing the map" surface.
- **Check-in privacy** ([COMMUNITY_BUILDING.md](COMMUNITY_BUILDING.md)) - a **different audience** (a mutual Tramily or explicit safety contacts, never the general public) and a **different protection model** (opt-in per session, minimal retention, no public links) than the anonymity window. Governs a completely different surface - shared location, not public comment attribution.
- **Reporter identity** ([REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md)) - originally scoped around a device-local anonymous ID stopgap, written before Authentication was MVP. **Resolved 2026-07-28:** Authentication is MVP now too, so reporters are real (but pseudonymous, via trail name) accounts from day one - the stopgap is no longer needed.

### Who sees what, on which surface - the table none of the five source docs states on its own

| Surface | Who sees it | What they see | Governed by |
|---|---|---|---|
| A condition report, closure, or warning pin | Anyone using the app (public) | Trail name + reporter type; name and exact date masked for `anonymity_window_days` | [HIKER_SAFETY.md](HIKER_SAFETY.md) |
| A Tramily's shared location (a check-in) | Only mutually-connected Tramily/safety-contact members | Trail name + current/recent location | [COMMUNITY_BUILDING.md](COMMUNITY_BUILDING.md) |
| An "@" mention | Only the mentioned hiker (must be mutually connected) | Trail name of whoever mentioned them | [COMMUNITY_BUILDING.md](COMMUNITY_BUILDING.md) |
| A hiker's own device | Only that hiker | Full local data - trail name, all their own contributions, unredacted | [ONBOARDING.md](ONBOARDING.md) / local storage |

## Reconciling the real tension, since it's easy to read these as contradictory

Hiker Safety's anonymity window exists to stop *the general public* from linking a hiker's identity to a place and time. Community Building's Check-ins exist to let *specific, chosen people* do exactly that. **These aren't in conflict - they govern different audiences.** A hiker can have their public comments anonymized for the maximum window while simultaneously running an active Tramily check-in - the anonymity window never touches who a Tramily sees, and Check-ins never touch what the general public sees on a report. Worth stating explicitly here since neither source doc, read alone, rules out the other reading.

## The consolidated `UserPreferences` model

Replaces five separate small models with one, grouped by concern rather than by which doc happened to define it first:

```
UserPreferences   (client-side by default, IndexedDB - syncs via Authentication
                   once linked to a real account, same as trail name above)

  # Identity
  trail_name: string, optional
  is_linked_to_account: bool

  # App-wide display
  theme: light | dark | auto                    (default: auto)
  unit_system: imperial | metric                 (default: imperial)

  # Map display
  background_source: hiking_topo_live | usgs_topo_offline  (default: hiking_topo_live)
  max_background_zoom: 11 | 12 | 13
  show_roads: bool                               (default: false)
  waypoint_types_shown: set of POI types         (default: all)
  layer_detail_level: minimal | standard | full
  auto_rotate_enabled: bool                      (default: false)

  # Safety / privacy
  anonymity_window_days: int

  # Onboarding progress
  onboarding_completed: bool
  download_choice_made: bool
  location_permission_requested: bool
```

**Deliberately excluded:** `show_closures` isn't a preference at all - Map Options already recommends it stay always-on, not user-hideable, since suppressing known safety information isn't the same kind of choice as picking a background tile style. It's a fixed display rule, not a setting.

### What this replaces

| Old model | Doc it lived in | Now |
|---|---|---|
| `MapDisplaySettings` | MAP_OPTIONS.md | Folded into the Map display group above |
| `AppPreferences` | UX_CUSTOMIZATION.md | Folded into the App-wide display group above |
| `OnboardingState` + `TrailNameProfile` | ONBOARDING.md | Folded into the Identity + Onboarding progress groups above |
| `UserSafetySettings` | HIKER_SAFETY.md | Folded into the Safety / privacy group above |

Each source doc still owns the *design* of its own settings (why `auto_rotate_enabled` defaults to false, why `anonymity_window_days` exists at all) - only the data model itself moved here, so there's one canonical shape instead of five.

## Open questions (for you, not decided here)

- **Whether `UserPreferences` syncs automatically the instant an account gets linked, or needs an explicit "sync my settings" action** - a real product decision, not a data-model one.
- **Whether Tramily members should ever see a hiker's real, unredacted location even during that hiker's public anonymity window** - the reconciliation above says yes (different surfaces), but worth confirming explicitly once there's a real settings screen showing both controls side by side, since that's exactly where a hiker could reasonably expect them to interact.
- **`UserPreferences` as a name undersells that it also holds identity-sensitive fields** (`trail_name`, `anonymity_window_days`), not just cosmetic preferences - worth a better name once this actually gets built, not blocking here.
