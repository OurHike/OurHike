"""Tennessee Trails Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

YouTube is video, not a podcast.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/media-resources/` lists only a YouTube channel and a Facebook group. (Skeptic: the iTunes Search API"
        ' for "Tennessee Trails" (media=podcast) returned 15 shows on 2026-10-01. None is TTA\'s. The nearest is'
        ' TWRA\'s "Tennessee WildCast".)',
    ),
    where=("https://tennesseetrails.org/",),
)
