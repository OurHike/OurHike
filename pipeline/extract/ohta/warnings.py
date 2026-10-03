"""Ozark Highlands Trail Association: warnings, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

The posts are WP REST JSON but stale. The live burn data is the USFS layer.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Trail Alerts" category posts include prescribed burns (e.g. "Prescribed Burn near Richland Creek '
        'March 4, 2022"). The FAQ covers hunting season ("wear some sort of blaze orange"), bears and snakes. '
        "The R8 burn layer covers Ozark-St Francis (213 blocks).",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://ozarkhighlandstrail.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
