# OurHike — Community Building (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Builds on [AUTHENTICATION.md](AUTHENTICATION.md) (real accounts, required throughout), [SEGMENTS.md](SEGMENTS.md) (a shared route is a Hike/Segment tree, not a new structure), and [ONBOARDING.md](ONBOARDING.md) (a hiker's trail name is the identity shown here). Extends FEATURES.md's existing Trail Magic line, "no location-sharing or contact exchange without explicit, per-instance consent" - this entire feature is that principle's real test case, not an exception to it.

**Scope:** entirely Post-MVP - every piece of this needs real accounts, so unlike Onboarding there's no MVP-tier slice to carve out here.

---

## The real tension this feature runs into, named directly rather than smoothed over

Every feature designed so far in this project has been pointed at *minimizing* identity and location exposure: Hiker Safety's anonymity window, Data Nudges' deliberately non-tracking passive design, Report a Problem's "bad hikers" routed away from public view. This feature asks for the opposite - sharing real-time location with named other people. That's not a contradiction, but it's a real shift worth stating plainly rather than pretending it's the same kind of feature as the others. The design below treats it as a deliberate, carefully-scoped exception (opt-in, mutual, revocable, minimal-retention) for a specific, valuable purpose - not a general loosening of the stance those other docs took.

## Tramily - forming a group, sharing a route

**Reuses [SEGMENTS.md](SEGMENTS.md)'s Hike/Segment tree directly - a shared route is an existing Hike, not a new data structure.** Sharing a planned hike with a Tramily is just granting other accounts read access to a Hike record that already exists.

**Membership is mutual, not a one-way follow.** An invite has to be accepted before someone's in a Tramily - consistent with the explicit-consent principle above, and with how Segments/Volunteering have both avoided one-sided visibility elsewhere.

**Two real lifetimes, worth designing for separately rather than forcing one shape:**
- **A persistent Tramily** - the classic thru-hiker pack that forms over weeks and stays together loosely for the rest of a hike. Long-lived, low-friction to check on over time.
- **An ephemeral session group** - "hikers tend to form packs or plan a day hike with friends" is a different use case: a group that exists for one day and doesn't need to persist afterward. Worth a lighter-weight join mechanism (e.g. a short-lived shareable code) rather than the same full setup as a persistent Tramily, and it should expire on its own rather than accumulate as digital clutter.

**"See the location of others in the group" is not a separate feature - it's Check-ins below, scoped to a Tramily as one possible audience.** No second location-sharing mechanism needed.

## Check-ins - the actual location-sharing mechanism

**Two modes, exactly as specified:**
- **On-demand** - a single, explicit "share my location right now" action. The same one-time GPS-pin pattern already used elsewhere (Report a Problem's location picker), just shared with people instead of attached to a report.
- **Auto-tracking** - a periodic (~30 min) update while a session is active, so a Tramily or safety contact can see rough progress without the hiker doing anything further.

**Privacy design, treated as the actual point of this section, not an afterthought:**
- **Opt-in per session, not a standing account setting.** Turned on for a specific hike/day, with a persistent, unambiguous visual indicator while it's active ("sharing is ON"), and a one-tap way to stop - never a silent background state a hiker has to dig through settings to confirm.
- **Recipients must be mutual, authenticated connections** - a Tramily, or an explicit safety-contacts list of other real accounts. **No public or anonymous shareable link in this design** - a leaked link would mean anyone, not just someone chosen, can track a hiker's real-time location, which is a materially different (and much larger) exposure than sharing with people already explicitly connected. Flagged below as a real open question for a possible future extension (e.g. a non-hiking family member who doesn't use the app), not solved here.
- **Minimal retention by default: show the latest point, not a breadcrumb trail.** Auto-tracking's job is "are they still moving, roughly where," not building a permanent record of everywhere someone has been - each new ping should be able to simply replace the last one rather than accumulate into a history, unless a hiker explicitly opts into keeping one (a different, bigger decision, flagged as an open question rather than a default).
- **"Only publish when not in airplane mode," precisely:** a web app can't directly query whether airplane mode is toggled - that's a device-level OS setting, not something exposed to a browser or WebView. What it *can* reliably check is actual network connectivity (`navigator.onLine` and the standard `online`/`offline` events), which achieves the real intent here just as well: **don't transmit a location ping without a live connection, and don't queue one up to send later once reconnected either** - queuing would mean quietly accumulating a location history on-device even while "not sharing," which is exactly the kind of hidden data collection this feature is trying to avoid. Only ever publish a point that's genuinely current.

