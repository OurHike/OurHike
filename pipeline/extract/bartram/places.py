"""Bartram Trail Conference: places, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Historical markers across 8 states. A place set, not hiking POIs.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'BTC (not BRBTC): "Bartram Trail Markers", a Google My Maps KML '
        "(`mid=1ek21kngs9TQ-bAbmjDWtpFWGvLw-Cwre`, embedded on `/page-1647832`) with 127 placemarks (88 points,"
        ' 38 lines). "Bartram Trail", My Maps `mid=z-XY_0WikHLg.kpJrukA3Genw` (`/page-1647833`), has 245 '
        'placemarks (109 points, 95 lines) in folders such as "Bartram Sites", "Markers" and "Properties".',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/YfqBAUM5nWR3yhGP/arcgis/rest/services",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/ArcGIS/rest/services",
        "https://bartramtrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
