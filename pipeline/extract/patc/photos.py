"""Potomac Appalachian Trail Club: photos, nothing published (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Flickr `patcgpsrangers`, album 72157700329546151: 32 photos, every one `license: 0` (All Rights "
        "Reserved). The shelter layer's Photo1/Photo2 fields carry no licence",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services7.arcgis.com/BbnVmymrKxjFL0SO/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://patc.net/",
    ),
)
