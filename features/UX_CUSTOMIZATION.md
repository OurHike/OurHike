# OurHike — UX Customization (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Extends [MAP_OPTIONS.md](MAP_OPTIONS.md)'s already-designed MapLibre chrome, and reuses [HIKER_SAFETY.md](HIKER_SAFETY.md)'s GPS-trajectory bearing math for auto-rotate. [ONBOARDING.md](ONBOARDING.md) is where these settings first get a one-line mention - deliberately not a walkthrough of every default here. Data model consolidated 2026-07-28 into [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md)'s `UserPreferences`.

**Scope note:** mixed, like Map Options before it. **Light/dark mode is MVP in full - the three-way override too, moved 2026-08-06; see the section below for why the original split was wrong.** The compass button stays a near-free detail of an MVP item already committed (Map Options' chrome spec). Everything else here - layer/waypoint display preferences, metric units, and especially auto-rotate - is real Post-MVP settings work. Auto-rotate specifically turns out to be a harder problem than the one-line ask suggests, in the same way the wrong-way alert did - taken seriously below, not glossed over.

---

## Planning first, since these six asks aren't one thing

**The real distinction this doc needs before listing anything: persistent *settings* and momentary *on-map controls* are different UI, and conflating them produces a worse design than treating them separately.**

- **Persistent settings** - things a hiker sets once and rarely revisits: theme, units, default waypoint types, default layer detail. These belong in a Settings screen, client-side, no account needed - the exact same storage model [SEGMENTS.md](SEGMENTS.md) and [MAP_OPTIONS.md](MAP_OPTIONS.md) already established, not a new one.
- **On-map controls** - things tapped in the moment, not "set": the compass button is the clearest example. Nobody configures a compass button in settings; it's just there, like the zoom buttons Map Options already designs.

**A second distinction, just as real: not everything here is *map-specific*.** Map Options' `MapDisplaySettings` (background source, zoom, roads, closures) is genuinely about the map. Theme and units affect every screen in the app - the elevation profile chart, Trip Planning's distance estimates, Segments' displays, not just the map. Bundling them into `MapDisplaySettings` would make that model do two unrelated jobs. **This doc introduces a separate `AppPreferences` for the app-wide pair (theme, units), and extends `MapDisplaySettings` only for what's actually map-specific** (which waypoint types render, layer detail, auto-rotate).

With that sorted, the six asks split cleanly:

| Ask | Bucket |
|---|---|
| Light/dark mode | `AppPreferences` (persistent) - **MVP** |
| Metric units | `AppPreferences` (persistent) |
| What waypoints get displayed | `MapDisplaySettings` (persistent) |
| Layer details | `MapDisplaySettings` (persistent) |
| Auto-rotate | `MapDisplaySettings` (persistent - the on/off default), but the rotation itself happens live, not "set" |
| Compass button | on-map control (not a setting at all - see Map Options' `NavigationControl`) |

## Light / dark mode

**Auto-detect via the standard `prefers-color-scheme` media query is near-free** - matches the OS setting automatically, standard web-platform behavior, works the same way in the Capacitor-wrapped shell since it's still rendering the same web content.

**Moved into MVP in full on 2026-08-06, three-way override included, and the original split is worth recording as a mistake rather than quietly deleting.** This doc had auto-detection as MVP and the manual override as "small Post-MVP polish on top." That reasoning measured the wrong thing. It is true that the override is a small amount of code on top of the detection - and irrelevant, because **a theme is not a small preference. It changes the look and feel of every screen at once**, which is a different category of thing from the settings it was filed beside, and shipping the half that cannot be argued with while withholding the half a hiker actually controls is the worse of the two possible partial answers.

Two concrete consequences, either of which would have been enough on its own:

- **Auto alone means the app is only ever as right as the OS setting.** Somebody who keeps their phone dark and wants a readable paper map in daylight has nowhere to say so - and `prefers-color-scheme` structurally cannot express that, since it reports the OS's answer and has no notion of an override. This is not polish missing from a working feature; it is a hiker with a preference and no control.
- **The reason to want dark here is not the reason to want it on a laptop.** A phone in a shelter after dark, or checking the next water source at 4am, is the brightest object for a mile, and a bright screen costs night vision for several minutes after it goes away. That is a real outdoor use, and it is the argument for the theme being genuinely dark rather than fashionably grey.

**The explicit non-goal is unchanged and is now said in the app itself, not only here:** dark mode is not an answer to the sunlight-glare readability problem the outdoor usability pass already owns - hikers use this app outdoors in bright daylight far more than in the dark, and glare needs high contrast and legible sizing, not a darker palette. Two separate problems even though they sound adjacent. The Settings control says so in its own words, because the mistake is the intuitive one: somebody squinting at a screen in full sun reaches for the darker option first.

### What the map can and cannot do

Worth stating here rather than only in the code, because it is a product-visible limit and it follows from a choice made long before this feature.

- **The live vector sheet goes genuinely dark.** Its colours are ours (`client/src/map/liveTopo.ts`), so it is re-drawn to the same brief as the paper version - ground to ink, labels the brightest thing on it - rather than inverted. An inverted topo sheet gets it backwards twice: contours and roads are the quiet layers, and inversion makes them the loudest while leaving the blaze colours, which mean something and are therefore not inverted, the quietest.
- **The downloaded USGS corridor archive is dimmed, not darkened.** US Topo quads are pre-rendered raster; their ink is pixels and nothing knows which pixels are contours. [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md) recorded this trade-off when that background was chosen. The dim is a per-layer raster paint property rather than a filter over the canvas, so the trail lines, pins and chrome over it stay at full strength - and it is deliberately moderate, because this is the screen a hiker uses to decide where to walk and the setting that makes it dark must not be the setting that makes it unreadable.
- **Blaze colours never change.** A white blaze is the AT. Re-hueing the trail lines per theme would make the map lie about which trail somebody is standing on, which is a worse problem than a bright map at night.

## Auto-rotate + compass button - one mechanism, taken seriously as hard

**Checked directly rather than assumed: MapLibre has no built-in "rotate the map to match my heading" feature.** `GeolocateControl` tracks position, not device heading; the map's bearing (`map.setBearing()`) can be set programmatically, but nothing wires it to a compass automatically - this is real custom code, not a config flag.

**The device-compass path has a genuine, concrete platform gotcha, not just a permission prompt.** iOS Safari requires `DeviceOrientationEvent.requestPermission()` from a user gesture, and the compass heading value itself (`webkitCompassHeading`) is a non-standard, WebKit-only property - Android needs a different code path. **Worse, for the Capacitor-wrapped app specifically:** since iOS 15, `WKWebView` only delivers orientation events at all if the native host app implements a specific `WKUIDelegate` callback - without it, the permission request is silently denied, no prompt ever shown. That's real native-shell work, not something that falls out of the PWA build for free.

**Compass sensors are also just noisy in practice, worth naming honestly:** magnetometer readings jitter, and hiking gear (trekking poles, a stove, anything metal near the phone) can throw off a raw compass reading. **Design recommendation: prefer GPS-derived movement bearing over the device compass while actually walking, falling back to the compass only when stationary** (GPS bearing is meaningless if you're not moving). This reuses [HIKER_SAFETY.md](HIKER_SAFETY.md)'s wrong-way-alert bearing computation directly - the same trailing-GPS-window trajectory math, not a second implementation - and sidesteps most of the iOS/Capacitor compass complexity above for the common case of a hiker actually walking.

**The compass button itself needs none of this new design work - it's already spec'd.** Map Options' MVP chrome detail already includes MapLibre's `NavigationControl`, which ships a compass showing current bearing; tapping it to reset to north-up (and drop out of auto-rotate) is the same standard convention Apple/Google Maps already use. This doc's contribution is just wiring auto-rotate's bearing source into that existing control, not building a second one.

## Layer details & which waypoints display - related, not identical

Two different questions, worth distinguishing rather than treating as one setting:

- **Which waypoint *types* show at all** (water, shelters, campsites, resupply, viewpoints, parking, privies, bridges, communities) - a persistent default filter. **Distinct from, and complementary to, FEATURES.md's already-MVP "basic search/filter by POI type"** - that's an ephemeral, in-the-moment lookup ("show me water sources right now"); this is an ongoing display preference ("I never care about privies, stop showing them"). Both are useful, for different reasons - this doesn't replace that MVP item, it extends it into something that persists.
- **How much label/detail clutter accompanies whatever's shown** - a detail-density setting (e.g. names always visible vs. only once zoomed in), independent of which types are on at all.

## Metric units

**The real engineering principle: store one canonical unit internally, convert only at the display layer.** Worth stating plainly because this project's own real data already mixes unit systems at the source - the ATC's mile-marker system (`half_mile_points_from_springer`) is inherently imperial by real hiking convention, while the USGS 3DEP elevation data is inherently metric. Converting at display time, never storing a user-facing preference into the canonical data, avoids exactly the class of bug that comes from mixing the two.

**A distinction worth keeping separate from the general unit toggle: mile-marker numbers are a cultural reference point, not just a measurement.** "I'm at mile 1000" is how thru-hikers actually talk about their position on the trail - that label probably shouldn't silently become a kilometer-marker number just because a hiker set a general metric preference elsewhere (elevation gain, segment distances). Flagged below as a real open question, not decided here.

## Data model sketch

**Update 2026-07-28: consolidated into [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md)'s `UserPreferences`**, alongside Map Options', Onboarding's, and Hiker Safety's settings, rather than a separate `AppPreferences` model plus an extension to Map Options' own. This doc still owns the *why* behind each default (auto theme via `prefers-color-scheme`, imperial matching the AT's own convention, `auto_rotate_enabled` defaulting false given its real iOS permission cost) - only the data model shape moved: `theme`, `unit_system`, `waypoint_types_shown`, `layer_detail_level`, `auto_rotate_enabled`.

**Update 2026-08-06:** `theme` is the first of those five to be built. It stays `light | dark | auto` defaulting to `auto` exactly as designed - what changed is that all three values are now reachable from Settings rather than only the default being honoured.

## Open questions (for you, not decided here)

- **Whether metric unit_system should also convert mile-marker labels**, or keep those as a fixed cultural reference regardless of the general unit preference - flagged above, a real product call.
- **Default `waypoint_types_shown`** - all types on by default (today's implicit MVP behavior) vs. a curated "important" subset by default - worth deciding once there's a real settings screen in front of you.
- **Exact `layer_detail_level` zoom thresholds** - a real tuning question once there's a map to look at, not answerable from this doc.
- **Whether auto-rotate is worth its build cost** - the native `WKUIDelegate` work for the Capacitor iOS shell is real engineering effort for a feature that, unlike the wrong-way alert, isn't safety-critical. Worth weighing deliberately rather than assuming it's cheap because the ask itself is a short bullet point.
