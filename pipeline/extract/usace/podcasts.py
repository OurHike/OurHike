"""US Army Corps of Engineers: podcasts, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Mostly engineering programming. "Rangers to the Corps" is the one about park rangers and lake
recreation, and it has been quiet since August 2024. DVIDS carries a copyright line, not a licence.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Norfolk District "Corps Talk" (`nao.usace.army.mil/Media/CorpsTalk/`), ERDC "Engineering With Nature",'
        " Mississippi Valley Division podcasts.",
        "Skeptic adds machine-readable feeds (RSS on DVIDS, found through the Apple podcast directory): "
        '"Rangers to the Corps" (Wilmington District), `https://www.dvidshub.net/rss/podcast/585`, 20 items, '
        'newest 2024-08-19 ("Hydropower Time", "Dam Safety", "Shoreline Rangers"), `<copyright>DVIDSHub.net`. '
        'Also "Inside the Castle" (HQ, `…/rss/podcast/443`, 159 episodes per the directory) and "Corps '
        'Chronicles" (Kansas City District, `…/608`).',
    ),
    where=(
        "https://www.dvidshub.net/rss/podcast/585",
        "https://nao.us",
        "https://usace.army.mil/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
