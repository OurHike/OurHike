"""NC High Peaks Trail Association: challenges, the Black Mountain Challenge's trail list as a PDF only a
person can read, and not landed (decision 54 wave 4, section K, 2026-10-04).

HPHikeChallengeTrailsR3a.pdf (an Excel sheet printed to PDF, 2018, 4 pages) lists the challenge's 23 trails and
sections with their USFS number, length, difficulty and blazes, but its text layer interleaves each row with its
notes column, tab by tab across lines ('1 Bald Knob Ridge ... Upper trailhead at Parkway milepost 355 / 186 2.8
Moderate White Diamond Deep woods hike along Bald'), so which figure is whose cannot be read reliably. Its notes
carry safety facts a person should read (one lower trailhead 'requires high clearance 4WD').

The note this replaces read, whole:

NC High Peaks Trail Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

A place-based programme. Fits #1780's shape.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/blackmountainchallenge`: "complete hiking the 23 trails and
trail sections … receive a patch". Trails hiked on or after 2018-01-01 count. PDFs
`HPHikeChallengeTrailsR3a.pdf` (64.82 KB) and `NCHPTAChallengeRecordRev3a.pdf`.

Its `where`: https://nchighpeaks.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://nchighpeaks.org/sites/default/files/HPHikeChallengeTrailsR3a.pdf (HTTP 200, 66,374 bytes, Last-Modified 2023-02-08, 2026-10-04): 4 pages, rows interleaved with notes",
    ),
    where=("https://nchighpeaks.org/blackmountainchallenge",),
    reason="a PDF only a person can read: the trail list's rows interleave with their notes column",
)
