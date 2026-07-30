# OurHike — Surrounding Land Ownership (Feature Design Draft v1)

Companion to [MAP_OPTIONS.md](MAP_OPTIONS.md), [TRAIL_BLAZE_COLORS.md](TRAIL_BLAZE_COLORS.md), [../OurHikeValues.md](../OurHikeValues.md) and [../WIREFRAMES.md](../WIREFRAMES.md).

In much of its length the AT is a narrow protected sliver with private property on both sides. A hiker stepping fifty feet off-trail to camp, find water, or take a shortcut may be leaving public land without any sign that they have. This feature shows what kind of land surrounds the corridor — national park, national forest, state forest, local park, AT-owned — so that leaving it is a visible act rather than an accident.

---

## Research findings, before any design

### ATC's own GIS does not have this

Checked the live NPS/ATC ArcGIS org (`services1.arcgis.com/fBc8EJBxQRMcHlei`) directly on 2026-07-30, the same way `bridges`/`privies`/`at_treadway` were originally found by listing the FeatureServer root rather than trusting the public map's layer list.

Seven AT-specific services exist:

```
APPA_ECBS_Monitor_Sections            APPA_NatResRriorityZones
APPA_HeleneStatusCenterline           APPA_Trail_Club_Sections   (registered)
APPA_HUC10_LargeLandscape_dissolve    SHEN_TRANS_AppalachianTrail
Appalachian_National_Scenic_Trail_500ft_Buffer
```

**None carries land ownership.** The closest candidate — `Appalachian_National_Scenic_Trail_500ft_Buffer` — turns out to be pure geometry: its only fields are `FID`, `Shape_Area`, `Shape__Area`, `Shape__Length`. It is a 500 ft geometric buffer drawn around the centerline, not a record of what is actually owned or protected. Useful later as a crude "nominal corridor" hint, useless for ownership.

So this is the first feature in a while that genuinely cannot be sourced from data we already hold.

### PAD-US is the right source, and it has exactly the right fields

The USGS **Protected Areas Database of the United States** is the canonical national dataset for this. Verified live on `services.arcgis.com/v01gqwM5QqNysAAi`, which publishes several PAD-US views (`Manager_Type_PADUS`, `Fee_Managers_PADUS`, `Manager_Name_PADUS`, and others).

The attributes map almost one-to-one onto what was asked for:

| field | coded values (excerpt) |
|---|---|
| `Mang_Type` | Federal · State · Local Government · Regional Agency · **Private** · Non-Governmental Organization · Joint · Unknown · American Indian Lands |
| `Des_Tp` | National Park · National Forest · Wilderness Area · National Wildlife Refuge · **National Scenic or Historic Trail** · Conservation Area |
| `Own_Name` / `Mang_Name` | National Park Service · Forest Service · TVA · Army Corps of Engineers · … |
| `Unit_Nm` | the actual unit's name, for display |
| `GAP_Sts` | protection status 1–4 (biodiversity mandate vs multiple-use) |

`Des_Tp = "National Scenic or Historic Trail"` combined with `Own_Name = "National Park Service"` is how AT-owned corridor land identifies itself — so "AT owned land" is a query against PAD-US, not a separate source to find.

## The thing this feature must not do

**Absence from PAD-US does not mean private.** PAD-US maps *protected* areas. Land that is unmapped is **unmapped** — it may be private, or it may be public land that a steward has not yet submitted, or a gap in a state's reporting.

This matters more than any rendering decision in this document, because the obvious implementation is the wrong one. Painting "not in PAD-US" as private and telling a hiker *"do not go here, this is private land"* would be:

- **Wrong sometimes**, in a way the hiker cannot check and would have no reason to doubt.
- **Consequential when wrong** in both directions — either implying a trespass that is not one, or (worse) implying by omission that unshaded ground is fine to walk on.
- **Against [../OurHikeValues.md](../OurHikeValues.md) #4**, trustworthy above all: a confident claim we cannot actually support.

**So the feature shows what land IS, and lets absence be absence.** Protected land is drawn and named. Everything else is simply not drawn, and the legend says plainly that unshaded ground is *unknown*, not *private*. A hiker who sees the shading end knows they are leaving mapped protected land — which is the actionable fact, and is true.

The same restraint appears elsewhere in this project already: [MAP_OPTIONS.md](MAP_OPTIONS.md) refuses to compute detours, and [SPUR_TRAILS.md](SPUR_TRAILS.md) says nothing rather than "Unknown destination". This is that principle applied where the stakes are legal rather than logistical.

