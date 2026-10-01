"""Trailkeepers of Oregon: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c6_regional_3).

The API is machine-readable, and robots.txt does not disallow `api.php`. Blocked on the Field Guide
terms.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Oregon Hikers Field Guide, MediaWiki API `https://www.oregonhikers.org/w/api.php`: "
        "`Category:Trailheads` holds 1,738 pages. Each carries `{{maplinkinfo|latitude=…|longitude=…}}` and an "
        "elevation, e.g. Larch Mountain Trailhead 45.52937, -122.08843, 3,900 ft. Also "
        "`OregonHikers_Featured_Hikes_PublicView/FeatureServer/0` (4,069 points, last edited 2021-09-11) and "
        "`OCT_Section_Points` (11).",
    ),
    where=(
        "https://www.oregonhikers.org/w/api.php",
        "https://services3.arcgis.com/3g7oRa9lIIf3eCBb/arcgis/rest/services/OregonHikers_Featured_Hikes_PublicView/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
