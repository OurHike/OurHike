# OurHike — Feature List (Draft v2)

This translates [OurHikeValues.md](OurHikeValues.md) into concrete features. v1 scope was narrowed on 2026-07-24: keep the first release small, get it in hikers' hands, then grow.

**v1 targets replacing two tools:** Avenza (what NYNJTC used, now shut down) and FarOut/Guthook (the ATC's current official AT map app, used by most thru-hikers). Revenue from OurHike is meant to help fund the ATC and its affiliated maintaining clubs — the nonprofits that actually build and maintain the trail — so this isn't just a free replacement, it's meant to be a better funding mechanism for them too.

---

## v1 MVP — Core Map App

Keep this simple. One thing, done well: an offline-capable map app for hikers, built on a downloadable dataset, showing the handful of things thru-hikers actually need mid-hike.

- Trail line / route data, downloadable for offline use
- Water sources
- Trailheads & road crossings
- Shelters & campsites
- Resupply points (towns, stores, post offices)
- "You are here" GPS positioning while fully offline
- Basic search/filter by POI type
- Same core experience on phone (iOS + Android, day one) and on the web
- **Waypoint icon spec** (2026-07-25, from [Guthook Guides redesign case study](https://www.zoesymon.com/guthook-guides) — see "UX principles" below): ~8 color-coded POI categories, one accent color per category against a contrasting background, WCAG AA contrast compliance. A concrete, testable spec to design the shelter/water/resupply/etc. icons against, not just "make it readable."

**Explicitly deferred**, not because they're low-value, but to keep v1 shippable:
- Community-submitted condition reports & maintainer verification
- Trail magic / hiker-to-hiker features
- Multi-club admin/config tooling
- Weather integration
- Any in-app purchases (see business model below)

## Business model

- No purchases, subscriptions, tips, or payment prompts inside the mobile app shell — this avoids the ~15-30% Apple/Google App Store cut, so more of every dollar reaches the trail clubs.
- Any paid tier, donation flow, or sponsorship purchase lives on the **web version only**. The mobile app can link out to the web for that.
- Per value #5, this is about *sustainability*, not paywalling safety data — core map/POI data stays free everywhere; monetization is additive (e.g., donations, maybe premium convenience features later), never a gate on safety-relevant info.
- Longer-term intent: revenue should flow toward funding ATC / affiliated maintaining clubs, not just cover OurHike's own hosting costs.

## Data sources (decided 2026-07-24, refined 2026-07-24)

- **Trail POI data (centerline, side trails, shelters, campsites, viewpoints, parking, communities):** from the ATC's own public GIS map (ArcGIS-hosted: [arcg.is/1nqL542](https://arcg.is/1nqL542), 9 layers cataloged programmatically — see `pipeline/`) — the same authoritative source FarOut itself uses. The ATC has maintained this data since 1998. Exact redistribution terms still need to be confirmed with ATC directly; the user can help pull the data or make an introduction. **Confirmed gap: ATC's data has no dedicated water-source or general resupply layer.**
- **Water sources & resupply POIs (filling the gap above):** OpenStreetMap tags (`amenity=drinking_water`, `natural=spring` for water; shops/post offices/hostels for resupply) plus USGS hydrography (streams/springs) as an approximate water proxy. Both are unverified/approximate, not confirmed-current data — the UI should be honest about that distinction (value #4), not present them with the same confidence as ATC's official facility data.
- **Offline base map tiles:** **USGS US Topo / National Map raster tiles** ([apps.nationalmap.gov/downloader](https://apps.nationalmap.gov/downloader/)), clipped to the corridor — public domain, pre-rendered, the topo format hikers already trust. OpenStreetMap is deliberately *not* used for the background map (see TECHNICAL_ARCHITECTURE.md for the raster-vs-vector reasoning) — its role is limited to the supplementary POIs above. **Scoped to a ~30-mile corridor around the trail and its waypoints only** — not full state/regional coverage. This keeps offline downloads small for hikers and hosting costs low (value #8), while still covering everything within a reasonable resupply/support range of the trail.

## Platform/tech approach — recommendation

Given the "one codebase" preference, needing phone + web day one, no in-app purchases, and the values around sustainability (#8) and being inheritable by other volunteer-run clubs (#7), my recommendation:

**A Progressive Web App (PWA)** — a single web codebase (e.g., React/TypeScript) using **MapLibre GL JS** (open-source map renderer, no vendor lock-in, unlike Mapbox or Google Maps) for the map itself, with offline map data shipped as **PMTiles** (single static archive files — no tile server to run or pay for, which fits the bounded 30-mile-corridor dataset well). The same codebase is wrapped with **Capacitor** to produce installable iOS and Android app shells for the app stores, so hikers can still find and install a "real app" — just built from the one web codebase, not a second implementation.

Why this over Flutter or React Native: it draws from the largest possible volunteer developer pool (plain web skills are far more common than Dart or React Native's native-module knowledge), everything in the stack is fully open source with no vendor lock-in, and it sidesteps app-store complexity entirely for anything except distribution — which matters since no purchases happen in the app anyway.

**Trade-off to know about:** continuous background GPS track-recording (tracking your route while the phone is locked in your pocket) is weaker in a PWA/Capacitor app than a fully native one. Foreground use — open the app, see the map, see "you are here," look up nearby water/shelters — works fine with this approach. If background track-recording becomes a priority later, Capacitor supports native GPS plugins to close most of that gap without a rewrite.

## UX principles (inspiration)

Pulled from [Zoe Symon's Guthook Guides (now FarOut) redesign case study](https://www.zoesymon.com/guthook-guides) (2026-07-25) — a UX case study on the app we're most directly positioned against, worth referencing again later. Cross-cutting design guidance, not phase-specific:

- **"Use the app less often, and find information faster when you do."** Optimize for quick lookups, not session time/engagement metrics — the opposite of typical app growth goals, and a natural fit with value #1 (hike your own hike): no reason to manufacture engagement.
- **Architect for extensibility from day one.** Guthook's original build reportedly lacked this and it limited later feature work — validates our existing instinct (unified POI schema, avoiding AT/NYNJTC-only assumptions per value #7) rather than introducing something new.
- **Community features should be core, not bolted on.** Their research found thru-hiking is inherently social — direct validation of the commenting/upvoting/guides items under Community reporting below.
- **Fast, low-friction onboarding** — minimal setup before the map is usable, no heavy signup wall blocking time-to-value. Fits our no-account-needed PWA approach.
- **Separate "available" from "owned/downloaded" content clearly** — relevant once we have per-section downloads or any paid tier, so users aren't confused about what they already have.
- **A good feature undermined by poor discoverability is its own failure mode.** Their route-creation tool was well-liked but hard to find — worth designing findability in explicitly (e.g. for our own trip-planning tools under Extras below), not just building the feature and assuming it'll be found.
- **Process note, not a feature:** they ran open-ended surveys across thru-hikers/section-hikers/day-hikers *before* designing anything — worth doing something similar once NYNJTC's soft launch gives us real users, rather than guessing at priorities.

---

## Post-MVP (Phase 2+)

Grouped by value, for later prioritization — not committed, just not forgotten.

### Authentication *(#1, #3, #7, #8)* — build this one first
- **Design drafted 2026-07-28: see [AUTHENTICATION.md](AUTHENTICATION.md).** Google/Apple/email sign-in, email verification, optional MFA, recommended technical approach (Supabase Auth). Doesn't change the MVP's no-account-needed principle - this is foundational for Segments (cross-device sync), Volunteering (club admin access), and Report a Problem (reporter identity), so it should be the first Post-MVP feature actually built, ahead of the three below that depend on it.

### Community reporting *(#2, #4)*
- Hiker-submitted condition reports (text + photo), with timestamp + reporter type shown. **Design drafted 2026-07-28: see [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md)** - report types (blow downs, trash, bad hikers, flooding, shelter repair, animals), pick-a-location flow (existing POI, dropped pin, or current location), and a path toward richer type-specific follow-up over time.
- Maintainer verification/flagging workflow
- Moderation queue for club admins
- Link between hiker reports and official trail-maintenance logs
- **Club data-entry tooling** (2026-07-24): local ATC-affiliated clubs need a way to directly add/edit their own shelters, water sources, campsites, and other trail features - not just via the GIS pipeline, which only they (not volunteers at large) can realistically operate. This is the actual mechanism behind "per-club admin roles" below, made concrete.
- **Community submission + upvoting** (2026-07-24): beyond condition reports, let community members submit their own POIs/corrections and have other members upvote them - a lightweight trust signal ahead of full maintainer verification. Needs a spam/abuse-resistant design before it ships (value #4 - trustworthy above all - means a wrong upvoted submission is worse than no submission).
- **Place-based social commenting, FarOut-style** (2026-07-24): comment threads tied to a specific map location, not just structured condition reports. This is the single feature most directly competing with FarOut's actual daily-use appeal, so it matters a lot - but it also sits in the most direct tension with value #9 ("be magical," not just have a magic feature): unmoderated place-based comments are exactly the kind of feature that can tip into the things value #9 explicitly warns against (broadcast/overcrowding pressure, unattended-cache-style posts, oversharing). Needs real moderation/design thought before building, not just a clone of FarOut's comment UI.
- **User-generated guides** (2026-07-24): let hikers compile their own guides/route collections from the underlying data (a bigger, more curated unit than a single comment or report) - e.g. "my recommended water sources for a NOBO thru-hike." Not scoped further yet; revisit once the underlying POI/reporting data model exists to build on.

### Water reliability prediction *(#4)*
- Predict whether a given water source is likely flowing or dry right now, rather than just showing the last static entry. wikitrail.org's own founding story is literally a hiker hitting a "should be flowing" water source that was dry - this is a real, recurring failure mode of static trail data, not a hypothetical.
- Likely inputs: historical hiker reports (frequency/recency of "dry" vs "flowing" reports at a source), seasonal/precipitation patterns, and possibly NHD stream classification (perennial vs intermittent) already noted as a data source in TECHNICAL_ARCHITECTURE.md.
- Directly extends value #4's existing "reported 3 days ago vs. confirmed today" idea from a passive timestamp into an actual predictive signal - but the bar is high: a confidently wrong prediction is more dangerous than an honest "unknown," so this should ship after there's enough real report volume to back it, not as a launch feature.

### Trail magic, done right *(#9)*
- Point-in-time help requests/offers between hikers — ephemeral, expires automatically, never a persistent pin
- **Explicitly excluded, permanently:** any feature for broadcasting unattended caches ("food left at mile X")
- Volunteer-opportunity surfacing (trail maintenance workdays, club events). **Design drafted 2026-07-28: see [VOLUNTEERING.md](VOLUNTEERING.md)** - a club-side work-project management module, plus (the more important half) upcoming projects shown on the map to encourage hikers to join one.
- Hiker-friendly local business directory
- Contextual Leave No Trace reminders (e.g., bear-country food storage) tied to location/season
- No location-sharing or contact exchange without explicit, per-instance consent

### Data openness & portability *(#3, #6)*
- User data export (routes, saved hikes) in open formats (GPX/GeoJSON/CSV)
- Public read API for trail/POI data
- Documented, versioned open data schema

### Multi-club / inheritance support *(#7)*
- Org/club as a first-class data model concept — trails and POIs scoped to a club/region
- Per-club admin roles
- Onboarding path for the next ATC-affiliated club with no NYNJTC-specific assumptions baked in

### Extras
- Elevation profiles per trail/section
- Trip planning tools (distance, elevation gain, estimated time) — informational, not prescriptive (no streaks/leaderboards, per value #1). **Design drafted 2026-07-28: see [SEGMENTS.md](SEGMENTS.md)** — lets a hiker break a thru-hike/section/day-hike into a personal, hierarchical set of pieces (a "segment" means a day to a thru-hiker, a leg between landmarks to a day-hiker) and mark them done as they go.
- Weather overlay relevant to trail conditions
