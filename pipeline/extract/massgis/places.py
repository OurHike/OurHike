"""MassGIS (Bureau of Geographic Information): places, published, and not landed (coverage audit
2026-10-01, batch b5_nyc_nj_ct_ma_pa).

Open space is MassGIS's own compilation, so `_shared/massgis/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('`AGOL/openspace/MapServer/0` "Protected and Recreational OpenSpace (Polygons)": 61,486. `AGOL/Census2020_Towns`.',),
    where=("https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/openspace/MapServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
