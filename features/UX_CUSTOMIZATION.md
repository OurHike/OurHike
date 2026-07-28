# OurHike — UX Customization (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Extends [MAP_OPTIONS.md](MAP_OPTIONS.md)'s `MapDisplaySettings` model and its already-designed MapLibre chrome, and reuses [HIKER_SAFETY.md](HIKER_SAFETY.md)'s GPS-trajectory bearing math for auto-rotate. [ONBOARDING.md](ONBOARDING.md) is where these settings first get a one-line mention - deliberately not a walkthrough of every default here.

**Scope note:** mixed, like Map Options before it. Dark-mode auto-detection and the compass button are near-free details of MVP items already committed (the outdoor usability pass, Map Options' chrome spec). Everything else here - manual theme override, layer/waypoint display preferences, metric units, and especially auto-rotate - is real Post-MVP settings work. Auto-rotate specifically turns out to be a harder problem than the one-line ask suggests, in the same way the wrong-way alert did - taken seriously below, not glossed over.

---

## Planning first, since these six asks aren't one thing

**The real distinction this doc needs before listing anything: persistent *settings* and momentary *on-map controls* are different UI, and conflating them produces a worse design than treating them separately.**

- **Persistent settings** - things a hiker sets once and rarely revisits: theme, units, default waypoint types, default layer detail. These belong in a Settings screen, client-side, no account needed - the exact same storage model [SEGMENTS.md](SEGMENTS.md) and [MAP_OPTIONS.md](MAP_OPTIONS.md) already established, not a new one.
- **On-map controls** - things tapped in the moment, not "set": the compass button is the clearest example. Nobody configures a compass button in settings; it's just there, like the zoom buttons Map Options already designs.

**A second distinction, just as real: not everything here is *map-specific*.** Map Options' `MapDisplaySettings` (background source, zoom, roads, closures) is genuinely about the map. Theme and units affect every screen in the app - the elevation profile chart, Trip Planning's distance estimates, Segments' displays, not just the map. Bundling them into `MapDisplaySettings` would make that model do two unrelated jobs. **This doc introduces a separate `AppPreferences` for the app-wide pair (theme, units), and extends `MapDisplaySettings` only for what's actually map-specific** (which waypoint types render, layer detail, auto-rotate).

With that sorted, the six asks split cleanly:

| Ask | Bucket |
|---|---|
| Light/dark mode | `AppPreferences` (persistent) |
| Metric units | `AppPreferences` (persistent) |
| What waypoints get displayed | `MapDisplaySettings` (persistent) |
| Layer details | `MapDisplaySettings` (persistent) |
| Auto-rotate | `MapDisplaySettings` (persistent - the on/off default), but the rotation itself happens live, not "set" |
| Compass button | on-map control (not a setting at all - see Map Options' `NavigationControl`) |

## Light / dark mode

**Auto-detect via the standard `prefers-color-scheme` media query is near-free** - matches the OS setting automatically, standard web-platform behavior, works the same way in the Capacitor-wrapped shell since it's still rendering the same web content. Worth treating as a detail of the outdoor usability pass already in ROADMAP.md rather than new scope. A manual three-way override (light / dark / auto) in Settings is real but small Post-MVP polish on top.

**An explicit non-goal, worth stating so it isn't assumed to solve something it doesn't:** dark mode is not an answer to the sunlight-glare readability problem the outdoor usability pass already owns - hikers use this app outdoors in bright daylight far more than in the dark, and glare needs high contrast and legible sizing, not a darker palette. Keep these as two separate problems even though they sound adjacent.

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

```
AppPreferences                    (app-wide, not map-specific - client-side, no account, same
                                    storage model as Segments/Map Options)
  theme: light | dark | auto      (default: auto, via prefers-color-scheme)
  unit_system: imperial | metric  (default: imperial, matching the AT's own convention)

MapDisplaySettings                (extends MAP_OPTIONS.md's existing model)
  + waypoint_types_shown: set of POI types (default: all)
  + layer_detail_level: minimal | standard | full
  + auto_rotate_enabled: bool     (default: false - not everyone wants this, and it costs
                                    real permission friction on iOS to turn on)
```

## Open questions (for you, not decided here)

- **Whether metric unit_system should also convert mile-marker labels**, or keep those as a fixed cultural reference regardless of the general unit preference - flagged above, a real product call.
- **Default `waypoint_types_shown`** - all types on by default (today's implicit MVP behavior) vs. a curated "important" subset by default - worth deciding once there's a real settings screen in front of you.
- **Exact `layer_detail_level` zoom thresholds** - a real tuning question once there's a map to look at, not answerable from this doc.
- **Whether auto-rotate is worth its build cost** - the native `WKUIDelegate` work for the Capacitor iOS shell is real engineering effort for a feature that, unlike the wrong-way alert, isn't safety-critical. Worth weighing deliberately rather than assuming it's cheap because the ask itself is a short bullet point.
