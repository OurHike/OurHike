"""Keystone Trails Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Irregular, and the 2025 dates are already stale. A resource has to read the sitemap's `/news/`
pages, not the feed, and pick warnings by keyword (@unvalidated). The Game Commission is the
authoritative source for hunting Sundays, so this is a lead for a `_shared/` PGC source as much as a
KTA file …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Blog post "How Will The Repeal Of The Ban On Sunday Hunting Affect Pennsylvania Hikers?" by a named '
        "individual, "
        "`https://www.kta-hike.org/news/how-will-the-repeal-of-the-ban-on-sunday-hunting-affect-pennsylvania-hikers-by-jim-foster`"
        " (2025-08-08). It lists the 13 PGC-designated hunting Sundays for 2025 (Sept. 14 … Dec. 7) and what "
        'they change for hikers. Also "Deer Ticks and Babesia" by a named individual (2025). Weebly blog pages:'
        " the sitemap lists 291 `/news/` URLs. RSS `https://www.kta-hike.org/news/feed` holds only the 10 "
        "newest (read 2026-10-01: nine President's letters and one …",
    ),
    where=(
        "https://www.kta-hike.org/news/how-will-the-repeal-of-the-ban-on-sunday-hunting-affect-pennsylvania-hikers-by-jim-foster",
        "https://www.kta-hike.org/news/feed",
        "https://kta-hike.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
