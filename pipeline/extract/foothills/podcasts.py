"""Foothills Trail Conservancy: podcasts, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Nav, `/feed/` and the newsletter archive. (Skeptic, 2026-10-01: `/feed/` has 9 items and no "
        '`<enclosure>` or `itunes:` tags. The iTunes Search API for "Foothills Trail" returned 15 shows, none '
        "of them FTC's. The only FTC audio is a guest spot on a third party's show: \"REPLAY: The Foothills "
        'Trail Conservancy with a named individual", Highlights of the Carolina Outdoors, 2024-09-25.)',
    ),
    where=("https://foothillstrail.org/",),
)
