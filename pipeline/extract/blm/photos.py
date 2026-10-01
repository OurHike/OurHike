"""Bureau of Land Management: photos, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Corrected by skeptic: BLM's Flickr photos are CC BY 4.0, not public domain, so attribution is
required and the credit must travel with each photo. Licence is still per photo, so read it at fetch
time.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`BLM_Natl_Recreation/MapServer/3`: 794 rec sites carry `PHOTO_LINK` / `PHOTO_TEXT`, all sampled on "
        "`live.staticflickr.com` (BLM's Flickr).",
        "Skeptic (Measured 2026-10-01): today 783 rec sites have a non-empty `PHOTO_LINK`. BLM's Flickr account"
        ' (`https://www.flickr.com/photos/mypubliclands/`, "Bureau of Land Management | Flickr", 8,816 photos):'
        " all 25 photos on its first page carry Flickr licence id 11. One photo page "
        "(`/photos/mypubliclands/55114923117/`) links `creativecommons.org/licenses/by/4.0`, so id 11 is CC BY "
        "4.0.",
    ),
    where=(
        "https://www.flickr.com/photos/mypubliclands/",
        "https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recreation/MapServer/3",
        "https://live.staticflickr.com",
        "https://creativecommons.org/licenses/by/4.0",
        "https://blm.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
