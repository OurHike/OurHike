"""Iditarod Historic Trail Alliance: closures, published, and not landed (coverage audit 2026-10-01,
batch p10_persist).

RSS and page: federal works, public domain. CNF polygons: licenseInfo empty; a USFS work, public
domain. The polygons are motorized closures, so they do not close the footpath. They matter because
the INHT is "primarily a winter trail" (the Alliance's words, in the audit) used by skiers and …

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
        '`https://www.blm.gov/press-release/alaska/rss` (RSS) holds 50 items, newest 2026-09-29. It carries BLM Alaska trail closures, e.g. "BLM Temporarily Closes Wickersham Dome Trailhead in White Mountains National Recreation Area…" (2026-09-29) and "BLM Begins Temporary Trail Closures at Campbell Tract During Fuel Treatment Work" (2026-07-16). 0 of the 50 is an INHT closure. The one Iditarod item is the 2026-01-15 ceremonial-start event. Chugach NF `https://www.fs.usda.gov/r10/chugach/alerts` (HTML) holds 8 alerts, none naming an INHT segment. Chugach NF closure areas …',
        "via blm/ `blm_press_alaska` (decision 53 phase B, 2026-10-03): FeedNotices, 50 items read live, a window, 0 naming the INHT",
    ),
    where=(
        "https://www.blm.gov/press-release/alaska/rss",
        "https://www.fs.usda.gov/r10/chugach/alerts",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/CNF_ClosureAreaPolygons/FeatureServer",
        "https://gis.blm.gov/arcgis/rest/services/recreation",
        "https://arcgis.dnr.alaska.gov/arcgis/rest/services",
        "https://iditarod100.org",
        "https://iditarod100.org/",
    ),
    reason="drawn from blm/'s `blm_press_alaska`, extracted once there (decision 34); and from usfs/'s `usfs_r10_chugach_alerts`; avalanche.org waits on its permission",
)
