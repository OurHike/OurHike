"""Florida Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

`Gateway_Community_Businesses` (129) is commercial listings. Leave it out unless the maintainer
wants businesses.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../FT_Gateway_Communities/FeatureServer/0`: 17 towns with websites. "
        "`.../Managed_Conservation_Areas/FeatureServer/0`: 103 polygons with `MANAME` and `MANAGING_A`. The "
        "pages `/gateway-communities/` and `/permits/`.",
    ),
    where=("https://floridatrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
