"""Colorado Parks & Wildlife — COTREX: places, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`CPWAdminData/5` "CPW Managed Properties (public access only)": 920 polygons (STL 410, SWA 322, '
        "Recreation Area 50, SP 48, Fishing Access 45…). `/13` property centroids: 1,056.",
    ),
    where=(
        "https://ndismaps.nrel.colostate.edu/arcgis/rest/services",
        "https://services3.arcgis.com/0jWpHMuhmHsukKE3/arcgis/rest/services",
        "https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services",
        "https://trails.colorado.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
