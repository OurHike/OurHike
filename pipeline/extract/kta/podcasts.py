"""Keystone Trails Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

The verdict holds. Hemlocks to Hellbenders is a `_shared/podcasts` lead on PA parks if wanted.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`multimedia.html` holds video only (Lancaster County Conservancy, abc27 "Take a Hike PA" PSAs).',
        'Skeptic, 2026-10-01: the iTunes Search API for "Keystone Trails Association" finds Hemlocks to '
        "Hellbenders (a named individual, `https://rss.buzzsprout.com/2110005.rss`, 96 episodes). Its host is a"
        " KTA board member and wrote a KTA guest post, but the show is his own, not KTA's.",
    ),
    where=("https://rss.buzzsprout.com/2110005.rss",),
)
