"""Catamount Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

Trailhead/parking access.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`…/data/CTA_ACCESS_MASTER_WEBMAP.csv`: 80 access points with lat/lon and a PRIMARY flag (2017-11-27).",),
    where=("https://catamounttrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
