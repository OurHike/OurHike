"""Continental Divide Trail Coalition: elevation, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Not worth loading: the shared USGS source covers it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Format pdf. The CDT Map Set v4.0 "includes topographic data, elevation charts" (maps-and-data page, '
        "via WebFetch). It is sold through the NeonCRM store; free section PDFs come off the Interactive Map "
        "(`Mapset_Pages/0`). No elevation layer among the 133 items.",
    ),
    where=("https://services.wygisc.org/HostGIS/rest/services",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
