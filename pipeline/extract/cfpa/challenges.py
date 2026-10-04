"""Connecticut Forest & Park Association: challenges, a mileage challenge with no list of places, and not
landed (decision 54 wave 5, section K, 2026-10-04).

The Blue-Blazed Hiking Trails Challenge awards 50, 200, 400 and 800 miles of the Blue-Blazed trails (a patch, a
bottle, a beanie, a vest), logged in an Excel or Google Sheets mileage log; the trails it counts are
cfpa/suggested_hikes.py's cfpa_trails. The NET Hike Challenge 2026 is newenglandtrail.org's, with AMC.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Connecticut Forest & Park Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

A mileage challenge rather than a place list. It fits #1780's model less well. Skeptic spot-check: the
challenge page returns 200.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01):
`https://ctwoodlands.org/explore-trails/blue-blazed-hiking-trails-challenge/`: 50, 200, 400 and 800-mile
categories (patch, bottle, beanie, vest), with an Excel or Google Sheets mileage log. Also the NET Hike
Challenge 2026 (`newenglandtrail.org/hike-50-challenge/`), run jointly with AMC.

Its `where`: https://ctwoodlands.org/explore-trails/blue-blazed-hiking-trails-challenge/
https://newenglandtrail.org/hike-50-challenge/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /explore-trails/blue-blazed-hiking-trails-challenge/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://ctwoodlands.org/explore-trails/blue-blazed-hiking-trails-challenge/",),
    reason="not this type: a tally of miles on the trail system, no list of places",
)
