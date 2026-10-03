"""Friends of the Mountains-to-Sea Trail: podcasts, nothing published (coverage audit 2026-10-01, batch
c7_regional_4).

RSS. Not FMST's own, so per decision 18 these feeds belong in `_shared/podcasts`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Two third-party podcasts that FMST curates:",
        '`/news/away-message-podcast/`: Our State magazine\'s "Away Message", Season 4 is about the MST. Feed '
        '`https://rss.libsyn.com/shows/101496/destinations/536767.xml`, now titled "North Carolina Rabbit '
        'Hole", 71 episodes, latest 2026-08-06.',
        '`/news/jester-podcast/`: a named individual\'s "Jester Section Hiker", feed '
        "`https://rss.libsyn.com/shows/231680/destinations/1710515.xml`, 286 episodes.",
    ),
    where=(
        "https://rss.libsyn.com/shows/101496/destinations/536767.xml",
        "https://rss.libsyn.com/shows/231680/destinations/1710515.xml",
        "https://mountainstoseatrail.org/",
    ),
)
