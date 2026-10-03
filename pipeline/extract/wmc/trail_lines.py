"""Wasatch Mountain Club: trail lines, drawn from another folder's resource (coverage audit 2026-10-01,
batch c5_regional_2).

The via verdict is only as good as a name match.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The catalogue's 40 Wasatch-named features (`trail_orgs.json`, counted 2026-09-17). WMC publishes no "
        "geometry of its own (nav, `/site-map`, ArcGIS search returned 0). (Changed by skeptic, evidence only, "
        'verdict kept: "no geometry of its own" is wrong. `sitemap.xml` (2,397 URLs) lists '
        '`/wmc-hikes-as-gps-gpx-files` ("WMC Hikes Viewable Via A GPS … Click on a link to download the file"),'
        " with 156 GPX files under `/hike/gpx/`, and `/wmc-hikes-as-google-earth-kmz-files`, with 157 KMZ files"
        ' under `/hike/kmz/`. Sample: `LONE_PEAK_FROM_JACOBS_LADDER.gpx`, 53,017 bytes, `creator="Garmin '
        'Desktop App"` …',
    ),
    where=("https://wasatchmountainclub.org/",),
    reason="drawn from utah_sgid/'s resources, extracted once there (decision 34); checked names the layer this org's "
    "data arrives in",
)
