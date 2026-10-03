"""Old Spanish Trail Association: photos, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Flickr links are not "openly licensed" until each is read

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAPI/multimedia/galleries` olsp 2. BLM layers carry `Flickr_Photo_Link` per feature, licence per photo unknown",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://oldspanishtrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
