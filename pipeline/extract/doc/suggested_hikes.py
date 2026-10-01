"""Dartmouth Outing Club: suggested hikes, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

The verdict holds: a name list on a self-declared unmaintained page is not a hike description, and
the guide is sold (Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Trips are student sign-ups behind `https://doc.dartmouth.edu/welcome` (the "Trailhead" app). There are'
        " no public hike write-ups in the sitemap.",
        "Skeptic, 2026-10-01: `https://cabtrail.host.dartmouth.edu/trails.shtml` lists 15 hike names (Velvet "
        "Rocks, Gile Mountain … Mt. Monadnock) in three drive-time bands, with no description or route: "
        '"Purchase a Dartmouth Outing Guide … for more information on these hikes".',
    ),
    where=(
        "https://doc.dartmouth.edu/welcome",
        "https://cabtrail.host.dartmouth.edu/trails.shtml",
    ),
)
