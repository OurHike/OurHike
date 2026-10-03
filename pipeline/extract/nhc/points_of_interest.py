"""Nantahala Hiking Club: points of interest, drawn from another folder's resource (coverage audit
2026-10-01, batch c3_at_clubs_south).

(skeptic) The September 2026 newsletter reports a new bear box at Muskrat Creek Shelter (installed
2026-08-26). Whether ATC's shelter layer records food storage at all was not checked.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Code 29: shelters 10, campsites 9, privies 11, parking 18, viewpoints 39, bridges 13.",),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://nantahalahikingclub.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
