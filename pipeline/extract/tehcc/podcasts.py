"""Tennessee Eastman Hiking & Canoeing Club: podcasts, nothing published (coverage audit 2026-10-01,
batch c3_at_clubs_south).

(skeptic) Not the club's, but close: the Trail Maintainers Podcast by a named individual (RSS
`https://rss.libsyn.com/shows/157376/destinations/1028318.xml`, 30 episodes, 2019-02-21 to
2024-11-22) interviews TEHCC, CMC and MRATC maintainers by name, e.g. "a named individual TEHCC"
(ep. 6), "a named …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('Nav, WP search, wiki namespaces, iTunes. (skeptic) Also WP search "trail maintainers" and "libsyn".',),
    where=(
        "https://rss.libsyn.com/shows/157376/destinations/1028318.xml",
        "https://tehcc.org",
    ),
)
