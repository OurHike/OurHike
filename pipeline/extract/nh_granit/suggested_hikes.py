"""NH GRANIT (University of New Hampshire): suggested hikes, nothing published (coverage audit
2026-10-01, batch c9_federal_state_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Same check. The skeptic's sitemap read also found no hike URL. `/datasets/nh-recreational-trails` and "
        "`/datasets/nhdot-rails-and-trails-viewer` are dataset pages, not hike descriptions.",
    ),
    where=("https://granit.unh.edu/",),
)
