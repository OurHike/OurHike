"""Bay Area Ridge Trail Council: challenges, a completion award with no list of places, and not landed (decision 54
wave 5, section K, 2026-10-04).

The Circumnavigation ('over 400 miles', a finisher form, certificate and wall of fame) and the 2026 Ridge Trail
Challenge (complete 5 sections by 2026-12-31): completion of sections, whose places are the trail's own.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Bay Area Ridge Trail Council: challenges, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

A section-completion programme over a published segment layer. It is a close fit for #1780.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Circumnavigation (`/circumnavigation/`): every dedicated section,
"over 400 miles", with a finisher form, certificate and wall of fame. The Circumnavigator category has 9
posts. 2026 Ridge Trail Challenge (`/2026-ridge-trail-challenge/`): complete 5 sections by 2026-12-31.
Both are HTML.

Its `where`: https://ridgetrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /circumnavigation/ and /2026-ridge-trail-challenge/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://ridgetrail.org/circumnavigation/",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
