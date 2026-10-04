"""Foothills Trail Conservancy: challenges, a completion award with no list of places, and not landed (decision 54 wave
5, section K, 2026-10-04).

The Peregrine Award (since 2011): complete all 77 miles, as a thru-hike or in sections, as a member, with a
report; a certificate and patch.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Foothills Trail Conservancy: challenges, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/peregrine-award/`: complete all 77 mi, as a thru-hike or in
sections, as a member. Applicants submit a report and receive a certificate and patch. Running since
2011. HTML page.

Its `where`: https://foothillstrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /peregrine-award/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://foothillstrail.org/peregrine-award/",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
