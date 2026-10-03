"""Ice Age Trail Alliance: challenges, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

The challenge geometry is machine-readable even though the rules sit on blocked pages. #1780 — Let a
club publish a challenge… is the shape to port into. Skeptic: spot-checked
`HometownHighlights_2026/0` = 32, last edit 2026-09-16. Earlier years also exist as layers:
`Hometown_Highlights_MHC_2025` …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Pages `/mammoth-hike-challenge/` (44 miles plus 3 trail communities in October; patch; free), "
        "`/explore/plan-hike/thousand-miler-recognition/` and `/explore/plan-hike/hiking-awards-programs/`. "
        "ArcGIS `.../HometownHighlights_2026`: 32 points. `.../Trail_Magic_2026`: 166 business points. "
        '`.../IAT_ColdCache_sites`: 96, and `ColdCache`: 105 (the "ColdCaching" programme).',
    ),
    where=("https://iceagetrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
