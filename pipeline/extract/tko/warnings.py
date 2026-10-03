"""Trailkeepers of Oregon: warnings, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

Water outages in the same posts ("No water at Arcadia Beach", Hug Point's broken water line) stay
out of warnings, by poll 2. They belong with water-source attributes.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same two posts: Sand Lake crossing "ONLY when tide is low enough", landowners refusing hikers on '
        'N. Clancy Road, shelters on Tillamook Head being torn down. `/oct/` warns that southern rivers "can be'
        ' safely waded only between about mid-June and late October" and of falling trees in winter winds.',
    ),
    where=("https://trailkeepersoforegon.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
