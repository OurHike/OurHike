"""North Country Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

The largest unloaded water and camp set in the batch, one layer number away from what is already
fetched.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`nct_public/FeatureServer/1` "Point Data - Public": 2,549 points, last edit 2026-04-24. `wptType`: POI'
        " 730, Parking 695, Water 547, Camping 504, Shelter 53, Ford 18, Developed Water Source 2. This is the "
        "same service as the loaded line. Per-state half-mile points also exist (`halfmile_ny`, "
        "`pa_halfmile_points`, …).",
    ),
    where=("https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services/nct_public/FeatureServer/1",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
