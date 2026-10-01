"""Natchez Trace NST (NPS-administered): podcasts, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

Place-tied audio. It is the `nps` folder's podcasts resource filtered to this park.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "API `/multimedia/audio`: 62 (skeptic: `total` 62 confirmed). These are Mount Locust audio-tour stops, "
        'e.g. "Welcome to Mount Locust, Milepost 15.5" (250 s) and "Human Trafficking Along the Old Trace" (148'
        " s).",
    ),
    where=("https://nps.gov/natr/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