**A second, related honesty limit:** PAD-US is a compiled national dataset, not a legal boundary survey. Its polygons are accurate enough to say "you are in Nantahala National Forest" and *not* accurate enough to say "you crossed a property line eight metres ago." The UI must never imply parcel-level precision — no "you are now on private land" alerts, no boundary-crossing notification. Which is also consistent with OurHike's one-notification policy.

## Design

### 1. Pipeline: a new corridor-clipped source

Follows the existing pattern exactly — a `sources.json` entry, a fetch, corridor clipping, an export:

```
pipeline/fetch_land_ownership.py     PAD-US, queried per corridor cell
pipeline/export_land_ownership.py    clip + simplify + emit
```

**Clipped to the same 30-mile corridor** every other layer uses. PAD-US nationwide is very large; the AT's 14 states are a small fraction of it and the corridor is a small fraction of those.

**Simplified aggressively.** These are background context polygons, not safety-critical geometry — nothing about them needs the 1 m tolerance [`export_trails.py`](../pipeline/export_trails.py) uses for the trail line. A much coarser tolerance is appropriate and should be measured the same way, since polygon vertex counts dominate the size of a dataset like this.

**Fields kept:** `Mang_Type`, `Des_Tp`, `Own_Name`, `Unit_Nm`. Everything else dropped — `GAP_Sts` is interesting to a conservationist and noise to a hiker.

**Freshness:** PAD-US publishes on a versioned cycle (PAD-US 3.0, 4.0…), so [`check_freshness.py`](../pipeline/check_freshness.py) gains a source whose marker is the published version rather than a per-file timestamp — closest in shape to the elevation edition-set marker already there.

### 2. Rendering: quiet, and beneath everything that matters

A translucent fill per `Mang_Type`, under every existing layer. Ordering is not cosmetic here — this sits **below** the topo background's features, the trail lines, closures and warning pins, all of which are either safety-relevant or the reason the app exists. A land-ownership wash that competes with a closure band would be a real regression.

Colour should not reuse the blaze palette or the closure red. [TRAIL_BLAZE_COLORS.md](TRAIL_BLAZE_COLORS.md) already spends the saturated end of the palette on line colours that carry meaning, and [`closureStyle.ts`](../client/src/lib/closureStyle.ts) deliberately made closures structurally distinct from a red blaze — a new fill layer must not undo that by introducing a large red region.

**Off by default is worth considering** and is left open below: this is context, not navigation, and a permanently-shaded map costs legibility for something most hikers want occasionally.

### 3. What the hiker sees

**Tapping an area** names it plainly, using PAD-US's own words rather than our interpretation:

> **Nantahala National Forest**
> National Forest · managed by the Forest Service

**Where shading stops**, the legend explains the boundary honestly:

> Shaded areas are mapped public or protected land.
> Unshaded means we don't have ownership data — not that it's private.

That second line is the whole feature's integrity in one sentence, and should survive any copy edit.

## What this deliberately isn't

- **Not a trespass warning.** No alerts, no boundary-crossing notification, no "private land ahead". The data does not support it and the notification policy forbids it.
- **Not parcel data.** No owner names of private individuals, ever — PAD-US does not carry them and it would be a privacy problem if it did.
- **Not a routing constraint.** It does not affect snapping, wrong-way detection, or anything that computes.
- **Not a substitute for signage and blazes.** On the ground, the blazes and the landowner's own signs are authoritative. This is orientation, not permission.

## Open questions (for you, not decided here)

- **On or off by default.** Argued weakly for off above; genuinely depends on how heavy the shading reads on a real topo background, which wants seeing rather than deciding.
- **How many `Mang_Type` categories to actually distinguish visually.** Nine coded values is far too many fills to tell apart. Federal / State / Local / Private-protected / NGO is probably four too many already — the honest minimum may be just "protected" vs "not mapped".
- **Whether to include the 500 ft APPA buffer as a separate hint.** It is the *nominal* corridor and cheap to add, but showing a geometric buffer next to real ownership polygons risks reading as though it were also ownership.
- **Size after clipping and simplification.** Unmeasured. Polygon layers can be much heavier than they look, and this ships inside a download people already weigh against phone storage — worth measuring before committing to a tier.
- **Whether this is MVP.** It needs a new source, a new fetch, a new export and a new client layer, none of which exist. Reads Post-MVP, but it is a scope call.
