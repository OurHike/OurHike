"""Superior Hiking Trail Association: challenges, a completion award with no list of places, and not landed (decision
54 wave 5, section K, 2026-10-04).

The annual Hike 40 patch ('Hike any 40 miles of the Superior Hiking Trail') and the End-2-Ender Program, on the
honour system, for members or recent volunteers.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Superior Hiking Trail Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/hike50challenge/`: an annual patch. The page text reads "Hike
any 40 miles of the Superior Hiking Trail to earn your annual … patch". `/end-2-ender-program/`:
certificate, patch and magnet, on the honour system, for members at $45/yr or more or recent volunteers.

Its `where`: https://superiorhiking.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /hike50challenge/ and /end-2-ender-program/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://superiorhiking.org/hike50challenge/",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
