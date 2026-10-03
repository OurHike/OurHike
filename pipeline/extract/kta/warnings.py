"""Keystone Trails Association: warnings, not published as notices (decision 53 phase B, 2026-10-03).

KTA's news feed (https://www.kta-hike.org/news/feed) held 10 items from 2025-10-06 to 2026-09-08 on
2026-10-03, nine monthly president's letters and a trail-care recap, all 'Uncategorized', and 0
notices; its sitemap lists 291 /news/ URLs (the decision 53 inventory, batch 5). Hazard posts on its
blog are articles (the 2025 hunting-Sundays post has expired); the Pennsylvania Game Commission is
the authority for hunting dates. Some titles carry a person's name, which is one more reason the
feed is not read.

Before decision 53 phase B, 2026-10-03, this note read:

Keystone Trails Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Irregular, and the 2025 dates are already stale. A resource has to read the sitemap's `/news/`
pages, not the feed, and pick warnings by keyword (@unvalidated). The Game Commission is the
authoritative source for hunting Sundays, so this is a lead for a `_shared/` PGC source as much as a
KTA file …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Blog post "How Will The Repeal Of The Ban On Sunday Hunting
Affect Pennsylvania Hikers?" by a named individual,
`https://www.kta-hike.org/news/how-will-the-repeal-of-the-ban-on-sunday-hunting-affect-pennsylvania-hikers-by-jim-foster`
(2025-08-08). It lists the 13 PGC-designated hunting Sundays for 2025 (Sept. 14 … Dec. 7) and what
they change for hikers. Also "Deer Ticks and Babesia" by a named individual (2025). Weebly blog
pages: the sitemap lists 291 `/news/` URLs. RSS `https://www.kta-hike.org/news/feed` holds only the
10 newest (read 2026-10-01: nine President's letters and one …

Its `where`:
https://www.kta-hike.org/news/how-will-the-repeal-of-the-ban-on-sunday-hunting-affect-pennsylvania-hikers-by-jim-foster
https://www.kta-hike.org/news/feed https://kta-hike.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "(the decision 53 inventory, batch 5, 2026-10-03) https://www.kta-hike.org/news/feed: 200 (Weebly), 10 items, 0 notices; robots.txt disallows /ajax/, /apps/ and 13 named pages, none under /news/.",
    ),
    where=(
        "https://www.kta-hike.org/news/feed",
        "https://kta-hike.org/",
    ),
    reason="not published as notices: the blog's posts are letters and articles; the hunting dates' authority is the Game Commission",
)
