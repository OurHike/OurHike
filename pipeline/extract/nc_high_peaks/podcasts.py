"""NC High Peaks Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c7_regional_4).

Skeptic: this is borderline under "audio/podcast content the org publishes". A jingle and a PSA are
not episodes, so I left it NOT_PUBLISHED. A maintainer who reads the type more broadly could flip
it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Only two MP3 radio spots (`sites/default/files/2025-04/HighPeaksJingle.mp3`, `…/Please dont feed the "
        "bears.mp3`), with no feed.",
    ),
    where=("https://nchighpeaks.org/",),
)
