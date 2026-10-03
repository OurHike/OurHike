"""Florida Trail Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

Do not load the End-to-End roster. It lists finishers' real names and hometowns. Skeptic spot-check:
`Passport Stamp Location` (layer `/1`) = 34, last edit 2026-06-10, and `/passport-program/` returns
200. There is also a StoryMap, Florida Trail Passport Program (`ca41aa3016e04516bcee83512bbbc90b`).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://floridatrail.org/passport-program/` plus ArcGIS "
        '`.../Gateway_Community_Businesses_WFL1_view/FeatureServer/1` "Passport Stamp Location": 34 points '
        "(table 6 has 35 rows). The End-to-End certificate at `/end-to-end-hikers/`.",
    ),
    where=(
        "https://floridatrail.org/passport-program/",
        "https://floridatrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
