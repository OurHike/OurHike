"""Tennessee Trails Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

Fits the challenges mart from #1780 — Let a club publish a challenge — places on its own trails that
hikers opt into and tag at camp — starting with the ATC's A.T. Summer Bucket List, but the terms
block it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"a named individual Hiked \'em All": 36 hikes in TN State Parks, a commemorative patch plus an '
        "achievement rocker, and a qualification form "
        "`/wp-content/uploads/2020/08/FranWallasQualificationForm.pdf`. 2026 is its 15th year (HTML page).",
    ),
    where=("https://tennesseetrails.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
