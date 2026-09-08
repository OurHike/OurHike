# OurHike — Hiker Safety (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Builds directly on [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) (serious warnings are an escalation of its existing report types, not a new report system), [AUTHENTICATION.md](AUTHENTICATION.md) (the anonymity setting lives on the identity layer it designs), and [MAP_OPTIONS.md](MAP_OPTIONS.md) (serious-warning pins reuse its waypoint icon spec). The `anonymity_window_days` setting's data model consolidated 2026-07-28 into [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md), which also reconciles this section against Community Building's check-in privacy - different audiences, not competing settings.

**Scope note, revised 2026-07-28: split, not uniform.** This doc originally flagged serious warning pins and the wrong-way alert as "genuinely safety-critical enough to deserve the same MVP-promotion conversation Elevation got" without deciding it here - that conversation happened, and **both moved into v1 MVP**, along with their real dependencies (Authentication, Report a Problem's moderation queue and backend), rather than staying blocked behind a Post-MVP timeline. **The comment-anonymity window and NWS weather integration (sections 2-4) stay genuinely Post-MVP** - they don't carry the same physical-safety weight, and nothing about promoting the other two requires them to move too.

**Update, 2026-09-08: the wrong-way alert (section 5, as promoted above) was built in full and later removed** ([#93](https://github.com/OurHike/OurHike/issues/93), [#308](https://github.com/OurHike/OurHike/issues/308)) - see section 5 below for what shipped, what didn't, and why. Serious warning pins (section 1) are unaffected and remain in v1 MVP.

---

## 1. Serious warnings as separate pins - moved into v1 MVP 2026-07-28

**Reuses [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md)'s existing types rather than inventing new ones.** Bear sightings are the `animals` type; blow downs are already a type; "dangerous humans" is the same real-world concern that doc already calls `bad_hikers`. Nothing here needs a seventh report type - what's missing is a way for some reports, regardless of type, to be treated as more serious than others.

**Design: add a `severity` tier, set by moderation, not self-declared.** A report starts as a normal condition report, exactly as Report a Problem already designs. A club moderator/maintainer can escalate specific reports to `serious` during the verification step that doc already plans - the same review step, not a second one. Self-declared severity was considered and rejected: letting any hiker mark their own report "serious" is directly spammable/exaggeratable, and a false serious warning is worse than a missing one (value #4) - the same reasoning Report a Problem already applied to why `bad_hikers` isn't a public pin by default.

**Display:** `serious`-tier reports render as a visually distinct pin (larger, high-contrast, an exclamation treatment) - a variant within the same waypoint icon spec / legend system [MAP_OPTIONS.md](MAP_OPTIONS.md) already designs, not a separate visual language.

**Notification:** a serious warning does **not** trigger a push - OurHike sends no push notification of any kind (section 5 below). It surfaces prominently in-app instead (the distinct pin above, plus a "serious warnings on your route" indicator when the map or a planned Segment is opened) - consistent with FEATURES.md's own existing UX principle, "use the app less often, and find information faster when you do... no reason to manufacture engagement."

**The real tension worth naming, not glossing over:** Report a Problem deliberately keeps `bad_hikers` off the public map entirely, routed privately to moderators, because an unverified accusation about a specific person can cause real harm if wrong. A *verified, moderator-escalated* dangerous-person warning is a different thing - genuinely useful to surface - but where exactly that line sits (how much corroboration, whose judgment call) is real moderation policy, not a data-model question. Report a Problem already flagged this exact category as needing "a real moderation conversation before it ships" - this feature is why that conversation now has real stakes attached, not a reason to skip it.

## 2. Anonymous comments (configurable window)

**The real concern, worth stating plainly:** a name plus an exact date/time next to a trail-mile location is a location-and-pattern-of-life disclosure, not just a comment byline - a legitimate, known worry for solo hikers in particular. Masking it for a while is a genuine safety feature, not decoration.

**Complementary to, not a substitute for, [ONBOARDING.md](ONBOARDING.md)'s trail name.** A trail name is already a partial pseudonym by hiking convention, which helps before this window even exists - but it doesn't mask the exact date/location the way this mechanism does, so both matter together, not either/or.

**Design - a display-layer redaction, not a data deletion.** The underlying `Report` (from Report a Problem) keeps its real `reporter_id` and real `timestamp` always - moderation, spam-prevention, and the "reported 3 days ago vs. confirmed today" honesty principle already in FEATURES.md all need the real data underneath. What changes is what's *shown*:

- **Name/handle:** hidden, shown only as the existing `reporter_type` category (thru-hiker/section-hiker/day-hiker/maintainer) - which isn't identity-revealing on its own, so it stays visible even while anonymized.
- **Date:** coarsened to something like "posted several days ago" rather than an exact timestamp, for the same reason - an exact date is exactly the other half of the location-and-pattern-of-life problem.
- **Window:** `anonymity_window_days`, evaluated live against the report's real timestamp (`now - report.timestamp < anonymity_window_days`) - not baked in at posting time.

**User-configurable, per your ask - lives on the identity layer.** A durable, personal "X days" setting belongs with [AUTHENTICATION.md](AUTHENTICATION.md)'s `User` once that exists. It could reasonably start as a device-local setting before Authentication ships, the same client-first-then-account-synced path Segments already took - not a reason to block this feature on Authentication landing first, just an honest note that it becomes a *real* durable preference (synced across devices) only once Authentication does.

**Honest edge case, worth flagging rather than quietly ignoring:** because the window is evaluated live, changing X after posting has real effects - shortening it can reveal identity on old posts sooner than a hiker expected when they wrote them; lengthening it can't un-reveal a post someone already saw while it was attributed. Worth a clear UI warning at the moment someone changes the setting, not solved further here.

## 3. Weather alerts

**Real, free, no-key data source confirmed directly: the National Weather Service's own public API (`api.weather.gov`).** `/alerts` (by area, or resolved from a `/points/{lat},{lon}` lookup to a forecast zone) needs no API key, just a descriptive `User-Agent` header identifying the app - the same courtesy convention OSM's tile policy already asks for. One honest forward-looking caveat, stated in NWS's own FAQ: the keyless model is explicitly expected to be "replaced with an API key system" eventually - worth reconfirming at build time, the same "don't trust this doc alone, verify against current terms" caveat AUTHENTICATION.md already applies to Supabase's pricing.

**"Responsibly," answered directly: relay, don't originate.** OurHike shouldn't try to interpret raw weather data into its own severe-weather judgment - it should show NWS's own already-issued alerts (headline, effective/expiry window, official text), clearly labeled as a relayed NWS alert. This is the same principle FEATURES.md's Water Reliability Prediction section already commits to: "a confidently wrong prediction is more dangerous than an honest unknown" - the authority and the liability both stay with NWS, where they belong.

**Architecture: proxy and cache through OurHike's own backend, don't have every phone call NWS directly.** NWS's docs explicitly note point-to-zone mappings "don't change very often" and ask callers to cache them - many hikers within the same few trail miles resolve to the same forecast zone, so a shared cache at the Phase 2+ backend (already planned, FastAPI/Postgres) avoids redundant load on a free public service. This is what "responsibly" means here in the same sense OSM's tile policy already shaped the background-tile decision in Map Options: be a good citizen of a free public resource, don't just consume it at max volume because it's technically reachable.

**Geographic scope:** ties to the hiker's live GPS position (already MVP) or a planned Segment's location (Trip Planning) - either resolves to the same NWS zone lookup, no separate mechanism needed per source.

**Notification - a genuine open tension, not resolved here.** OurHike sends no push notification of any kind today (section 5 below records the wrong-way alert's removal). A tornado warning or flash-flood alert is arguably as time-critical as being lost - it's a real question whether weather alerts would be worth building push infrastructure for at all, or whether they stay in-app-only like serious warnings above. Flagging this directly rather than picking one side quietly.

## 4. Weather conditions (daily temperature)

**Checked [atweather.org](https://www.atweather.org/) directly, since you pointed at it specifically.** It's a real, well-targeted hobby project (run by an individual, Pat Jones, NWS/NOAA-sourced, per-shelter and per-waypoint forecasts with elevation listed for each) - genuinely the right shape of feature, and worth a courtesy outreach the same way ROADMAP.md already plans for opentrail.org's maintainer, both as reciprocity and because they've clearly already thought about this problem. **But it has no public API or data feed** - there's nothing to integrate against as a live dependency, the same "inspirational prior art, not a technical dependency" situation as opentrail.org before its own outreach happens.

**The actual buildable path: replicate the approach directly on the same underlying free data, using what this project already has.** Same NWS point-lookup plumbing as section 3's alerts (literally the same API call, different response fields - current conditions/forecast instead of alerts - not a second integration). The elevation-sensitivity the user is right to flag ("weather changes a lot based on elevation") is exactly what the already-MVP dense 1-meter DEM elevation data (see [TRIP_PLANNING.md](TRIP_PLANNING.md)'s design history) is for - and it's a real opportunity to do this *better* than atweather.org's own approach, which is necessarily limited to named shelters/waypoints: OurHike's continuous elevation coverage means a forecast/current-temp reading could be offered at any point along the trail a hiker actually is, not just at a fixed list of named locations.

## 5. Wrong-way / off-trail alert — removed 2026-09-08

**Promoted into v1 MVP 2026-07-28, built in full, and removed** ([#93](https://github.com/OurHike/OurHike/issues/93), [#308](https://github.com/OurHike/OurHike/issues/308)) rather than shipped or left sitting unmounted indefinitely. Kept brief here on purpose - the full design history (the two detection modes, the notification-delivery-by-platform research, the false-positive measurements) lives in those closed issues' comment history and in git, not repeated in a doc describing a feature that no longer exists.

**Two independent reasons drove the removal, and fixing one would not have fixed the other:**

- **The distance-from-trail mode's thresholds were never field-validated** ([#93](https://github.com/OurHike/OurHike/issues/93)). 90 ft / 12 min / 25 min were WIREFRAMES.md mock-up placeholders from the start. Even after [#699](https://github.com/OurHike/OurHike/issues/699) (closed by PR #700) made the distance measurement side-trail-aware - cutting the shelter false-positive rate from a measured 72% down to 5% - nobody ever walked real GPS traces under canopy to check the numbers themselves, and the maintainer deferred that field validation to v2 rather than guess.
- **The wrong-direction mode was never built at all.** The design below called for a movement bearing derived from a trailing GPS window; no such computation ever existed in the client. So the mechanism that reached production could only ever detect "off the trail," never "walking the trail backwards" - an off-trail cue wearing a wrong-way name, per [#308](https://github.com/OurHike/OurHike/issues/308)'s investigation. [UX_CUSTOMIZATION.md](UX_CUSTOMIZATION.md)'s auto-rotate feature was designed to reuse the same bearing computation and is in the same unbuilt state.

**What stays, and why:** the client's `wrong_way_alert_enabled` preference and the backend's `hikes` table / `GET /hikes/{id}/direction` endpoint remain in place even though nothing reads or calls them today - both are part of released clients' API contracts, and removing either is an expand/contract change across supported releases (RELEASING.md §8c), not a same-PR deletion. `WrongWayCheck` in the data model below has no successor.

If a wrong-way or off-trail alert is built again, it should be designed against whatever GPS and notification story exists at that time - not resurrected from this section's placeholder thresholds or its never-built bearing mode.

## Data model additions

```
Report                       (extends REPORT_A_PROBLEM.md's existing model)
  + severity: normal | serious          (moderator-set, never self-declared)

(display-layer only, not stored)
  anonymized_view(report, viewer_now) -> {
    reporter: report.reporter_type (name withheld),
    posted: coarse ("X days ago") if viewer_now - report.timestamp < reporter.anonymity_window_days
            else report.timestamp (exact)
  }

WeatherAlert                  (relayed + briefly cached server-side, not owned data)
  nws_alert_id, zone, headline, effective, expires, relayed_at
```

(`WrongWayCheck`, the wrong-way alert's client-side ephemeral computation, is gone with section 5 above.)

## Open questions (for you, not decided here)

- **The "dangerous humans" verified-serious threshold and moderation policy** - flagged above as needing a real conversation, the same one Report a Problem already deferred.
- **Whether weather alerts are worth building push-notification infrastructure for at all**, given OurHike sends none today - an investment question, not a design one.
- **Default `anonymity_window_days` value, and the change-it-later edge case** - a real policy/UX choice once there's a real settings screen in front of you, not answerable from this doc.
