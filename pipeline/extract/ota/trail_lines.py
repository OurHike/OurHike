"""Ozark Trail Association: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

Machine-readable. Partly LOADED via `usfs_trails` (253.7 mi, correction 4). No OTA-owned ArcGIS
(`jadams007`'s "Ozark Trails Association _merged" is a personal account).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The OTA's Google My Map, embedded on `/maps/` (`iframe "
        "src=…/maps/d/embed?mid=1k4nsYuKHFtLk05shVlUX-L9tb-clI7iX`). KML: "
        "`https://www.google.com/maps/d/kml?mid=1k4nsYuKHFtLk05shVlUX-L9tb-clI7iX&forcekml=1`. Its folders "
        "hold: Main Trail 18, Connecting Trail 38, Trailhead Spur 24, OT Spur Trail 4, Alternate Trail 2, Road "
        '2, Nearby trail 1 (89 lines). Also, on each of 14 section pages, a "GPS Download" zip (e.g. '
        '`wp-content/uploads/2018/02/currentriver_gps.zip`, 43,896 B, 2020-09-14) and a "Google Earth Download"'
        " KML zip. Free PDFs date from 2018.",
    ),
    where=(
        "https://www.google.com/maps/d/kml?mid=1k4nsYuKHFtLk05shVlUX-L9tb-clI7iX&forcekml=1",
        "https://ozarktrail.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
