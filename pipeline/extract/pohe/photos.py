"""Potomac Heritage Trail Association: photos, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "NPS `/multimedia/galleries`: 18 for `pohe`. Licence is per asset (c9: filter `constraintsInfo` for public domain).",
        "Skeptic: `total` 18 confirmed. `POHE_Scenic_View_Points/0` (116) carries `photo_url`, `photo_cred`, "
        "`photo_use`, `photo_use_link` and `photo_use_notes`, a per-photo usage field that the first pass did "
        "not see. It was not profiled.",
    ),
    where=("https://nps.gov/pohe/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
