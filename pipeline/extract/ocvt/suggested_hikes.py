"""Outdoor Club at Virginia Tech: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c3_at_clubs_south).

A 1991 PDF is the weakest form available. Low value.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Hiking Adventures Around Virginia Tech", `https://ocvt.club/media/documents/Hikes_Around_VT_1991.pdf`'
        ' (PDF, 2,962,871 bytes, "Created by OCVT in 1991"). `/trips` lists club outings, which are events with'
        " an account-gated sign-up.",
    ),
    where=("https://ocvt.club/media/documents/Hikes_Around_VT_1991.pdf",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
