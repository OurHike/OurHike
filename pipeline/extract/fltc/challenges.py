"""Finger Lakes Trail Conference: challenges, a completion award with no list of places, and not landed (decision 54
wave 5, section K, 2026-10-04).

The Main Trail End-to-End (~580 miles), the Branch Trail End-to-End, the Passport programme's booklets and the
FLT50/FLT100 2026; the recipients' lists on /about-the-fltc/awards-for-hikers/ are rosters.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Finger Lakes Trail Conference: challenges, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Main Trail End-to-End (~580 mi; patches and a certificate). Branch
Trail End-to-End. The Passport programme. FLT50/FLT100 2026. Recipient lists on
`/about-the-fltc/awards-for-hikers/`.

Its `where`: https://fingerlakestrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /about-the-fltc/awards-for-hikers/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://fingerlakestrail.org/",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
