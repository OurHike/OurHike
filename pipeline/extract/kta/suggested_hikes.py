"""Keystone Trails Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c1_at_clubs_north).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`favorite-hikes-in-pennsylvania.html` (page; bilingual EN/ES, each hike with county, link and "
        'description, e.g. "Kurmes Trail … 2.2-mile loop"). Also `southcentralaccessible.html` and '
        "`accessible-philadelphia.html`.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://kta-hike.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
