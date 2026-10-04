"""US Army Corps of Engineers: podcasts, refused by its host's robots.txt for now (decision 54 wave 3,
section C, 2026-10-04).

The Corps' shows are DVIDS feeds (Rangers to the Corps, `/rss/podcast/585`; Inside the Castle,
`/443`; Corps Chronicles, `/608`, the coverage audit). www.dvidshub.net/robots.txt answered HTTP 502
twice, at 07:28 and 08:09 UTC on 2026-10-04, and RFC 9309 reads a 5xx robots.txt as disallowing
everything until it answers, so no feed was read. Recheck: once robots.txt answers 200 and allows
/rss/, register each feed as a podcast_feed row (extract/_content.py's podcast_episodes).

The note this replaces read, whole:

US Army Corps of Engineers: podcasts, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Mostly engineering programming. "Rangers to the Corps" is the one about park rangers and lake
recreation, and it has been quiet since August 2024. DVIDS carries a copyright line, not a licence.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.dvidshub.net/robots.txt: HTTP 502 at 2026-10-04T07:28 and T08:09 UTC, under our agent; nothing else on the host was asked.",
        '(the coverage audit, 2026-10-01) Norfolk District "Corps Talk" (`nao.usace.army.mil/Media/CorpsTalk/`), ERDC "Engineering With Nature", Mississippi Valley Division podcasts.',
        '(the coverage audit, 2026-10-01) Skeptic adds machine-readable feeds (RSS on DVIDS, found through the Apple podcast directory): "Rangers to the Corps" (Wilmington District), `https://www.dvidshub.net/rss/podcast/585`, 20 items, newest 2024-08-19 ("Hydropower Time", "Dam Safety", "Shoreline Rangers"), `<copyright>DVIDSHub.net`. Also "Inside the Castle" (HQ, `…/rss/podcast/443`, 159 episodes per the directory) and "Corps Chronicles" (Kansas City District, `…/608`).',
    ),
    where=(
        "https://www.dvidshub.net/robots.txt",
        "https://www.dvidshub.net/rss/podcast/585",
        "https://nao.us",
        "https://usace.army.mil/",
    ),
    reason="refused: the host's robots.txt answers 5xx, which RFC 9309 reads as disallow; recheck when it answers",
)
