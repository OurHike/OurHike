# OurHike — Hiker Safety (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Builds directly on [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) (serious warnings are an escalation of its existing report types, not a new report system), [AUTHENTICATION.md](AUTHENTICATION.md) (the anonymity setting lives on the identity layer it designs), [SEGMENTS.md](SEGMENTS.md) (a Hike's direction of travel is what "wrong way" is measured against), and [MAP_OPTIONS.md](MAP_OPTIONS.md) (off-trail detection reuses its DuckDB distance-to-trail math). The `anonymity_window_days` setting's data model consolidated 2026-07-28 into [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md), which also reconciles this section against Community Building's check-in privacy - different audiences, not competing settings.

**Scope note, revised 2026-07-28: split, not uniform.** This doc originally flagged serious warning pins and the wrong-way alert as "genuinely safety-critical enough to deserve the same MVP-promotion conversation Elevation got" without deciding it here - that conversation happened, and **both moved into v1 MVP**, along with their real dependencies (Authentication, Report a Problem's moderation queue and backend), rather than staying blocked behind a Post-MVP timeline. **The comment-anonymity window and NWS weather integration (sections 2-4) stay genuinely Post-MVP** - they don't carry the same physical-safety weight, and nothing about promoting the other two requires them to move too.

---

## 1. Serious warnings as separate pins - moved into v1 MVP 2026-07-28

**Reuses [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md)'s existing types rather than inventing new ones.** Bear sightings are the `animals` type; blow downs are already a type; "dangerous humans" is the same real-world concern that doc already calls `bad_hikers`. Nothing here needs a seventh report type - what's missing is a way for some reports, regardless of type, to be treated as more serious than others.

**Design: add a `severity` tier, set by moderation, not self-declared.** A report starts as a normal condition report, exactly as Report a Problem already designs. A club moderator/maintainer can escalate specific reports to `serious` during the verification step that doc already plans - the same review step, not a second one. Self-declared severity was considered and rejected: letting any hiker mark their own report "serious" is directly spammable/exaggeratable, and a false serious warning is worse than a missing one (value #4) - the same reasoning Report a Problem already applied to why `bad_hikers` isn't a public pin by default.

**Display:** `serious`-tier reports render as a visually distinct pin (larger, high-contrast, an exclamation treatment) - a variant within the same waypoint icon spec / legend system [MAP_OPTIONS.md](MAP_OPTIONS.md) already designs, not a separate visual language.

**Notification - resolved by your own framing below, not decided here independently:** per the "only notification we ever send" line in section 5, a serious warning does **not** trigger a push. It surfaces prominently in-app instead (the distinct pin above, plus a "serious warnings on your route" indicator when the map or a planned Segment is opened) - consistent with FEATURES.md's own existing UX principle, "use the app less often, and find information faster when you do... no reason to manufacture engagement."

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

**Notification - a genuine open tension, not resolved here.** Section 5 sets "the wrong-way alert is the only notification we ever send." A tornado warning or flash-flood alert is arguably as time-critical as being lost - it's a real question whether weather alerts deserve a second exception to that rule, or whether they stay in-app-only like serious warnings above. Flagging this directly rather than picking one side quietly.

## 4. Weather conditions (daily temperature)

**Checked [atweather.org](https://www.atweather.org/) directly, since you pointed at it specifically.** It's a real, well-targeted hobby project (run by an individual, Pat Jones, NWS/NOAA-sourced, per-shelter and per-waypoint forecasts with elevation listed for each) - genuinely the right shape of feature, and worth a courtesy outreach the same way ROADMAP.md already plans for opentrail.org's maintainer, both as reciprocity and because they've clearly already thought about this problem. **But it has no public API or data feed** - there's nothing to integrate against as a live dependency, the same "inspirational prior art, not a technical dependency" situation as opentrail.org before its own outreach happens.

**The actual buildable path: replicate the approach directly on the same underlying free data, using what this project already has.** Same NWS point-lookup plumbing as section 3's alerts (literally the same API call, different response fields - current conditions/forecast instead of alerts - not a second integration). The elevation-sensitivity the user is right to flag ("weather changes a lot based on elevation") is exactly what the already-MVP dense 1-meter DEM elevation data (see [TRIP_PLANNING.md](TRIP_PLANNING.md)'s design history) is for - and it's a real opportunity to do this *better* than atweather.org's own approach, which is necessarily limited to named shelters/waypoints: OurHike's continuous elevation coverage means a forecast/current-temp reading could be offered at any point along the trail a hiker actually is, not just at a fixed list of named locations.

## 5. Wrong-way / off-trail alert - moved into v1 MVP 2026-07-28

**Ships as the conservative in-app-cue version described below, not the full background-tracking/push version** - consistent with TECHNICAL_ARCHITECTURE.md's foreground-GPS-is-sufficient-for-MVP stance, which didn't need to change to accommodate this promotion.

**Taking "extremely difficult to do well" seriously rather than hand-waving past it.** Two distinct failure modes, worth separating because they need different detection logic:

- **Off the path** - physically wandered off the trail line. This reuses [MAP_OPTIONS.md](MAP_OPTIONS.md)'s snap-to-segment math, run continuously against live GPS instead of once against a tap. If the live position's distance from the nearest trail line exceeds a threshold, the hiker is probably off-trail. **"Nearest trail line" means the nearest mapped tread of any kind - the centerline or a blue-blazed side trail - and not the centerline alone.** That distinction is the whole feature rather than a detail: the median A.T. shelter is 197 ft from the A.T. and 72% of them sit past the threshold, because a shelter is at the end of a side trail. Measured against the centerline alone, this mode is a shelter detector wearing an off-trail name; counting the side trails takes that 72% to 5% without moving a threshold. The client therefore keeps two distances - a centerline one, which is what a mile is measured along, and a tread one, which is what "off trail" means (`TrailFix.offTreadFeet`).
- **Wrong direction** - physically on the trail, but walking back the way they came. This needs to know *intended* direction, which [SEGMENTS.md](SEGMENTS.md)'s `Hike` already models (its overall start/end reference implies NOBO vs. SOBO) - no new state needed, just reading what Segments already has. Detecting it needs a trailing window of GPS samples (a single point has no direction), a minimum-movement threshold (so standing still at a shelter doesn't read as "stopped going the right way"), and a minimum-persistence duration before concluding anything - a short backtrack to a spring, a privy, or a dropped pack is completely normal hiker behavior and must not trigger a false alarm.

**Why the false-positive cost matters more here than almost anywhere else in this project:** you've scoped this as the *only* notification OurHike ever sends - which means every false alarm spends the entire trust budget this feature was designed around (value #4). Recommend a deliberately conservative v1: generous distance/duration thresholds biased toward silence, and considering a lower-stakes first step (an in-app visual/audible cue while the app is open, escalating to an actual push only after sustained divergence) rather than jumping straight to an interrupt. A more sophisticated version - extra sensitivity specifically near known `side_trails` junctions, since that's genuinely where a missed blaze turn actually happens, using data the pipeline already has - is a real refinement worth flagging for later, not solving in v1.

**A real architecture constraint already on record, not new to this feature:** FEATURES.md's own "trade-off to know about" already says continuous background GPS is weaker in a PWA/Capacitor app than a fully native one, and foreground use is what reliably works today. This feature is exactly the case that trade-off was warning about - a wrong-way check that only runs while the app is open misses the case of a phone locked in a pocket. Building this well likely means adopting the native GPS plugin path FEATURES.md already named as the way to close that gap, not assuming the default PWA behavior is sufficient. **[COMMUNITY_BUILDING.md](COMMUNITY_BUILDING.md)'s auto-tracking check-ins need the exact same capability** - worth building once for both rather than treating each as a separate ask.

**Notification delivery, checked directly rather than assumed - and it splits by distribution channel:**
- **The wrapped app-store app (Capacitor):** native push (APNs/FCM), no special caveats beyond the usual platform permission prompt.
- **The web PWA specifically:** Web Push works on iOS Safari, but **only for installs added to the Home Screen** - a hiker just using OurHike in a regular Safari tab cannot receive it at all, iOS support only since 16.4 (any current device, so not a practical gap, just a real mechanic worth knowing). The service worker ROADMAP.md's Phase 2 already scaffolds is the prerequisite either way. Practically: the wrapped app is the more reliable channel for the one notification this feature sends: if this ships, prompting/encouraging Home Screen installation for web users becomes more than a nice-to-have.

**Reused elsewhere:** [UX_CUSTOMIZATION.md](UX_CUSTOMIZATION.md)'s auto-rotate feature reuses this section's trailing-GPS-window bearing computation directly, preferring it over the device compass while the hiker is actually moving - one bearing calculation, two features.

**No server relay in v1 — decided 2026-08-20, resolving
[#247](https://github.com/OurHike/OurHike/issues/247).** The backend briefly carried a
`POST /wrong-way-events` endpoint whose docstring deferred to "a later task wires this
endpoint's acceptance to an actual push send". It has been removed rather than reshaped:
its contract required ownership of a `Hike` no client code created, no client code named
the endpoint at all (the monitor's `relay` is an injected seam, mounted nowhere — #308),
its acceptance persisted nothing and pushed nothing, and the data model below never
defined a server-side wrong-way record — `WrongWayCheck` is client-side and ephemeral by
design. The endpoint was an inference ahead of this doc, not an implementation of it.
When the open question at the foot of this doc is answered and push infrastructure is
actually built, the relay should be designed against the reality then — the client's
declared hike in `plannedHike.ts`, and whatever server story
[ACCOUNT_SYNC.md](ACCOUNT_SYNC.md) has given plans by that point — not rebuilt from
today's guess. The client keeps the seam: `createWrongWayMonitor` still takes a `relay`
dependency and still treats it as fire-and-forget telemetry that may never swallow the
alert.

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

WrongWayCheck                 (client-side, ephemeral - a live computation, not a persisted record)
  distance_from_nearest_trail_line, bearing_delta_from_hike_direction, sustained_since
```

## Open questions (for you, not decided here)

- **The "dangerous humans" verified-serious threshold and moderation policy** - flagged above as needing a real conversation, the same one Report a Problem already deferred.
- **Whether weather alerts earn a second exception to "only one notification"** - presented both ways above, not resolved.
- **Default `anonymity_window_days` value, and the change-it-later edge case** - a real policy/UX choice once there's a real settings screen in front of you, not answerable from this doc.
- **Off-trail distance and wrong-direction persistence thresholds** - need real field-testing against actual GPS behavior under tree canopy, not a number this doc can responsibly guess at.
- **Whether it's worth building push-notification infrastructure (web + native) for one alert type**, given how deliberately narrow its use is meant to stay - an investment question, not a design one.
