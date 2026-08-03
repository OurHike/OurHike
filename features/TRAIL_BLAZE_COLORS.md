# OurHike — Trail Blaze Colors (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Also relevant to [SEGMENTS.md](SEGMENTS.md) - see "Segments integration" below.

**Scope note, framed differently than the last four drafts:** this isn't new scope - it's a correctness detail of a feature FEATURES.md already lists in the **v1 MVP itself** ("Trail line / route data, downloadable for offline use"). Hikers navigate real trails partly *by* blaze color - a junction where the map's line color doesn't match what's painted on the tree is a trustworthiness gap (value #4), not a missing nice-to-have. Recommend treating this as part of the MVP trail-line work, not Post-MVP - flagging clearly in case that read is wrong.

---

## What the real data already tells us

Checked directly against the actual fetched ATC data rather than assumed:

- **`side_trails` (1,200 features) already has a `Blaze` field** - and it's not just loose text, it's an official ArcGIS coded-value domain, fetched straight from the FeatureServer's own field metadata:

  | code | color |
  |---|---|
  | 0 | None |
  | 1 | Blue |
  | 2 | White |
  | 3 | Red |
  | 4 | Orange |
  | 5 | Yellow |
  | 6 | Green |
  | 7 | Purple |
  | 8 | Black |
  | 9 | Other |

  Real distribution: 641 Blue, 484 None, 20 Yellow, 6 Orange, 4 Green, 3 White, 2 each Red/Purple/Other - plus messier entries worth naming honestly: 24 features with no value at all, and 9 with the literal string `"Unknown"` and 3 with `"Gold"` - neither of which is an actual code in the domain above. Real data is never as clean as the schema promises; the pipeline needs to handle that, not assume it away.

- **`centerline` (the AT itself, 3,025 features) has no `Blaze` field at all** - because the main trail is uniformly white-blazed, a fact about the AT, not something that needs storing per-segment. Worth not hardcoding that fact in application code, though - see below.

## Design

**1. Normalize every trail-line feature to one `blaze_color` attribute during ingestion**, regardless of source:
- For a source with a real coded domain (like `side_trails`'s `Blaze` field): decode it. Fetch the domain from the FeatureServer's own field metadata rather than hardcoding the code table above by hand - the same "derive from real metadata, don't guess" approach `fetch_topo_quads.py` already uses for quad neatlines. Any value that doesn't decode cleanly (the `"Unknown"`/`"Gold"`/null cases found above) falls through to the neutral default, with a loud pipeline warning - matching the existing convention (e.g. `fetch_topo_quads.py`'s corrupted-quad warnings) of never silently swallowing a data-quality issue.
- For a source that's uniformly one color with no per-feature field (like `centerline`): a flat default color, set **per source in `sources.json`**, not hardcoded as "white" in application code. The AT's centerline happens to always be white, but that's a fact about *this* trail, not a safe assumption for the next club's trail data (value #7 - inheritable, no AT-specific assumptions baked into the architecture).
- Any future imported trail-line source (this is the general "ability to import color-coded lines" capability asked for) resolves to the same normalized attribute one of these three ways: decode a real domain, apply a flat per-source default, or fall through to the neutral color. No source-specific rendering logic needed beyond that.

**2. Rendering is a data-driven MapLibre style expression, not per-layer hardcoding.** MapLibre GL's `match` expression on `line-color` reads the normalized `blaze_color` attribute directly per feature - well-supported, no exotic tooling, and it means `centerline` and `side_trails` (and anything imported later) share one rendering rule instead of two hardcoded layer styles. **Reused elsewhere:** [MAP_OPTIONS.md](MAP_OPTIONS.md) applies this same normalize-then-`match` pattern to road walkability, rather than inventing a second rendering mechanism.

**3. Neutral default color for unknown/unclassified blazes.** With up to 9 real blaze colors possible in the data (including literal Black), the fallback can't be black, near-black, or anything close to the 8 real hues - it needs to read unambiguously as "we don't know," not "confidently wrong." Recommend a clear, medium neutral gray, tuned against the actual USGS topo basemap tones (cream background, green cover, tan contours) with the same WCAG AA contrast rigor FEATURES.md's existing waypoint icon spec already applies - this is the same kind of decision, just for line color instead of icon color.

## Accessibility, worth naming explicitly

Up to 9 distinguishable line colors (8 real blaze colors + neutral) is a lot to tell apart at a glance, including for hikers with color vision deficiency - red/green confusion is the most common form, and red/orange or orange/yellow pairs are also commonly confused. Relying on hue alone risks exactly the failure FEATURES.md already warns about elsewhere: "a map that's unreadable at a junction fails at its one job." Worth considering a secondary visual cue (line pattern/dash style, or a tap-to-confirm label) at minimum for color pairs that are hard to distinguish - this connects directly to the "outdoor usability pass" already in FEATURES.md's v1 MVP list, not a separate concern.

**Where this landed, and where it stands now (2026-08-03).** The secondary cue shipped as dash style, then came back out. Per-blaze dash rhythms made the map's own subject unreadable: the AT centerline's blaze is near-white, so the gaps in its dash - dark casing showing through - were the part that read, and the trail a hiker was standing on looked like a dotted grey-and-white thread. Lines are now solid, and **width** carries the hue-independent channel instead: the AT centerline is drawn markedly wider than every other trail, keyed off the pipeline's `source` attribute (see WIREFRAMES.md §3). That answers "which line is the AT" with hue removed entirely, which is the question this section's own accessibility argument cares most about. It does **not** answer "is this spur yellow or orange" - those two are now separable by hue alone, and 26 features in today's data are affected. The tap sheet naming the blaze remains the honest fallback there, and a non-dash second cue for the warm hues (a casing weight, a label at high zoom) is still open work rather than a settled question.

## Segments integration

[SEGMENTS.md](SEGMENTS.md) already ties every Segment's boundaries to real trail geometry (centerline mile-markers, POIs). That means a planned Hike's segments can render in their real blaze color automatically, with no new field on Segment itself - a segment that runs along the white AT renders white, one that detours to a blue-blazed shelter spur renders blue, purely by reading whatever trail-line data that segment actually spans. The two features compose without needing to talk to each other explicitly.

## Open questions (for you, not decided here)

- **"None" (code 0, a genuinely unblazed trail) vs. true unknown (missing/invalid data).** Recommended above as the same neutral fallback for both, since there's no way to visually distinguish "confirmed no blaze exists" from "we don't have data" without extra UI. Worth deciding if that distinction ever needs to be surfaced (e.g. in a tap-for-details popup) rather than just collapsed into one color.
- **Exact neutral gray value.** A real color choice, not a data question - worth picking with an actual rendered map in front of you, not from this doc alone.
- **Whether `centerline`'s "always white" default belongs in `sources.json` now or is premature** given only one trail's data exists today. Recommended above for inheritability's sake, but reasonable to defer until a second trail/club's data actually shows up if that feels like solving a problem that doesn't exist yet.
