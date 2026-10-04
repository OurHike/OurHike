"""Randolph Mountain Club: challenges, a completion award with no list of places, and not landed (decision 54 wave 5,
section K, 2026-10-04).

The RMC 100 Challenge (since 2010): walk all 100 miles of RMC trails. Its logbook
(RMC-100-Challenge-Logbook.pdf, 163,662 bytes, 2023-02-16) is a hiker's log of the club's whole network, not a list
of places; the trails themselves are the club's trail_lines.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Randolph Mountain Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

A trail-completion programme, not a place list.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): RMC 100 Challenge: walk all 100 miles of RMC trails (since 2010).
Page `/trails/rmc-100-challenge/`; logbook `/wp-content/uploads/RMC-100-Challenge-Logbook.pdf` (PDF,
163,662 bytes, 2023-02-16).

Its `where`: https://randolphmountainclub.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://randolphmountainclub.org/wp-content/uploads/RMC-100-Challenge-Logbook.pdf (HTTP 200, 163,662 bytes, Last-Modified 2023-02-16, 2026-10-04)",
    ),
    where=("https://randolphmountainclub.org/trails/rmc-100-challenge/",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
