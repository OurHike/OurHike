"""Foothills Trail Conservancy: challenges, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/peregrine-award/`: complete all 77 mi, as a thru-hike or in sections, as a member. Applicants submit"
        " a report and receive a certificate and patch. Running since 2011. HTML page.",
    ),
    where=("https://foothillstrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
