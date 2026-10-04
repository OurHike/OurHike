"""Friends of the Blue Hills: challenges, a completion award with no list of places, and not landed (decision 54 wave
5, section K, 2026-10-04).

The 125 Mile Club: 'hike every mile of every trail'; the Skyline Trail earns a first patch, all 125 miles a
second, a repeat a third.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Friends of the Blue Hills: challenges, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/125mileclub/`: "hike every mile of every trail". The Skyline
Trail earns a first patch, all 125 miles a second, a repeat a third.

Its `where`: https://arcgisserver.digital.mass.gov/arcgisserver/rest/services
https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services https://friendsofthebluehills.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /125mileclub/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://friendsofthebluehills.org/125mileclub/",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
