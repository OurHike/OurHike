"""Central Iowa Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

(Skeptic: now machine-readable. The API's `trail` object gives `name`, `location` ("Ewing Park, Des
Moines, IA"), a coordinate inside `locationUrl`, `homeUrl`, `description` and `isActive` for each of
the 10 codes.)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("The 6 area pages plus the 10 status codes (BAN, CEN, DEN …) form a small named-area directory (pages).",),
    where=(
        "https://services.arcgis.com/HT7H9QGiZQoRJDpJ/arcgis/rest/services",
        "https://bikecita.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
