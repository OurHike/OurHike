"""Outing Club at Virginia Tech: suggested hikes, published as a scanned 1991 folder, and not landed (decision
54 wave 4, section K, 2026-10-04).

'Hiking Adventures Around Virginia Tech' (Hikes_Around_VT_1991.pdf) is a paper capture: its text layer is OCR of a
folded brochure ('HI,KES NEAR VIRGINIATECH'), prose about the mountains and an equipment shop list, 35 years old.
/trips are club outings, dated, behind an account's sign-up.

The note this replaces read, whole:

Outdoor Club at Virginia Tech: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c3_at_clubs_south).

A 1991 PDF is the weakest form available. Low value.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "Hiking Adventures Around Virginia Tech",
`https://ocvt.club/media/documents/Hikes_Around_VT_1991.pdf` (PDF, 2,962,871 bytes, "Created by OCVT in
1991"). `/trips` lists club outings, which are events with an account-gated sign-up.

Its `where`: https://ocvt.club/media/documents/Hikes_Around_VT_1991.pdf

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://ocvt.club/media/documents/Hikes_Around_VT_1991.pdf (HTTP 200, 2,962,871 bytes, 2026-10-04): 2 pages, Adobe Acrobat 8 Paper Capture, OCR prose",
    ),
    where=("https://ocvt.club/media/documents/Hikes_Around_VT_1991.pdf",),
    reason="a PDF only a person can read: a scanned 1991 brochure whose text layer is OCR of prose",
)
