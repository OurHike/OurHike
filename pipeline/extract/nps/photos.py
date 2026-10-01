"""National Park Service: photos, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Filter on `constraintsInfo.constraint == 'Public domain'`. Licence is per asset. Skeptic: not every
NPS-published photo is public domain. Some of NPS's Flickr photos are CC BY 2.0, so attribution has
to travel with them.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'API `/multimedia/galleries`: 10,507 galleries. All 3 sampled had `constraintsInfo` "Public domain" '
        "(c9). My re-check got HTTP 429 (DEMO_KEY exhausted). NPGallery was not opened.",
        "Skeptic adds (Measured 2026-10-01): NPS's Flickr account, "
        "`https://www.flickr.com/photos/nationalparkservice/`, holds 513 photos. Of the 25 on its first page, "
        "12 carry Flickr licence id 10 (Public Domain Mark) and 13 carry id 4 (CC BY 2.0). NPGallery "
        '(`https://npgallery.nps.gov/`, "NPGallery Search") answers 200; no API was probed. A galleries retry '
        "with DEMO_KEY returned no `total`.",
    ),
    where=(
        "https://www.flickr.com/photos/nationalparkservice/",
        "https://npgallery.nps.gov/",
        "https://nps.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
