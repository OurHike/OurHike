"""Central Iowa Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Nav, the news RSS. (Skeptic: the sitemap's only audio-sounding URL is "
        "`/news/2019/4/25/cita-mixtape-1-music-to-shred-to`, which is a music playlist.)",
    ),
    where=("https://bikecita.org/",),
)
