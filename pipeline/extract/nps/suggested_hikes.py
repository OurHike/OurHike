"""National Park Service: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

A point per hike, not a route. `geometryPoiId` joins to the POI layer. Tours include museum walks,
so filter by activity.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "API `/thingstodo?q=hiking`: 1,644 (total 3,572 per c9). Fields include `duration`, `season`, "
        "`petsDescription`, `latitude`/`longitude`, `geometryPoiId`. API `/tours`: 717 tours with `stops[]` and"
        ' `durationMin/Max`. The first returned was "Japanese American Remembrance Trail", 42 stops.',
    ),
    where=("https://mapservices.nps.gov/arcgis/rest/services",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
