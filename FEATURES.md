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

## Data sources (decided 2026-07-24)

- **Trail POI data (centerline, shelters, campsites, water sources, road crossings, resupply):** from the ATC's own GIS program (ArcGIS-hosted: [arcg.is/1nqL542](https://arcg.is/1nqL542)) — the same authoritative source FarOut itself uses. The ATC has maintained this data since 1998. Exact licensing/access terms still need to be confirmed with ATC directly; the user can help pull the data or make an introduction.
- **Offline base map tiles:** USGS National Map ([apps.nationalmap.gov/downloader](https://apps.nationalmap.gov/downloader/)) and/or OpenStreetMap ([openstreetmap.org/export](https://www.openstreetmap.org/export)), both open data. **Scoped to a ~30-mile corridor around the trail and its waypoints only** — not full state/regional coverage. This keeps offline downloads small for hikers and hosting costs low (value #8), while still covering everything within a reasonable resupply/support range of the trail.

## Platform/tech approach — recommendation

Given the "one codebase" preference, needing phone + web day one, no in-app purchases, and the values around sustainability (#8) and being inheritable by other volunteer-run clubs (#7), my recommendation:

**A Progressive Web App (PWA)** — a single web codebase (e.g., React/TypeScript) using **MapLibre GL JS** (open-source map renderer, no vendor lock-in, unlike Mapbox or Google Maps) for the map itself, with offline map data shipped as **PMTiles** (single static archive files — no tile server to run or pay for, which fits the bounded 30-mile-corridor dataset well). The same codebase is wrapped with **Capacitor** to produce installable iOS and Android app shells for the app stores, so hikers can still find and install a "real app" — just built from the one web codebase, not a second implementation.

Why this over Flutter or React Native: it draws from the largest possible volunteer developer pool (plain web skills are far more common than Dart or React Native's native-module knowledge), everything in the stack is fully open source with no vendor lock-in, and it sidesteps app-store complexity entirely for anything except distribution — which matters since no purchases happen in the app anyway.

**Trade-off to know about:** continuous background GPS track-recording (tracking your route while the phone is locked in your pocket) is weaker in a PWA/Capacitor app than a fully native one. Foreground use — open the app, see the map, see "you are here," look up nearby water/shelters — works fine with this approach. If background track-recording becomes a priority later, Capacitor supports native GPS plugins to close most of that gap without a rewrite.

---

## Post-MVP (Phase 2+)

Grouped by value, for later prioritization — not committed, just not forgotten.

### Community reporting *(#2, #4)*
- Hiker-submitted condition reports (text + photo), with timestamp + reporter type shown
- Maintainer verification/flagging workflow
- Moderation queue for club admins
- Link between hiker reports and official trail-maintenance logs

### Trail magic, done right *(#9)*
- Point-in-time help requests/offers between hikers — ephemeral, expires automatically, never a persistent pin
- **Explicitly excluded, permanently:** any feature for broadcasting unattended caches ("food left at mile X")
- Volunteer-opportunity surfacing (trail maintenance workdays, club events)
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
- Trip planning tools (distance, elevation gain, estimated time) — informational, not prescriptive (no streaks/leaderboards, per value #1)
- Weather overlay relevant to trail conditions
