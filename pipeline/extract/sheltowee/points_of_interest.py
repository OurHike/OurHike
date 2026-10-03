"""Sheltowee Trace Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c8_regional_5).

Page and PDF.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/campgrounds`: 16 campgrounds with FarOut mileages, seasons, fees and `goo.gl/maps` links. "Major '
        'Trailheads and Road Crossings" PDF (`/s/major_trailheads.pdf`): 1 page, 2020-02-17, mileposts and '
        'overnight-parking rules, no coordinates. "Google Maps Points of Access" '
        "(`goo.gl/maps/eqnPDxPa3ZqnranP8`, not opened).",
    ),
    where=("https://sheltoweetrace.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
