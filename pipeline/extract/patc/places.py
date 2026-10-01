"""Potomac Appalachian Trail Club: places, published, and not landed (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

Most of these parcels are closed to the public. They must never render as "places to go", and if
they are loaded at all, `PUBACCESS` has to travel with them (Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`PATC_Lands_Compilation_Version_1_0_0/0`: 55 PATC-held parcels (2020-10-28). `PUBACCESS`: 40 "closed",'
        ' 1 closed-presumed, 2 unknown, 1 "by arrangement", 11 blank. `/places-to-hike` (page, about 30 parks '
        "keyed to PATC maps). `ShenandoahNP_Boundary_PATC_022023` (NPS is the authority for this one). Trail "
        "towns LOADED via atc",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services7.arcgis.com/BbnVmymrKxjFL0SO/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://patc.net/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
