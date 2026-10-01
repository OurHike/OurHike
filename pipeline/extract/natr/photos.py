"""Natchez Trace NST (NPS-administered): photos, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

Skeptic: not re-checked (`DEMO_KEY` returned `OVER_RATE_LIMIT`).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("API `/multimedia/galleries`: 34.",),
    where=("https://nps.gov/natr/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
