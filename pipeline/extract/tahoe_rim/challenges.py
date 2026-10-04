"""Tahoe Rim Trail Association: challenges, a completion award with no list of places, and not landed (decision 54 wave
5, section K, 2026-10-04).

The 165-Mile Club: an application for completing the whole trail, and its members by year, a roster.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Tahoe Rim Trail Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Format page: `tahoerimtrail.org/165-mile-club/` (completion club,
application, members by year).

Its `where`: https://tahoerimtrail.org/165-mile-club/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /165-mile-club/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://tahoerimtrail.org/165-mile-club/",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
