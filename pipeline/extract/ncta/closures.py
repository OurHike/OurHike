"""North Country Trail Association: closures, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

No active flag, so every row is "not reviewed" under decision 7. Rows dated 2021 are still in the
layer, so expiry by `Date` is @unvalidated.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`trail_alerts/FeatureServer/1`: 67 points with `Date` (2021-01-01 to 2026-09-11), `Location`, `desc_`,"
        ' `label`. Example: "Trail Alert: Garrison Dam — …closed the shoreline to all recreation through Nov. '
        '15". Page: `northcountrytrail.org/the-trail/trail-alerts/` ("Any current North Country Trail closures '
        'or reroutes will be posted here").',
    ),
    where=(
        "https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services/trail_alerts/FeatureServer/1",
        "https://northcountrytrail.org/the-trail/trail-alerts/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
