"""Nez Perce (Nee-Me-Poo) Trail Foundation: trail lines, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Only the first 2,000 bytes of the KML were read, so feature count and licence are unchecked. Google
My Maps is a third-party host, and its terms are a maintainer question

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "USFS Google My Maps KML "
        "`https://www.google.com/maps/d/kml?mid=1rdJCOzX2Wh3yt7E-nVDfrz0CbSc&forcekml=1` answers 200 "
        "`text/xml`, `<name>Nez Perce National Historic Trail</name>`. It is linked from "
        "`fs.usda.gov/trails/nez-perce-nht/data-tools/interactive-maps`. `usfs_trails` (LOADED) holds only 7 "
        'NHT-designated features, 7.0 mi. `nps_trails` holds 14 YELL/BIHO "Nez Perce" rows. Own: the '
        "Foundation's legacy My Maps (`msid=105417867471941730284.000466baf9e3509d0e06f`) now 404s as KML",
    ),
    where=(
        "https://www.google.com/maps/d/kml?mid=1rdJCOzX2Wh3yt7E-nVDfrz0CbSc&forcekml=1",
        "https://fs.usda.gov/trails/nez-perce-nht/data-tools/interactive-maps",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
