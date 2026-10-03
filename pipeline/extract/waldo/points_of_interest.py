"""Waldo County Trails Coalition: points of interest, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

PDF only. Kiosks are mentioned on the site.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Section 3 PDF legend: "Parking area · Parking: Plowed in winter · Parking: Roadside or limited · Trail'
        ' information"; trailhead access mileages.',
    ),
    where=(
        "https://www.hillstosea.org/maps",
        "https://www.hillstosea.org/closures",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
