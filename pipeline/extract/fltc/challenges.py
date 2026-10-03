"""Finger Lakes Trail Conference: challenges, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Main Trail End-to-End (~580 mi; patches and a certificate). Branch Trail End-to-End. The Passport "
        "programme. FLT50/FLT100 2026. Recipient lists on `/about-the-fltc/awards-for-hikers/`.",
    ),
    where=("https://fingerlakestrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
