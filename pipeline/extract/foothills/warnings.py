"""Foothills Trail Conservancy: warnings, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same `/trail-conditions/` page warns that fire-burned steps and bridges expose "nails and rebar" '
        'and that dead trees ("widow makers") may fall. `/safety/` is a static page on hunting season, bears, '
        "waterfalls and lightning.",
    ),
    where=("https://foothillstrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
