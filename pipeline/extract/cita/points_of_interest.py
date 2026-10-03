"""Central Iowa Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c5_regional_2).

No coordinates. (Skeptic correction: there is one coordinate per area. The status API's
`trail.locationUrl` is a Google Maps URL that carries a lat/lng, e.g. Ewing Park
`@41.5416301,-93.5852384`. It marks the area, not a trailhead or parking lot, so it is a place point
rather than a POI. The …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Six trail-area pages (`/banner`, `/center-trails-denmans`, `/fourmilemtb`, `/ewing-park`, "
        '`/grandview-park`, `/sycamore-trails-1`) each have a "PARKING" section in prose.',
    ),
    where=(
        "https://services.arcgis.com/HT7H9QGiZQoRJDpJ/arcgis/rest/services",
        "https://bikecita.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
