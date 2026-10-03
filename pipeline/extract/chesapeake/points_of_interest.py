"""Chesapeake Conservancy: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

"Water access" means boat launches, not drinking water. Must never enter the water mart

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Own: `cicgis.org/…/CCP/Water_Access/MapServer/0`: 1,424 points, © "2017, Chesapeake Conservation '
        'Partnership & Chesapeake Conservancy". `Chesapeake/CC_Access_Sites`: 14',
    ),
    where=(
        "https://cicgis.org/arcgis/rest/services",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://chesapeakeconservancy.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
