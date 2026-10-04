"""Pacific Northwest Trail Association: challenges, a completion award with no list of places, and not landed (decision
54 wave 5, section K, 2026-10-04).

'Register as a 1,200 Miler' and /pnt-finishers/, a roster.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Pacific Northwest Trail Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

Do not load the finishers list. Skeptic spot-check: `/1200-milers/` returns 200.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/pnta/know-before-you-go/1200-milers/` ("Register as a 1,200
Miler") and `/pnt-finishers/`.

Its `where`: https://pnt.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /pnta/know-before-you-go/1200-milers/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://pnt.org/",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
