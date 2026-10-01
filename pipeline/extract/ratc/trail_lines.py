"""Roanoke Appalachian Trail Club: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c3_at_clubs_south).

ATC's `side_trails` row "Andy Layne Side Trail" was edited 2026-08-13 (with `Trail_Club` null). So
the reroute is probably already in ATC, and RATC's line is a cross-check (Reasoned; nobody has
compared the geometries). CalTopo terms are unreviewed.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`centerline` (215 features, 117.1 mi under `RATC`, plus 14.5 mi under `"23"`, see Defects 3), '
        "`side_trails` (84), and `trail_club_sections`. RATC's own geometry: CalTopo. "
        "`https://caltopo.com/m/8AEHQUP` is embedded on `/at-hiking/ratcs-14-at-hikes/`. Its JSON is at "
        "`https://caltopo.com/api/v1/map/8AEHQUP/since/0` and holds 14 LineStrings, one per hike, plus 16 "
        "parking Markers. `https://caltopo.com/m/139L030` is embedded on `/andy-layne-trail/` and holds 2 "
        'LineStrings ("New Andy Layne Trail Route", "Loop hiker road walk") plus 3 Markers.',
    ),
    where=(
        "https://caltopo.com/m/8AEHQUP",
        "https://caltopo.com/api/v1/map/8AEHQUP/since/0",
        "https://caltopo.com/m/139L030",
        "https://ratc.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
