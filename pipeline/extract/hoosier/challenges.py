"""Hoosier Hikers Council: challenges, a completion award with no list of places, and not landed (decision 54 wave 5,
section K, 2026-10-04).

The 2016 Bicentennial Challenge (hike 200 miles of Indiana natural-surface trail) closed with the bicentennial;
its trail list is the PDF suggested_hikes.py notes, whose text layer runs its cells together.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Hoosier Hikers Council: challenges, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

It ended in 2016, so the challenges mart should probably leave it out. Recorded so nobody hunts for it
again. (Skeptic correction, 2026-10-01: `/bicentennial-challenge/` says "The time period for the
challenge was from January 1, 2016 through December 31, 2017", so it ended at the close of 2017 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "2016 Bicentennial Challenge": hike 200 mi of Indiana
natural-surface trail. The list is the PDF above.

Its `where`: https://hoosierhikerscouncil.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://hoosierhikerscouncil.org/assets/Bicentennial_Trail_List.pdf (HTTP 200, 2026-10-04): '2016 Bicentennial Challenge', updated Feb. 2, 2020",
    ),
    where=("https://hoosierhikerscouncil.org/assets/Bicentennial_Trail_List.pdf",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
