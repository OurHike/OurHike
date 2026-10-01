"""Potomac Heritage Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "NPS `/thingstodo?parkCode=pohe`: 53 (hiking-tagged items across `natr`+`pohe`: 24; skeptic: `total` 53"
        " confirmed). The association: 3 route-overview PowerPoints (`/s/A1_HFNHP_PHNST_overview.pptx`, "
        "`A2_ShortHillMountain.pptx`, `A3_LoudounHeights_Wayside_summary.pptx`).",
    ),
    where=("https://nps.gov/pohe/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
