"""Hoosier Hikers Council: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

The only shelter in the batch with a coordinate.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/assets/Tecumseh_Trail_POI_Waypts.gpx` (GPX, 8,666 bytes): 27 waypoints. They are numbered parking "
        'areas from 01 MMSF Office to 24 Crooked Creek, road crossings, and "Foxes_Den_Shelter". Every `sym` is'
        ' "RED MAP PIN". There is also `/assets/Tecumseh_Trail_Guide.pdf` (1,289,157 bytes, 2022-06-30), which '
        "covers parking, access, water and camping. (Skeptic HEAD, 2026-10-01: the POI GPX is 8,666 bytes with "
        "Last-Modified 2017-10-05, so its parking list predates the 2022 reroute. The track GPX is 817,229 "
        "bytes with Last-Modified 2024-03-12. Both are unchanged.)",
    ),
    where=("https://hoosierhikerscouncil.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
