"""The Anza Trail Foundation: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`NPSAPI/thingstodo` juba 7: "Hike the Anza Trail through Moreno Valley" (2–4 h), "Hike the Arrowhead '
        'Loop Trail", "Delta de Anza/Mokelumne Loop", "Tumacácori to Tubac" (2–6 h), "Hike the Santa Cruz '
        'River". Plus the county guides',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://anzatrailfoundation.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
