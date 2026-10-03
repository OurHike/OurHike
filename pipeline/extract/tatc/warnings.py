"""Tidewater Appalachian Trail Club: warnings, published, and not landed (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

The reports are ATC ridgerunner output that the club republishes. They name ATC staff and give their
emails. Whether `atc_licence` covers them is a maintainer question. Severity is low (blowdowns "not
really an obstacle").

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Tye River Ridgerunner Reports", an index PDF at '
        "`https://tidewateratc.com/wp-content/uploads/2026/08/Tye-River-Ridge-Runner-Reports.pdf` (2026-08-03)."
        ' It links about 70 weekly ATC RIMS "Stewardship Report Digest" PDFs from 2023 to 2026 (week 13), each '
        "up to 7.3 MB. They cover the NBATC, ODATC and TATC sections, with per-assessment coordinates, "
        "downed-tree counts, tread issues and campsite notes",
    ),
    where=("https://tidewateratc.com/wp-content/uploads/2026/08/Tye-River-Ridge-Runner-Reports.pdf",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
