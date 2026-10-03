"""NH GRANIT (University of New Hampshire): podcasts, nothing published (coverage audit 2026-10-01,
batch c9_federal_state_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Same check, plus the skeptic's sitemap read (no podcast or audio URL among 913).",),
    where=("https://granit.unh.edu/",),
)
