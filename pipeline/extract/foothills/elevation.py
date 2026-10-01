"""Foothills Trail Conservancy: elevation, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

These are pictures of profiles, not data. Do not load them. USGS 3DEP is the source.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/wp-content/uploads/2024/01/West-Elevation-Profile-Final-1-scaled.jpg` and "
        "`East-Elevation-Profile-Final-1-scaled.jpg`.",
    ),
    where=("https://foothillstrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
