"""Iditarod Historic Trail Alliance: warnings, published, and not landed (coverage audit 2026-10-01,
batch p10_persist).

avalanche.org: explicit_restriction. Its API root says "Please contact avalanche.org / American
Avalanche Associate for permission" (sic, "Associate"). Batched below. MOA layer: licenseInfo empty,
so none_stated. Its `EDITOR` field holds 1 distinct value, a person's name or account, not copied.
The …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

BLM Alaska's press releases (https://www.blm.gov/press-release/alaska/rss) are read once, in
blm/warnings.py as `blm_press_alaska` (decision 34): 50 items on 2026-10-03, a window, none naming
the INHT. The Chugach NF's alerts page (https://www.fs.usda.gov/r10/chugach/alerts) is the Forest
Service's, read once in usfs/closures.py as `usfs_r10_chugach_alerts`. avalanche.org's CNFAIC zones
wait on the permission its API root asks for, noted once in _shared/avalanche_org/notes.py and not
fetched (decision 55).

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/CNF_ClosureAreaPolygons/FeatureServer,
Chugach NF's 22 winter motorized closure-area layers, deferred in usfs/closures.py;
https://services2.arcgis.com/Ce3DhLRthdwbHlfF/arcgis/rest/services/AvalancheZones/FeatureServer/0,
historic avalanche paths last edited 2019-11-15, planning-grade and not a forecast; its EDITOR field
names a person.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        'avalanche.org `https://api.avalanche.org/v2/public/products/map-layer/CNFAIC` (GeoJSON) holds 4 forecast zones: Chugach State Park, Seward and Lost Lake, Summit Lake, and Turnagain Pass and Girdwood. Those are the Seward-to-Eagle-River segments. Today every zone reads `danger` "no rating", `off_season` true. Fields include `danger_level`, `travel_advice` and `warning`. Municipality of Anchorage `https://services2.arcgis.com/Ce3DhLRthdwbHlfF/arcgis/rest/services/AvalancheZones/FeatureServer/0` ("Historic Avalanche Zones within MOA", item `9e39d70c7c434187b95a99c3a144cdb2`, 2026-08-25) holds …',
        "via blm/ `blm_press_alaska` (decision 53 phase B, 2026-10-03): FeedNotices, 50 items read live, a window, 0 naming the INHT",
    ),
    where=(
        "https://api.avalanche.org/v2/public/products/map-layer/CNFAIC",
        "https://services2.arcgis.com/Ce3DhLRthdwbHlfF/arcgis/rest/services/AvalancheZones/FeatureServer/0",
        "https://avalanche.org",
    ),
    reason="drawn from blm/'s `blm_press_alaska`, extracted once there (decision 34); and from usfs/'s `usfs_r10_chugach_alerts`; avalanche.org waits on its permission",
)
