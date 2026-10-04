"""COTREX: challenges, refused by the application's terms (decision 54 wave 5, section K, 2026-10-04).

trails.colorado.gov/challenges lists 13 citizen-science challenges (drinking water, conditions reports, butterflies,
...) inside the COTREX application, whose terms forbid copying its content, as cotrex/suggested_hikes.py quotes
them; the CPW Passport Program (42 state parks and 15 hatcheries) is a park-visit stamp programme.

The note this replaces read, whole:

Colorado Parks & Wildlife — COTREX: challenges, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

The COTREX terms caveat applies.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Format page. The CPW Passport Program covers 42 state parks and 15
hatcheries, with a patch (from search). `trails.colorado.gov/challenges` lists 13 COTREX citizen-science
challenges (`drinking-water`, `conditions-report`, `butterfly`, …).

Its `where`: https://trails.colorado.gov/challenges

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "cotrex/suggested_hikes.py's note quotes the COTREX application's terms, read 2026-10-04",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://trails.colorado.gov/challenges",),
    reason="refused: the COTREX application's terms forbid copying its content (cotrex/suggested_hikes.py quotes them)",
)