**Architecture note, connecting a dot across two features rather than treating this as isolated:** reliable ~30-minute auto-tracking needs the app to check location periodically even when it isn't the foreground app - the same background-location gap FEATURES.md's own PWA-vs-native trade-off already flags, and the same native GPS plugin path Hiker Safety already named for the wrong-way alert. This is now the **second** feature that needs that capability - worth treating as one investment to make once, not two separate asks that each get deferred.

## @ mentions - attached to content, not a chat thread

**Not inline, per your framing - a mention attaches to something, it doesn't start a conversation.** A hiker tags another on a piece of existing content (a Report a Problem entry, a Data Nudges check-in, a shared Segment) - or, when there's genuinely nothing existing to attach to, a lightweight standalone `Note` pinned to a location. This is what makes mentions "easily findable": they live where the content already lives (on the map, in a shared Hike), not buried in a scrolling thread that has to be searched.

**Findable via a simple "mentions of me" list, not a conversation UI.** No threads, no read receipts, no typing indicators - genuinely not a chat app, matching what you asked for directly.

**Notification: no push, in-app only - consistent with how this project has answered this question every time it's come up.** Hiker Safety scoped the wrong-way alert as the only notification OurHike sends; Data Nudges resolved "nudge" to mean visual map prominence, not a push. A mention isn't time-critical the way either of those cases is, so it follows the same default: it shows up in the findable list above next time the app is open, nothing interrupts.

**A real abuse guardrail worth stating explicitly, not assuming away:** mentions should only be possible between hikers who are already mutually connected (Tramily members, or an equivalent explicit connection) - not any hiker mentioning any other hiker at will. This limits the feature to people who already have a real relationship, the same reasoning Report a Problem already applied to why "bad hikers" needs careful, non-open handling.

## The anti-gamification guardrail - a pattern this project keeps needing, worth naming as one again

The fourth feature that's had to say this explicitly, after Segments, Volunteering, and Data Nudges: **no follower/friend counts, no public profile, no leaderboard of Tramily size or how many mentions someone's received.** This feature's whole job is making a real connection easier to act on in the moment - not turning connection itself into something to accumulate or compare.

## Architecture fit

Everything here needs Authentication (real, mutually-verifiable accounts - none of this works with an anonymous device-local ID) and the same Phase 2+ backend Report a Problem and Data Nudges already require for their write paths. Check-ins' auto-tracking mode additionally needs the native background-location capability already flagged for Hiker Safety's wrong-way alert - not a new dependency, the same one, now needed twice.

## Data model sketch

```
Tramily
  id, name (optional)
  members: [user_id]                    (mutual - invite + accept, not one-way)
  lifetime: persistent | session         (session groups auto-expire)
  shared_hike_id (optional - references an existing SEGMENTS.md Hike)

CheckIn
  id, user_id
  mode: on_demand | auto_tracking
  location, timestamp
  shared_with: Tramily id | explicit safety-contact user_ids
  session_active: bool                  (auto-tracking only - explicit stop control)
  # deliberately no history table by default - latest point replaces the last one

Note                                    (new - only exists when there's nothing else to attach a mention to)
  id, author_user_id
  location reference (point - same anchoring pattern as Segments' boundaries)
  text
  timestamp

Mention
  id
  from_user_id, to_user_id              (must be mutually connected)
  attached_to: Report | ConditionConfirmation | Segment | Note
  timestamp
```

## Open questions (for you, not decided here)

- **Whether Check-ins should ever support a non-app-user recipient** (e.g. a family member at home who isn't a hiker) via some kind of shareable, view-only access - flagged above as a materially bigger privacy exposure than in-app-only sharing, and deliberately not included in this design. Worth a real, separate conversation if it matters enough to you.
- **Whether auto-tracking should ever offer an opt-in full breadcrumb trail** instead of just the latest point - a real product decision, not defaulted to here given the retention-minimization reasoning above.
- **The ephemeral session-group join mechanism** (a code? a QR-style link? something else) - a real UX decision once there's an actual screen to design it against.
- **Whether persistent Tramilies need any moderation given they're an ongoing relationship, not a one-off report** - most of this project's moderation thinking (Report a Problem, Hiker Safety) has been about individual pieces of content; a standing group is a different shape of thing, worth its own look once this is closer to being built.
