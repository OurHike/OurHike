"""Washington RCO — State Trails Database: closures, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

This is not a feed. Load the attribute; do not build a closure source on it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Attribute only: Trailheads `trailhead_status` reads `closed` 1, `construction` 6, `seasonal` 6, with "
        "no dates. `trail_condition` on the trails holds condition grades (A–D, Class 1–5), not closures.",
    ),
    where=(
        "https://gis.dnr.wa.gov/site1/rest/services",
        "https://gis.dnr.wa.gov/site3/rest/services",
        "https://services2.arcgis.com/TGEC20q86HQAeMS6/arcgis/rest/services",
        "https://trails-wa-rco.hub.arcgis.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
