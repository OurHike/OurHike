"""Roanoke Appalachian Trail Club: warnings, published, and not landed (coverage audit 2026-10-01,
batch c3_at_clubs_south).

These are regulations and a water hazard, not closures. Under decision 7 they are warnings. ATC
LOADED carries the bear and high-water rows.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.ratc.org/at-hiking/mcafee-knob-and-the-triple-crown/` (page, modified 2026-02-24). "
        'Standing federal rules for VA 624–US 220: "NO camping outside of 7 designated areas", no fires outside'
        ' metal rings, group size 25 for day hikes and 10 overnight. Water: "There are no natural water sources'
        ' along the A.T. in the Dragons Tooth area, so bring all your water". The Dragons Tooth Special '
        "Biological Area is closed to camping. A drone prohibition. The bears category (id 31) has 2 posts, "
        "both 2016.",
    ),
    where=("https://www.ratc.org/at-hiking/mcafee-knob-and-the-triple-crown/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
