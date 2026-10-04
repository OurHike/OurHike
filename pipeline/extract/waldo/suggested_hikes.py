"""Waldo County Trails Coalition (Hills to Sea Trail): suggested hikes, published as map PDFs only a person
can read (decision 54 wave 4, section K, 2026-10-04).

hillstosea.org/maps links a full map and six section maps as PDFs (/s/H2S_Section1_20220106.pdf and the rest),
'Online section maps show mileage between points'. A map's mileages are labels on a drawing, not a table, so
they stay a note.

The note this replaces read, whole:

Waldo County Trails Coalition: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

Section guides in PDF form.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): 6 sections with mileage on `/maps`, and `/activities`.

Its `where`: https://www.hillstosea.org/maps https://www.hillstosea.org/closures

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.hillstosea.org/maps (HTTP 200, 2026-10-04): FULL MAP and SECTION 1 to 6, each a PDF map under /s/ (2021 to 2025)",
    ),
    where=("https://www.hillstosea.org/maps",),
    reason="a PDF only a person can read: the section maps are drawings whose mileages are map labels",
)
