"""Palmetto Conservation Foundation: closures, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Page. The single post is edited in place.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/updates/post/trail-closures-updated-2-5-26`, organised by region. Examples:",
        'Enoree Passage: "hard stops" at mi 20.5, 24.5 and 30 while the USFS repairs bridges and boardwalks (7/15/26)',
        "Fort Jackson: damage (8/11/26)",
        'Peak to Prosperity: a section closes from Oct 19; Plus each passage\'s "Trail Alerts" block.',
    ),
    where=("https://palmettoconservation.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
