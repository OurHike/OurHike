"""Iditarod Historic Trail Alliance: podcasts, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

Not opened. Licence unknown

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('Nav item "Project Jukebox Oral History" (UAF Project Jukebox audio, third-party host)',),
    where=(
        "https://gis.blm.gov/arcgis/rest/services",
        "https://services2.arcgis.com/Ce3DhLRthdwbHlfF/arcgis/rest/services",
        "https://iditarod100.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
