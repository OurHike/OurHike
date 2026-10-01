"""Buckeye Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "No BTA show; BTA has a YouTube channel (`youtube.com/user/BuckeyeTrailTV`, video). A third party has "
        "one: Hike, \"Introducing Ohio's Buckeye Trail\" (2020-10-29), with the BTA's executive director.",
        'Skeptic: the Apple directory searched by "Buckeye Trail" and "Buckeye Trail Association" (30 shows) '
        "has none by the BTA; the hits are Ohio State sports and radio shows. I did not re-read the BTA site, "
        "because of its terms.",
    ),
    where=("https://youtube.com/user/BuckeyeTrailTV",),
)
