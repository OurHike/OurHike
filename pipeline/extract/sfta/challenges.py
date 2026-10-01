"""Santa Fe Trail Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Geocaching.com terms gate the cache list (see fetch note)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Own: Santa Fe NHT GeoTour, `https://santafetrail.org/geocaching/`: "over 70 caches" over ~900 mi, a '
        "downloadable passport of code words, and a challenge coin for 50 finds (search snippet). Upstream: "
        '`NPSAPI/passportstamplocations` safe 32; a personal ArcGIS account web map "SAFE Junior Wagon Master '
        'Overview Web Map 2023"',
    ),
    where=("https://santafetrail.org/geocaching/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
