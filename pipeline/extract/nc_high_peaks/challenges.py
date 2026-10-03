"""NC High Peaks Trail Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

A place-based programme. Fits #1780's shape.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/blackmountainchallenge`: "complete hiking the 23 trails and trail sections … receive a patch". '
        "Trails hiked on or after 2018-01-01 count. PDFs `HPHikeChallengeTrailsR3a.pdf` (64.82 KB) and "
        "`NCHPTAChallengeRecordRev3a.pdf`.",
    ),
    where=("https://nchighpeaks.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
