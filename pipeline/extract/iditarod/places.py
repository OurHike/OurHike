"""Iditarod Historic Trail Alliance: places, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

Trail towns

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "About 17 community pages in the sitemap (seward, moose-pass, girdwood, eagle-river, eklutna, knik, "
        "skwentna, rainy-pass, takotna, iditarod, kaltag, galena, unalakleet, golovin, solomon, nome, "
        "tolovana-roadhouse), HTML",
    ),
    where=(
        "https://gis.blm.gov/arcgis/rest/services",
        "https://services2.arcgis.com/Ce3DhLRthdwbHlfF/arcgis/rest/services",
        "https://iditarod100.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
