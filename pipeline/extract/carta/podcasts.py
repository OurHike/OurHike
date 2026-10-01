"""El Camino Real de Tierra Adentro Trail Association (CARTA): podcasts, published, and not landed
(coverage audit 2026-10-01, batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`NPSAPI/multimedia/audio` elca 20. a personal ArcGIS account StoryMap audio transcripts (PDF items)",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://caminorealcarta.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
