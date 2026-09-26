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
- **Measurement identity — none, deliberately** ([EVENTING.md](EVENTING.md), added 2026-08-09) - the fourth kind of identity is the one v2's analytics does not have. No account id, no device id, no session id, no rotating pseudonym: unique-user counts are deduplicated on the device and sent as answers rather than as evidence, so the identifier this list would otherwise have gained does not exist. Recorded here so the next doc that needs it finds the question already settled rather than open.
- **A contact detail, given deliberately and held privately** ([APP_FAILURE_REPORTS.md](APP_FAILURE_REPORTS.md), added 2026-08-20) - the fifth kind of identity, and the only one in this document a hiker *hands over on purpose in order to be found*. Everything else here is about limiting who can link a person to a place; this is somebody asking to be contacted after the app failed them on the trail. Free text, optional, unparsed - an email, a phone number, a forum handle, where they will be on Friday. It lives in one column of `app_failures`, which is RLS-locked and which **no endpoint serves**, so it never reaches any of the surfaces in the table below. It is never attached to a report, a photo, a check-in or a public issue. **Retention is undecided for the reports that arrive with no account, and that is still a real gap** - most of them do, and nothing deletes those rows. What is settled since #895 is the narrower half: a report filed while signed in loses both its `reporter_id` and its `contact` when that hiker deletes their account, while `what_happened` stays, because the bug is ours to fix and the way to reach them was theirs to withdraw. The form still promises only that the maintainers see it.
- **A hiker's own private content, held on a server for their own convenience** ([ACCOUNT_SYNC.md](ACCOUNT_SYNC.md), added 2026-08-20) - the sixth kind, and the one that looks harmless: trips, the planned hike and private waypoint photos, published to nobody, attributed to nobody, visible to nobody else - and, for the first time, out of the hiker's sole physical control. It reaches none of the surfaces in the table below and does not touch the anonymity window, which governs what the *public* sees. Two things follow. Row-level security is the floor rather than the design: a private photo never enters `poi_photos`, because sharing grants a CC BY-SA 4.0 licence that cannot be taken back and syncing grants nothing. And **account deletion, which was a gap costing nothing, became a promise** the moment phases A and B put preferences and trips on a server - so it is built (#895, ACCOUNT_SYNC.md phase E, `DELETE /profiles/me` and `GET /profiles/me/export`). Two limits belong here rather than only in that document. **A shared photo keeps the trail name it was credited under**, because CC BY-SA 4.0 was granted on that condition and deletion cannot walk a licence back; the deletion screen says so before the button. And **this backend cannot delete the Supabase Auth user** - that needs a service-role key `app/config.py` does not hold - so the email address and password Supabase stores outlive the OurHike account until something with that key removes them. The account cannot be signed back into (`core/auth.py` refuses a row carrying `deleted_at`), which is the part that would otherwise hurt somebody; the leftover credential itself is an open gap.
- **Reporter identity** ([REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md)) - originally scoped around a device-local anonymous ID stopgap, written before Authentication was MVP. **Resolved 2026-07-28:** Authentication is MVP now too, so reporters are real (but pseudonymous, via trail name) accounts from day one - the stopgap is no longer needed.
- **A real name put to one report, and a consent to be contacted about it** ([REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) step 5, added 2026-09-17, [#1563](https://github.com/OurHike/OurHike/issues/1563)) - the seventh kind, and like the contact detail above it is one a hiker *hands over on purpose*. Every report is signed with the trail name by default and nothing changes that; the receipt and the long form offer, per report, to sign with the hiker's real name instead (`signed_name`, `signed_name_kind`) and to tick "You can contact me for more information" (`contact_ok`). The real name is kept in the preferences as `real_name` so a second report offers it, and it reaches a report only when chosen for that report. Both fields are withheld from every response but the reporter's own and a moderator's, exactly as `reporter_id` is (`ReportOut.for_viewer`), so they never reach the public surfaces in the table below; account deletion clears them from every report the hiker filed. **No address travels with the consent** - the account is how a club reaches them - and an unticked box is a no rather than an absence.

### Who sees what, on which surface - the table none of the five source docs states on its own

| Surface | Who sees it | What they see | Governed by |
|---|---|---|---|
| A condition report, closure, or warning pin | Anyone using the app (public) | Reporter type only — see "What v1 actually ships" below; the trail name, and the date masking, are the window's job | [HIKER_SAFETY.md](HIKER_SAFETY.md) |
| A Tramily's shared location (a check-in) | Only mutually-connected Tramily/safety-contact members | Trail name + current/recent location | [COMMUNITY_BUILDING.md](COMMUNITY_BUILDING.md) |
| An "@" mention | Only the mentioned hiker (must be mutually connected) | Trail name of whoever mentioned them | [COMMUNITY_BUILDING.md](COMMUNITY_BUILDING.md) |
| A hiker's own device | Only that hiker | Full local data - trail name, all their own contributions, unredacted | [ONBOARDING.md](ONBOARDING.md) / local storage |
| A trip or a private photo synced to the hiker's account | Only that hiker, on their own signed-in devices | Their own content, unredacted, served to nobody else and public nowhere | [ACCOUNT_SYNC.md](ACCOUNT_SYNC.md) |
| A contact detail on an app-failure report | Whoever maintains OurHike, reading the database directly | Whatever the hiker typed, verbatim. Served by no endpoint at all, so this row has no API surface to get wrong | [APP_FAILURE_REPORTS.md](APP_FAILURE_REPORTS.md) |
| The name a report was signed with, and whether its reporter may be contacted | The reporter, and a moderator reading the queue | "signed Jane Doe (real name)" and "may be contacted" on the moderation row, and nothing on any public surface: the public serialisation drops both with `reporter_id` | [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md), `backend/app/schemas/report.py` |
| A recorded GPS trace | Only that hiker, on the one device that recorded it | A continuous list of their own positions, timestamped, with the accuracy the phone claimed - the most precise record of somebody's movements this app can hold, kept until they delete it. No endpoint, no sync, and no path to an app-failure report: `readAll`, `traceToCsv` and `downloadTrace` have one caller between them, the manual export. It leaves the phone only if the hiker saves the file and sends it somewhere themselves | #1180, `client/src/lib/gpsTrace.ts` |
| What a podcast card's ▶ or + sends to Spotify | Spotify | ▶ loads Spotify's own player, so Spotify gets the episode id, this phone's IP address and any Spotify cookies the browser holds. + sends the same episode id with the hiker's own Spotify token, to save that one episode to their library. No position, mile or hike id is sent - the episode list is fetched whole and matched on the phone - but an episode picked for one hike says something about which hike, which is why nothing reaches Spotify before a tap. The token stays in this browser's storage and no OurHike server sees it. The phone apps send nothing: they hand the hiker a link | [#1683](https://github.com/OurHike/OurHike/issues/1683), `client/src/chrome/PodcastCard.tsx`, `client/src/lib/spotify.ts` |

### What v1 actually ships, as against the row above — written down 2026-08-07

The table describes the anonymity window, and the window is Post-MVP (ROADMAP.md). Left at that, the row read as a present-tense description of a v1 that does not exist, so here is the difference, stated rather than implied.

**What the public gets on a report in v1: `reporter_type`, and nothing else that identifies anyone.** [#252](https://github.com/OurHike/OurHike/issues/252) removed what was actually being served, which was worse than the row suggested in one direction and thinner in another:

- **`reporter_id` — removed.** The backend was serving a stable Supabase account UUID to anonymous callers alongside a trail position and a time. Group by it and a hiker's route down the corridor falls out, with `curl` and no account. That is the linkability this whole document exists to prevent, and it was shipping while the row above described a masked trail name.
- **`received_at`, `maintainer_id`, `club_id` — removed** from the public serialisation for the same reason. `maintainer_id` in particular was a second account UUID nobody had noticed: it is copied from the request for every report type while only a `thanks` is forced to `club_only`, so a public `blowdown` could carry a real person's id.
- **No trail name is served at all**, so the row's "trail name" half was aspirational rather than descriptive. Public attribution is `reporter_type` alone today.
- **The exact authored time is still served, deliberately.** The masking this document describes is *windowed* — `anonymity_window_days`, configurable, per-hiker — and an always-on coarsening is a different policy invented on the spot, not a smaller version of the designed one. The linkability that made an exact time dangerous was the stable identifier next to it, and that is gone. Revisit this when the window is built; it is a one-line change on the server and nothing in the client reads the field.

`anonymity_window_days` is still accepted, stored, and read by nothing. That remains true and remains Post-MVP; what changed is that the version shipping in the meantime is no longer the linkable one.

## Reconciling the real tension, since it's easy to read these as contradictory

Hiker Safety's anonymity window exists to stop *the general public* from linking a hiker's identity to a place and time. Community Building's Check-ins exist to let *specific, chosen people* do exactly that. **These aren't in conflict - they govern different audiences.** A hiker can have their public comments anonymized for the maximum window while simultaneously running an active Tramily check-in - the anonymity window never touches who a Tramily sees, and Check-ins never touch what the general public sees on a report. Worth stating explicitly here since neither source doc, read alone, rules out the other reading.

## The consolidated `UserPreferences` model

Replaces five separate small models with one, grouped by concern rather than by which doc happened to define it first:

```
UserPreferences   (client-side by default, IndexedDB - syncs via Authentication
                   once linked to a real account, same as trail name above)

  # Identity
  trail_name: string, optional
  real_name: string, optional     (2026-09-17, #1563 - shown to nobody; offered
                                   as the name to sign a single report with)
  is_linked_to_account: bool

  # App-wide display
  theme: light | dark | auto                    (default: auto)
  unit_system: imperial | metric                 (default: imperial)

  # Map display
  background_source: hiking_topo_live | usgs_topo_offline  (default: hiking_topo_live)
  max_background_zoom: 11 | 12 | 13
  show_roads: bool                               (default: false)
  blaze_colors_shown: bool                       (default: false)
  waypoint_types_shown: set of POI types         (default: shelter, water, campsite, privy)
  layer_detail_level: minimal | standard | full
  auto_rotate_enabled: bool                      (default: false)

  # Safety / privacy
  anonymity_window_days: int
  measurement_enabled: bool                      (default: true; v2, EVENTING.md §9)

  # Onboarding progress
  onboarding_completed: bool
  download_choice_made: bool
  location_permission_requested: bool

  # Where they hike (first run's "Where do you hike?", #1373)
  default_place: {id, name, kind, lon, lat, state?, category?, within?, bbox?} | null   (default: null)
```

`default_place` is a place the hiker **named** from the published places index — a park, a town, a trailhead — snapshotted in full, and it syncs so a second device opens on the same place (the maintainer's decision of 2026-09-10, [#1374](https://github.com/OurHike/OurHike/pull/1374)). It is never a GPS fix: the permission card's promise that location "is read on this phone and never sent anywhere" is about fixes, and nothing on this object may hold where somebody is standing (`client/src/lib/defaultPlace.test.ts` pins that no key does).

`blaze_colors_shown` is the legend's "Blaze colors" switch ([#1575](https://github.com/OurHike/OurHike/issues/1575)): off, every trail line on the map is drawn in one red; on, each line in its blaze hue. It syncs, unlike the Alerts switch below, because a hiker who finds the hues distracting on one phone means it on the next, and nothing about a hiker's safety turns on which colour a line is drawn in — the blaze is still named on the tapped line's sheet, the legend's "Trails in view" rows and the day hike card's legs, none of which read the key (the maintainer, 2026-09-17: *"Changing the color option should only affect the map itself, not the other options"*).

**Deliberately excluded:** `show_closures` isn't a preference at all - Map Options already recommends it stay always-on, not user-hideable, since suppressing known safety information isn't the same kind of choice as picking a background tile style. It's a fixed display rule, not a setting.

**Still excluded, and [#1047](https://github.com/OurHike/OurHike/issues/1047) remains the sharpest argument for the exclusion this model has — even though the control it built is gone.** For three weeks the legend carried an Alerts switch that took the closure bands, the ATC's marks and the serious-warning pins off the canvas, and the question of whether it belonged in this object came up and was answered no: a field here syncs, so a hiker who cleared the bands once in Virginia would open a new phone in Maine with them already gone. The flag lived in a `useState` instead, was written nowhere, and came back at the next open.

**The maintainer removed the switch on 2026-09-20**, having been shown the table of every mechanism that could hide a closure with that one the last row still reading "yes". So there is no hiker-facing control over the alert marks at all now, and nothing for this model to consider. The reasoning above is kept because it is the general rule and the next control will be argued against it: **a control existing is not a reason for this model to learn about it**; whether the state may outlive the moment is.

### What this replaces

| Old model | Doc it lived in | Now |
|---|---|---|
| `MapDisplaySettings` | MAP_OPTIONS.md | Folded into the Map display group above |
| `AppPreferences` | UX_CUSTOMIZATION.md | Folded into the App-wide display group above |
| `OnboardingState` + `TrailNameProfile` | ONBOARDING.md | Folded into the Identity + Onboarding progress groups above |
| `UserSafetySettings` | HIKER_SAFETY.md | Folded into the Safety / privacy group above |

Each source doc still owns the *design* of its own settings (why `auto_rotate_enabled` defaults to false, why `anonymity_window_days` exists at all) - only the data model itself moved here, so there's one canonical shape instead of five.

## Open questions (for you, not decided here)

- ~~**Whether `UserPreferences` syncs automatically the instant an account gets linked, or needs an explicit "sync my settings" action.**~~ **Answered by the build, automatically** ([#891](https://github.com/OurHike/OurHike/issues/891), [ACCOUNT_SYNC.md](ACCOUNT_SYNC.md) phase A): signing in pulls the account's settings with no separate action, because a hiker signing in on a second device is *already* asking for their settings and a second button asking whether they meant it is a question with one sensible answer. What the build does NOT do is claim this is visible - nothing in the app says a sync happened, which is [#894](https://github.com/OurHike/OurHike/issues/894)'s job and the reason that issue exists. An explicit control belongs there, as "turn it off", not here as "turn it on".
- **Whether Tramily members should ever see a hiker's real, unredacted location even during that hiker's public anonymity window** - the reconciliation above says yes (different surfaces), but worth confirming explicitly once there's a real settings screen showing both controls side by side, since that's exactly where a hiker could reasonably expect them to interact.
- **`UserPreferences` as a name undersells that it also holds identity-sensitive fields** (`trail_name`, `anonymity_window_days`), not just cosmetic preferences - worth a better name once this actually gets built, not blocking here.
